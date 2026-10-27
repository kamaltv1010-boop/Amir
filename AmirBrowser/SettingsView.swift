import SwiftUI
import WebKit

struct SettingsView: View {
    @ObservedObject var browser: BrowserModel
    @Binding var searchEngine: SearchEngine

    @ObservedObject private var extensions = ExtensionManager.shared
    @AppStorage(BrowserModel.clearOnQuitKey) private var clearOnQuit = false
    @AppStorage(TrackerBlocker.enabledKey) private var blockTrackers = true
    @AppStorage(HTTPSUpgrade.enabledKey) private var upgradeConnections = true
    @AppStorage(LinkCleaner.enabledKey) private var cleanLinks = true
    @AppStorage(PrivacyScreen.enabledKey) private var hideInSwitcher = true
    @AppStorage(NightMode.enabledKey) private var nightMode = false
    @Environment(\.dismiss) private var dismiss
    @State private var confirmation: Confirmation?
    @State private var didClear = false

    private enum Confirmation: Identifiable {
        case browsingData, history, stats

        var id: Self { self }
    }

    var body: some View {
        NavigationView {
            Form {
                Section("Search Engine") {
                    Picker("Search Engine", selection: $searchEngine) {
                        ForEach(SearchEngine.allCases) { engine in
                            Text(engine.name).tag(engine)
                        }
                    }
                    .pickerStyle(.inline)
                    .labelsHidden()
                }

                Section {
                    Toggle(isOn: $blockTrackers) {
                        SettingsLabel("Block Trackers", systemName: "hand.raised.slash", color: Theme.shields)
                    }
                    Toggle(isOn: $upgradeConnections) {
                        SettingsLabel("Upgrade Connections to HTTPS", systemName: "lock.shield", color: .green)
                    }
                    Toggle(isOn: $cleanLinks) {
                        SettingsLabel("Remove Tracking From Links", systemName: "link", color: .teal)
                    }
                    Toggle(isOn: $hideInSwitcher) {
                        SettingsLabel("Hide in App Switcher", systemName: "eye.slash", color: .gray)
                    }
                    NavigationLink(destination: FingerprintSettingsView(browser: browser)) {
                        SettingsLabel("Fingerprint Protection", systemName: "hand.raised.fill", color: .blue)
                    }
                    NavigationLink(destination: ShieldsDownSitesView()) {
                        SettingsLabel("Sites With Shields Down", systemName: "shield.slash", color: .red)
                    }
                } header: {
                    Text("Shields & Privacy")
                } footer: {
                    Text("Blocks Meta Pixel, Facebook and Instagram on other sites, Google Analytics, TikTok and other trackers, so they can't follow you from site to site. Pages open over HTTPS when the site supports it. Links lose tracking codes such as fbclid, igshid and utm_. The app switcher shows a blank screen instead of the page.")
                }

                Section {
                    NavigationLink(destination: ProfilesView(browser: browser)) {
                        HStack {
                            SettingsLabel("Profiles", systemName: "person.2.fill", color: .mint)
                            Spacer()
                            Text(verbatim: browser.profile.name)
                                .foregroundColor(.secondary)
                        }
                    }
                } footer: {
                    Text("Each profile has its own cookies, website data, history, tabs and fingerprints, so accounts stay apart. Bookmarks, pinned links, extensions and settings are shared.")
                }

                Section {
                    Toggle(isOn: $nightMode) {
                        SettingsLabel("Night Mode", systemName: "moon.fill", color: .indigo)
                    }
                } header: {
                    Text("Appearance")
                } footer: {
                    Text("Shows websites with dark colors. Pictures and videos keep their colors.")
                }

                Section {
                    NavigationLink(destination: ExtensionsView(onOpenPage: { dismiss() })) {
                        HStack {
                            SettingsLabel("Extensions", systemName: "puzzlepiece.extension.fill", color: .purple)
                            Spacer()
                            if !extensions.extensions.isEmpty {
                                Text(verbatim: "\(extensions.extensions.filter(\.isEnabled).count)")
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                } footer: {
                    Text("Chrome and Safari web extensions, such as ad blockers and Dark Reader.")
                }

                Section {
                    Button(role: .destructive) {
                        confirmation = .history
                    } label: {
                        SettingsLabel("Clear History", systemName: "clock.arrow.circlepath", color: .orange)
                    }
                    Button(role: .destructive) {
                        confirmation = .browsingData
                    } label: {
                        SettingsLabel("Clear Browsing Data", systemName: "trash", color: .red)
                    }
                    Button(role: .destructive) {
                        confirmation = .stats
                    } label: {
                        SettingsLabel("Reset Privacy Stats", systemName: "chart.bar", color: .gray)
                    }
                    Toggle(isOn: $clearOnQuit) {
                        SettingsLabel("Clear Everything on Quit", systemName: "flame.fill", color: .red)
                    }
                } header: {
                    Text("Data")
                } footer: {
                    Text("With Clear Everything on Quit on, cookies, website data and history stay only in memory, never on the phone, and are gone when you close the app (swipe it away). Every launch starts fresh: tabs are closed and every fingerprint changes. Bookmarks and pinned links are kept. Takes effect from the next launch; “New Session” in the ⋯ menu starts fresh right away.")
                }

                Section("About") {
                    HStack {
                        Text("Version")
                        Spacer()
                        Text(appVersion)
                            .foregroundColor(.secondary)
                    }
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
            .confirmationDialog(confirmationTitle, isPresented: isConfirming, titleVisibility: .visible) {
                Button("Clear", role: .destructive, action: confirm)
            }
            .alert("Done", isPresented: $didClear) {
                Button("OK", role: .cancel) {}
            }
        }
        .navigationViewStyle(.stack)
    }

    private var isConfirming: Binding<Bool> {
        Binding(get: { confirmation != nil }, set: { if !$0 { confirmation = nil } })
    }

    private var confirmationTitle: LocalizedStringKey {
        switch confirmation {
        case .history: return "Clear History?"
        case .stats: return "Reset Privacy Stats?"
        default: return "Clear Browsing Data?"
        }
    }

    private func confirm() {
        switch confirmation {
        case .history:
            browser.history.clear()
            didClear = true
        case .stats:
            browser.stats.reset()
            didClear = true
        case .browsingData:
            browser.clearBrowsingData {
                didClear = true
            }
        case nil:
            break
        }
        confirmation = nil
    }

    private var appVersion: String {
        let info = Bundle.main.infoDictionary
        let version = info?["CFBundleShortVersionString"] as? String ?? "1.0"
        let build = info?["CFBundleVersion"] as? String ?? "1"
        return "\(version) (\(build))"
    }
}

/// The profiles: the one in use, a new one, and deleting one.
private struct ProfilesView: View {
    @ObservedObject var browser: BrowserModel
    @State private var deleting: Profile?

    var body: some View {
        List {
            Section {
                ForEach(browser.profiles) { profile in
                    HStack {
                        Button {
                            browser.switchProfile(to: profile)
                        } label: {
                            Label {
                                Text(verbatim: profile.name)
                                    .foregroundColor(.primary)
                            } icon: {
                                Image(systemName: profile.id == browser.profile.id ? "checkmark.circle.fill" : "circle")
                                    .foregroundColor(.accentColor)
                            }
                        }
                        .buttonStyle(.borderless)
                        Spacer()
                        if !profile.isDefault {
                            Button(role: .destructive) {
                                deleting = profile
                            } label: {
                                Image(systemName: "trash")
                            }
                            .buttonStyle(.borderless)
                            .accessibilityLabel(Text("Delete Profile"))
                        }
                    }
                }
            } footer: {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Tap a profile to switch to it. Each one has its own cookies, website data, history, tabs and fingerprints.")
                    if !Profiles.keepsDataOfEveryProfile {
                        Text("On iOS 16 and earlier, only the first profile keeps its website data on the phone; the others keep theirs while the app is open.")
                    }
                }
            }

            Section {
                Button {
                    ProfilePrompts.newProfile(in: browser)
                } label: {
                    Label("New Profile", systemImage: "plus")
                }
                if browser.profiles.count > 1 {
                    Button(role: .destructive) {
                        ProfilePrompts.confirmDeleteAll(in: browser)
                    } label: {
                        Label("Delete All Profiles", systemImage: "trash")
                    }
                }
            } footer: {
                Text("The profiles are also in the ⋯ menu and on the start page, to switch quickly.")
            }
        }
        .navigationTitle("Profiles")
        .navigationBarTitleDisplayMode(.inline)
        .confirmationDialog(deleteTitle, isPresented: isDeleting, titleVisibility: .visible) {
            Button("Delete Profile", role: .destructive) {
                if let profile = deleting {
                    browser.deleteProfile(profile)
                }
                deleting = nil
            }
        } message: {
            Text("This deletes the profile’s cookies, website data, history and tabs. Bookmarks and pinned links are kept.")
        }
    }

    private var isDeleting: Binding<Bool> {
        Binding(get: { deleting != nil }, set: { if !$0 { deleting = nil } })
    }

    private var deleteTitle: LocalizedStringKey {
        let name = deleting?.name ?? ""
        return "Delete “\(name)”?"
    }
}

/// The fingerprint protection switches, iPad mode, and the values pages see.
private struct FingerprintSettingsView: View {
    @ObservedObject var browser: BrowserModel

    var body: some View {
        Form {
            Section {
                ForEach(FingerprintProtection.Kind.allCases) { kind in
                    ProtectionToggle(kind: kind)
                }
            } footer: {
                Text("Websites can recognize your device from these details. When a protection is on, they get changed or common values. Change them any time from the ⋯ menu under Fingerprint.")
            }

            Section {
                Toggle(isOn: Binding(get: { browser.isIPadMode }, set: { browser.setIPadMode($0) })) {
                    SettingsLabel("iPad Mode", systemName: "ipad", color: .blue)
                }
            } footer: {
                Text("Websites see one of 13 real iPads instead of an iPhone, and the page is shown as big as the iPad’s screen, scaled down to fit, like on a tablet.")
            }

            Section("Current Values") {
                let screen = FingerprintProtection.screenDevice
                let agent = FingerprintProtection.userAgentDevice
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("Screen Size")
                        Spacer()
                        Text(verbatim: "\(screen.width) × \(screen.height)")
                            .foregroundColor(.secondary)
                    }
                    Text(verbatim: screen.name)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("User Agent")
                        Spacer()
                        Text(verbatim: "\(agent.name) · \(agent.system)")
                            .foregroundColor(.secondary)
                    }
                    Text(verbatim: agent.userAgent)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .navigationTitle("Fingerprint Protection")
        .navigationBarTitleDisplayMode(.inline)
    }
}

/// One fingerprint protection's on/off switch, stored in UserDefaults.
private struct ProtectionToggle: View {
    let kind: FingerprintProtection.Kind
    @AppStorage private var isOn: Bool

    init(kind: FingerprintProtection.Kind) {
        self.kind = kind
        _isOn = AppStorage(wrappedValue: true, kind.enabledKey)
    }

    var body: some View {
        Toggle(isOn: $isOn) {
            Label(kind.title, systemImage: kind.symbol)
        }
    }
}

/// The sites shields are down for. Removing one turns them back on there.
private struct ShieldsDownSitesView: View {
    @State private var sites = Shields.downSites

    var body: some View {
        List {
            if sites.isEmpty {
                Text("Shields are up on every site.")
                    .foregroundColor(.secondary)
            } else {
                Section {
                    ForEach(sites, id: \.self) { site in
                        Label {
                            Text(verbatim: site)
                        } icon: {
                            Image(systemName: "shield.slash")
                                .foregroundColor(.secondary)
                        }
                    }
                    .onDelete { offsets in
                        for site in offsets.map({ sites[$0] }) {
                            Shields.setUp(true, for: site)
                        }
                        sites = Shields.downSites
                    }
                } footer: {
                    Text("Swipe a site to turn shields back on there.")
                }
            }
        }
        .navigationTitle("Sites With Shields Down")
        .navigationBarTitleDisplayMode(.inline)
    }
}
