import Foundation

/// The search engine used when the address bar text is not a web address.
enum SearchEngine: String, CaseIterable, Identifiable {
    case google
    case duckDuckGo
    case bing

    var id: Self { self }

    var name: String {
        switch self {
        case .google: return "Google"
        case .duckDuckGo: return "DuckDuckGo"
        case .bing: return "Bing"
        }
    }

    var homeURL: URL {
        switch self {
        case .google: return URL(string: "https://www.google.com")!
        case .duckDuckGo: return URL(string: "https://duckduckgo.com")!
        case .bing: return URL(string: "https://www.bing.com")!
        }
    }

    func searchURL(for query: String) -> URL? {
        let prefix: String
        switch self {
        case .google: prefix = "https://www.google.com/search?q="
        case .duckDuckGo: prefix = "https://duckduckgo.com/?q="
        case .bing: prefix = "https://www.bing.com/search?q="
        }
        guard let encoded = query.addingPercentEncoding(withAllowedCharacters: Self.unreserved) else {
            return nil
        }
        return URL(string: prefix + encoded)
    }

    /// RFC 3986 unreserved characters. Everything else, including "+", "&" and
    /// non-ASCII text such as Arabic, gets percent-encoded.
    private static let unreserved = CharacterSet(
        charactersIn: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~"
    )
}
