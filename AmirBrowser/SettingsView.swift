import SwiftUI
import WebKit

struct SettingsView: View {
    @Binding var searchEngine: SearchEngine

    @AppStorage(BrowserModel.clearOnQuitKey) private var clearOnQuit = false
    @AppStorage(TrackerBlocker.enabledKey) private var blockTrackers = true
    @AppStorage(LinkCleaner.enabledKey) private var cleanLinks = true
    @AppStorage(PrivacyScreen.enabledKey) private var hideInSwitcher = true
    @Environment(\.dismiss) private var dismiss
    @State private var isConfirmingClear = false
    @State private var didClear = false

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
                        Label("Block Trackers", systemImage: "hand.raised.slash")
                    }
                    Toggle(isOn: $cleanLinks) {
                        Label("Remove Tracking From Links", systemImage: "link")
                    }
                    Toggle(isOn: $hideInSwitcher) {
                        Label("Hide in App Switcher", systemImage: "eye.slash")
                    }
                } header: {
                    Text("Tracking Protection")
                } footer: {
                    Text("Blocks Meta Pixel, Facebook and Instagram on other sites, Google Analytics, TikTok and other trackers, so they can't follow you from site to site. Links lose tracking codes such as fbclid, igshid and utm_. The app switcher shows a blank screen instead of the page.")
                }

                Section {
                    ForEach(FingerprintProtection.Kind.allCases) { kind in
                        ProtectionToggle(kind: kind)
                    }
                } header: {
                    Text("Fingerprint Protection")
                } footer: {
                    Text("Websites can recognize your device from these details. When a protection is on, they get changed or common values. Change them any time from the ⋯ menu under Fingerprint.")
                }

                Section {
                    Toggle("Clear Everything on Quit", isOn: $clearOnQuit)
                } header: {
                    Text("When Closing the App")
                } footer: {
                    Text("Cookies and website data stay only in memory, never on the phone, and are gone when you close the app (swipe it away). Every launch starts fresh: open pages are closed and every fingerprint changes. Bookmarks and pinned links are kept. Takes effect from the next launch; “New Session” in the ⋯ menu starts fresh right away.")
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
                            Text(verbatim: "\(agent.name) · iOS \(agent.iOS)")
                                .foregroundColor(.secondary)
                        }
                        Text(verbatim: agent.userAgent)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }

                Section {
                    Button("Clear Browsing Data", role: .destructive) {
                        isConfirmingClear = true
                    }
                } footer: {
                    Text("Removes cookies, cache and saved website data. Bookmarks are kept.")
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
            .confirmationDialog("Clear Browsing Data?", isPresented: $isConfirmingClear, titleVisibility: .visible) {
                Button("Clear", role: .destructive, action: clearBrowsingData)
            }
            .alert("Browsing data cleared", isPresented: $didClear) {
                Button("OK", role: .cancel) {}
            }
        }
        .navigationViewStyle(.stack)
    }

    private var appVersion: String {
        let info = Bundle.main.infoDictionary
        let version = info?["CFBundleShortVersionString"] as? String ?? "1.0"
        let build = info?["CFBundleVersion"] as? String ?? "1"
        return "\(version) (\(build))"
    }

    private func clearBrowsingData() {
        WKWebsiteDataStore.default().removeData(
            ofTypes: WKWebsiteDataStore.allWebsiteDataTypes(),
            modifiedSince: .distantPast
        ) {
            didClear = true
        }
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
