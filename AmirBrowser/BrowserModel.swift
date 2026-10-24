import Combine
import UIKit
import WebKit

/// Owns the single WKWebView and mirrors its state (address, title, progress…)
/// into published properties the SwiftUI views observe.
@MainActor
final class BrowserModel: NSObject, ObservableObject {
    let webView: WKWebView

    @Published private(set) var currentURL: URL?
    @Published private(set) var pageTitle = ""
    @Published private(set) var canGoBack = false
    @Published private(set) var canGoForward = false
    @Published private(set) var isLoading = false
    @Published private(set) var progress = 0.0
    @Published private(set) var isDesktopMode = false
    /// Set when a page fails to load; the view shows it over the web content.
    @Published private(set) var loadError: String?
    /// The address that failed, so "Try Again" retries it rather than the
    /// previous page.
    @Published private(set) var failedURL: URL?
    /// What the address bar shows: the failed address while the error is up,
    /// the current page otherwise.
    @Published private(set) var displayedURL: URL?

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

    private static let lastURLKey = "lastURL"
    /// Schemes WebKit loads itself; anything else (tel:, mailto:, App Store
    /// links…) is handed to iOS.
    private static let webSchemes: Set<String> = ["http", "https", "about", "data", "blob", "file", "javascript"]

    override init() {
        let configuration = WKWebViewConfiguration()
        configuration.allowsInlineMediaPlayback = true
        webView = WKWebView(frame: .zero, configuration: configuration)
        super.init()

        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsBackForwardNavigationGestures = true

        refreshControl.addTarget(self, action: #selector(pullToRefresh), for: .valueChanged)
        webView.scrollView.refreshControl = refreshControl

        webView.publisher(for: \.url).assign(to: &$currentURL)
        webView.publisher(for: \.title).map { $0 ?? "" }.assign(to: &$pageTitle)
        webView.publisher(for: \.canGoBack).assign(to: &$canGoBack)
        webView.publisher(for: \.canGoForward).assign(to: &$canGoForward)
        webView.publisher(for: \.isLoading).assign(to: &$isLoading)
        webView.publisher(for: \.estimatedProgress).assign(to: &$progress)
        $currentURL.combineLatest($failedURL, $loadError)
            .map { url, failedURL, error in error == nil ? url : failedURL ?? url }
            .removeDuplicates()
            .assign(to: &$displayedURL)
    }

    // MARK: - Actions

    /// Opens the last visited page, or `home` on first launch.
    func loadInitialPage(home: URL) {
        guard webView.url == nil, !webView.isLoading else { return }
        load(UserDefaults.standard.url(forKey: Self.lastURLKey) ?? home)
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
        // The new content mode is applied in decidePolicyFor on the reload.
        reload()
    }

    func share() {
        guard let url = webView.url else { return }
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
        if let url = webView.url {
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
