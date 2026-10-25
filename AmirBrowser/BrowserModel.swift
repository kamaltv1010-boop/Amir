import Combine
import UIKit
import WebKit

/// Owns the single WKWebView and mirrors its state (address, title, progress…)
/// into published properties the SwiftUI views observe.
@MainActor
final class BrowserModel: NSObject, ObservableObject {
    /// Replaced by a fresh one for a new session, which also drops the old
    /// back/forward history.
    @Published private(set) var webView: WKWebView

    @Published private(set) var currentURL: URL?
    @Published private(set) var pageTitle = ""
    @Published private(set) var canGoBack = false
    @Published private(set) var canGoForward = false
    @Published private(set) var isLoading = false
    @Published private(set) var progress = 0.0
    @Published private(set) var isDesktopMode = false
    /// Whether pages see a real iPad instead of an iPhone.
    @Published private(set) var isIPadMode = false
    /// Set when a page fails to load; the view shows it over the web content.
    @Published private(set) var loadError: String?
    /// The address that failed, so "Try Again" retries it rather than the
    /// previous page.
    @Published private(set) var failedURL: URL?
    /// What the address bar shows: the failed address while the error is up,
    /// the current page otherwise.
    @Published private(set) var displayedURL: URL?
    /// The fingerprint protections in effect: the ones switched on, plus the
    /// user agent in iPad mode.
    @Published private(set) var enabledProtections: Set<FingerprintProtection.Kind> = []
    private var appliedPrivacySignature = ""
    /// Set while the model itself writes privacy settings, so the resulting
    /// UserDefaults notifications don't trigger a second reload.
    private var isUpdatingPrivacy = false
    /// The compiled tracker blocking rules, once ready.
    private var trackerRules: WKContentRuleList?
    private var trackerRulesLoaded = false
    /// The home page to open once the tracker rules are ready, so the first
    /// page never loads unprotected.
    private var pendingInitialHome: URL?
    /// The last address cleaned of tracking codes, so a site that redirects
    /// back to the tracking address can't cause an endless loop.
    private var lastCleanedURL: URL?

    private let refreshControl = UIRefreshControl()
    private var lastContentProcessCrash: Date?
    /// JavaScript dialogs the current page has shown. After a few, dialogs get
    /// a "Leave Page" button so a page looping alert() can't lock the app.
    private var dialogCount = 0
    /// Set by "Leave Page" so the old page can't show more dialogs while the
    /// home page loads.
    private var isSuppressingDialogs = false
    /// A window a page opened with window.open(), shown in a sheet.
    private var popup: (webView: WKWebView, controller: UIViewController)?
    private var webViewObservers: Set<AnyCancellable> = []
    /// Called with a link the user pinned from the long-press menu.
    var onPinLink: ((URL) -> Void)?

    private static let lastURLKey = "lastURL"
    /// The UserDefaults key of the "Clear Everything on Quit" switch.
    nonisolated static let clearOnQuitKey = "clearOnQuit"
    /// Schemes WebKit loads itself; anything else (tel:, mailto:, App Store
    /// links…) is handed to iOS.
    private static let webSchemes: Set<String> = ["http", "https", "about", "data", "blob", "file", "javascript"]

    override init() {
        webView = Self.makeWebView()
        super.init()

        refreshControl.addTarget(self, action: #selector(pullToRefresh), for: .valueChanged)
        attach(webView)
        applyPrivacySettings()
        Task { [weak self] in
            let rules = await TrackerBlocker.compile()
            self?.trackerRulesDidLoad(rules)
        }

        $currentURL.combineLatest($failedURL, $loadError)
            .map { url, failedURL, error in error == nil ? url : failedURL ?? url }
            .removeDuplicates()
            .assign(to: &$displayedURL)
    }

    // MARK: - Actions

    /// With "Clear Everything on Quit" on, website data lives only in memory
    /// and is never written to the phone.
    private static func makeWebView() -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.allowsInlineMediaPlayback = true
        configuration.websiteDataStore = UserDefaults.standard.bool(forKey: clearOnQuitKey) ? .nonPersistent() : .default()
        return WKWebView(frame: .zero, configuration: configuration)
    }

    private func trackerRulesDidLoad(_ rules: WKContentRuleList?) {
        trackerRules = rules
        trackerRulesLoaded = true
        applyPrivacySettings()
        if let home = pendingInitialHome {
            pendingInitialHome = nil
            loadInitialPage(home: home)
        }
    }

    /// Makes the model the web view's delegate and mirrors its state.
    private func attach(_ webView: WKWebView) {
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        webView.scrollView.refreshControl = refreshControl
        webViewObservers = [
            webView.publisher(for: \.url).sink { [weak self] in self?.currentURL = $0 },
            webView.publisher(for: \.title).sink { [weak self] in self?.pageTitle = $0 ?? "" },
            webView.publisher(for: \.canGoBack).sink { [weak self] in self?.canGoBack = $0 },
            webView.publisher(for: \.canGoForward).sink { [weak self] in self?.canGoForward = $0 },
            webView.publisher(for: \.isLoading).sink { [weak self] in self?.isLoading = $0 },
            webView.publisher(for: \.estimatedProgress).sink { [weak self] in self?.progress = $0 },
        ]
    }

    /// Opens the last visited page, or `home` on first launch. With "Clear
    /// Everything on Quit" on, every launch starts a new session instead.
    func loadInitialPage(home: URL) {
        guard webView.url == nil, !webView.isLoading else { return }
        guard trackerRulesLoaded || !TrackerBlocker.isEnabled else {
            pendingInitialHome = home
            return
        }
        if UserDefaults.standard.bool(forKey: Self.clearOnQuitKey) {
            startNewSession(home: home)
        } else {
            load(UserDefaults.standard.url(forKey: Self.lastURLKey) ?? home)
        }
    }

    /// Deletes cookies, cache and all other website data, closes every open
    /// page (the back/forward history goes with the old web view), gives
    /// every site new fingerprints and opens `home`. Bookmarks and pinned
    /// links are kept.
    func startNewSession(home: URL) {
        closePopup()
        webView.stopLoading()
        webView.navigationDelegate = nil
        webView.uiDelegate = nil
        UserDefaults.standard.removeObject(forKey: Self.lastURLKey)
        clearError()

        webView = Self.makeWebView()
        attach(webView)
        isUpdatingPrivacy = true
        FingerprintProtection.newSeeds(FingerprintProtection.Kind.allCases)
        isUpdatingPrivacy = false
        applyPrivacySettings()

        // Load only once the old data is gone, so no cookie can carry over.
        WKWebsiteDataStore.default().removeData(
            ofTypes: WKWebsiteDataStore.allWebsiteDataTypes(),
            modifiedSince: .distantPast
        ) { [weak self] in
            self?.load(home)
        }
    }

    /// Loads whatever the user typed: an address or a search.
    func open(_ input: String, searchEngine: SearchEngine) {
        guard let url = AddressResolver.url(for: input, searchEngine: searchEngine) else { return }
        load(url)
    }

    func load(_ url: URL) {
        clearError()
        webView.load(URLRequest(url: url))
    }

    func goBack() {
        // With the error up, Back just reveals the page underneath it.
        if loadError != nil {
            clearError()
        } else {
            webView.goBack()
        }
    }

    func goForward() {
        webView.goForward()
    }

    func reload() {
        if loadError != nil, let failedURL {
            load(failedURL)
        } else if webView.url != nil {
            webView.reload()
        } else {
            refreshControl.endRefreshing()
        }
    }

    func stopLoading() {
        webView.stopLoading()
    }

    func toggleDesktopMode() {
        isDesktopMode.toggle()
        applyPrivacySettings()
        // The new content mode is applied in decidePolicyFor on the reload.
        reload()
    }

    /// Turns iPad mode on or off and reloads the page. Turning it on leaves
    /// desktop mode, which would replace the iPad's user agent with a Mac's.
    func setIPadMode(_ isOn: Bool) {
        isUpdatingPrivacy = true
        FingerprintProtection.setIPadMode(isOn)
        isUpdatingPrivacy = false
        if isOn {
            isDesktopMode = false
        }
        applyPrivacySettings()
        reload()
    }

    /// Installs the fingerprint protections that are on. Pages pick up the
    /// change when they next load.
    func applyPrivacySettings() {
        isUpdatingPrivacy = true
        defer { isUpdatingPrivacy = false }
        let controller = webView.configuration.userContentController
        controller.removeAllUserScripts()
        if let script = FingerprintProtection.userScript(desktopMode: isDesktopMode) {
            controller.addUserScript(script)
        }
        controller.removeAllContentRuleLists()
        if TrackerBlocker.isEnabled, let trackerRules {
            controller.add(trackerRules)
        }
        // Desktop mode needs WebKit's own desktop user agent.
        let spoofAgent = FingerprintProtection.isActive(.userAgent) && !isDesktopMode
        webView.customUserAgent = spoofAgent ? FingerprintProtection.userAgent : nil
        enabledProtections = Set(FingerprintProtection.Kind.allCases.filter(FingerprintProtection.isActive))
        isIPadMode = FingerprintProtection.isIPadMode
        appliedPrivacySignature = privacySignature
    }

    /// Changes whenever a setting that needs a reload changes.
    private var privacySignature: String {
        FingerprintProtection.signature + "|\(TrackerBlocker.isEnabled)"
    }

    /// Re-applies the protections and reloads if a switch changed in Settings.
    func privacySettingsMayHaveChanged() {
        guard !isUpdatingPrivacy, privacySignature != appliedPrivacySignature else { return }
        applyPrivacySettings()
        reload()
    }

    /// Gives every site new values for `kinds` and reloads the page with them.
    func newFingerprint(_ kinds: [FingerprintProtection.Kind]) {
        isUpdatingPrivacy = true
        FingerprintProtection.newSeeds(kinds)
        isUpdatingPrivacy = false
        applyPrivacySettings()
        reload()
    }

    func share() {
        guard let pageURL = webView.url else { return }
        let url = LinkCleaner.isEnabled ? LinkCleaner.clean(pageURL) ?? pageURL : pageURL
        let activity = UIActivityViewController(activityItems: [url], applicationActivities: nil)
        activity.popoverPresentationController?.sourceView = webView
        present(activity)
    }

    @objc private func pullToRefresh() {
        reload()
    }

    // MARK: - Helpers

    private func clearError() {
        loadError = nil
        failedURL = nil
    }

    private func showError(_ error: Error) {
        refreshControl.endRefreshing()
        let nsError = error as NSError
        // Cancelled loads (stop button, a new page replacing the old one) and
        // loads WebKit hands off elsewhere (downloads, plug-ins) are not failures.
        if nsError.domain == NSURLErrorDomain, nsError.code == NSURLErrorCancelled { return }
        if nsError.domain == "WebKitErrorDomain", [102, 204].contains(nsError.code) { return }

        failedURL = nsError.userInfo[NSURLErrorFailingURLErrorKey] as? URL ?? webView.url
        loadError = nsError.localizedDescription
    }

    /// Presents `controller` above whatever is on screen and returns true. If
    /// that isn't possible right now (for example a sheet is mid-animation,
    /// when UIKit would silently drop the presentation), runs `fallback`
    /// instead, so WebKit completion handlers are always called.
    @discardableResult
    private func present(_ controller: UIViewController, otherwise fallback: () -> Void = {}) -> Bool {
        guard var top = webView.window?.rootViewController else {
            fallback()
            return false
        }
        while let presented = top.presentedViewController {
            if presented.isBeingDismissed {
                fallback()
                return false
            }
            top = presented
        }
        guard !top.isBeingPresented, !top.isBeingDismissed else {
            fallback()
            return false
        }
        top.present(controller, animated: true)
        return true
    }

    private func confirmOpeningExternally(_ url: URL) {
        let alert = UIAlertController(
            title: String(localized: "Open Another App?"),
            message: url.absoluteString,
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: String(localized: "Cancel"), style: .cancel))
        alert.addAction(UIAlertAction(title: String(localized: "Open"), style: .default) { _ in
            UIApplication.shared.open(url)
        })
        present(alert)
    }

    /// Counts a JavaScript dialog and, from the third one on a page, adds a
    /// "Leave Page" button that answers it with `dismiss` and goes home.
    private func addLeavePageAction(to alert: UIAlertController, dismiss: @escaping @MainActor () -> Void) {
        dialogCount += 1
        guard dialogCount >= 3 else { return }
        alert.addAction(UIAlertAction(title: String(localized: "Leave Page"), style: .destructive) { [weak self] _ in
            dismiss()
            self?.leavePage()
        })
    }

    private func leavePage() {
        isSuppressingDialogs = true
        closePopup()
        load(SearchEngine.current.homeURL)
    }

    private func closePopup() {
        popup?.controller.dismiss(animated: true)
        popup = nil
    }
}

// MARK: - WKNavigationDelegate

extension BrowserModel: WKNavigationDelegate {
    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        preferences: WKWebpagePreferences,
        decisionHandler: @escaping @MainActor @Sendable (WKNavigationActionPolicy, WKWebpagePreferences) -> Void
    ) {
        preferences.preferredContentMode = isDesktopMode ? .desktop : .mobile

        // Open pages without tracking codes such as fbclid or utm_source.
        if LinkCleaner.isEnabled,
           navigationAction.targetFrame?.isMainFrame == true,
           navigationAction.navigationType != .backForward,
           navigationAction.request.httpMethod == "GET",
           let url = navigationAction.request.url,
           let cleaned = LinkCleaner.clean(url),
           cleaned != lastCleanedURL {
            lastCleanedURL = cleaned
            decisionHandler(.cancel, preferences)
            webView.load(URLRequest(url: cleaned))
            return
        }

        guard let url = navigationAction.request.url,
              let scheme = url.scheme?.lowercased(),
              !Self.webSchemes.contains(scheme)
        else {
            decisionHandler(.allow, preferences)
            return
        }

        // Opening tel:, mailto:, App Store or other apps always asks first,
        // because scripts can fake link taps. Iframes only get to ask on a click.
        if navigationAction.navigationType == .linkActivated || (navigationAction.targetFrame?.isMainFrame ?? true) {
            confirmOpeningExternally(url)
        }
        decisionHandler(.cancel, preferences)
    }

    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
        clearError()
    }

    func webView(_ webView: WKWebView, didCommit navigation: WKNavigation!) {
        clearError()
        dialogCount = 0
        isSuppressingDialogs = false
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        refreshControl.endRefreshing()
        lastCleanedURL = nil
        // With "Clear Everything on Quit" on, nothing about the visit is kept.
        if let url = webView.url, !UserDefaults.standard.bool(forKey: Self.clearOnQuitKey) {
            UserDefaults.standard.set(url, forKey: Self.lastURLKey)
        }
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        showError(error)
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        showError(error)
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        let now = Date()
        defer { lastContentProcessCrash = now }
        // Reload once. If the page crashes again right away, stop instead of
        // reloading forever, and let the user decide.
        if let last = lastContentProcessCrash, now.timeIntervalSince(last) < 10 {
            refreshControl.endRefreshing()
            failedURL = webView.url
            loadError = String(localized: "A problem repeatedly occurred on this page.")
            return
        }
        webView.reload()
    }
}

// MARK: - WKUIDelegate

extension BrowserModel: WKUIDelegate {
    func webView(
        _ webView: WKWebView,
        createWebViewWith configuration: WKWebViewConfiguration,
        for navigationAction: WKNavigationAction,
        windowFeatures: WKWindowFeatures
    ) -> WKWebView? {
        // A tapped target="_blank" link just opens in the same view.
        if navigationAction.navigationType == .linkActivated,
           let url = navigationAction.request.url,
           url.absoluteString != "about:blank" {
            webView.load(navigationAction.request)
            return nil
        }

        // A script's window.open() (sign-in and payment popups) gets a real
        // window, so the page can talk to it and close it again.
        if let popup {
            popup.webView.load(navigationAction.request)
            return nil
        }
        let popupView = WKWebView(frame: .zero, configuration: configuration)
        // The user agent belongs to the web view, not its configuration.
        popupView.customUserAgent = webView.customUserAgent
        popupView.uiDelegate = self
        popupView.allowsBackForwardNavigationGestures = true

        let content = UIViewController()
        content.view = popupView
        content.navigationItem.title = navigationAction.request.url?.host
        content.navigationItem.rightBarButtonItem = UIBarButtonItem(
            systemItem: .done,
            primaryAction: UIAction { [weak self] _ in self?.closePopup() }
        )
        let controller = UINavigationController(rootViewController: content)
        // Only Done or the page's window.close() dismiss it, so `popup` stays accurate.
        controller.isModalInPresentation = true

        guard present(controller) else {
            webView.load(navigationAction.request)
            return nil
        }
        popup = (popupView, controller)
        return popupView
    }

    /// Adds "Pin Link" to WebKit's own long-press menu for links.
    func webView(
        _ webView: WKWebView,
        contextMenuConfigurationForElement elementInfo: WKContextMenuElementInfo,
        completionHandler: @escaping @MainActor @Sendable (UIContextMenuConfiguration?) -> Void
    ) {
        let link = elementInfo.linkURL
        completionHandler(UIContextMenuConfiguration(identifier: nil, previewProvider: nil) { [weak self] suggested in
            guard let link else { return UIMenu(children: suggested) }
            let pin = UIAction(title: String(localized: "Pin Link"), image: UIImage(systemName: "pin")) { _ in
                self?.onPinLink?(link)
            }
            return UIMenu(children: suggested + [pin])
        })
    }

    func webViewDidClose(_ webView: WKWebView) {
        if webView === popup?.webView {
            closePopup()
        }
    }

    func webView(
        _ webView: WKWebView,
        runJavaScriptAlertPanelWithMessage message: String,
        initiatedByFrame frame: WKFrameInfo,
        completionHandler: @escaping @MainActor @Sendable () -> Void
    ) {
        guard !isSuppressingDialogs else { return completionHandler() }
        let alert = UIAlertController(title: frame.securityOrigin.host, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: String(localized: "OK"), style: .default) { _ in
            completionHandler()
        })
        addLeavePageAction(to: alert) { completionHandler() }
        present(alert) { completionHandler() }
    }

    func webView(
        _ webView: WKWebView,
        runJavaScriptConfirmPanelWithMessage message: String,
        initiatedByFrame frame: WKFrameInfo,
        completionHandler: @escaping @MainActor @Sendable (Bool) -> Void
    ) {
        guard !isSuppressingDialogs else { return completionHandler(false) }
        let alert = UIAlertController(title: frame.securityOrigin.host, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: String(localized: "Cancel"), style: .cancel) { _ in
            completionHandler(false)
        })
        alert.addAction(UIAlertAction(title: String(localized: "OK"), style: .default) { _ in
            completionHandler(true)
        })
        addLeavePageAction(to: alert) { completionHandler(false) }
        present(alert) { completionHandler(false) }
    }

    func webView(
        _ webView: WKWebView,
        runJavaScriptTextInputPanelWithPrompt prompt: String,
        defaultText: String?,
        initiatedByFrame frame: WKFrameInfo,
        completionHandler: @escaping @MainActor @Sendable (String?) -> Void
    ) {
        guard !isSuppressingDialogs else { return completionHandler(nil) }
        let alert = UIAlertController(title: frame.securityOrigin.host, message: prompt, preferredStyle: .alert)
        alert.addTextField { $0.text = defaultText }
        alert.addAction(UIAlertAction(title: String(localized: "Cancel"), style: .cancel) { _ in
            completionHandler(nil)
        })
        alert.addAction(UIAlertAction(title: String(localized: "OK"), style: .default) { [weak alert] _ in
            completionHandler(alert?.textFields?.first?.text)
        })
        addLeavePageAction(to: alert) { completionHandler(nil) }
        present(alert) { completionHandler(nil) }
    }
}
