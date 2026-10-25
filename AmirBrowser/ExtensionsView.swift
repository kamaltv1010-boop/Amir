import SwiftUI
import UniformTypeIdentifiers

/// Installing, switching on and off, and removing web extensions.
struct ExtensionsView: View {
    @ObservedObject private var manager = ExtensionManager.shared
    @State private var isImporting = false

    var body: some View {
        List {
            if ExtensionManager.isSupported {
                Section {
                    Button {
                        isImporting = true
                    } label: {
                        Label("Add Extension…", systemImage: "plus.circle.fill")
                    }
                } footer: {
                    Text("Install Chrome or Safari web extensions from a .zip or .crx file, or a folder with a manifest.json file, saved in Files. Extensions that block ads or change how pages look usually work; some Chrome-only features don't. Extensions run in normal tabs, not in private ones.")
                }

                if !manager.extensions.isEmpty {
                    Section("Installed") {
                        ForEach(manager.extensions) { info in
                            ExtensionRow(info: info, manager: manager)
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
        .alert(
            Text(verbatim: manager.pendingInstall.map { String(localized: "Add “\($0.name)”?") } ?? ""),
            isPresented: Binding(get: { manager.pendingInstall != nil }, set: { _ in }),
            presenting: manager.pendingInstall
        ) { _ in
            Button("Add Extension") { manager.confirmInstall() }
            Button("Cancel", role: .cancel) { manager.cancelInstall() }
        } message: { pending in
            Text(verbatim: description(of: pending))
        }
        .alert(
            "Can't add this extension",
            isPresented: Binding(get: { manager.errorMessage != nil }, set: { if !$0 { manager.errorMessage = nil } })
        ) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(verbatim: manager.errorMessage ?? "")
        }
    }

    private static let fileTypes: [UTType] = [.zip, .folder] + [UTType(filenameExtension: "crx")].compactMap { $0 }

    private func description(of pending: ExtensionManager.PendingInstall) -> String {
        var lines: [String] = []
        if let sites = pending.sites {
            if !sites.isEmpty {
                lines.append(String(localized: "It can read and change these sites:") + "\n" + sites.joined(separator: ", "))
            }
        } else {
            lines.append(String(localized: "It can read and change every website you visit."))
        }
        if !pending.permissions.isEmpty {
            lines.append(String(localized: "It can also:") + "\n" + pending.permissions.map { "• " + $0 }.joined(separator: "\n"))
        }
        return lines.joined(separator: "\n\n")
    }
}

private struct ExtensionRow: View {
    let info: ExtensionInfo
    @ObservedObject var manager: ExtensionManager

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
            if info.hasOptionsPage {
                Button {
                    manager.openOptions(info.id)
                } label: {
                    Label("Options", systemImage: "gearshape")
                        .font(.subheadline)
                }
                .buttonStyle(.borderless)
            }
        }
        .padding(.vertical, 4)
    }
}
