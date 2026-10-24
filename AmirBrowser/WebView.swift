import SwiftUI
import WebKit

/// Puts the model's WKWebView on screen. The web view itself lives in
/// `BrowserModel`, so it survives SwiftUI re-creating this wrapper.
struct WebView: UIViewRepresentable {
    let webView: WKWebView

    func makeUIView(context: Context) -> WKWebView {
        webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {}
}
