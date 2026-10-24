import Foundation

/// Turns what the user typed in the address bar into the URL to load:
/// a full URL, a bare address like "hespress.com", or a web search.
enum AddressResolver {
    static func url(for input: String, searchEngine: SearchEngine) -> URL? {
        let text = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return nil }

        if let url = makeURL(text),
           let scheme = url.scheme?.lowercased(),
           scheme == "http" || scheme == "https",
           url.host != nil {
            return url
        }

        if !text.contains(where: \.isWhitespace), let host = hostKind(of: text) {
            // Local servers rarely have certificates, so they get plain http.
            let scheme = host == .local ? "http://" : "https://"
            if let url = makeURL(scheme + text), url.host != nil {
                return url
            }
        }

        return searchEngine.searchURL(for: text)
    }

    /// Before iOS 17, URL(string:) rejects non-ASCII text such as Arabic, so
    /// fall back to percent-encoding it; WebKit decodes it again when loading.
    private static func makeURL(_ string: String) -> URL? {
        if let url = URL(string: string) { return url }
        guard !string.contains(where: \.isWhitespace) else { return nil }
        var allowed = CharacterSet.urlFragmentAllowed
        allowed.insert(charactersIn: "#%[]")
        return string.addingPercentEncoding(withAllowedCharacters: allowed).flatMap { URL(string: $0) }
    }

    private enum HostKind {
        case domain
        case local
    }

    /// Looks at the part before the first "/", "?" or "#" and decides whether it
    /// is a domain ("google.com"), an IPv4 address, "localhost" or a ".local"
    /// device name, optionally followed by a port.
    private static func hostKind(of text: String) -> HostKind? {
        var host = text.prefix { !"/?#".contains($0) }
        if let colon = host.lastIndex(of: ":") {
            let port = host[host.index(after: colon)...]
            guard !port.isEmpty, port.allSatisfy({ $0.isASCII && $0.isNumber }) else { return nil }
            host = host[..<colon]
        }

        if host.lowercased() == "localhost" { return .local }

        let labels = host.split(separator: ".", omittingEmptySubsequences: false)
        guard labels.count >= 2,
              labels.allSatisfy({ label in
                  !label.isEmpty && label.allSatisfy { $0.isLetter || $0.isNumber || $0 == "-" }
              })
        else { return nil }

        if labels.last?.lowercased() == "local" { return .local }

        let isIPv4 = labels.count == 4 && labels.allSatisfy { label in
            label.allSatisfy { $0.isASCII && $0.isNumber } && (Int(label).map { $0 <= 255 } ?? false)
        }
        if isIPv4 { return .local }

        // The last label must look like a real top-level domain: "com", "ma",
        // "المغرب" or a punycode one such as "xn--mgbc0a9azcg".
        guard let tld = labels.last,
              tld.count >= 2,
              tld.allSatisfy(\.isLetter) || tld.lowercased().hasPrefix("xn--")
        else { return nil }

        return .domain
    }
}
