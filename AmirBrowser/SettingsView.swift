import SwiftUI
import WebKit

struct SettingsView: View {
    @Binding var searchEngine: SearchEngine
    @AppStorage(CanvasProtection.enabledKey) private var canvasProtection = true

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
                    Toggle("Canvas Protection", isOn: $canvasProtection)
                } header: {
                    Text("Privacy")
                } footer: {
                    Text("Adds invisible noise to what websites read from canvases, so they can't use it to recognize your device. “New Canvas Fingerprint” in the ⋯ menu changes it.")
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
