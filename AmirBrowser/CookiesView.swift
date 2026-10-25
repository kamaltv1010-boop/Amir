import SwiftUI
import UniformTypeIdentifiers

/// Export the current site's cookies as a header string, and import cookies
/// back from pasted text or a file.
struct CookiesView: View {
    @ObservedObject var tab: BrowserTab

    @Environment(\.dismiss) private var dismiss
    @State private var exported = ""
    @State private var importText = ""
    @State private var isImporting = false
    @State private var message: Message?

    private struct Message: Identifiable {
        let text: LocalizedStringKey
        var id: String { "\(text)" }
    }

    private var site: String {
        CookieManager.host(of: tab.webView.url) ?? ""
    }

    var body: some View {
        NavigationView {
            Form {
                Section {
                    Text(verbatim: site)
                        .font(.headline)
                } footer: {
                    Text("Cookies are the small files that keep you signed in to a site. These are the cookies for this site only.")
                }

                Section {
                    if exported.isEmpty {
                        Text("No cookies for this site.")
                            .foregroundColor(.secondary)
                    } else {
                        Text(verbatim: exported)
                            .font(.footnote.monospaced())
                            .textSelection(.enabled)
                            .lineLimit(6)
                        Button {
                            UIPasteboard.general.string = exported
                            show("Copied")
                        } label: {
                            Label("Copy", systemImage: "doc.on.doc")
                        }
                        Button {
                            share(exported)
                        } label: {
                            Label("Save or Share…", systemImage: "square.and.arrow.up")
                        }
                    }
                } header: {
                    Text("Export")
                } footer: {
                    Text("The cookies in header string format: name=value; name2=value2.")
                }

                Section {
                    TextEditor(text: $importText)
                        .font(.footnote.monospaced())
                        .frame(minHeight: 90)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                    Button {
                        isImporting = true
                    } label: {
                        Label("Choose a File…", systemImage: "folder")
                    }
                    Button {
                        applyImport()
                    } label: {
                        Label("Import Cookies", systemImage: "square.and.arrow.down")
                    }
                    .disabled(importText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                } header: {
                    Text("Import")
                } footer: {
                    Text("Paste a header string, or choose a file, then import. The page reloads with the new cookies.")
                }
            }
            .navigationTitle("Cookies")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
            .task {
                exported = await CookieManager.exportHeaderString(from: tab.webView)
            }
            .fileImporter(isPresented: $isImporting, allowedContentTypes: [.text, .plainText, .data]) { result in
                if case .success(let url) = result {
                    readFile(url)
                }
            }
            .alert(item: $message) { message in
                Alert(title: Text(message.text))
            }
        }
        .navigationViewStyle(.stack)
    }

    private func applyImport() {
        let text = importText
        Task {
            let count = await CookieManager.importHeaderString(text, into: tab.webView)
            if let count {
                tab.reload()
                show("Imported \(count) cookies")
                importText = ""
                exported = await CookieManager.exportHeaderString(from: tab.webView)
            } else {
                show("No cookies found in the text.")
            }
        }
    }

    private func readFile(_ url: URL) {
        let isScoped = url.startAccessingSecurityScopedResource()
        defer {
            if isScoped {
                url.stopAccessingSecurityScopedResource()
            }
        }
        if let data = try? Data(contentsOf: url), let text = String(data: data, encoding: .utf8) {
            importText = text
        } else {
            show("Couldn't read this file.")
        }
    }

    private func share(_ text: String) {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("cookies-\(site).txt")
        guard (try? text.write(to: url, atomically: true, encoding: .utf8)) != nil else { return }
        let activity = UIActivityViewController(activityItems: [url], applicationActivities: nil)
        Presenter.present(activity)
    }

    private func show(_ text: LocalizedStringKey) {
        message = Message(text: text)
    }
}
