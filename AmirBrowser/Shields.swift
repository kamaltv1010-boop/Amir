import SwiftUI
import WebKit

/// Brave-style shields. Tracker blocking, HTTPS upgrades and fingerprint
/// protection are on everywhere, and can be turned off for a single site
/// that doesn't work with them.
enum Shields {
    static let downSitesKey = "shieldsDownSites"

    /// What shields are set for: the host without "www.".
    static func site(of url: URL?) -> String? {
        guard let host = url?.host?.lowercased(), !host.isEmpty else { return nil }
        return host.hasPrefix("www.") ? String(host.dropFirst(4)) : host
    }

    /// The sites shields are down for, sorted.
    static var downSites: [String] {
        UserDefaults.standard.stringArray(forKey: downSitesKey) ?? []
    }

    static func areUp(for url: URL?) -> Bool {
        guard let site = site(of: url) else { return true }
        return !downSites.contains(site)
    }

    static func setUp(_ isUp: Bool, for site: String) {
        var sites = downSites.filter { $0 != site }
        if !isUp {
            sites.append(site)
        }
        UserDefaults.standard.set(sites.sorted(), forKey: downSitesKey)
    }
}

/// Opens http:// pages over https://, and goes back to http:// for the
/// sites that don't support it.
enum HTTPSUpgrade {
    static let enabledKey = "httpsUpgrade"

    static var isEnabled: Bool {
        UserDefaults.standard.object(forKey: enabledKey) as? Bool ?? true
    }

    /// The https:// version of `url`, or nil if it should be left alone:
    /// it isn't http://, names a port, or is a local address.
    static func upgraded(_ url: URL) -> URL? {
        guard url.scheme?.lowercased() == "http",
              var components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              components.port == nil,
              let host = components.host?.lowercased(),
              host.contains("."),
              !host.hasSuffix(".local"),
              !host.contains(":"),
              !host.split(separator: ".").allSatisfy({ $0.allSatisfy(\.isNumber) })
        else { return nil }
        components.scheme = "https"
        return components.url
    }
}

/// Shows pages with dark colors by inverting them, and inverting pictures
/// and videos back so they look as they should.
enum NightMode {
    static let enabledKey = "nightMode"

    static var isEnabled: Bool {
        UserDefaults.standard.bool(forKey: enabledKey)
    }

    /// Runs in its own world, so pages can't see or remove it. The style is
    /// added as soon as the page has a root element, so it never flashes white.
    @MainActor
    static let script = WKUserScript(source: #"""
    (() => {
      const style = document.createElement("style");
      style.textContent =
        "html{filter:invert(1) hue-rotate(180deg)!important;background:#fff!important}" +
        "img,video,picture,canvas,iframe,embed,object,svg image,[style*='background-image']" +
        "{filter:invert(1) hue-rotate(180deg)!important}";
      const add = () => document.documentElement.appendChild(style);
      if (document.documentElement) {
        add();
      } else {
        new MutationObserver((records, observer) => {
          if (!document.documentElement) return;
          observer.disconnect();
          add();
        }).observe(document, { childList: true });
      }
    })();
    """#, injectionTime: .atDocumentStart, forMainFrameOnly: true, in: .defaultClient)
}

/// Counts the trackers blocked on a page. WebKit doesn't report what a
/// content blocker blocked, so a script in its own world watches for files
/// that failed to load from the tracker domains in TrackerRules.json. Requests
/// scripts make themselves (fetch, beacons) aren't seen, so this undercounts.
enum TrackerCounter {
    static let messageName = "amirTrackers"

    @MainActor
    static let script: WKUserScript? = {
        guard let rules = trackerDomains(),
              let json = try? JSONSerialization.data(withJSONObject: rules),
              let list = String(data: json, encoding: .utf8)
        else { return nil }
        let source = #"""
        (() => {
          const rules = \#(list);
          const within = (host, domain) => host === domain || host.endsWith("." + domain);
          let page = location.hostname;
          try { page = window.top.location.hostname; } catch (e) {}
          // Like the rules: third-party files only, and Meta's files are fine on Meta's sites.
          const isTracker = (host) => rules.some((rule) =>
            within(host, rule.domain) && !within(page, rule.domain) &&
            !rule.allowedOn.some((site) => within(page, site)));
          const reported = new Set();
          addEventListener("error", (event) => {
            const element = event.target;
            if (!(element instanceof Element)) return;
            const address = element.currentSrc || element.src || element.href;
            if (typeof address !== "string" || !address || reported.has(address)) return;
            let host;
            try { host = new URL(address, location.href).hostname; } catch (e) { return; }
            if (!isTracker(host)) return;
            reported.add(address);
            window.webkit.messageHandlers.\#(messageName).postMessage(host);
          }, true);
        })();
        """#
        return WKUserScript(source: source, injectionTime: .atDocumentStart, forMainFrameOnly: false, in: .defaultClient)
    }()

    /// The domain each rule in TrackerRules.json blocks, and the sites where
    /// it is allowed, from url-filters like `^[^:]+://+([^:/]+\.)?domain\.com[:/]`.
    private static func trackerDomains() -> [[String: Any]]? {
        struct Rule: Decodable {
            struct Trigger: Decodable {
                let urlFilter: String
                let unlessDomain: [String]?

                enum CodingKeys: String, CodingKey {
                    case urlFilter = "url-filter"
                    case unlessDomain = "unless-domain"
                }
            }

            let trigger: Trigger
        }

        guard let url = Bundle.main.url(forResource: "TrackerRules", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let rules = try? JSONDecoder().decode([Rule].self, from: data)
        else { return nil }
        let prefix = #"^[^:]+://+([^:/]+\.)?"#
        let suffix = "[:/]"
        return rules.compactMap { rule in
            let filter = rule.trigger.urlFilter
            guard filter.hasPrefix(prefix), filter.hasSuffix(suffix) else { return nil }
            let domain = filter.dropFirst(prefix.count).dropLast(suffix.count).replacingOccurrences(of: "\\", with: "")
            let allowedOn = (rule.trigger.unlessDomain ?? []).map { $0.hasPrefix("*") ? String($0.dropFirst()) : $0 }
            return ["domain": domain, "allowedOn": allowedOn]
        }
    }
}

/// Totals for the start page, like Brave's.
@MainActor
final class PrivacyStats: ObservableObject {
    @Published private(set) var trackersBlocked: Int
    @Published private(set) var httpsUpgrades: Int

    private static let trackersKey = "stats.trackersBlocked"
    private static let upgradesKey = "stats.httpsUpgrades"

    init() {
        trackersBlocked = UserDefaults.standard.integer(forKey: Self.trackersKey)
        httpsUpgrades = UserDefaults.standard.integer(forKey: Self.upgradesKey)
    }

    /// About 50 ms of loading for every tracker that didn't load.
    var timeSaved: TimeInterval {
        Double(trackersBlocked) * 0.05
    }

    func trackerBlocked() {
        trackersBlocked += 1
        UserDefaults.standard.set(trackersBlocked, forKey: Self.trackersKey)
    }

    func connectionUpgraded() {
        httpsUpgrades += 1
        UserDefaults.standard.set(httpsUpgrades, forKey: Self.upgradesKey)
    }

    func reset() {
        trackersBlocked = 0
        httpsUpgrades = 0
        UserDefaults.standard.removeObject(forKey: Self.trackersKey)
        UserDefaults.standard.removeObject(forKey: Self.upgradesKey)
    }
}

/// Forwards script messages to a handler it holds weakly, so the web view's
/// content controller doesn't keep its tab alive.
@MainActor
final class WeakScriptMessageHandler: NSObject, WKScriptMessageHandler {
    private weak var target: WKScriptMessageHandler?

    init(_ target: WKScriptMessageHandler) {
        self.target = target
    }

    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        target?.userContentController(controller, didReceive: message)
    }
}
