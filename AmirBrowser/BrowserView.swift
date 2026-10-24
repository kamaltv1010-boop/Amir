import SwiftUI

struct BrowserView: View {
    @StateObject private var browser = BrowserModel()
    @StateObject private var bookmarks = BookmarkStore()
    @AppStorage(SearchEngine.storageKey) private var searchEngine = SearchEngine.google

    @State private var addressText = ""
    @FocusState private var isEditingAddress: Bool
    @State private var sheet: Sheet?

    private enum Sheet: String, Identifiable {
        case bookmarks
        case settings

        var id: String { rawValue }
    }

    var body: some View {
        VStack(spacing: 0) {
            addressBar
            ZStack {
                WebView(webView: browser.webView)
                if let message = browser.loadError {
                    ErrorView(message: message) { browser.reload() }
                }
            }
            toolbar
        }
        // The keyboard covers the toolbar instead of pushing the page up;
        // WKWebView scrolls its own focused fields into view.
        .ignoresSafeArea(.keyboard, edges: .bottom)
        .onAppear {
            browser.loadInitialPage(home: searchEngine.homeURL)
        }
        .onReceive(browser.$displayedURL) { url in
            if !isEditingAddress {
                addressText = displayText(for: url)
            }
        }
        .onChange(of: isEditingAddress) { editing in
            // Show the full address while editing, just the site name otherwise.
            addressText = editing
                ? browser.displayedURL?.absoluteString ?? ""
                : displayText(for: browser.displayedURL)
        }
        .sheet(item: $sheet) { sheet in
            switch sheet {
            case .bookmarks:
                BookmarksView(store: bookmarks) { url in browser.load(url) }
            case .settings:
                SettingsView(searchEngine: $searchEngine)
            }
        }
    }

    // MARK: - Address bar

    private var addressBar: some View {
        HStack(spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: addressIcon)
                    .font(.footnote)
                    .foregroundColor(.secondary)

                TextField("Search or enter address", text: $addressText)
                    .focused($isEditingAddress)
                    .keyboardType(.webSearch)
                    .textInputAutocapitalization(.never)
                    .disableAutocorrection(true)
                    .submitLabel(.go)
                    .onSubmit(submitAddress)

                if isEditingAddress {
                    if !addressText.isEmpty {
                        Button {
                            addressText = ""
                        } label: {
                            Image(systemName: "xmark.circle.fill")
                                .foregroundColor(.secondary)
                        }
                        .accessibilityLabel(Text("Clear"))
                    }
                } else {
                    Button {
                        if browser.isLoading {
                            browser.stopLoading()
                        } else {
                            browser.reload()
                        }
                    } label: {
                        Image(systemName: browser.isLoading ? "xmark" : "arrow.clockwise")
                    }
                    .accessibilityLabel(browser.isLoading ? Text("Stop") : Text("Reload"))
                }
            }
            .padding(.horizontal, 10)
            .frame(height: 38)
            .background(Color(.secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))

            if isEditingAddress {
                Button("Cancel") {
                    isEditingAddress = false
                }
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(.bar)
        .overlay(alignment: .bottom) {
            if browser.isLoading {
                ProgressView(value: browser.progress)
                    .progressViewStyle(.linear)
            }
        }
    }

    private var addressIcon: String {
        if isEditingAddress { return "magnifyingglass" }
        switch browser.displayedURL?.scheme {
        case "https": return "lock.fill"
        case "http": return "lock.open"
        default: return "globe"
        }
    }

    private func displayText(for url: URL?) -> String {
        guard let url else { return "" }
        guard let host = url.host else { return url.absoluteString }
        return host.hasPrefix("www.") ? String(host.dropFirst(4)) : host
    }

    private func submitAddress() {
        browser.open(addressText, searchEngine: searchEngine)
        isEditingAddress = false
    }

    // MARK: - Toolbar

    private var toolbar: some View {
        HStack {
            Button {
                browser.goBack()
            } label: {
                toolbarIcon("chevron.backward")
            }
            .disabled(!browser.canGoBack && browser.loadError == nil)
            .accessibilityLabel(Text("Back"))

            Spacer()

            Button {
                browser.goForward()
            } label: {
                toolbarIcon("chevron.forward")
            }
            .disabled(!browser.canGoForward)
            .accessibilityLabel(Text("Forward"))

            Spacer()

            Button {
                browser.share()
            } label: {
                toolbarIcon("square.and.arrow.up")
            }
            .disabled(browser.currentURL == nil)
            .accessibilityLabel(Text("Share"))

            Spacer()

            Button {
                sheet = .bookmarks
            } label: {
                toolbarIcon("book")
            }
            .accessibilityLabel(Text("Bookmarks"))

            Spacer()

            moreMenu
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 4)
        .background(.bar)
    }

    private var moreMenu: some View {
        Menu {
            Button {
                if let url = browser.currentURL {
                    bookmarks.toggle(title: browser.pageTitle, url: url)
                }
            } label: {
                if let url = browser.currentURL, bookmarks.contains(url) {
                    Label("Remove Bookmark", systemImage: "star.slash")
                } else {
                    Label("Add Bookmark", systemImage: "star")
                }
            }
            .disabled(browser.currentURL == nil)

            Button {
                browser.load(searchEngine.homeURL)
            } label: {
                Label("Home", systemImage: "house")
            }

            Button {
                browser.toggleDesktopMode()
            } label: {
                if browser.isDesktopMode {
                    Label("Request Mobile Website", systemImage: "iphone")
                } else {
                    Label("Request Desktop Website", systemImage: "desktopcomputer")
                }
            }

            Divider()

            Button {
                sheet = .settings
            } label: {
                Label("Settings", systemImage: "gearshape")
            }
        } label: {
            toolbarIcon("ellipsis.circle")
        }
        .accessibilityLabel(Text("More"))
    }

    private func toolbarIcon(_ systemName: String) -> some View {
        Image(systemName: systemName)
            .font(.system(size: 20))
            .frame(width: 44, height: 44)
    }
}

/// Shown over the page when it could not be loaded.
private struct ErrorView: View {
    let message: String
    let retry: @MainActor () -> Void

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "wifi.exclamationmark")
                .font(.system(size: 44))
                .foregroundColor(.secondary)
            Text("Can't open this page")
                .font(.headline)
            Text(message)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            Button("Try Again") { retry() }
                .buttonStyle(.borderedProminent)
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(.systemBackground))
    }
}
