import Foundation
import WebKit

/// Reads and writes the cookies of the page you are on, like the Cookie-Editor
/// extension: export them as a header string to copy, share or save, and
/// import them back from pasted text or a file. Works on your own cookies in
/// this browser's own store.
@MainActor
enum CookieManager {
    /// The host whose cookies the page uses, without a leading "www.".
    static func host(of url: URL?) -> String? {
        url?.host?.lowercased()
    }

    /// The cookies the current page sends, as the `Cookie:` header string
    /// "name=value; name2=value2". Only the cookies for this site.
    static func exportHeaderString(from webView: WKWebView) async -> String {
        guard let host = host(of: webView.url) else { return "" }
        let cookies = await webView.configuration.websiteDataStore.httpCookieStore.allCookies()
        return cookies
            .filter { matches(host: host, cookieDomain: $0.domain) }
            .map { "\($0.name)=\($0.value)" }
            .joined(separator: "; ")
    }

    /// Reads a header string ("name=value; name2=value2") and sets each cookie
    /// on the current site. Returns how many were set, or nil if the text has
    /// none or there is no page to set them on.
    @discardableResult
    static func importHeaderString(_ text: String, into webView: WKWebView) async -> Int? {
        guard let url = webView.url, let host = host(of: url) else { return nil }
        let pairs = text
            .split(separator: ";")
            .compactMap { pair -> (String, String)? in
                let pair = pair.trimmingCharacters(in: .whitespacesAndNewlines)
                guard let equals = pair.firstIndex(of: "="), equals != pair.startIndex else { return nil }
                return (String(pair[..<equals]), String(pair[pair.index(after: equals)...]))
            }
        guard !pairs.isEmpty else { return nil }

        let store = webView.configuration.websiteDataStore.httpCookieStore
        let isSecure = url.scheme == "https"
        for (name, value) in pairs {
            var properties: [HTTPCookiePropertyKey: Any] = [
                .name: name,
                .value: value,
                .domain: host,
                .path: "/",
            ]
            if isSecure {
                properties[.secure] = "TRUE"
            }
            if let cookie = HTTPCookie(properties: properties) {
                await store.setCookie(cookie)
            }
        }
        return pairs.count
    }

    /// True when a cookie's domain covers `host`. A leading dot means it also
    /// covers subdomains.
    private static func matches(host: String, cookieDomain: String) -> Bool {
        let domain = cookieDomain.hasPrefix(".") ? String(cookieDomain.dropFirst()) : cookieDomain
        return host == domain || host.hasSuffix("." + domain)
    }
}
