import Combine
import Foundation
import Network
import WebKit

/// A proxy server pages can go through: an HTTP proxy (pages go through it
/// with CONNECT, as https:// pages need) or a SOCKS5 one, with the user and
/// password it asks for, if any, and what its last check found.
struct ProxyServer: Identifiable, Codable, Equatable {
    enum Kind: String, Codable, CaseIterable {
        case http
        case socks5

        var title: String {
            switch self {
            case .http: return "HTTP"
            case .socks5: return "SOCKS5"
            }
        }
    }

    var id = UUID()
    var kind: Kind
    var host: String
    var port: Int
    var username: String?
    var password: String?
    /// Found in a public list of free proxies; the others are the user's.
    var isFree = false
    /// The last check: whether a page opened through the proxy, the address
    /// and the country (a region code, such as "DE") sites saw, and how long
    /// the page took, in milliseconds.
    var works: Bool?
    var exitIP: String?
    var country: String?
    var latency: Int?
    var checked: Date?

    /// "host:port", with an IPv6 address in brackets.
    var address: String {
        host.contains(":") ? "[\(host)]:\(port)" : "\(host):\(port)"
    }

    /// What tells two proxies apart: the same kind, address and user are
    /// the same proxy.
    var key: String {
        "\(kind.rawValue)://\(username ?? "")@\(address)".lowercased()
    }

    /// The flag of the proxy's country, or a globe.
    var flag: String {
        guard let country, country.count == 2 else { return "🌐" }
        var flag = ""
        for letter in country.uppercased().unicodeScalars {
            // A regional indicator letter per letter of the code.
            guard (65...90).contains(letter.value), let indicator = UnicodeScalar(0x1F1E6 + letter.value - 65) else { return "🌐" }
            flag.unicodeScalars.append(indicator)
        }
        return flag
    }

    /// The proxy's country in the user's language, such as "Allemagne".
    var countryName: String? {
        country.flatMap { Locale.current.localizedString(forRegionCode: $0) }
    }

    /// What WebKit and URLSession are given to go through the proxy.
    @available(iOS 17.0, *)
    var configuration: ProxyConfiguration? {
        guard (1...65535).contains(port), let endpointPort = NWEndpoint.Port(rawValue: UInt16(port)) else { return nil }
        let endpoint = NWEndpoint.hostPort(host: NWEndpoint.Host(host), port: endpointPort)
        var configuration = kind == .socks5 ? ProxyConfiguration(socksv5Proxy: endpoint) : ProxyConfiguration(httpCONNECTProxy: endpoint)
        if let username, !username.isEmpty {
            configuration.applyCredential(username: username, password: password ?? "")
        }
        // A proxy that fails stops the page; it never goes around it.
        configuration.allowFailover = false
        return configuration
    }

    /// A proxy written as lists and providers write them: "host:port",
    /// "host:port:user:password" or "user:password@host:port", with or
    /// without "http://" or "socks5://" in front (which sets the kind;
    /// without it, it is `kind`). Nil if `text` isn't one.
    static func parse(_ text: String, kind: Kind = .http) -> ProxyServer? {
        var rest = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !rest.isEmpty, !rest.hasPrefix("#") else { return nil }
        var kind = kind
        if let range = rest.range(of: "://") {
            switch rest[..<range.lowerBound].lowercased() {
            case "http", "https": kind = .http
            case "socks5", "socks5h", "socks": kind = .socks5
            default: return nil
            }
            rest = String(rest[range.upperBound...])
        }
        if let slash = rest.firstIndex(of: "/") {
            rest = String(rest[..<slash])
        }
        var username: String?
        var password: String?
        if let at = rest.lastIndex(of: "@") {
            let credentials = rest[..<at].split(separator: ":", maxSplits: 1, omittingEmptySubsequences: false)
            username = credentials.first.map(String.init)
            password = credentials.count > 1 ? String(credentials[1]) : nil
            rest = String(rest[rest.index(after: at)...])
        }
        var host: String
        var fields: [Substring]
        if rest.hasPrefix("["), let close = rest.firstIndex(of: "]") {
            host = String(rest[rest.index(after: rest.startIndex)..<close])
            fields = Array(rest[rest.index(after: close)...].split(separator: ":", omittingEmptySubsequences: false).dropFirst())
        } else {
            let all = rest.split(separator: ":", omittingEmptySubsequences: false)
            guard all.count >= 2 else { return nil }
            host = String(all[0])
            fields = Array(all.dropFirst())
        }
        host = host.trimmingCharacters(in: .whitespaces)
        guard !host.isEmpty, !host.contains(" "), let portText = fields.first,
              let port = Int(portText.trimmingCharacters(in: .whitespaces)), (1...65535).contains(port) else { return nil }
        // "host:port:user:password", as proxy providers give them (a list's
        // "host:port:Country" has one field too few to be read so).
        if username == nil, fields.count >= 3 {
            username = String(fields[1])
            password = fields.dropFirst(2).joined(separator: ":")
        }
        if username?.isEmpty == true {
            username = nil
            password = nil
        }
        return ProxyServer(kind: kind, host: host, port: port, username: username, password: password)
    }
}

/// What a page opened through a proxy (or straight) says of its visitor:
/// the address the visit came from, that address's country, and the time
/// it took, in milliseconds.
struct ProxyTrace: Equatable {
    var ip: String
    var country: String?
    var latency: Int
}

/// How far a search for free proxies is.
struct ProxySearch: Equatable {
    enum Phase: Equatable {
        /// Getting this phone's own address and the lists of free proxies.
        case starting
        /// Checking the proxies of the lists, many at a time.
        case checking
        case done
        /// The internet, or the lists, couldn't be reached.
        case failed
    }

    var phase: Phase = .starting
    var checked = 0
    var total = 0
    var found = 0

    var isRunning: Bool {
        phase == .starting || phase == .checking
    }
}

/// What changes often while proxies are checked, apart from ProxyManager so
/// the browser isn't drawn again for every proxy checked.
@MainActor
final class ProxyProgress: ObservableObject {
    @Published fileprivate(set) var search: ProxySearch?
    /// The proxies being checked now.
    @Published fileprivate(set) var checking: Set<UUID> = []
}

/// What is kept of the proxies between launches.
private struct ProxyState: Codable {
    var isEnabled = false
    var perProfile = true
    var shared: UUID?
    var assigned: [String: UUID] = [:]
    var proxies: [ProxyServer] = []

    init() {}

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        isEnabled = try container.decodeIfPresent(Bool.self, forKey: .isEnabled) ?? false
        perProfile = try container.decodeIfPresent(Bool.self, forKey: .perProfile) ?? true
        shared = try container.decodeIfPresent(UUID.self, forKey: .shared)
        assigned = try container.decodeIfPresent([String: UUID].self, forKey: .assigned) ?? [:]
        proxies = try container.decodeIfPresent([ProxyServer].self, forKey: .proxies) ?? []
    }
}

/// A website data store given its profile's proxy, kept weakly.
private final class AttachedStore {
    weak var store: WKWebsiteDataStore?
    let profile: UUID
    /// The route last given to the store (see ProxyManager.signature).
    var applied: String?

    init(_ store: WKWebsiteDataStore, profile: UUID) {
        self.store = store
        self.profile = profile
    }
}

/// The proxies, which one each profile goes through, and finding free ones
/// that work. Each profile's website data store (its tabs', and the hidden
/// web view collecting its cookies) goes through the profile's proxy:
/// WebKit takes proxies from iOS 17 on. With proxies on, a page never goes
/// around its proxy: a proxy that fails, or none at all, stops it.
@MainActor
final class ProxyManager: ObservableObject {
    static let shared = ProxyManager()

    /// Whether WebKit can go through a proxy here (iOS 17 and later).
    nonisolated static var isAvailable: Bool {
        if #available(iOS 17.0, *) {
            return true
        }
        return false
    }

    /// How many free proxies a search keeps.
    nonisolated static let freeCount = 50
    /// How many proxies of the lists are checked at a time, and at most.
    private nonisolated static let atOnce = 40
    private nonisolated static let mostChecked = 2500

    @Published private(set) var proxies: [ProxyServer]
    @Published private(set) var isEnabled: Bool
    /// A proxy for each profile (or one for every profile).
    @Published private(set) var perProfile: Bool
    let progress = ProxyProgress()
    /// Sent after the route of any profile may have changed; the browser
    /// loads the page again if its own did.
    let changed = PassthroughSubject<Void, Never>()
    /// Sent as a search for free proxies ends, with what it found.
    let searchEnded = PassthroughSubject<ProxySearch, Never>()

    /// The proxy every profile goes through, without a proxy for each.
    private var shared: UUID?
    /// Each profile's proxy, with a proxy for each.
    private var assigned: [UUID: UUID]
    private var attached: [AttachedStore] = []
    private var searchTask: Task<Void, Never>?

    private init() {
        let state = Self.load()
        proxies = state.proxies
        isEnabled = state.isEnabled
        perProfile = state.perProfile
        shared = state.shared
        var assigned: [UUID: UUID] = [:]
        for (profile, proxy) in state.assigned {
            if let id = UUID(uuidString: profile) {
                assigned[id] = proxy
            }
        }
        self.assigned = assigned
    }

    // MARK: - Routes

    enum Route: Equatable {
        /// Proxies off: pages go straight.
        case direct
        case proxy(ProxyServer)
        /// Proxies on, but there is no proxy: pages don't open.
        case noProxy
    }

    /// Where `profile`'s pages go.
    func route(for profile: UUID) -> Route {
        guard isEnabled, Self.isAvailable else { return .direct }
        if let found = proxy(for: profile) {
            return .proxy(found)
        }
        return .noProxy
    }

    /// The proxy `profile` goes through while proxies are on: the one given
    /// to it (or to every profile), else the one it will be given.
    func proxy(for profile: UUID) -> ProxyServer? {
        if let id = perProfile ? assigned[profile] : shared, let proxy = proxies.first(where: { $0.id == id }) {
            return proxy
        }
        return pick(avoiding: [])
    }

    /// Changes with where `profile`'s pages go.
    func signature(for profile: UUID) -> String {
        switch route(for: profile) {
        case .direct: return "direct"
        case .proxy(let proxy): return "proxy:" + proxy.id.uuidString
        case .noProxy: return "none"
        }
    }

    /// Whether `profile`'s pages go through a proxy (or nowhere), so nothing
    /// in them may go around it (see FingerprintProtection's WebRTC part).
    func isProxied(_ profile: UUID) -> Bool {
        route(for: profile) != .direct
    }

    /// The proxy to give a profile: a working one before one known not to
    /// work, the user's own before free ones, the one the fewest profiles
    /// use, then the fastest; one in `avoiding` only if there is no other.
    private func pick(avoiding: Set<UUID>) -> ProxyServer? {
        let others = proxies.filter { !avoiding.contains($0.id) }
        let pool = others.isEmpty ? proxies : others
        var uses: [UUID: Int] = [:]
        if perProfile {
            for id in assigned.values {
                uses[id, default: 0] += 1
            }
        }
        return pool.min { a, b in
            let aFails = a.works == false
            let bFails = b.works == false
            if aFails != bFails { return !aFails }
            if a.isFree != b.isFree { return !a.isFree }
            let aUses = uses[a.id] ?? 0
            let bUses = uses[b.id] ?? 0
            if aUses != bUses { return aUses < bUses }
            return (a.latency ?? Int.max) < (b.latency ?? Int.max)
        }
    }

    /// Gives `profile` (or every profile) its proxy for good, if proxies are
    /// on and it has none. Whether it changed anything.
    @discardableResult
    private func settle(_ profile: UUID) -> Bool {
        guard isEnabled, !proxies.isEmpty else { return false }
        if let id = perProfile ? assigned[profile] : shared, proxies.contains(where: { $0.id == id }) {
            return false
        }
        guard let proxy = pick(avoiding: []) else { return false }
        if perProfile {
            assigned[profile] = proxy.id
        } else {
            shared = proxy.id
        }
        return true
    }

    // MARK: - Website data stores

    /// Gives `store`, a website data store of `profile` (its tabs', or the
    /// web view collecting its cookies), the profile's proxy, now and
    /// whenever it changes. Called before the store loads anything, so no
    /// page of the profile goes around the proxy.
    func attach(_ store: WKWebsiteDataStore, to profile: UUID) {
        attached.removeAll { $0.store == nil || $0.store === store }
        let entry = AttachedStore(store, profile: profile)
        attached.append(entry)
        if settle(profile) {
            save()
        }
        apply(entry)
    }

    private func apply(_ entry: AttachedStore) {
        guard #available(iOS 17.0, *), let store = entry.store else { return }
        let applying = signature(for: entry.profile)
        guard applying != entry.applied else { return }
        entry.applied = applying
        switch route(for: entry.profile) {
        case .direct:
            store.proxyConfigurations = []
        case .proxy(let proxy):
            store.proxyConfigurations = [proxy.configuration ?? Self.nowhere]
        case .noProxy:
            store.proxyConfigurations = [Self.nowhere]
        }
    }

    /// A proxy that refuses everything (this phone's discard port), for
    /// pages that must not go straight.
    @available(iOS 17.0, *)
    private static var nowhere: ProxyConfiguration {
        ProxyConfiguration(httpCONNECTProxy: .hostPort(host: "127.0.0.1", port: 9))
    }

    /// After a change: every profile with a store keeps or gets its proxy,
    /// the proxies are saved, every store goes through its profile's, and
    /// the browser hears of it.
    private func commit() {
        attached.removeAll { $0.store == nil }
        for entry in attached {
            settle(entry.profile)
        }
        save()
        for entry in attached {
            apply(entry)
        }
        changed.send()
    }

    // MARK: - Choices

    /// Turns proxies on or off. On with no proxy yet, free ones are looked
    /// for at once (and pages wait for them).
    func setEnabled(_ isOn: Bool) {
        isEnabled = isOn
        commit()
        if isOn, proxies.isEmpty {
            findFree()
        }
    }

    func setPerProfile(_ isOn: Bool) {
        perProfile = isOn
        commit()
    }

    /// Makes `proxy` the one `profile` goes through (every profile's, with
    /// one proxy for all), and turns proxies on.
    func use(_ proxy: ProxyServer, for profile: UUID) {
        guard proxies.contains(where: { $0.id == proxy.id }) else { return }
        if perProfile {
            assigned[profile] = proxy.id
        } else {
            shared = proxy.id
        }
        isEnabled = true
        commit()
    }

    /// Gives `profile` (every profile, with one proxy for all) another
    /// proxy: the next in the list that works, one no other profile uses if
    /// there is one. The new one.
    @discardableResult
    func changeProxy(for profile: UUID) -> ProxyServer? {
        guard !proxies.isEmpty else { return nil }
        let current = isEnabled ? proxy(for: profile) : nil
        var uses: [UUID: Int] = [:]
        if perProfile {
            for (owner, id) in assigned where owner != profile {
                uses[id, default: 0] += 1
            }
        }
        let start = current.flatMap { now in proxies.firstIndex { $0.id == now.id } } ?? -1
        let count = proxies.count
        let ordered = (1...count).map { proxies[(start + $0 + count) % count] }.filter { $0.id != current?.id }
        let working = ordered.filter { $0.works != false }
        guard let next = working.first(where: { (uses[$0.id] ?? 0) == 0 }) ?? working.first ?? ordered.first else { return nil }
        if perProfile {
            assigned[profile] = next.id
        } else {
            shared = next.id
        }
        isEnabled = true
        commit()
        return next
    }

    /// Forgets the proxy of a profile being deleted. The one it had.
    @discardableResult
    func forget(_ profile: UUID) -> UUID? {
        attached.removeAll { $0.profile == profile }
        guard let old = assigned.removeValue(forKey: profile) else { return nil }
        save()
        return old
    }

    /// Gives a new profile, made in the place of a deleted one, a proxy
    /// other than the deleted one's (`old`), with a proxy for each profile,
    /// so the new profile has a new address too.
    func assignNew(_ profile: UUID, avoiding old: UUID?) {
        var avoiding = Set<UUID>()
        if let old {
            avoiding.insert(old)
        }
        guard isEnabled, perProfile, let proxy = pick(avoiding: avoiding) else { return }
        assigned[profile] = proxy.id
        save()
    }

    // MARK: - The list

    /// Adds the user's proxies, one per line (see ProxyServer.parse), before
    /// the free ones, and checks them. How many were new.
    @discardableResult
    func add(_ text: String, kind: ProxyServer.Kind) -> Int {
        var known = Set(proxies.map(\.key))
        var added: [ProxyServer] = []
        for line in text.split(whereSeparator: \.isNewline) {
            guard let proxy = ProxyServer.parse(String(line), kind: kind), known.insert(proxy.key).inserted else { continue }
            added.append(proxy)
        }
        guard !added.isEmpty else { return 0 }
        proxies = proxies.filter { !$0.isFree } + added + proxies.filter(\.isFree)
        commit()
        check(Set(added.map(\.id)))
        return added.count
    }

    /// Deletes proxies; the profiles that went through them get others.
    func remove(_ ids: Set<UUID>) {
        guard !ids.isEmpty else { return }
        proxies.removeAll { ids.contains($0.id) }
        if let id = shared, ids.contains(id) {
            shared = nil
        }
        assigned = assigned.filter { !ids.contains($0.value) }
        commit()
    }

    func removeFree() {
        remove(Set(proxies.filter(\.isFree).map(\.id)))
    }

    /// Checks proxies again (all, or `ids`): whether they still open pages,
    /// and the country and speed they have now.
    func check(_ ids: Set<UUID>? = nil) {
        guard #available(iOS 17.0, *) else { return }
        let targets = proxies.filter { (ids?.contains($0.id) ?? true) && !progress.checking.contains($0.id) }
        guard !targets.isEmpty else { return }
        progress.checking.formUnion(targets.map(\.id))
        Task { [weak self] in
            await withTaskGroup(of: (UUID, ProxyTrace?).self) { group in
                for proxy in targets {
                    group.addTask {
                        (proxy.id, await ProxyManager.trace(through: proxy))
                    }
                }
                for await result in group {
                    self?.record(result.0, trace: result.1)
                }
            }
            self?.commit()
        }
    }

    private func record(_ id: UUID, trace: ProxyTrace?) {
        progress.checking.remove(id)
        guard let index = proxies.firstIndex(where: { $0.id == id }) else { return }
        proxies[index].checked = Date()
        if let trace {
            proxies[index].works = true
            proxies[index].exitIP = trace.ip
            proxies[index].country = trace.country
            proxies[index].latency = trace.latency
        } else {
            proxies[index].works = false
        }
    }

    // MARK: - Free proxies

    /// Looks for free proxies that work from here, up to 50, in the
    /// background: the free ones kept are checked again (those that stopped
    /// working go), then the proxies of public lists, many at a time, until
    /// 50 work, each with an address of its own. The fastest come first;
    /// the user's own proxies stay as they are.
    func findFree() {
        guard searchTask == nil else { return }
        guard #available(iOS 17.0, *) else { return }
        progress.search = ProxySearch()
        searchTask = Task { [weak self] in
            await self?.runSearch()
            self?.searchTask = nil
        }
    }

    /// Stops the search; the proxies found so far are kept.
    func stopSearch() {
        searchTask?.cancel()
    }

    @available(iOS 17.0, *)
    private func runSearch() async {
        // This phone's own address: a "proxy" that shows it is none.
        guard let home = await Self.trace(through: nil, timeout: 12) else {
            fail()
            return
        }
        var known = Set(proxies.map(\.key))
        var candidates = proxies.filter(\.isFree)
        let listed = await Self.freeListProxies()
        for proxy in listed where known.insert(proxy.key).inserted {
            candidates.append(proxy)
        }
        if candidates.isEmpty {
            fail()
            return
        }
        candidates = Array(candidates.prefix(Self.mostChecked))
        progress.search?.phase = .checking
        progress.search?.total = candidates.count
        var found: [ProxyServer] = []
        var addresses: Set<String> = [home.ip]
        await withTaskGroup(of: (ProxyServer, ProxyTrace?).self) { group in
            var next = 0
            while next < min(Self.atOnce, candidates.count) {
                let candidate = candidates[next]
                next += 1
                group.addTask {
                    (candidate, await ProxyManager.trace(through: candidate))
                }
            }
            while let result = await group.next() {
                if Task.isCancelled {
                    break
                }
                progress.search?.checked += 1
                if let trace = result.1, addresses.insert(trace.ip).inserted {
                    var proxy = result.0
                    proxy.isFree = true
                    proxy.works = true
                    proxy.exitIP = trace.ip
                    proxy.country = trace.country
                    proxy.latency = trace.latency
                    proxy.checked = Date()
                    found.append(proxy)
                    progress.search?.found = found.count
                    if found.count >= Self.freeCount {
                        break
                    }
                }
                if next < candidates.count {
                    let candidate = candidates[next]
                    next += 1
                    group.addTask {
                        (candidate, await ProxyManager.trace(through: candidate))
                    }
                }
            }
            group.cancelAll()
        }
        found.sort { ($0.latency ?? Int.max) < ($1.latency ?? Int.max) }
        proxies = proxies.filter { !$0.isFree } + found
        progress.search?.phase = .done
        commit()
        if let search = progress.search {
            searchEnded.send(search)
        }
    }

    /// The internet, or the lists, couldn't be reached.
    private func fail() {
        progress.search?.phase = .failed
        if let search = progress.search {
            searchEnded.send(search)
        }
    }

    /// Public lists of free proxies, checked often by those who keep them:
    /// first those of proxies that open https:// pages.
    private nonisolated static let freeLists: [(url: String, kind: ProxyServer.Kind)] = [
        ("https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/https/data.txt", .http),
        ("https://raw.githubusercontent.com/zloi-user/hideip.me/main/https.txt", .http),
        ("https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt", .http),
        ("https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt", .socks5),
        ("https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks5.txt", .socks5),
        ("https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt", .socks5),
    ]

    /// The proxies of the free lists, in their order.
    private nonisolated static func freeListProxies() async -> [ProxyServer] {
        let lists = freeLists
        return await withTaskGroup(of: (Int, [ProxyServer]).self) { group in
            for (index, list) in lists.enumerated() {
                group.addTask {
                    guard let url = URL(string: list.url) else { return (index, []) }
                    let request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 20)
                    guard let result = try? await URLSession.shared.data(for: request),
                          (result.1 as? HTTPURLResponse)?.statusCode == 200,
                          let text = String(data: result.0, encoding: .utf8) else { return (index, []) }
                    let proxies = text.split(whereSeparator: \.isNewline).prefix(4000).compactMap {
                        ProxyServer.parse(String($0), kind: list.kind)
                    }
                    return (index, proxies)
                }
            }
            var found = Array(repeating: [ProxyServer](), count: lists.count)
            for await result in group {
                found[result.0] = result.1
            }
            return found.flatMap { $0 }
        }
    }

    /// Cloudflare's trace page, which says the address a visit came from and
    /// its country.
    private nonisolated static let traceURL = URL(string: "https://www.cloudflare.com/cdn-cgi/trace")!

    /// What the trace page says through `proxy` (or straight, with nil), or
    /// nil if it didn't open within `timeout` seconds.
    @available(iOS 17.0, *)
    nonisolated static func trace(through proxy: ProxyServer?, timeout: TimeInterval = 7) async -> ProxyTrace? {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = timeout
        configuration.timeoutIntervalForResource = timeout + 3
        configuration.waitsForConnectivity = false
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        configuration.urlCache = nil
        configuration.httpCookieStorage = nil
        if let proxy {
            guard let proxyConfiguration = proxy.configuration else { return nil }
            configuration.proxyConfigurations = [proxyConfiguration]
        }
        let session = URLSession(configuration: configuration)
        defer { session.invalidateAndCancel() }
        let started = Date()
        do {
            let (data, response) = try await session.data(from: traceURL)
            guard (response as? HTTPURLResponse)?.statusCode == 200,
                  let text = String(data: data, encoding: .utf8) else { return nil }
            var fields: [String: String] = [:]
            for line in text.split(whereSeparator: \.isNewline) {
                let parts = line.split(separator: "=", maxSplits: 1)
                if parts.count == 2 {
                    fields[String(parts[0])] = String(parts[1])
                }
            }
            guard let ip = fields["ip"], !ip.isEmpty else { return nil }
            var country: String?
            if let code = fields["loc"]?.uppercased(), code.count == 2, code != "XX", code != "T1" {
                country = code
            }
            return ProxyTrace(ip: ip, country: country, latency: Int(Date().timeIntervalSince(started) * 1000))
        } catch {
            return nil
        }
    }

    // MARK: - Saving

    private nonisolated static var fileURL: URL? {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first?.appendingPathComponent("Proxies.json")
    }

    private static func load() -> ProxyState {
        guard let url = fileURL, let data = try? Data(contentsOf: url),
              let state = try? JSONDecoder().decode(ProxyState.self, from: data) else { return ProxyState() }
        return state
    }

    private func save() {
        var state = ProxyState()
        state.isEnabled = isEnabled
        state.perProfile = perProfile
        state.shared = shared
        state.assigned = Dictionary(uniqueKeysWithValues: assigned.map { ($0.key.uuidString, $0.value) })
        state.proxies = proxies
        guard let url = Self.fileURL, let data = try? JSONEncoder().encode(state) else { return }
        try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        // Kept from other apps and from a locked phone's backups (the
        // passwords of the user's proxies are in it).
        try? data.write(to: url, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
    }
}
