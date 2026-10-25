import SwiftUI
import UniformTypeIdentifiers

/// Installing, switching on and off, and removing web extensions.
struct ExtensionsView: View {
    /// Called after opening a page in a tab (the store, an options page), so
    /// the screen showing this list can close.
    var onOpenPage: () -> Void = {}

    @ObservedObject private var manager = ExtensionManager.shared
    @State private var isImporting = false

    var body: some View {
        List {
            if ExtensionManager.isSupported {
                Section {
                    Button {
                        manager.openStore()
                        onOpenPage()
                    } label: {
                        HStack(spacing: 12) {
                            SettingsIcon(systemName: "bag.fill", color: .blue)
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Chrome Web Store")
                                    .foregroundColor(.primary)
                                Text("Open an extension's page, then tap “Add to Noor”.")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                    Button {
                        isImporting = true
                    } label: {
                        HStack(spacing: 12) {
                            SettingsIcon(systemName: "folder.fill", color: .orange)
                            Text("Add From Files…")
                                .foregroundColor(.primary)
                        }
                    }
                } header: {
                    Text("Add Extensions")
                } footer: {
                    Text("Install Chrome or Safari web extensions from the Chrome Web Store, or from a .zip or .crx file, or a folder with a manifest.json file, saved in Files. Extensions that block ads or change how pages look usually work; some Chrome-only features don't.")
                }

                Section {
                    Toggle(isOn: $manager.allowsPrivateTabs) {
                        SettingsLabel("Allow in Private Tabs", systemName: "eyeglasses", color: Theme.privateTint)
                    }
                } footer: {
                    Text("Extensions can also see and change the pages you open in private tabs.")
                }

                if !manager.extensions.isEmpty {
                    Section("Installed") {
                        ForEach(manager.extensions) { info in
                            ExtensionRow(info: info, manager: manager, onOpenPage: onOpenPage)
                        }
                        .onDelete { offsets in
                            for id in offsets.map({ manager.extensions[$0].id }) {
                                manager.remove(id)
                            }
                        }
                    }
                }
            } else {
                Section {
                    VStack(alignment: .leading, spacing: 8) {
                        Label("Extensions need iOS 18.4 or later", systemImage: "puzzlepiece.extension")
                            .font(.headline)
                        Text("Update your iPhone in Settings > General > Software Update to use Chrome and Safari web extensions.")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                    .padding(.vertical, 6)
                }
            }
        }
        .listStyle(.insetGrouped)
        .navigationTitle("Extensions")
        .navigationBarTitleDisplayMode(.inline)
        .fileImporter(isPresented: $isImporting, allowedContentTypes: Self.fileTypes) { result in
            if case .success(let url) = result {
                manager.install(from: url)
            }
        }
    }

    private static let fileTypes: [UTType] = [.zip, .folder] + [UTType(filenameExtension: "crx")].compactMap { $0 }
}

private struct ExtensionRow: View {
    let info: ExtensionInfo
    @ObservedObject var manager: ExtensionManager
    let onOpenPage: () -> Void

    @State private var isConfirmingRemoval = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 12) {
                Group {
                    if let icon = info.icon {
                        Image(uiImage: icon)
                            .resizable()
                            .scaledToFit()
                    } else {
                        Image(systemName: "puzzlepiece.extension.fill")
                            .font(.system(size: 22))
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                            .background(Color.purple)
                    }
                }
                .frame(width: 40, height: 40)
                .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))

                VStack(alignment: .leading, spacing: 2) {
                    Text(verbatim: info.name)
                        .font(.headline)
                        .lineLimit(1)
                    if !info.version.isEmpty {
                        Text(verbatim: info.version)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }

                Spacer(minLength: 0)

                Toggle("", isOn: Binding(get: { info.isEnabled }, set: { manager.setEnabled($0, id: info.id) }))
                    .labelsHidden()
            }

            if !info.summary.isEmpty {
                Text(verbatim: info.summary)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .lineLimit(3)
            }
            if let error = info.error {
                Label {
                    Text(verbatim: error)
                } icon: {
                    Image(systemName: "exclamationmark.triangle.fill")
                }
                .font(.caption)
                .foregroundColor(.orange)
            }
            // Borderless, so each button reacts on its own in the list row.
            HStack(spacing: 20) {
                if info.hasOptionsPage {
                    Button {
                        manager.openOptions(info.id)
                        onOpenPage()
                    } label: {
                        Label("Options", systemImage: "gearshape")
                    }
                }
                Spacer(minLength: 0)
                Button(role: .destructive) {
                    isConfirmingRemoval = true
                } label: {
                    Label("Remove", systemImage: "trash")
                        .foregroundColor(.red)
                }
            }
            .font(.subheadline)
            .buttonStyle(.borderless)
        }
        .padding(.vertical, 4)
        .contextMenu {
            Button(role: .destructive) {
                isConfirmingRemoval = true
            } label: {
                Label("Remove Extension", systemImage: "trash")
            }
        }
        .confirmationDialog(Text("Remove “\(info.name)”?"), isPresented: $isConfirmingRemoval, titleVisibility: .visible) {
            Button("Remove Extension", role: .destructive) {
                withAnimation {
                    manager.remove(info.id)
                }
            }
        } message: {
            Text("The extension and its data are deleted from Noor.")
        }
    }
}
