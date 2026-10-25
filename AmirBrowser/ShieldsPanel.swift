import SwiftUI

/// Brave-style shields for the current site: up or down, what was blocked,
/// and the switches that apply to all sites.
struct ShieldsPanel: View {
    @ObservedObject var browser: BrowserModel
    @ObservedObject var tab: BrowserTab

    @AppStorage(TrackerBlocker.enabledKey) private var blockTrackers = true
    @AppStorage(HTTPSUpgrade.enabledKey) private var upgradeConnections = true
    @AppStorage(LinkCleaner.enabledKey) private var cleanLinks = true
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationView {
            List {
                Section {
                    header
                }

                if tab.shieldsUp {
                    Section("This Page") {
                        HStack {
                            SettingsLabel("Trackers blocked", systemName: "hand.raised.slash.fill", color: Theme.shields)
                            Spacer()
                            Text(verbatim: "\(tab.trackersBlocked)")
                                .font(.body.monospacedDigit().weight(.semibold))
                                .foregroundColor(.secondary)
                        }
                        HStack {
                            SettingsLabel("Connection", systemName: isSecure ? "lock.fill" : "lock.open.fill", color: isSecure ? .green : .red)
                            Spacer()
                            Text(isSecure ? "Encrypted (HTTPS)" : "Not encrypted")
                                .foregroundColor(.secondary)
                        }
                        HStack {
                            SettingsLabel("Fingerprint protection", systemName: "hand.raised.fill", color: .blue)
                            Spacer()
                            Text(verbatim: "\(browser.enabledProtections.count)/\(FingerprintProtection.Kind.allCases.count)")
                                .font(.body.monospacedDigit())
                                .foregroundColor(.secondary)
                        }
                    }
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
                } header: {
                    Text("All Sites")
                } footer: {
                    Text("Change fingerprint protection and see the sites with shields down in Settings.")
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Shields")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
        .navigationViewStyle(.stack)
    }

    private var isSecure: Bool {
        tab.webView.url?.scheme == "https"
    }

    private var header: some View {
        VStack(spacing: 10) {
            Image(systemName: tab.shieldsUp ? "shield.fill" : "shield.slash.fill")
                .font(.system(size: 34, weight: .semibold))
                .foregroundColor(.white)
                .frame(width: 72, height: 72)
                .background(tab.shieldsUp ? Theme.shields : Color.gray, in: Circle())
            Text(verbatim: Shields.site(of: tab.webView.url) ?? "")
                .font(.title3.weight(.bold))
                .lineLimit(1)
            Toggle(isOn: Binding(get: { tab.shieldsUp }, set: { browser.setShieldsUp($0) })) {
                Text(tab.shieldsUp ? "Shields are UP" : "Shields are DOWN")
                    .font(.headline)
                    .foregroundColor(tab.shieldsUp ? Theme.shields : .secondary)
            }
            .tint(Theme.shields)
            .disabled(Shields.site(of: tab.webView.url) == nil)
            Text(tab.shieldsUp
                ? "Trackers, fingerprinting and insecure connections are blocked on this site."
                : "Protections are off for this site. Turn shields back on if the site works without them.")
                .font(.footnote)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
    }
}
