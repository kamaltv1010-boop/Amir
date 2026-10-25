import SwiftUI

struct BrowserView: View {
    @StateObject private var browser = BrowserModel()
    @StateObject private var bookmarks = BookmarkStore()
    @StateObject private var pins = BookmarkStore(key: "pinnedLinks")
    @AppStorage(SearchEngine.storageKey) private var searchEngine = SearchEngine.google
    @AppStorage(PrivacyScreen.enabledKey) private var hideInSwitcher = true
    @Environment(\.scenePhase) private var scenePhase

    @State private var addressText = ""
    @FocusState private var isEditingAddress: Bool
    @State private var sheet: Sheet?
    @State private var toast: LocalizedStringKey?
    @State private var isConfirmingNewSession = false

    private enum Sheet: String, Identifiable {
        case bookmarks
        case settings

        var id: String { rawValue }
    }

    var body: some View {
        VStack(spacing: 0) {
            addressBar
            if !pins.bookmarks.isEmpty && !isEditingAddress {
                pinnedLinks
            }
            ZStack {
                WebView(webView: browser.webView)
                if let message = browser.loadError {
                    ErrorView(message: message) { browser.reload() }
                }
                if let toast {
                    Text(toast)
                        .font(.subheadline.weight(.semibold))
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                        .background(.regularMaterial, in: Capsule())
                        .frame(maxHeight: .infinity, alignment: .bottom)
                        .padding(.bottom, 16)
                        .transition(.opacity)
                }
            }
            toolbar
        }
        // The keyboard covers the toolbar instead of pushing the page up;
        // WKWebView scrolls its own focused fields into view.
        .ignoresSafeArea(.keyboard, edges: .bottom)
        // iOS takes the app switcher's screenshot as the app goes inactive.
        .overlay {
            if hideInSwitcher && scenePhase != .active {
                ZStack {
                    Color(.systemBackground)
                    Image(systemName: "lock.shield")
                        .font(.system(size: 56))
                        .foregroundColor(.secondary)
                }
                .ignoresSafeArea()
            }
        }
        .onAppear {
            browser.onPinLink = { url in
                pins.add(title: url.host ?? url.absoluteString, url: url)
                showToast("Link pinned")
            }
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
        .onReceive(NotificationCenter.default.publisher(for: UserDefaults.didChangeNotification)) { _ in
            browser.privacySettingsMayHaveChanged()
        }
        .confirmationDialog("Start a New Session?", isPresented: $isConfirmingNewSession, titleVisibility: .visible) {
            Button("New Session", role: .destructive) {
                browser.startNewSession(home: searchEngine.homeURL)
                showToast("New session started")
            }
        } message: {
            Text("This deletes cookies and website data, closes open pages and changes every fingerprint. Bookmarks and pinned links are kept.")
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

    // MARK: - Pinned links

    private var pinnedLinks: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(pins.bookmarks) { pin in
                    Button {
                        browser.load(pin.url)
                    } label: {
                        Label(pin.title, systemImage: "pin.fill")
                            .font(.footnote)
                            .lineLimit(1)
                            .frame(maxWidth: 160)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 6)
                            .background(Color(.secondarySystemBackground), in: Capsule())
                    }
                    .buttonStyle(.plain)
                    .contextMenu {
                        Button(role: .destructive) {
                            pins.remove(pin.url)
                        } label: {
                            Label("Unpin", systemImage: "pin.slash")
                        }
                    }
                }
            }
            .padding(.horizontal)
            .padding(.bottom, 6)
        }
        .background(.bar)
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
                if let url = browser.currentURL {
                    pins.toggle(title: browser.pageTitle, url: url)
                }
            } label: {
                if let url = browser.currentURL, pins.contains(url) {
                    Label("Unpin This Page", systemImage: "pin.slash")
                } else {
                    Label("Pin This Page", systemImage: "pin")
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

            fingerprintMenu

            Button(role: .destructive) {
                isConfirmingNewSession = true
            } label: {
                Label("New Session", systemImage: "flame")
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

    private var fingerprintMenu: some View {
        Menu {
            ForEach(FingerprintProtection.Kind.allCases) { kind in
                Button {
                    browser.newFingerprint([kind])
                    showToast(kind.changedMessage)
                } label: {
                    Label(kind.newTitle, systemImage: kind.symbol)
                }
                .disabled(!browser.enabledProtections.contains(kind))
            }

            Divider()

            Button {
                browser.newFingerprint(Array(browser.enabledProtections))
                showToast("All fingerprints changed")
            } label: {
                Label("Change All", systemImage: "arrow.triangle.2.circlepath")
            }
            .disabled(browser.enabledProtections.isEmpty)
        } label: {
            Label("Fingerprint", systemImage: "hand.raised")
        }
    }

    private func showToast(_ message: LocalizedStringKey) {
        withAnimation { toast = message }
        Task {
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            withAnimation { toast = nil }
        }
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
