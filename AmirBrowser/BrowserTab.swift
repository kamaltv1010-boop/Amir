import Combine
import UIKit
import WebKit

/// What is saved of a tab between launches.
struct SavedTab: Codable {
    var url: URL
    var title: String
}

/// One tab: its WKWebView, mirrored into published properties the views
/// observe (address, title, progress…). `BrowserModel` owns the tabs.
@MainActor
final class BrowserTab: NSObject, ObservableObject, Identifiable {
    let id = UUID()
    /// Private tabs keep their data in memory only and aren't remembered.
    let isPrivate: Bool
    let webView: WKWebView
    private(set) weak var model: BrowserModel?

    @Published private(set) var currentURL: URL?
    @Published private(set) var title = ""
    @Published private(set) var canGoBack = false
    @Published private(set) var canGoForward = false
    @Published private(set) var isLoading = false
    @Published private(set) var progress = 0.0
    @Published private(set) var isDesktopMode = false
    /// The page zoom, 1 being 100%.
    @Published private(set) var zoom = 1.0
    /// Set when a page fails to load; the view shows it over the web content.
    @Published private(set) var loadError: String?
    /// The address that failed, so "Try Again" retries it rather than the
    /// previous page.
    @Published private(set) var failedURL: URL?
    /// A restored tab, or one opened before the tracker rules are ready,
    /// loads this address when it is shown.
    @Published private(set) var pendingURL: URL?
    /// What the address bar shows: the failed address while the error is up,
    /// the current page otherwise.
    @Published private(set) var displayedURL: URL?
    /// Trackers blocked on the current page.
    @Published private(set) var trackersBlocked = 0
    /// The address the page gives itself (its canonical link), when on the
    /// same site: what a bookmark or a pin of it keeps.
    @Published private(set) var canonicalURL: URL?
    /// Whether shields are up for the current site.
    @Published private(set) var shieldsUp = true
    /// A picture of the page for the tab overview.
    @Published private(set) var snapshot: UIImage?

    /// The tab whose page opened this one with window.open() or a link, so
    /// closing it goes back there.
    weak var opener: BrowserTab?
    private var pendingTitle = ""
    private var appliedSettings = ""
    private var appliedUserAgent = ""
    /// An https:// load upgraded from http://, and the http:// address, so it
    /// can go back to http:// if the site doesn't support https.
    private var upgrade: (navigation: WKNavigation?, original: URL)?
    /// The last address cleaned of tracking codes, so a site that redirects
    /// back to the tracking address can't cause an endless loop.
    private var lastCleanedURL: URL?
    private let refreshControl = UIRefreshControl()
    private var lastContentProcessCrash: Date?
    /// JavaScript dialogs the current page has shown. After a few, dialogs get
    /// a "Leave Page" button so a page looping alert() can't lock the app.
    private var dialogCount = 0
    /// Set by "Leave Page" so the old page can't show more dialogs.
    private var isSuppressingDialogs = false
    private var observers: Set<AnyCancellable> = []

    /// Schemes WebKit loads itself; anything else (tel:, mailto:, App Store
    /// links…) is handed to iOS.
    private static let webSchemes: Set<String> = [
        "http", "https", "about", "data", "blob", "file", "javascript", "webkit-extension",
    ]

    /// A new tab. `configuration` is the one WebKit hands over for a window a
    /// page opens; it gets its own content controller, so the new tab's
    /// settings don't change the page that opened it.
    init(model: BrowserModel, isPrivate: Bool, configuration: WKWebViewConfiguration? = nil, restoring saved: SavedTab? = nil) {
        self.model = model
        self.isPrivate = isPrivate
        let configuration = configuration ?? model.makeConfiguration(isPrivate: isPrivate)
        configuration.userContentController = WKUserContentController()
        webView = WKWebView(frame: .zero, configuration: configuration)
        pendingTitle = saved?.title ?? ""
        super.init()
        pendingURL = saved?.url

        webView.configuration.userContentController.add(
            WeakScriptMessageHandler(self), contentWorld: .defaultClient, name: TrackerCounter.messageName
        )
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        webView.allowsLinkPreview = true
        if #available(iOS 16.0, *) {
            webView.isFindInteractionEnabled = true
        }
        refreshControl.addTarget(self, action: #selector(pullToRefresh), for: .valueChanged)
        webView.scrollView.refreshControl = refreshControl

        observers = [
            webView.publisher(for: \.url).sink { [weak self] in self?.currentURL = $0 },
            webView.publisher(for: \.title).sink { [weak self] in self?.titleDidChange($0 ?? "") },
            webView.publisher(for: \.canGoBack).sink { [weak self] in self?.canGoBack = $0 },
            webView.publisher(for: \.canGoForward).sink { [weak self] in self?.canGoForward = $0 },
            webView.publisher(for: \.isLoading).sink { [weak self] in self?.isLoading = $0 },
            webView.publisher(for: \.estimatedProgress).sink { [weak self] in self?.progress = $0 },
        ]
        Publishers.CombineLatest4($currentURL, $failedURL, $loadError, $pendingURL)
            .map { url, failedURL, error, pendingURL in
                error == nil ? url ?? pendingURL : failedURL ?? url
            }
            .removeDuplicates()
            .assign(to: &$displayedURL)

        applySettings(for: pendingURL)
    }

    /// A tab with nothing loaded shows the start page.
    var isBlank: Bool {
        currentURL == nil && pendingURL == nil && loadError == nil
    }

    /// The title to show for the tab: the page's, or its address.
    var displayTitle: String {
        if !title.isEmpty { return title }
        if !pendingTitle.isEmpty { return pendingTitle }
        return Shields.site(of: displayedURL) ?? ""
    }

    /// The address and title to remember, or nil for an empty tab.
    var saved: SavedTab? {
        guard let url = pendingURL ?? webView.url, ["http", "https"].contains(url.scheme ?? "") else { return nil }
        return SavedTab(url: url, title: displayTitle)
    }

    // MARK: - Actions

    /// Loads whatever the user typed: an address or a search.
    func open(_ input: String, searchEngine: SearchEngine) {
        guard let url = AddressResolver.url(for: input, searchEngine: searchEngine) else { return }
        load(url)
    }

    /// Loads `url`, or keeps it for later if the tracker rules aren't ready,
    /// so no page loads unprotected.
    func load(_ url: URL) {
        clearError()
        guard model?.isReadyToLoad ?? true else {
            pendingURL = url
            return
        }
        pendingURL = nil
        applySettings(for: url)
        webView.load(URLRequest(url: url))
    }

    /// Loads the restored or postponed page, if there is one.
    func loadIfNeeded() {
        if let pendingURL {
            load(pendingURL)
        }
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
        } else if pendingURL != nil {
            loadIfNeeded()
        } else if webView.url != nil {
            webView.reload()
        } else {
            refreshControl.endRefreshing()
        }
    }

    func stopLoading() {
        webView.stopLoading()
    }

    func setDesktopMode(_ isOn: Bool, reload shouldReload: Bool = true) {
        guard isOn != isDesktopMode else { return }
        isDesktopMode = isOn
        applySettings(for: webView.url)
        // The new content mode is applied in decidePolicyFor on the reload.
        if shouldReload {
            reload()
        }
    }

    func setZoom(_ zoom: Double) {
        self.zoom = zoom
        webView.pageZoom = zoom
    }

    /// Shows the find bar (iOS 16 and later).
    func findInPage() {
        if #available(iOS 16.0, *) {
            webView.findInteraction?.presentFindNavigator(showingReplace: false)
        }
    }

    func share() {
        guard let pageURL = webView.url else { return }
        let url = LinkCleaner.isEnabled ? LinkCleaner.clean(pageURL) ?? pageURL : pageURL
        let activity = UIActivityViewController(activityItems: [url], applicationActivities: nil)
        activity.popoverPresentationController?.sourceView = webView
        model?.present(activity)
    }

    /// Updates `snapshot` with a small picture of the page.
    func takeSnapshot() {
        guard webView.url != nil, webView.window != nil else { return }
        let configuration = WKSnapshotConfiguration()
        configuration.snapshotWidth = 360
        webView.takeSnapshot(with: configuration) { [weak self] image, _ in
            if let image {
                self?.snapshot = image
            }
        }
    }

    /// Stops everything before the tab goes away.
    func close() {
        webView.stopLoading()
        webView.navigationDelegate = nil
        webView.uiDelegate = nil
        webView.configuration.userContentController.removeAllScriptMessageHandlers()
    }

    /// Installs what this tab's pages get: fingerprint protection and tracker
    /// blocking (unless shields are down for the site), night mode and the
    /// user agent. Sites with shields down see this iPhone as it is. Sign-in
    /// sites see its own user agent and screen size, which they check
    /// against the device, but still get the canvas, WebGL, audio and
    /// ClientRects noise, so each profile looks to them like another phone
    /// of the same kind. Pages pick up a change when they next load. Returns
    /// whether the user agent changed.
    @discardableResult
    func applySettings(for url: URL?, force: Bool = false) -> Bool {
        guard let model else { return false }
        let shieldsUp = Shields.areUp(for: url)
        if self.shieldsUp != shieldsUp {
            self.shieldsUp = shieldsUp
        }
        let isSignInSite = Shields.isSignInSite(url)
        let settings = "\(shieldsUp)|\(isSignInSite)|\(isDesktopMode)|\(model.settingsSignature)"
        guard force || settings != appliedSettings else { return false }
        appliedSettings = settings

        let controller = webView.configuration.userContentController
        controller.removeAllUserScripts()
        controller.removeAllContentRuleLists()
        if let script = FingerprintProtection.userScript(desktopMode: isDesktopMode, protections: shieldsUp, realDevice: isSignInSite) {
            controller.addUserScript(script)
        }
        if NightMode.isEnabled {
            controller.addUserScript(NightMode.script)
        }
        if shieldsUp, TrackerBlocker.isEnabled, let rules = model.trackerRules {
            controller.add(rules)
            if let counter = TrackerCounter.script {
                controller.addUserScript(counter)
            }
        }
        let agent = FingerprintProtection.userAgent(protections: shieldsUp && !isSignInSite, desktopMode: isDesktopMode)
        webView.customUserAgent = agent
        defer { appliedUserAgent = agent ?? "" }
        return (agent ?? "") != appliedUserAgent
    }

    @objc private func pullToRefresh() {
        reload()
    }

    // MARK: - Helpers

    private func titleDidChange(_ newTitle: String) {
        title = newTitle
        if let url = webView.url {
            model?.tabDidUpdateTitle(self, url: url)
        }
    }

    private func clearError() {
        loadError = nil
        failedURL = nil
    }

    private func showError(_ error: Error, navigation: WKNavigation?) {
        refreshControl.endRefreshing()
        let nsError = error as NSError
        // Cancelled loads (stop button, a new page replacing the old one) and
        // loads WebKit hands off elsewhere (downloads, plug-ins) are not failures.
        if nsError.domain == NSURLErrorDomain, nsError.code == NSURLErrorCancelled { return }
        if nsError.domain == "WebKitErrorDomain", [102, 204].contains(nsError.code) { return }

        // An https:// upgrade the site doesn't support: go back to http://.
        if let upgrade, upgrade.navigation === navigation, let host = upgrade.original.host {
            self.upgrade = nil
            model?.httpOnlyHosts.insert(host.lowercased())
            webView.load(URLRequest(url: upgrade.original))
            return
        }

        failedURL = nsError.userInfo[NSURLErrorFailingURLErrorKey] as? URL ?? webView.url
        loadError = nsError.localizedDescription
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
        model?.present(alert)
    }

    /// Counts a JavaScript dialog and, from the third one on a page, adds a
    /// "Leave Page" button that answers it with `dismiss` and goes home.
    private func addLeavePageAction(to alert: UIAlertController, dismiss: @escaping @MainActor () -> Void) {
        dialogCount += 1
        guard dialogCount >= 3 else { return }
        alert.addAction(UIAlertAction(title: String(localized: "Leave Page"), style: .destructive) { [weak self] _ in
            dismiss()
            self?.isSuppressingDialogs = true
            self?.load(SearchEngine.current.homeURL)
        })
    }

    /// Presents `alert`, or answers it with `fallback` if it can't be shown,
    /// so WebKit completion handlers are always called.
    private func presentDialog(_ alert: UIAlertController, otherwise fallback: () -> Void) {
        if let model, model.selectedTab === self, model.present(alert) {
            return
        }
        fallback()
    }
}

// MARK: - WKNavigationDelegate

extension BrowserTab: WKNavigationDelegate {
    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        preferences: WKWebpagePreferences,
        decisionHandler: @escaping @MainActor @Sendable (WKNavigationActionPolicy, WKWebpagePreferences) -> Void
    ) {
        preferences.preferredContentMode = isDesktopMode ? .desktop : .mobile
        let isMainFrame = navigationAction.targetFrame?.isMainFrame == true
        let url = navigationAction.request.url

        // Open pages without tracking codes such as fbclid or utm_source.
        if LinkCleaner.isEnabled,
           isMainFrame,
           Shields.areUp(for: url),
           navigationAction.navigationType != .backForward,
           navigationAction.request.httpMethod == "GET",
           let url,
           let cleaned = LinkCleaner.clean(url),
           cleaned != lastCleanedURL {
            lastCleanedURL = cleaned
            decisionHandler(.cancel, preferences)
            webView.load(URLRequest(url: cleaned))
            return
        }

        // Open http:// pages over https:// when the site supports it.
        if HTTPSUpgrade.isEnabled,
           isMainFrame,
           navigationAction.request.httpMethod == "GET",
           let url,
           let model,
           let host = url.host?.lowercased(),
           !model.httpOnlyHosts.contains(host),
           Shields.areUp(for: url),
           let secure = HTTPSUpgrade.upgraded(url) {
            if upgrade?.original.host?.lowercased() == host {
                // The https:// page sent us back to http://, so the site
                // doesn't want https.
                model.httpOnlyHosts.insert(host)
                upgrade = nil
            } else {
                decisionHandler(.cancel, preferences)
                upgrade = (webView.load(URLRequest(url: secure)), url)
                return
            }
        }

        guard let url,
              let scheme = url.scheme?.lowercased(),
              !Self.webSchemes.contains(scheme)
        else {
            // Shields are per site: set them up before the new page loads. The
            // request already carries the old user agent, so a page that gets
            // a different one is asked for again.
            if isMainFrame,
               applySettings(for: url),
               ["http", "https"].contains(url?.scheme?.lowercased() ?? ""),
               navigationAction.request.httpMethod == "GET",
               navigationAction.navigationType != .backForward {
                decisionHandler(.cancel, preferences)
                webView.load(navigationAction.request)
                return
            }
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
        trackersBlocked = 0
        canonicalURL = nil
        if let upgrade, upgrade.navigation === navigation {
            self.upgrade = nil
            model?.stats.connectionUpgraded()
        }
        model?.tabDidChange(self)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        refreshControl.endRefreshing()
        lastCleanedURL = nil
        readCanonicalURL()
        model?.tabDidFinishLoading(self)
    }

    /// What a bookmark or a pin of this page keeps: the address the page
    /// gives itself (its canonical link, when on the same site), or the
    /// address without tracking codes. The address of the moment (a sign-up
    /// flow's, a campaign's) would bring the page back to that moment, and
    /// tell the site where the visit came from.
    var bookmarkURL: URL? {
        guard let url = webView.url else { return nil }
        return canonicalURL ?? LinkCleaner.clean(url) ?? url
    }

    /// Reads the page's canonical link, when it points to the same site.
    private func readCanonicalURL() {
        guard let pageURL = webView.url, Self.isWebPage(pageURL) else {
            canonicalURL = nil
            return
        }
        let script = "(function () { var link = document.querySelector('link[rel=\"canonical\"]'); return link && link.href ? String(link.href) : ''; })()"
        webView.evaluateJavaScript(script) { [weak self] result, _ in
            guard let self, self.webView.url == pageURL,
                  let href = result as? String, let url = URL(string: href),
                  Self.isWebPage(url), Self.isSameSite(url, pageURL)
            else { return }
            self.canonicalURL = url
        }
    }

    private static func isWebPage(_ url: URL) -> Bool {
        ["http", "https"].contains(url.scheme?.lowercased() ?? "")
    }

    /// Whether two addresses are on the same site ("www." aside).
    private static func isSameSite(_ a: URL, _ b: URL) -> Bool {
        guard var hostA = a.host?.lowercased(), var hostB = b.host?.lowercased() else { return false }
        if hostA.hasPrefix("www.") { hostA.removeFirst(4) }
        if hostB.hasPrefix("www.") { hostB.removeFirst(4) }
        return hostA == hostB || hostA.hasSuffix("." + hostB) || hostB.hasSuffix("." + hostA)
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        showError(error, navigation: navigation)
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        showError(error, navigation: navigation)
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

extension BrowserTab: WKUIDelegate {
    /// Links with target="_blank" and windows scripts open (sign-in and
    /// payment pop-ups) open in a new tab, which the page can still talk to
    /// and close again.
    func webView(
        _ webView: WKWebView,
        createWebViewWith configuration: WKWebViewConfiguration,
        for navigationAction: WKNavigationAction,
        windowFeatures: WKWindowFeatures
    ) -> WKWebView? {
        model?.openTab(configuration: configuration, from: self)?.webView
    }

    func webViewDidClose(_ webView: WKWebView) {
        model?.close(self)
    }

    /// Adds "Open in New Tab" and "Pin Link" to WebKit's own long-press menu
    /// for links.
    func webView(
        _ webView: WKWebView,
        contextMenuConfigurationForElement elementInfo: WKContextMenuElementInfo,
        completionHandler: @escaping @MainActor @Sendable (UIContextMenuConfiguration?) -> Void
    ) {
        let link = elementInfo.linkURL
        let isPrivate = isPrivate
        completionHandler(UIContextMenuConfiguration(identifier: nil, previewProvider: nil) { [weak self] suggested in
            guard let link else { return UIMenu(children: suggested) }
            var actions: [UIMenuElement] = [
                UIAction(title: String(localized: "Open in New Tab"), image: UIImage(systemName: "plus.square.on.square")) { _ in
                    self?.model?.openTab(url: link, isPrivate: isPrivate)
                },
            ]
            if !isPrivate {
                actions.append(UIAction(
                    title: String(localized: "Open in Private Tab"), image: UIImage(systemName: "eyeglasses")
                ) { _ in
                    self?.model?.openTab(url: link, isPrivate: true)
                })
            }
            actions.append(UIAction(title: String(localized: "Pin Link"), image: UIImage(systemName: "pin")) { _ in
                self?.model?.onPinLink?(link)
            })
            let tabActions: UIMenuElement = UIMenu(options: .displayInline, children: actions)
            return UIMenu(children: [tabActions] + suggested)
        })
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
        presentDialog(alert) { completionHandler() }
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
        presentDialog(alert) { completionHandler(false) }
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
        presentDialog(alert) { completionHandler(nil) }
    }
}

// MARK: - WKScriptMessageHandler

extension BrowserTab: WKScriptMessageHandler {
    /// The tracker counter reports each tracker file that didn't load.
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == TrackerCounter.messageName else { return }
        trackersBlocked += 1
        model?.stats.trackerBlocked()
    }
}
