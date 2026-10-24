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
    private var failedURL: URL?
    private let refreshControl = UIRefreshControl()

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
        loadError = nil
        failedURL = nil
        webView.load(URLRequest(url: url))
    }

    func goBack() {
        webView.goBack()
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

    /// Presents `controller` above whatever is on screen. If nothing can present
    /// it, `fallback` runs instead, so WebKit completion handlers are always called.
    private func present(_ controller: UIViewController, otherwise fallback: () -> Void = {}) {
        guard var top = webView.window?.rootViewController else {
            fallback()
            return
        }
        while let presented = top.presentedViewController, !presented.isBeingDismissed {
            top = presented
        }
        guard !top.isBeingDismissed else {
            fallback()
            return
        }
        top.present(controller, animated: true)
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

        // A tapped tel:/mailto:/App Store link opens directly. Anything a page
        // triggers on its own needs the user's OK; iframes never get to.
        if navigationAction.navigationType == .linkActivated {
            UIApplication.shared.open(url)
        } else if navigationAction.targetFrame?.isMainFrame ?? true {
            confirmOpeningExternally(url)
        }
        decisionHandler(.cancel, preferences)
    }

    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
        loadError = nil
        failedURL = nil
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
        webView.reload()
    }
}

// MARK: - WKUIDelegate

extension BrowserModel: WKUIDelegate {
    /// Links with target="_blank" and window.open() load in the same view.
    func webView(
        _ webView: WKWebView,
        createWebViewWith configuration: WKWebViewConfiguration,
        for navigationAction: WKNavigationAction,
        windowFeatures: WKWindowFeatures
    ) -> WKWebView? {
        if navigationAction.targetFrame == nil {
            webView.load(navigationAction.request)
        }
        return nil
    }

    func webView(
        _ webView: WKWebView,
        runJavaScriptAlertPanelWithMessage message: String,
        initiatedByFrame frame: WKFrameInfo,
        completionHandler: @escaping @MainActor @Sendable () -> Void
    ) {
        let alert = UIAlertController(title: frame.securityOrigin.host, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: String(localized: "OK"), style: .default) { _ in
            completionHandler()
        })
        present(alert) { completionHandler() }
    }

    func webView(
        _ webView: WKWebView,
        runJavaScriptConfirmPanelWithMessage message: String,
        initiatedByFrame frame: WKFrameInfo,
        completionHandler: @escaping @MainActor @Sendable (Bool) -> Void
    ) {
        let alert = UIAlertController(title: frame.securityOrigin.host, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: String(localized: "Cancel"), style: .cancel) { _ in
            completionHandler(false)
        })
        alert.addAction(UIAlertAction(title: String(localized: "OK"), style: .default) { _ in
            completionHandler(true)
        })
        present(alert) { completionHandler(false) }
    }

    func webView(
        _ webView: WKWebView,
        runJavaScriptTextInputPanelWithPrompt prompt: String,
        defaultText: String?,
        initiatedByFrame frame: WKFrameInfo,
        completionHandler: @escaping @MainActor @Sendable (String?) -> Void
    ) {
        let alert = UIAlertController(title: frame.securityOrigin.host, message: prompt, preferredStyle: .alert)
        alert.addTextField { $0.text = defaultText }
        alert.addAction(UIAlertAction(title: String(localized: "Cancel"), style: .cancel) { _ in
            completionHandler(nil)
        })
        alert.addAction(UIAlertAction(title: String(localized: "OK"), style: .default) { [weak alert] _ in
            completionHandler(alert?.textFields?.first?.text)
        })
        present(alert) { completionHandler(nil) }
    }
}
