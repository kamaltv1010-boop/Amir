import SwiftUI
import WebKit

/// Puts the model's WKWebView on screen. The web view itself lives in
/// `BrowserModel`, so it survives SwiftUI re-creating this wrapper; a
/// container holds it so a new session can swap in a fresh one. In iPad
/// mode the container shows it as big as the iPad's screen, scaled down.
struct WebView: UIViewRepresentable {
    let webView: WKWebView
    /// The screen of the iPad pages see, in points, portrait; nil fills the
    /// space with the web view as usual.
    var tabletScreen: CGSize? = nil

    func makeUIView(context: Context) -> WebViewContainer {
        let container = WebViewContainer()
        container.tabletScreen = tabletScreen
        container.show(webView)
        return container
    }

    func updateUIView(_ container: WebViewContainer, context: Context) {
        if webView.superview !== container {
            container.show(webView)
        }
        if container.tabletScreen != tabletScreen {
            container.tabletScreen = tabletScreen
            container.setNeedsLayout()
        }
    }
}

/// Holds the web view: filling the container or, in iPad mode, as big as
/// the iPad's screen less Safari's bars and scaled down to the container's
/// width, at the top, with the rest of the container empty. A page then
/// lays out and measures itself (innerWidth, innerHeight, media queries,
/// the viewport scale) exactly as on that iPad, as it does in tablet
/// profiles of browsers like Octo. Touches go through the scaling, so the
/// page works as usual, just smaller.
final class WebViewContainer: UIView {
    var tabletScreen: CGSize?
    private weak var webView: WKWebView?
    /// What Safari's status bar and tab bar take of an iPad's screen in
    /// portrait, so the page's height is one Safari gives there.
    private static let tabletBars: CGFloat = 151

    override init(frame: CGRect) {
        super.init(frame: frame)
        setUp()
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
        setUp()
    }

    private func setUp() {
        backgroundColor = .systemBackground
        clipsToBounds = true
    }

    func show(_ webView: WKWebView) {
        subviews.forEach { $0.removeFromSuperview() }
        self.webView = webView
        webView.autoresizingMask = []
        addSubview(webView)
        setNeedsLayout()
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        guard let webView else { return }
        guard let screen = tabletScreen, bounds.width > 0, bounds.height > 0 else {
            webView.transform = .identity
            webView.frame = bounds
            return
        }
        let landscape = bounds.width > bounds.height
        let width = landscape ? screen.height : screen.width
        let tallest = (landscape ? screen.width : screen.height) - Self.tabletBars
        let scale = bounds.width / width
        let height = min(tallest, (bounds.height / scale).rounded(.down))
        webView.transform = .identity
        webView.bounds = CGRect(x: 0, y: 0, width: width, height: height)
        webView.transform = CGAffineTransform(scaleX: scale, y: scale)
        webView.center = CGPoint(x: width * scale / 2, y: height * scale / 2)
    }
}
