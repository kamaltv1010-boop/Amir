import SwiftUI

struct BrowserView: View {
    @StateObject private var browser = BrowserModel()
    @StateObject private var bookmarks = BookmarkStore()
    @StateObject private var pins = BookmarkStore(key: "pinnedLinks")
    @AppStorage(SearchEngine.storageKey) private var searchEngine = SearchEngine.google
    @AppStorage(PrivacyScreen.enabledKey) private var hideInSwitcher = true
    @Environment(\.scenePhase) private var scenePhase

    @State private var isEditingAddress = false
    @State private var isShowingTabs = false
    @State private var sheet: BrowserSheet?
    @State private var toast: LocalizedStringKey?
    @State private var isConfirmingNewSession = false

    var body: some View {
        ZStack {
            BrowserScreen(
                browser: browser,
                tab: browser.selectedTab,
                bookmarks: bookmarks,
                pins: pins,
                searchEngine: searchEngine,
                isEditingAddress: $isEditingAddress,
                isShowingTabs: $isShowingTabs,
                sheet: $sheet,
                isConfirmingNewSession: $isConfirmingNewSession,
                toast: toast,
                showToast: showToast
            )

            if isEditingAddress {
                AddressEditor(
                    tab: browser.selectedTab,
                    history: browser.history,
                    bookmarks: bookmarks,
                    searchEngine: searchEngine,
                    isPresented: $isEditingAddress
                )
                .transition(.opacity)
            }

            if isShowingTabs {
                TabOverview(browser: browser, isPresented: $isShowingTabs)
                    .transition(.opacity.combined(with: .scale(scale: 1.04)))
            }
        }
        .animation(.easeOut(duration: 0.2), value: isEditingAddress)
        .animation(.easeOut(duration: 0.22), value: isShowingTabs)
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
        }
        .onChange(of: scenePhase) { phase in
            if phase != .active {
                browser.saveTabs()
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: UserDefaults.didChangeNotification)) { _ in
            browser.privacySettingsMayHaveChanged()
        }
        .confirmationDialog("Start a New Session?", isPresented: $isConfirmingNewSession, titleVisibility: .visible) {
            Button("New Session", role: .destructive) {
                browser.startNewSession()
                showToast("New session started")
            }
        } message: {
            Text("This deletes cookies, website data and history, closes all tabs and changes every fingerprint. Bookmarks and pinned links are kept.")
        }
        .sheet(item: $sheet) { sheet in
            switch sheet {
            case .library:
                LibraryView(bookmarks: bookmarks, history: browser.history) { url in
                    browser.selectedTab.load(url)
                }
            case .settings:
                SettingsView(browser: browser, searchEngine: $searchEngine)
            case .shields:
                ShieldsPanel(browser: browser, tab: browser.selectedTab)
            case .extensions:
                NavigationView {
                    ExtensionsView { self.sheet = nil }
                        .toolbar {
                            ToolbarItem(placement: .confirmationAction) {
                                Button("Done") { self.sheet = nil }
                            }
                        }
                }
                .navigationViewStyle(.stack)
            case .cookies:
                CookiesView(tab: browser.selectedTab)
            }
        }
    }

    private func showToast(_ message: LocalizedStringKey) {
        withAnimation { toast = message }
        Task {
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            withAnimation { toast = nil }
        }
    }
}

enum BrowserSheet: String, Identifiable {
    case library
    case settings
    case shields
    case extensions
    case cookies

    var id: String { rawValue }
}

/// The page, or the start page, with the address bar and the toolbar below
/// it, like Safari.
private struct BrowserScreen: View {
    @ObservedObject var browser: BrowserModel
    @ObservedObject var tab: BrowserTab
    @ObservedObject var bookmarks: BookmarkStore
    @ObservedObject var pins: BookmarkStore
    @ObservedObject var extensions = ExtensionManager.shared
    let searchEngine: SearchEngine
    @Binding var isEditingAddress: Bool
    @Binding var isShowingTabs: Bool
    @Binding var sheet: BrowserSheet?
    @Binding var isConfirmingNewSession: Bool
    let toast: LocalizedStringKey?
    let showToast: (LocalizedStringKey) -> Void

    @AppStorage(NightMode.enabledKey) private var nightMode = false
    @AppStorage(TrackerBlocker.enabledKey) private var blockTrackers = true

    var body: some View {
        VStack(spacing: 0) {
            if !pins.bookmarks.isEmpty {
                pinnedLinks
            }
            ZStack {
                WebView(webView: tab.webView)
                    .opacity(tab.isBlank ? 0 : 1)
                if tab.isBlank {
                    StartPage(
                        stats: browser.stats,
                        bookmarks: bookmarks,
                        isPrivate: tab.isPrivate,
                        onSearch: { isEditingAddress = true },
                        onOpen: { tab.load($0) }
                    )
                }
                if let storeID = ChromeWebStore.extensionID(in: tab.currentURL) {
                    StoreBanner(storeID: storeID, extensions: extensions)
                }
                if let message = tab.loadError {
                    ErrorView(message: message) { tab.reload() }
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
            bottomBar
        }
        // The keyboard covers the bars instead of pushing the page up;
        // WKWebView scrolls its own focused fields into view.
        .ignoresSafeArea(.keyboard, edges: .bottom)
    }

    // MARK: - Bottom bar

    private var bottomBar: some View {
        VStack(spacing: 4) {
            addressCapsule
            toolbar
        }
        .padding(.top, 8)
        .background(.bar)
        .overlay(alignment: .top) {
            if tab.isLoading {
                ProgressView(value: tab.progress)
                    .progressViewStyle(.linear)
                    .tint(tab.isPrivate ? Theme.privateTint : .accentColor)
                    .scaleEffect(x: 1, y: 0.6, anchor: .top)
            } else {
                Divider()
            }
        }
        .environment(\.colorScheme, tab.isPrivate ? .dark : colorScheme)
    }

    @Environment(\.colorScheme) private var colorScheme

    private var addressCapsule: some View {
        HStack(spacing: 4) {
            Button {
                sheet = .shields
            } label: {
                ZStack(alignment: .topTrailing) {
                    Image(systemName: shieldsActive ? "shield.fill" : "shield.slash")
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundColor(shieldsActive ? Theme.shields : .secondary)
                        .frame(width: 40, height: 40)
                    if shieldsActive && tab.trackersBlocked > 0 {
                        Text(verbatim: tab.trackersBlocked > 99 ? "99+" : "\(tab.trackersBlocked)")
                            .font(.system(size: 9, weight: .bold))
                            .foregroundColor(.white)
                            .padding(.horizontal, 4)
                            .padding(.vertical, 1)
                            .background(Theme.shields, in: Capsule())
                            .offset(x: -2, y: 4)
                    }
                }
            }
            .disabled(tab.isBlank)
            .accessibilityLabel(Text("Shields"))

            Button {
                isEditingAddress = true
            } label: {
                HStack(spacing: 5) {
                    if tab.isPrivate {
                        Image(systemName: "eyeglasses")
                            .foregroundColor(Theme.privateTint)
                    } else if let icon = securityIcon {
                        Image(systemName: icon)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    Text(addressTitle)
                        .lineLimit(1)
                        .foregroundColor(tab.isBlank ? .secondary : .primary)
                }
                .font(.body)
                .frame(maxWidth: .infinity, minHeight: 40)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .contextMenu {
                if let url = tab.displayedURL {
                    Button {
                        UIPasteboard.general.url = url
                    } label: {
                        Label("Copy Link", systemImage: "doc.on.doc")
                    }
                }
                Button {
                    if let text = UIPasteboard.general.string {
                        tab.open(text, searchEngine: searchEngine)
                    }
                } label: {
                    Label("Paste and Go", systemImage: "doc.on.clipboard")
                }
            }

            Button {
                if tab.isLoading {
                    tab.stopLoading()
                } else {
                    tab.reload()
                }
            } label: {
                Image(systemName: tab.isLoading ? "xmark" : "arrow.clockwise")
                    .font(.system(size: 16, weight: .medium))
                    .frame(width: 40, height: 40)
            }
            .disabled(tab.isBlank)
            .accessibilityLabel(tab.isLoading ? Text("Stop") : Text("Reload"))
        }
        .padding(.horizontal, 4)
        .background(Color(.tertiarySystemFill), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .padding(.horizontal, 12)
    }

    private var shieldsActive: Bool {
        tab.shieldsUp && !tab.isBlank
    }

    private var securityIcon: String? {
        switch tab.displayedURL?.scheme {
        case "https": return "lock.fill"
        case "http": return "exclamationmark.triangle.fill"
        default: return nil
        }
    }

    private var addressTitle: String {
        guard let url = tab.displayedURL else {
            return String(localized: "Search or enter address")
        }
        return Shields.site(of: url) ?? url.absoluteString
    }

    private var toolbar: some View {
        HStack {
            Button {
                tab.goBack()
            } label: {
                toolbarIcon("chevron.backward")
            }
            .disabled(!tab.canGoBack && tab.loadError == nil)
            .accessibilityLabel(Text("Back"))

            Spacer()

            Button {
                tab.goForward()
            } label: {
                toolbarIcon("chevron.forward")
            }
            .disabled(!tab.canGoForward)
            .accessibilityLabel(Text("Forward"))

            Spacer()

            Button {
                browser.newTab(isPrivate: tab.isPrivate)
                isEditingAddress = true
            } label: {
                toolbarIcon("plus")
            }
            .accessibilityLabel(Text("New Tab"))

            Spacer()

            Button {
                tab.takeSnapshot()
                isShowingTabs = true
            } label: {
                TabCountIcon(count: tab.isPrivate ? browser.privateTabs.count : browser.tabs.count)
                    .frame(width: 44, height: 44)
            }
            .contextMenu {
                Button {
                    browser.newTab()
                } label: {
                    Label("New Tab", systemImage: "plus.square.on.square")
                }
                Button {
                    browser.newTab(isPrivate: true)
                } label: {
                    Label("New Private Tab", systemImage: "eyeglasses")
                }
                Button(role: .destructive) {
                    browser.close(tab)
                } label: {
                    Label("Close This Tab", systemImage: "xmark")
                }
            }
            .accessibilityLabel(Text("Tabs"))

            Spacer()

            moreMenu
        }
        .padding(.horizontal, 20)
    }

    // MARK: - Menu

    private var moreMenu: some View {
        Menu {
            Section {
                Button {
                    sheet = .settings
                } label: {
                    Label("Settings", systemImage: "gearshape")
                }
                Button(role: .destructive) {
                    isConfirmingNewSession = true
                } label: {
                    Label("New Session", systemImage: "flame")
                }
                Button {
                    browser.newTab(isPrivate: true)
                    isEditingAddress = true
                } label: {
                    Label("New Private Tab", systemImage: "eyeglasses")
                }
                Button {
                    sheet = .library
                } label: {
                    Label("Bookmarks & History", systemImage: "book")
                }
            }

            Section {
                Button {
                    tab.share()
                } label: {
                    Label("Share", systemImage: "square.and.arrow.up")
                }
                .disabled(tab.webView.url == nil)
                Button {
                    sheet = .cookies
                } label: {
                    Label("Cookies", systemImage: "birthday.cake")
                }
                .disabled(tab.webView.url?.host == nil)
                Button {
                    if let url = tab.webView.url {
                        bookmarks.toggle(title: tab.title, url: url)
                    }
                } label: {
                    if let url = tab.webView.url, bookmarks.contains(url) {
                        Label("Remove Bookmark", systemImage: "star.slash")
                    } else {
                        Label("Add Bookmark", systemImage: "star")
                    }
                }
                .disabled(tab.webView.url == nil)
                Button {
                    if let url = tab.webView.url {
                        pins.toggle(title: tab.title, url: url)
                    }
                } label: {
                    if let url = tab.webView.url, pins.contains(url) {
                        Label("Unpin This Page", systemImage: "pin.slash")
                    } else {
                        Label("Pin This Page", systemImage: "pin")
                    }
                }
                .disabled(tab.webView.url == nil)
                if #available(iOS 16.0, *) {
                    Button {
                        tab.findInPage()
                    } label: {
                        Label("Find on Page", systemImage: "doc.text.magnifyingglass")
                    }
                    .disabled(tab.isBlank)
                }
            }

            // Kept short enough to show whole on a phone, so nothing hides
            // above the top of the menu.
            Section {
                pageSettingsMenu
                fingerprintMenu
                extensionsMenu
            }
        } label: {
            toolbarIcon("ellipsis.circle")
        }
        .accessibilityLabel(Text("More"))
    }

    /// How the page looks and which device it sees: zoom, night mode, iPad
    /// mode and the desktop website.
    private var pageSettingsMenu: some View {
        Menu {
            zoomMenu
            Toggle(isOn: $nightMode) {
                Label("Night Mode", systemImage: "moon")
            }
            Toggle(isOn: Binding(get: { browser.isIPadMode }, set: { isOn in
                browser.setIPadMode(isOn)
                showToast(isOn ? "iPad mode on" : "iPad mode off")
            })) {
                Label("iPad Mode", systemImage: "ipad")
            }
            Button {
                tab.setDesktopMode(!tab.isDesktopMode)
            } label: {
                if tab.isDesktopMode {
                    Label("Request Mobile Website", systemImage: "iphone")
                } else {
                    Label("Request Desktop Website", systemImage: "desktopcomputer")
                }
            }
            .disabled(tab.isBlank)
        } label: {
            Label("Page Settings", systemImage: "textformat.size")
        }
    }

    private var zoomMenu: some View {
        Menu {
            ForEach([0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 1.75, 2.0], id: \.self) { zoom in
                Button {
                    tab.setZoom(zoom)
                } label: {
                    if abs(tab.zoom - zoom) < 0.01 {
                        Label {
                            Text(verbatim: "\(Int((zoom * 100).rounded()))%")
                        } icon: {
                            Image(systemName: "checkmark")
                        }
                    } else {
                        Text(verbatim: "\(Int((zoom * 100).rounded()))%")
                    }
                }
            }
        } label: {
            Label("Zoom", systemImage: "textformat.size")
        }
        .disabled(tab.isBlank)
    }

    @ViewBuilder
    private var extensionsMenu: some View {
        let _ = extensions.actionsRevision
        let actions = extensions.actions(for: tab)
        if ExtensionManager.isSupported {
            Menu {
                ForEach(actions) { action in
                    Button {
                        extensions.performAction(action.id, for: tab)
                    } label: {
                        Label {
                            Text(verbatim: action.badge.isEmpty ? action.label : "\(action.label) (\(action.badge))")
                        } icon: {
                            if let icon = action.icon {
                                Image(uiImage: icon)
                            } else {
                                Image(systemName: "puzzlepiece.extension")
                            }
                        }
                    }
                }
                Divider()
                Button {
                    browser.newTab(isPrivate: tab.isPrivate, url: ChromeWebStore.homeURL)
                } label: {
                    Label("Chrome Web Store", systemImage: "bag")
                }
                Button {
                    sheet = .extensions
                } label: {
                    Label("Manage Extensions", systemImage: "slider.horizontal.3")
                }
            } label: {
                Label("Extensions", systemImage: "puzzlepiece.extension")
            }
        }
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

    // MARK: - Pinned links

    private var pinnedLinks: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(pins.bookmarks) { pin in
                    Button {
                        tab.load(pin.url)
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
                        Button {
                            browser.newTab(url: pin.url)
                        } label: {
                            Label("Open in New Tab", systemImage: "plus.square.on.square")
                        }
                        Button(role: .destructive) {
                            pins.remove(pin.url)
                        } label: {
                            Label("Unpin", systemImage: "pin.slash")
                        }
                    }
                }
            }
            .padding(.horizontal)
            .padding(.vertical, 6)
        }
        .background(.bar)
    }

    private func toolbarIcon(_ systemName: String) -> some View {
        Image(systemName: systemName)
            .font(.system(size: 20))
            .frame(width: 44, height: 44)
    }
}

/// On a Chrome Web Store extension page: adds the extension to the app.
private struct StoreBanner: View {
    let storeID: String
    @ObservedObject var extensions: ExtensionManager

    var body: some View {
        HStack(spacing: 12) {
            Image("Logo")
                .resizable()
                .frame(width: 38, height: 38)
                .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
            VStack(alignment: .leading, spacing: 2) {
                Text("Chrome Web Store")
                    .font(.subheadline.weight(.semibold))
                Text(ExtensionManager.isSupported ? "Add this extension to Noor." : "Extensions need iOS 18.4 or later")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
            if extensions.downloadingStoreID == storeID {
                ProgressView()
                    .padding(.horizontal, 12)
            } else if extensions.isInstalled(storeID: storeID) {
                Label("Added", systemImage: "checkmark.circle.fill")
                    .font(.subheadline.weight(.semibold))
                    .foregroundColor(.green)
            } else {
                Button("Add to Noor") {
                    extensions.install(storeID: storeID)
                }
                .font(.subheadline.weight(.semibold))
                .buttonStyle(.borderedProminent)
                .disabled(!ExtensionManager.isSupported || extensions.downloadingStoreID != nil)
            }
        }
        .padding(12)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .shadow(color: .black.opacity(0.18), radius: 10, y: 4)
        .padding(.horizontal, 12)
        .padding(.bottom, 12)
        .frame(maxHeight: .infinity, alignment: .bottom)
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
