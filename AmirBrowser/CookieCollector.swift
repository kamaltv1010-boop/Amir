import Combine
import UIKit
import WebKit

// MARK: - Settings

/// What "Collect Cookies" does, as the settings keep it: which sites
/// (popular ones, a new random mix each time, or the user's own list), how
/// many popular ones, the user's list, whether a new profile collects by
/// itself, and how many profiles collect at once (0: as many as this iPhone
/// takes, see `CookieCollector.deviceLimit`).
struct CookieCollectSettings: Codable, Equatable {
    var mine = false
    var count = 20
    var sites: [String] = []
    var auto = false
    var parallel = 0

    static let key = "cookieCollect"
    /// The most sites one collection visits.
    static let maxSites = 200

    init() {}

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        mine = try container.decodeIfPresent(Bool.self, forKey: .mine) ?? false
        count = try container.decodeIfPresent(Int.self, forKey: .count) ?? 20
        sites = try container.decodeIfPresent([String].self, forKey: .sites) ?? []
        auto = try container.decodeIfPresent(Bool.self, forKey: .auto) ?? false
        parallel = try container.decodeIfPresent(Int.self, forKey: .parallel) ?? 0
    }

    static func load() -> CookieCollectSettings {
        guard let data = UserDefaults.standard.data(forKey: key),
              let saved = try? JSONDecoder().decode(CookieCollectSettings.self, from: data)
        else { return CookieCollectSettings() }
        return saved.checked
    }

    func save() {
        if let data = try? JSONEncoder().encode(checked) {
            UserDefaults.standard.set(data, forKey: Self.key)
        }
    }

    /// Each value within its bounds, the sites as addresses.
    var checked: CookieCollectSettings {
        var copy = self
        copy.count = max(1, min(Self.maxSites, count))
        copy.sites = CookieSites.normalize(sites.joined(separator: "\n")).map(\.absoluteString)
        copy.parallel = max(0, min(CookieCollector.maxAtOnce, parallel))
        return copy
    }
}

// MARK: - Sites

extension CookieSites {
    /// The regions of a time zone's visitors (see `zones`), the first the most.
    static func regions(for zone: String) -> [String] {
        for rule in zones where zone.range(of: rule.pattern, options: .regularExpression) != nil {
            return rule.regions
        }
        return []
    }

    /// What the settings call a region.
    static func regionName(_ code: String) -> String {
        switch code {
        case "MA": return String(localized: "Morocco")
        case "AR": return String(localized: "the Arab world")
        case "FR": return String(localized: "France")
        case "ES": return String(localized: "Spain")
        case "DE": return String(localized: "Germany")
        case "UK": return String(localized: "the United Kingdom")
        case "US": return String(localized: "the United States")
        case "IT": return String(localized: "Italy")
        case "NL": return String(localized: "the Netherlands")
        case "TR": return String(localized: "Türkiye")
        default: return code
        }
    }

    /// A site's own part of a host or a cookie's domain: its registered name
    /// ("hespress.com", "bbc.co.uk"), so its subdomains are the same site.
    static func siteKey(_ host: String) -> String {
        var name = host.lowercased()
        while name.hasSuffix(".") {
            name.removeLast()
        }
        while name.hasPrefix(".") {
            name.removeFirst()
        }
        if name.contains(":") || name.range(of: #"^\d+(\.\d+){3}$"#, options: .regularExpression) != nil {
            return name
        }
        let parts = name.split(separator: ".").map(String.init)
        if parts.count <= 2 {
            return parts.joined(separator: ".")
        }
        let second = parts[parts.count - 2]
        let top = parts[parts.count - 1]
        let shared: Set<String> = ["co", "com", "net", "org", "gov", "ac", "edu", "gob", "or", "ne", "go"]
        let keep = top.count == 2 && shared.contains(second) ? 3 : 2
        return parts.suffix(keep).joined(separator: ".")
    }

    /// `count` home pages to visit, in a random order, one per site: about
    /// half the world's and half the regions' of `zone` (the first region the
    /// most), or all the world's where the zone names no region.
    static func pick(_ count: Int, zone: String) -> [URL] {
        let wanted = max(1, min(CookieCollectSettings.maxSites, count))
        let regionList = Self.regions(for: zone)
        var chosen: [String] = []
        var seen = Set<String>()
        func take(_ pool: [String], _ number: Int) {
            var left = number
            for url in pool.shuffled() {
                if left <= 0 {
                    break
                }
                let key = siteKey(URL(string: url)?.host ?? url)
                guard seen.insert(key).inserted else { continue }
                chosen.append(url)
                left -= 1
            }
        }
        if let first = regionList.first {
            var regional = Int((Double(wanted) * 0.45).rounded())
            let firstShare = regionList.count > 1 ? Int((Double(regional) * 0.6).rounded(.up)) : regional
            take(popular[first] ?? [], firstShare)
            regional -= firstShare
            var index = 1
            while index < regionList.count && regional > 0 {
                let share = Int((Double(regional) / Double(regionList.count - index)).rounded(.up))
                take(popular[regionList[index]] ?? [], share)
                regional -= share
                index += 1
            }
        }
        take(popular["global"] ?? [], wanted - chosen.count)
        if chosen.count < wanted {
            take(popular.values.flatMap { $0 }, wanted - chosen.count)
        }
        return chosen.shuffled().compactMap(URL.init(string:))
    }

    /// Sites as a person writes them, one per line ("hespress.com",
    /// "https://www.youtube.com/"), as addresses to visit: https:// where no
    /// scheme is given, each once; what isn't a web address is left out.
    static func normalize(_ text: String) -> [URL] {
        var out: [URL] = []
        var seen = Set<String>()
        let separators = CharacterSet.whitespacesAndNewlines.union(CharacterSet(charactersIn: ",;"))
        for part in text.components(separatedBy: separators) where !part.isEmpty {
            let hasScheme = part.range(of: #"^[A-Za-z][A-Za-z0-9+.-]*://"#, options: .regularExpression) != nil
            guard var components = URLComponents(string: hasScheme ? part : "https://" + part),
                  let scheme = components.scheme?.lowercased(), scheme == "https" || scheme == "http",
                  let host = components.host, host.contains("."), !host.hasPrefix("."), !host.hasSuffix("."),
                  components.user == nil, components.password == nil
            else { continue }
            components.scheme = scheme
            components.host = host.lowercased()
            components.fragment = nil
            if components.path.isEmpty {
                components.path = "/"
            }
            guard let url = components.url, seen.insert(url.absoluteString).inserted else { continue }
            out.append(url)
            if out.count >= CookieCollectSettings.maxSites {
                break
            }
        }
        return out
    }

    /// An address as a person writes it: no "https://", no last "/".
    static func plain(_ address: String) -> String {
        var text = address
        if text.hasPrefix("https://") {
            text.removeFirst("https://".count)
        }
        if text.hasSuffix("/") {
            text.removeLast()
        }
        return text
    }
}

// MARK: - Status

/// What is under way in a profile, waits, or was last done there.
struct CookieCollectStatus: Equatable {
    let profileID: UUID
    var profileName: String
    var running = false
    var waiting = false
    /// Its place in line, while waiting.
    var position = 0
    var finished = false
    var stopped = false
    var total = 0
    var done = 0
    var failed = 0
    /// The site being visited.
    var current = ""
    /// The region whose sites are visited besides the world's.
    var region = ""
    /// Whether the sites are the user's own.
    var mine = false
    var cookies = 0
    /// How many sites the cookies are from.
    var sites = 0
    /// How many cookies there were before.
    var before = 0

    var added: Int { max(0, cookies - before) }
    var opened: Int { max(0, done - failed) }
}

/// Collections that just started or ended, told together (see BrowserView).
struct CookieCollectNews: Equatable {
    let id = UUID()
    var started: [String] = []
    var ended: [CookieCollectStatus] = []
}

// MARK: - The collector

/// Collecting cookies, as Noor for Windows does: so that a site that checks
/// finds a profile in daily use, not an empty one, Noor visits sites in that
/// profile, in a web view nobody sees (behind the browser, in the profile's
/// own website data, with its own fingerprints and the tracker blocking),
/// whichever profile is shown: switching doesn't stop it. Each visit reads
/// the page a little, scrolls it, accepts the cookie banner, and sometimes
/// opens another page of the site; it never signs in or out, buys or
/// downloads anything, and nothing goes into the history. Many profiles
/// collect at the same time (as many as the settings say), the others wait
/// their turn.
@MainActor
final class CookieCollector: ObservableObject {
    static let shared = CookieCollector()
    /// The most profiles that ever collect at once.
    nonisolated static let maxAtOnce = 10

    /// As many profiles as this iPhone collects in at once: each loads pages
    /// as a tab does, about 500 MB of memory, beside 2.5 GB for the rest.
    nonisolated static var deviceLimit: Int {
        let gigabytes = Double(ProcessInfo.processInfo.physicalMemory) / 1_073_741_824
        return max(1, min(8, Int((gigabytes - 2.5) / 0.5)))
    }

    /// Each profile's collection: under way, waiting, or the last one.
    @Published private(set) var statuses: [UUID: CookieCollectStatus] = [:]
    /// The profiles waiting their turn, in order.
    @Published private(set) var waitingIDs: [UUID] = []
    @Published private(set) var settings = CookieCollectSettings.load()
    /// What just started or ended.
    @Published private(set) var news: CookieCollectNews?

    /// The browser, for its tracker rules.
    weak var model: BrowserModel?
    private var active: [UUID: CookieCollection] = [:]
    private var queue: [(profile: Profile, count: Int?)] = []
    /// Where the web views nobody sees are.
    private var host: UIView?
    private var pending = CookieCollectNews()
    private var newsTask: Task<Void, Never>?
    private var backgroundTask: UIBackgroundTaskIdentifier = .invalid

    private init() {}

    /// The profiles collecting now.
    var runningIDs: [UUID] { Array(active.keys) }

    /// Whether a profile is collecting or waiting to.
    var isBusy: Bool { !active.isEmpty || !queue.isEmpty }

    /// How many profiles collect at once: as the settings say, or as many as
    /// this iPhone takes.
    var atOnce: Int { settings.parallel > 0 ? settings.parallel : Self.deviceLimit }

    func status(for profile: Profile) -> CookieCollectStatus {
        statuses[profile.id] ?? CookieCollectStatus(profileID: profile.id, profileName: profile.name)
    }

    /// The website data store a profile's tabs use (its cookies).
    static func store(for profile: Profile) -> WKWebsiteDataStore {
        let store = Profiles.dataStore(for: profile, inMemory: UserDefaults.standard.bool(forKey: BrowserModel.clearOnQuitKey))
        // Collected through the profile's proxy, as its pages go.
        ProxyManager.shared.attach(store, to: profile.id)
        return store
    }

    /// How many cookies a profile keeps, and for how many sites.
    static func count(_ profile: Profile) async -> (cookies: Int, sites: Int) {
        await count(in: store(for: profile))
    }

    static func count(in store: WKWebsiteDataStore) async -> (cookies: Int, sites: Int) {
        let cookies = await store.httpCookieStore.allCookies()
        return (cookies.count, Set(cookies.map { CookieSites.siteKey($0.domain) }).count)
    }

    /// Saves the settings, each value checked; a higher "at once" starts
    /// those waiting now.
    func save(_ next: CookieCollectSettings) {
        let checked = next.checked
        guard checked != settings else { return }
        settings = checked
        checked.save()
        startWaiting()
    }

    // MARK: Starting and stopping

    /// Collects the cookies of each of `profiles` (those not collecting or
    /// waiting already), all together: as many at once as `atOnce`, the rest
    /// once their turn comes. `count`: that many popular sites instead.
    func start(_ profiles: [Profile], count: Int? = nil) {
        for profile in profiles where active[profile.id] == nil && !queue.contains(where: { $0.profile.id == profile.id }) {
            queue.append((profile, count))
            var status = CookieCollectStatus(profileID: profile.id, profileName: profile.name)
            status.waiting = true
            statuses[profile.id] = status
        }
        startWaiting()
    }

    /// New profiles collect their cookies by themselves where the settings
    /// say so.
    func collectInNew(_ profiles: [Profile]) {
        guard settings.auto, !profiles.isEmpty else { return }
        start(profiles)
    }

    /// Stops the collection of a profile, or takes it out of the line; what
    /// it collected is kept.
    func stop(_ id: UUID) {
        if let index = queue.firstIndex(where: { $0.profile.id == id }) {
            let profile = queue.remove(at: index).profile
            statuses[id] = CookieCollectStatus(profileID: id, profileName: profile.name)
        }
        if let collection = active.removeValue(forKey: id) {
            collection.stop()
            statuses[id] = collection.status
            tell(ended: collection.status)
        }
        startWaiting()
    }

    /// Stops every collection, and empties the line.
    func stopAll() {
        for entry in queue {
            statuses[entry.profile.id] = CookieCollectStatus(profileID: entry.profile.id, profileName: entry.profile.name)
        }
        queue.removeAll()
        for id in Array(active.keys) {
            stop(id)
        }
        startWaiting()
    }

    /// A profile deleted: its visits end, and nothing of them is kept.
    func forget(_ id: UUID) {
        stop(id)
        statuses[id] = nil
    }

    /// Starts what waits, while fewer than `atOnce` are under way.
    private func startWaiting() {
        while active.count < atOnce, !queue.isEmpty {
            let (profile, count) = queue.removeFirst()
            guard Profiles.all.contains(where: { $0.id == profile.id }) else {
                statuses[profile.id] = nil
                continue
            }
            let collection = makeCollection(for: profile, count: count)
            active[profile.id] = collection
            statuses[profile.id] = collection.status
            collection.begin()
        }
        for (index, entry) in queue.enumerated() {
            statuses[entry.profile.id]?.waiting = true
            statuses[entry.profile.id]?.position = index + 1
        }
        waitingIDs = queue.map(\.profile.id)
        holdBackgroundTime()
    }

    /// The visits of `profile`: its own sites in a new order each time, or
    /// popular ones, the world's and those of the time zone's region.
    private func makeCollection(for profile: Profile, count: Int?) -> CookieCollection {
        let zone = TimeZone.current.identifier
        let mine = count == nil && settings.mine && !settings.sites.isEmpty
        let list = mine ? settings.sites.compactMap(URL.init(string:)).shuffled() : CookieSites.pick(count ?? settings.count, zone: zone)
        let region = mine ? "" : CookieSites.regions(for: zone).first.map(CookieSites.regionName) ?? ""
        return CookieCollection(collector: self, profile: profile, list: list, mine: mine, region: region)
    }

    // MARK: From the collections

    fileprivate func update(_ collection: CookieCollection) {
        guard active[collection.profile.id] === collection else { return }
        statuses[collection.profile.id] = collection.status
    }

    /// A collection over by itself: its result kept, the next one started.
    fileprivate func ended(_ collection: CookieCollection) {
        guard active[collection.profile.id] === collection else { return }
        active[collection.profile.id] = nil
        statuses[collection.profile.id] = collection.status
        tell(ended: collection.status)
        startWaiting()
    }

    fileprivate func tell(started name: String) {
        pending.started.append(name)
        sendNewsSoon()
    }

    private func tell(ended status: CookieCollectStatus) {
        pending.ended.append(status)
        sendNewsSoon()
    }

    /// One line for the collections that start (or end) together.
    private func sendNewsSoon() {
        guard newsTask == nil else { return }
        newsTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 400_000_000)
            guard let self else { return }
            self.news = self.pending
            self.pending = CookieCollectNews()
            self.newsTask = nil
        }
    }

    /// Where the web views nobody sees are: behind the browser, in its
    /// window, so their pages run as a shown page's do.
    fileprivate func hostView() -> UIView? {
        if let host, host.window != nil {
            return host
        }
        let windows = UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .flatMap(\.windows)
        guard let window = windows.first(where: \.isKeyWindow) ?? windows.first else { return nil }
        let view = UIView(frame: window.bounds)
        view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        view.isUserInteractionEnabled = false
        view.accessibilityElementsHidden = true
        window.insertSubview(view, at: 0)
        host = view
        return view
    }

    /// A moment more to go on when the app leaves the screen: iOS pauses
    /// pages once it is in the background.
    private func holdBackgroundTime() {
        if isBusy, backgroundTask == .invalid {
            backgroundTask = UIApplication.shared.beginBackgroundTask(withName: "Collect cookies") { [weak self] in
                Task { @MainActor in
                    self?.releaseBackgroundTime()
                }
            }
        } else if !isBusy {
            releaseBackgroundTime()
        }
    }

    private func releaseBackgroundTime() {
        guard backgroundTask != .invalid else { return }
        UIApplication.shared.endBackgroundTask(backgroundTask)
        backgroundTask = .invalid
    }
}

// MARK: - One profile's visits

/// One profile's visits: the web view nobody sees they happen in (in that
/// profile's website data, with its fingerprints), and how far they are.
@MainActor
final class CookieCollection: NSObject, WKNavigationDelegate {
    let profile: Profile
    private(set) var status: CookieCollectStatus {
        didSet {
            collector?.update(self)
        }
    }

    private weak var collector: CookieCollector?
    private let list: [URL]
    private let store: WKWebsiteDataStore
    private var webView: WKWebView?
    private var task: Task<Void, Never>?
    private var ticker: Task<Void, Never>?
    /// The page load waited for (see `waitForLoad`).
    private var loadWaiter: CheckedContinuation<Bool, Never>?
    private var loadToken = 0
    /// Whether the page waited for was shown at all.
    private var committed = false

    /// The world the scripts that read the page and press its banner run in:
    /// not the page's, which doesn't see them.
    private static let world = WKContentWorld.world(name: "NoorCookies")

    /// How long things take, in milliseconds: a pause before the first site
    /// (profiles started together don't all begin in the same second), a
    /// page's load at most; a pause once it is shown, between scrolls, after
    /// the banner; how many scrolls a page gets and how far each goes; the
    /// odds of going on to another page of the site.
    private enum Timing {
        static let start = 0...5000
        static let load = 25_000
        static let settle = 1500...3200
        static let between = 900...2600
        static let afterBanner = 700...1500
        static let scrolls = 2...4
        static let moreScrolls = 1...3
        static let scrollBy = 250...700
        static let follow = 0.5
    }

    init(collector: CookieCollector, profile: Profile, list: [URL], mine: Bool, region: String) {
        self.collector = collector
        self.profile = profile
        self.list = list
        store = CookieCollector.store(for: profile)
        var status = CookieCollectStatus(profileID: profile.id, profileName: profile.name)
        status.total = list.count
        status.mine = mine
        status.region = region
        self.status = status
        super.init()
    }

    /// Starts the visits; they go on after this returns.
    func begin() {
        task = Task { [weak self] in
            await self?.run()
        }
    }

    /// Ends the visits now: the web view goes, and they show as stopped.
    func stop() {
        task?.cancel()
        ticker?.cancel()
        settleLoad(false)
        close()
        status.running = false
        status.stopped = true
        status.finished = true
        status.current = ""
    }

    private func run() async {
        let counted = await CookieCollector.count(in: store)
        status.before = counted.cookies
        status.cookies = counted.cookies
        status.sites = counted.sites
        guard !Task.isCancelled, let host = collector?.hostView() else {
            await finish()
            return
        }
        webView = makeWebView(in: host)
        status.running = true
        collector?.tell(started: profile.name)
        startTicker()
        await waitForTrackerRules()
        await pause(Timing.start)
        for url in list {
            if Task.isCancelled || webView == nil {
                break
            }
            status.current = CookieSites.siteKey(url.host ?? "")
            let opened = await visit(url)
            if Task.isCancelled {
                break
            }
            status.done += 1
            if !opened {
                status.failed += 1
            }
            let now = await CookieCollector.count(in: store)
            status.cookies = now.cookies
            status.sites = now.sites
        }
        await finish()
    }

    /// The visits over: the cookies counted again, the web view gone.
    private func finish() async {
        ticker?.cancel()
        close()
        let now = await CookieCollector.count(in: store)
        status.cookies = now.cookies
        status.sites = now.sites
        status.running = false
        status.finished = true
        status.current = ""
        collector?.ended(self)
    }

    /// One site: its home page read and scrolled, the banner accepted, and
    /// sometimes another of its pages. Whether the home page opened.
    private func visit(_ url: URL) async -> Bool {
        guard await open(url) else { return false }
        await loaded()
        await pause(Timing.settle)
        await acceptBanner()
        await read(Timing.scrolls)
        if !Task.isCancelled, Double.random(in: 0..<1) < Timing.follow, let link = await linkHere(), await follow(link) {
            await loaded()
            await pause(Timing.settle)
            await acceptBanner()
            await read(Timing.moreScrolls)
        }
        return true
    }

    // MARK: The web view

    private func makeWebView(in host: UIView) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = store
        configuration.allowsInlineMediaPlayback = true
        // No sound, no video playing by itself.
        configuration.mediaTypesRequiringUserActionForPlayback = .all
        if #available(iOS 14.5, *) {
            configuration.upgradeKnownHostsToHTTPS = true
        }
        let webView = WKWebView(frame: host.bounds, configuration: configuration)
        webView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        webView.isUserInteractionEnabled = false
        webView.navigationDelegate = self
        host.addSubview(webView)
        return webView
    }

    private func close() {
        guard let webView else { return }
        self.webView = nil
        webView.stopLoading()
        webView.navigationDelegate = nil
        webView.removeFromSuperview()
    }

    /// What a page of `url` gets, as the profile's own tabs give it: its
    /// fingerprint protection and user agent (a sign-in site sees the
    /// iPhone's own), and the tracker blocking, unless shields are down for
    /// the site.
    private func applySettings(for url: URL) {
        guard let webView else { return }
        let shieldsUp = Shields.areUp(for: url)
        let isSignInSite = Shields.isSignInSite(url)
        let controller = webView.configuration.userContentController
        controller.removeAllUserScripts()
        controller.removeAllContentRuleLists()
        let proxied = ProxyManager.shared.isProxied(profile.id)
        if let script = FingerprintProtection.userScript(desktopMode: false, protections: shieldsUp, realDevice: isSignInSite, profile: profile, proxied: proxied) {
            controller.addUserScript(script)
        }
        if shieldsUp, TrackerBlocker.isEnabled, let rules = collector?.model?.trackerRules {
            controller.add(rules)
        }
        webView.customUserAgent = FingerprintProtection.userAgent(protections: shieldsUp && !isSignInSite, desktopMode: false, profile: profile)
    }

    /// No page loads before the tracker rules are ready.
    private func waitForTrackerRules() async {
        var tries = 0
        while tries < 40, let model = collector?.model, !model.isReadyToLoad, !Task.isCancelled {
            tries += 1
            try? await Task.sleep(nanoseconds: 250_000_000)
        }
    }

    /// Counts the cookies every few seconds while visiting.
    private func startTicker() {
        ticker = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 2_000_000_000)
                guard let self, self.status.running, !Task.isCancelled else { return }
                let now = await CookieCollector.count(in: self.store)
                self.status.cookies = now.cookies
                self.status.sites = now.sites
            }
        }
    }

    // MARK: Pages

    private func open(_ url: URL) async -> Bool {
        guard let webView, !Task.isCancelled else { return false }
        applySettings(for: url)
        return await waitForLoad {
            _ = webView.load(URLRequest(url: url))
        }
    }

    /// Starts a navigation and waits until its page is shown, as long as
    /// Timing.load at most: a page still loading by then has given most of
    /// its cookies. False if it didn't open.
    private func waitForLoad(_ start: () -> Void) async -> Bool {
        settleLoad(false)
        loadToken += 1
        let token = loadToken
        committed = false
        return await withCheckedContinuation { (continuation: CheckedContinuation<Bool, Never>) in
            loadWaiter = continuation
            start()
            Task { [weak self] in
                try? await Task.sleep(nanoseconds: UInt64(Timing.load) * 1_000_000)
                guard let self, self.loadToken == token else { return }
                self.settleLoad(self.committed)
            }
        }
    }

    private func settleLoad(_ opened: Bool) {
        guard let waiter = loadWaiter else { return }
        loadWaiter = nil
        loadToken += 1
        waiter.resume(returning: opened)
    }

    /// Waits until the page and what it loads are there, for a while at most.
    private func loaded() async {
        for _ in 0..<40 {
            if Task.isCancelled {
                return
            }
            if await evaluate("document.readyState") == "complete" {
                return
            }
            try? await Task.sleep(nanoseconds: 250_000_000)
        }
    }

    /// Accepts the cookie banner, if the page has one; a banner that shows a
    /// moment late is waited for once.
    private func acceptBanner() async {
        for attempt in 0..<2 {
            if Task.isCancelled {
                return
            }
            if await evaluate(CookieSites.acceptBannerScript) != nil {
                await pause(Timing.afterBanner)
                return
            }
            if attempt == 0 {
                await pause(Timing.afterBanner)
            }
        }
    }

    /// Reads the page: scrolls it down a few times, with a pause each time,
    /// as a person's thumb does.
    private func read(_ scrolls: ClosedRange<Int>) async {
        for _ in 0..<Int.random(in: scrolls) {
            if Task.isCancelled {
                return
            }
            scrollDown(by: CGFloat(Int.random(in: Timing.scrollBy)))
            await pause(Timing.between)
        }
    }

    private func scrollDown(by distance: CGFloat) {
        guard let scroll = webView?.scrollView else { return }
        let bottom = max(0, scroll.contentSize.height - scroll.bounds.height + scroll.adjustedContentInset.bottom)
        let y = min(bottom, scroll.contentOffset.y + distance)
        guard y > scroll.contentOffset.y else { return }
        scroll.setContentOffset(CGPoint(x: scroll.contentOffset.x, y: y), animated: true)
    }

    /// Another page of the site a reader might open, or nil.
    private func linkHere() async -> URL? {
        guard let href = await evaluate(CookieSites.pickLinkScript) else { return nil }
        return URL(string: href)
    }

    /// Opens a link from the page, as a tap on it does: the site sees which
    /// of its pages the visit came from.
    private func follow(_ link: URL) async -> Bool {
        guard let webView, !Task.isCancelled,
              let data = try? JSONSerialization.data(withJSONObject: [link.absoluteString]),
              let quoted = String(data: data, encoding: .utf8)
        else { return false }
        let script = "location.assign(\(quoted)[0]); null"
        let world = Self.world
        return await waitForLoad {
            webView.evaluateJavaScript(script, in: nil, in: world) { _ in }
        }
    }

    /// Runs `source` in the page, in a world of its own; what it gives back
    /// as text, or nil.
    private func evaluate(_ source: String) async -> String? {
        guard let webView else { return nil }
        let world = Self.world
        return await withCheckedContinuation { (continuation: CheckedContinuation<String?, Never>) in
            webView.evaluateJavaScript(source, in: nil, in: world) { result in
                switch result {
                case .success(let value):
                    continuation.resume(returning: value as? String)
                case .failure:
                    continuation.resume(returning: nil)
                }
            }
        }
    }

    /// A random wait between `range`'s ends, in milliseconds, cut short by
    /// stop().
    private func pause(_ range: ClosedRange<Int>) async {
        let milliseconds = Int.random(in: range)
        try? await Task.sleep(nanoseconds: UInt64(milliseconds) * 1_000_000)
    }

    // MARK: WKNavigationDelegate

    func webView(_ webView: WKWebView, didCommit navigation: WKNavigation!) {
        committed = true
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        settleLoad(true)
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        // Replaced by another load (one the page makes): that one is waited for.
        if Self.isCancelled(error) {
            return
        }
        settleLoad(false)
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        // Shown, then stopped loading: it counts.
        if Self.isCancelled(error) {
            return
        }
        settleLoad(true)
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        settleLoad(committed)
    }

    private static func isCancelled(_ error: Error) -> Bool {
        let nsError = error as NSError
        return nsError.domain == NSURLErrorDomain && nsError.code == NSURLErrorCancelled
    }
}
