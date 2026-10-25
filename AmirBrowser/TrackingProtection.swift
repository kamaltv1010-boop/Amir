import Foundation
import WebKit

/// Blocks tracking and ad services with a WebKit content blocker, so they
/// can't follow you from site to site: Meta Pixel and Facebook or Instagram
/// files on other sites, Google Analytics, TikTok, X, Snapchat and more. The
/// rules live in TrackerRules.json; Meta's own sites still load their files.
enum TrackerBlocker {
    static let enabledKey = "blockTrackers"

    static var isEnabled: Bool {
        UserDefaults.standard.object(forKey: enabledKey) as? Bool ?? true
    }

    /// The compiled rules, or nil if they are missing or don't compile.
    @MainActor
    static func compile() async -> WKContentRuleList? {
        guard let url = Bundle.main.url(forResource: "TrackerRules", withExtension: "json"),
              let rules = try? String(contentsOf: url, encoding: .utf8)
        else { return nil }
        return try? await WKContentRuleListStore.default().compileContentRuleList(
            forIdentifier: "TrackerRules",
            encodedContentRuleList: rules
        )
    }
}

/// Removes tracking codes such as fbclid, igshid, gclid and utm_* from the
/// addresses you open, so sites can't tell where you came from.
enum LinkCleaner {
    static let enabledKey = "cleanLinks"

    static var isEnabled: Bool {
        UserDefaults.standard.object(forKey: enabledKey) as? Bool ?? true
    }

    private static let trackingParameters: Set<String> = [
        "fbclid", "igshid", "igsh", "gclid", "dclid", "gbraid", "wbraid", "msclkid",
        "ttclid", "twclid", "li_fat_id", "yclid", "srsltid", "mc_cid", "mc_eid",
        "_hsenc", "_hsmi", "mkt_tok", "oly_anon_id", "oly_enc_id", "vero_id",
    ]

    /// `url` without its tracking parameters, or nil if it has none.
    static func clean(_ url: URL) -> URL? {
        guard var components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              let items = components.percentEncodedQueryItems
        else { return nil }
        let kept = items.filter { !isTracking($0.name) }
        guard kept.count < items.count else { return nil }
        components.percentEncodedQueryItems = kept.isEmpty ? nil : kept
        return components.url
    }

    private static func isTracking(_ name: String) -> Bool {
        let name = name.lowercased()
        return name.hasPrefix("utm_") || trackingParameters.contains(name)
    }
}

/// Covers the page while the app isn't active, so the app switcher shows a
/// blank screen instead of what you were looking at.
enum PrivacyScreen {
    static let enabledKey = "hideInSwitcher"
}
