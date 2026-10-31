import SwiftUI

/// The proxies: on or off, one for each profile or one for every profile,
/// the one this profile goes through, finding free ones that work and
/// adding one's own.
struct ProxyView: View {
    @ObservedObject var browser: BrowserModel
    @ObservedObject private var manager = ProxyManager.shared
    @ObservedObject private var progress = ProxyManager.shared.progress
    @State private var isAdding = false
    @State private var isConfirmingDeleteFree = false

    var body: some View {
        List {
            if ProxyManager.isAvailable {
                switches
                current
                finding
                if !manager.proxies.isEmpty {
                    list
                }
            } else {
                Section {
                    Text("Proxies need iOS 17 or later.")
                        .foregroundColor(.secondary)
                }
            }
        }
        .navigationTitle("Proxy")
        .navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $isAdding) {
            AddProxiesView()
        }
        .confirmationDialog("Delete Free Proxies?", isPresented: $isConfirmingDeleteFree, titleVisibility: .visible) {
            Button("Delete Free Proxies", role: .destructive) {
                manager.removeFree()
            }
        }
    }

    private var switches: some View {
        Section {
            Toggle(isOn: Binding(get: { manager.isEnabled }, set: { manager.setEnabled($0) })) {
                SettingsLabel("Use a Proxy", systemName: "network", color: .blue)
            }
            Toggle(isOn: Binding(get: { manager.perProfile }, set: { manager.setPerProfile($0) })) {
                SettingsLabel("A Different Proxy for Each Profile", systemName: "person.2.fill", color: .mint)
            }
        } footer: {
            Text("Pages, and the cookies collected in the background, go through the proxy: sites see its address and country, not yours. With a different proxy for each profile, two profiles never share an address. A proxy that stops working stops the pages (they never go around it): change the proxy. WebRTC, which could tell sites your own address, finds none while a proxy is on. Pages already open may take a minute to switch to a new proxy; to switch them at once, close Noor and open it again.")
        }
    }

    private var current: some View {
        Section {
            switch manager.route(for: browser.profile.id) {
            case .direct:
                Text("Off: sites see this phone’s own address.")
                    .foregroundColor(.secondary)
            case .noProxy:
                Text("No proxy yet: pages don’t open. Find free proxies or add yours.")
                    .foregroundColor(.red)
            case .proxy(let proxy):
                ProxyRow(proxy: proxy, isCurrent: false, isChecking: progress.checking.contains(proxy.id))
                if manager.proxies.count > 1 {
                    Button {
                        manager.changeProxy(for: browser.profile.id)
                    } label: {
                        Label("Change Proxy", systemImage: "arrow.triangle.2.circlepath")
                    }
                }
            }
        } header: {
            Text("Proxy of “\(browser.profile.name)”")
        }
    }

    private var finding: some View {
        Section {
            if let search = progress.search, search.isRunning {
                VStack(alignment: .leading, spacing: 8) {
                    ProgressView(value: Double(search.found), total: Double(ProxyManager.freeCount))
                    if search.phase == .starting {
                        Text("Getting the lists of free proxies…")
                    } else {
                        Text("Checked \(search.checked) of \(search.total): \(search.found) work")
                    }
                }
                .font(.footnote)
                .foregroundColor(.secondary)
                .padding(.vertical, 4)
                Button(role: .destructive) {
                    manager.stopSearch()
                } label: {
                    Label("Stop", systemImage: "stop.circle")
                }
            } else {
                Button {
                    manager.findFree()
                } label: {
                    Label("Find \(ProxyManager.freeCount) Free Proxies", systemImage: "magnifyingglass")
                }
                if progress.search?.phase == .failed {
                    Text("The lists of free proxies couldn’t be reached. Check the connection and try again.")
                        .font(.footnote)
                        .foregroundColor(.red)
                }
            }
            Button {
                isAdding = true
            } label: {
                Label("Add My Proxies", systemImage: "plus")
            }
            Button {
                manager.check()
            } label: {
                Label("Check All Proxies", systemImage: "checkmark.circle")
            }
            .disabled(manager.proxies.isEmpty || !progress.checking.isEmpty)
        } footer: {
            Text("Free proxies come from public lists and are checked from this phone: only those that open pages are kept, each with an address of its own, the fastest first. Strangers run them: they see which sites you open (not what you send to https:// sites), are often slow, stop working after a while (find new ones then), and Instagram, X or Google often block them. For accounts, use proxies of your own.")
        }
    }

    private var list: some View {
        Section {
            ForEach(manager.proxies) { proxy in
                Button {
                    manager.use(proxy, for: browser.profile.id)
                } label: {
                    ProxyRow(proxy: proxy, isCurrent: isCurrent(proxy), isChecking: progress.checking.contains(proxy.id))
                }
            }
            .onDelete { offsets in
                let ids = offsets.map { manager.proxies[$0].id }
                manager.remove(Set(ids))
            }
            if manager.proxies.contains(where: \.isFree) {
                Button(role: .destructive) {
                    isConfirmingDeleteFree = true
                } label: {
                    Label("Delete Free Proxies", systemImage: "trash")
                }
            }
        } header: {
            Text("Proxies: \(manager.proxies.count)")
        } footer: {
            Text("Tap a proxy to go through it in this profile. Swipe one to delete it.")
        }
    }

    private func isCurrent(_ proxy: ProxyServer) -> Bool {
        if case .proxy(let current) = manager.route(for: browser.profile.id) {
            return current.id == proxy.id
        }
        return false
    }
}

/// A proxy: its country's flag and name, its kind and address, and how fast
/// it was, or that it doesn't work.
struct ProxyRow: View {
    let proxy: ProxyServer
    let isCurrent: Bool
    let isChecking: Bool

    var body: some View {
        HStack(spacing: 12) {
            Text(verbatim: proxy.flag)
                .font(.title2)
            VStack(alignment: .leading, spacing: 2) {
                Text(verbatim: proxy.countryName ?? proxy.address)
                    .foregroundColor(.primary)
                    .lineLimit(1)
                details
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(1)
            }
            Spacer(minLength: 8)
            if isChecking {
                ProgressView()
            } else if proxy.works == false {
                Text("Not working")
                    .font(.caption)
                    .foregroundColor(.red)
            } else if let latency = proxy.latency {
                Text(verbatim: "\(latency) ms")
                    .font(.caption.monospacedDigit())
                    .foregroundColor(latency < 1500 ? .green : .orange)
            }
            if isCurrent {
                Image(systemName: "checkmark")
                    .font(.body.weight(.semibold))
                    .foregroundColor(.accentColor)
            }
        }
    }

    /// "HTTP · 1.2.3.4:8080", with the user if there is one, and "Free".
    private var details: Text {
        var parts = [proxy.kind.title, proxy.address]
        if let username = proxy.username, !username.isEmpty {
            parts.append(username)
        }
        let text = Text(verbatim: parts.joined(separator: " · "))
        return proxy.isFree ? text + Text(verbatim: " · ") + Text("Free") : text
    }
}

/// Adding one's own proxies, as a provider gives them: one per line.
struct AddProxiesView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var text = ""
    @State private var kind: ProxyServer.Kind = .http

    var body: some View {
        NavigationView {
            Form {
                Section {
                    Picker("Type", selection: $kind) {
                        ForEach(ProxyServer.Kind.allCases, id: \.self) { kind in
                            Text(verbatim: kind.title).tag(kind)
                        }
                    }
                    .pickerStyle(.segmented)
                    TextEditor(text: $text)
                        .font(.system(.footnote, design: .monospaced))
                        .frame(minHeight: 200)
                        .textInputAutocapitalization(.never)
                        .disableAutocorrection(true)
                } footer: {
                    Text("One proxy per line, as your provider gives them: host:port, host:port:user:password or user:password@host:port. “socks5://” or “http://” in front of a line sets its type.")
                }
            }
            .navigationTitle("Add My Proxies")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") {
                        ProxyManager.shared.add(text, kind: kind)
                        dismiss()
                    }
                    .disabled(text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
        }
        .navigationViewStyle(.stack)
    }
}
