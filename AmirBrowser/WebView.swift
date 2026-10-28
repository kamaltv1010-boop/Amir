import SwiftUI
import WebKit

/// Puts the model's WKWebView on screen. The web view itself lives in
/// `BrowserModel`, so it survives SwiftUI re-creating this wrapper; a plain
/// container holds it so a new session can swap in a fresh one.
struct WebView: UIViewRepresentable {
    let webView: WKWebView

    func makeUIView(context: Context) -> UIView {
        let container = UIView()
        show(webView, in: container)
        return container
    }

    func updateUIView(_ container: UIView, context: Context) {
        if webView.superview !== container {
            show(webView, in: container)
        }
    }

    private func show(_ webView: WKWebView, in container: UIView) {
        container.subviews.forEach { $0.removeFromSuperview() }
        webView.frame = container.bounds
        webView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        container.addSubview(webView)
    }
}
