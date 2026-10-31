import SwiftUI
import WebKit

/// Every cookie a profile keeps, site by site, as Noor for Windows' Cookies
/// page shows them: look for one, copy a value, delete a site's, or save them
/// all as a cookies.txt file (the format curl, yt-dlp and the "cookies.txt"
/// extensions use) or as JSON. Any profile, whichever is in use.
@MainActor
struct ProfileCookiesView: View {
    @ObservedObject var browser: BrowserModel
    @ObservedObject private var collector = CookieCollector.shared
    @State private var profileID: UUID?
    @State private var cookies: [HTTPCookie] = []
    @State private var isLoading = true
    @State private var query = ""
    @State private var opened: Set<String> = []
    @State private var deleting: String?
    @State private var copiedID: String?

    /// One cookie, told apart from the others by where it goes and its name.
    struct Item: Identifiable {
        let cookie: HTTPCookie
        var id: String { "\(cookie.domain)|\(cookie.path)|\(cookie.name)" }
    }

    /// A site's cookies.
    private struct Site: Identifiable {
        let name: String
        let items: [Item]
        var id: String { name }
    }

    private enum Format {
        case text, json
    }

    private var profile: Profile {
        browser.profiles.first { $0.id == profileID } ?? browser.profile
    }

    var body: some View {
        List {
            Section {
                Picker("Profile", selection: Binding(get: { profile.id }, set: { profileID = $0 })) {
                    ForEach(browser.profiles) { profile in
                        Text(verbatim: profile.name).tag(profile.id)
                    }
                }
                CookieCollectRow(profile: profile)
            } footer: {
                summary
            }

            ForEach(sites) { site in
                Section {
                    DisclosureGroup(isExpanded: isOpen(site.name)) {
                        ForEach(site.items) { item in
                            CookieRow(item: item, isCopied: copiedID == item.id) {
                                copy(item)
                            }
                        }
                    } label: {
                        HStack {
                            Text(verbatim: site.name)
                                .fontWeight(.semibold)
                            Spacer()
                            Text("\(site.items.count) cookies")
                                .font(.footnote)
                                .foregroundColor(.secondary)
                        }
                    }
                    .swipeActions(edge: .trailing) {
                        Button(role: .destructive) {
                            deleting = site.name
                        } label: {
                            Label("Delete", systemImage: "trash")
                        }
                    }
                    .contextMenu {
                        Button(role: .destructive) {
                            deleting = site.name
                        } label: {
                            Label("Delete the Site's Cookies", systemImage: "trash")
                        }
                    }
                }
            }
        }
        .searchable(text: $query, prompt: Text("Search sites and cookies"))
        .refreshable {
            await load()
        }
        .task(id: profile.id) {
            await load()
        }
        .onChange(of: collector.statuses[profile.id]?.finished ?? false) { finished in
            if finished {
                Task { await load() }
            }
        }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Menu {
                    Button {
                        save(.text)
                    } label: {
                        Label("cookies.txt", systemImage: "doc.text")
                    }
                    Button {
                        save(.json)
                    } label: {
                        Label("JSON", systemImage: "curlybraces")
                    }
                } label: {
                    Label("Save as File", systemImage: "square.and.arrow.up")
                }
                .disabled(cookies.isEmpty)
            }
        }
        .confirmationDialog(deleteTitle, isPresented: isDeleting, titleVisibility: .visible) {
            Button("Delete Cookies", role: .destructive) {
                if let site = deleting {
                    Task { await delete(site: site) }
                }
                deleting = nil
            }
        } message: {
            Text("The site forgets this profile: you may have to sign in to it again.")
        }
        .navigationTitle("Cookies")
        .navigationBarTitleDisplayMode(.inline)
    }

    // MARK: - What is shown

    /// The cookies by site: the sites with the most first. A site that
    /// matches the search shows all its cookies; another, those that match.
    private var sites: [Site] {
        let wanted = query.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        var bySite: [String: [HTTPCookie]] = [:]
        for cookie in cookies {
            bySite[CookieSites.siteKey(cookie.domain), default: []].append(cookie)
        }
        let found = bySite.compactMap { name, list -> Site? in
            let shown = wanted.isEmpty || name.contains(wanted)
                ? list
                : list.filter { $0.name.lowercased().contains(wanted) || $0.domain.lowercased().contains(wanted) }
            guard !shown.isEmpty else { return nil }
            let sorted = shown.sorted { ($0.name, $0.domain) < ($1.name, $1.domain) }
            return Site(name: name, items: sorted.map { Item(cookie: $0) })
        }
        return found.sorted { $0.items.count != $1.items.count ? $0.items.count > $1.items.count : $0.name < $1.name }
    }

    @ViewBuilder
    private var summary: some View {
        if isLoading {
            Text("Reading the cookies…")
        } else if cookies.isEmpty {
            Text("No cookies in this profile yet: tap Collect above, or browse a little.")
        } else {
            let siteCount = Set(cookies.map { CookieSites.siteKey($0.domain) }).count
            Text("\(cookies.count) cookies from \(siteCount) sites. Tap a site to see its cookies, and a value to copy it.")
        }
    }

    private func isOpen(_ site: String) -> Binding<Bool> {
        Binding(
            get: { opened.contains(site) || !query.isEmpty },
            set: { isOpen in
                if isOpen {
                    opened.insert(site)
                } else {
                    opened.remove(site)
                }
            }
        )
    }

    private var isDeleting: Binding<Bool> {
        Binding(get: { deleting != nil }, set: { if !$0 { deleting = nil } })
    }

    private var deleteTitle: LocalizedStringKey {
        let site = deleting ?? ""
        return "Delete the cookies of \(site)?"
    }

    // MARK: - Actions

    private func load() async {
        let profile = profile
        let list = await CookieCollector.store(for: profile).httpCookieStore.allCookies()
        guard profile.id == self.profile.id else { return }
        cookies = list
        isLoading = false
    }

    private func copy(_ item: Item) {
        UIPasteboard.general.string = item.cookie.value
        copiedID = item.id
        Task {
            try? await Task.sleep(nanoseconds: 900_000_000)
            if copiedID == item.id {
                copiedID = nil
            }
        }
    }

    /// Takes away every cookie of `site` in the profile.
    private func delete(site: String) async {
        let store = CookieCollector.store(for: profile).httpCookieStore
        for cookie in cookies where CookieSites.siteKey(cookie.domain) == site {
            await store.deleteCookie(cookie)
        }
        await load()
    }

    /// Every cookie of the profile as a file, to save or share.
    private func save(_ format: Format) {
        let name = profile.name.replacingOccurrences(of: #"[^\w.-]+"#, with: "-", options: .regularExpression)
        let fileName = "cookies-\(name)." + (format == .json ? "json" : "txt")
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(fileName)
        let text = format == .json ? CookieFile.json(cookies) : CookieFile.netscape(cookies)
        guard (try? text.write(to: url, atomically: true, encoding: .utf8)) != nil else { return }
        Presenter.present(UIActivityViewController(activityItems: [url], applicationActivities: nil))
    }
}

/// One cookie: its name, its value (a tap copies it), where it goes, when it
/// ends and its flags.
private struct CookieRow: View {
    let item: ProfileCookiesView.Item
    let isCopied: Bool
    let copy: () -> Void

    var body: some View {
        let cookie = item.cookie
        VStack(alignment: .leading, spacing: 4) {
            Text(verbatim: cookie.name)
                .font(.subheadline.weight(.semibold))
            Button(action: copy) {
                if isCopied {
                    Text("Copied")
                        .foregroundColor(.green)
                } else {
                    Text(verbatim: cookie.value)
                        .foregroundColor(.primary)
                        .multilineTextAlignment(.leading)
                }
            }
            .buttonStyle(.borderless)
            .font(.footnote.monospaced())
            .lineLimit(2)
            Text(verbatim: cookie.domain + cookie.path)
                .font(.caption)
                .foregroundColor(.secondary)
            HStack(spacing: 6) {
                if cookie.isSessionOnly {
                    Text("Until Noor closes")
                } else if let date = cookie.expiresDate {
                    Text(date, style: .date)
                }
                if cookie.isSecure {
                    Text(verbatim: "Secure")
                }
                if cookie.isHTTPOnly {
                    Text(verbatim: "HttpOnly")
                }
                if let policy = cookie.sameSitePolicy {
                    Text(verbatim: "SameSite=" + policy.rawValue.capitalized)
                }
            }
            .font(.caption2)
            .foregroundColor(.secondary)
        }
        .padding(.vertical, 2)
    }
}

/// A profile's cookies as a file.
enum CookieFile {
    /// As a cookies.txt file: domain, whether its subdomains get it, path,
    /// secure, expiry (0 for a cookie kept only while the app runs), name,
    /// value; an HttpOnly one's domain starts with "#HttpOnly_", as curl
    /// writes it.
    static func netscape(_ cookies: [HTTPCookie]) -> String {
        var lines = [
            "# Netscape HTTP Cookie File",
            "# https://curl.se/docs/http-cookies.html",
            "# Written by Noor. Every cookie of one profile.",
            "",
        ]
        let clean = { (text: String) -> String in
            text.replacingOccurrences(of: "\t", with: " ")
                .replacingOccurrences(of: "\r", with: " ")
                .replacingOccurrences(of: "\n", with: " ")
        }
        for cookie in cookies {
            let expires = cookie.isSessionOnly ? 0 : Int(cookie.expiresDate?.timeIntervalSince1970 ?? 0)
            lines.append([
                (cookie.isHTTPOnly ? "#HttpOnly_" : "") + clean(cookie.domain),
                cookie.domain.hasPrefix(".") ? "TRUE" : "FALSE",
                clean(cookie.path.isEmpty ? "/" : cookie.path),
                cookie.isSecure ? "TRUE" : "FALSE",
                String(expires),
                clean(cookie.name),
                clean(cookie.value),
            ].joined(separator: "\t"))
        }
        return lines.joined(separator: "\n") + "\n"
    }

    /// As JSON, each cookie with what Noor for Windows writes of it.
    static func json(_ cookies: [HTTPCookie]) -> String {
        let formatter = ISO8601DateFormatter()
        let list: [[String: Any]] = cookies.map { cookie in
            var item: [String: Any] = [
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path.isEmpty ? "/" : cookie.path,
                "secure": cookie.isSecure,
                "httpOnly": cookie.isHTTPOnly,
                "hostOnly": !cookie.domain.hasPrefix("."),
                "sameSite": cookie.sameSitePolicy?.rawValue ?? "unspecified",
                "session": cookie.isSessionOnly,
            ]
            if !cookie.isSessionOnly, let date = cookie.expiresDate {
                item["expires"] = formatter.string(from: date)
            } else {
                item["expires"] = NSNull()
            }
            return item
        }
        guard let data = try? JSONSerialization.data(withJSONObject: list, options: [.prettyPrinted, .sortedKeys]),
              let text = String(data: data, encoding: .utf8)
        else { return "[]\n" }
        return text + "\n"
    }
}
