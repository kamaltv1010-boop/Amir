import Combine
import UIKit
import WebKit

/// The browser window: its tabs, normal and private, which one is shown, and
/// what the tabs share: website data, tracker rules, settings and stats.
@MainActor
final class BrowserModel: NSObject, ObservableObject {
    @Published private(set) var tabs: [BrowserTab] = []
    @Published private(set) var privateTabs: [BrowserTab] = []
    @Published private var selectedID = UUID()
    /// The fingerprint protections in effect: the ones switched on, plus the
    /// user agent in iPad mode.
    @Published private(set) var enabledProtections: Set<FingerprintProtection.Kind> = []
    /// Whether pages see a real iPad instead of an iPhone.
    @Published private(set) var isIPadMode = false

    let stats = PrivacyStats()
    let history = HistoryStore()
    /// Sites that don't support https://, so they aren't upgraded again.
    var httpOnlyHosts: Set<String> = []
    /// The compiled tracker blocking rules, once ready.
    private(set) var trackerRules: WKContentRuleList?
    private var trackerRulesLoaded = false
    /// Set while a new session deletes the old website data.
    private var isClearingData = false
    /// Normal tabs share their cookies and website data; private tabs share
    /// theirs, in memory, until the last private tab closes.
    private var dataStore: WKWebsiteDataStore
    private var privateDataStore: WKWebsiteDataStore?
    private var appliedPrivacySignature = ""
    /// Set while the model itself writes privacy settings, so the resulting
    /// UserDefaults notifications don't trigger a second reload.
    private var isUpdatingPrivacy = false
    /// Called with a link the user pinned from the long-press menu.
    var onPinLink: ((URL) -> Void)?

    /// The UserDefaults key of the "Clear Everything on Quit" switch.
    nonisolated static let clearOnQuitKey = "clearOnQuit"
    private static let savedTabsKey = "openTabs"
    private static let selectedTabKey = "selectedTab"
    /// Where the first version kept the one page it remembered.
    private static let lastURLKey = "lastURL"

    override init() {
        let clearOnQuit = UserDefaults.standard.bool(forKey: Self.clearOnQuitKey)
        dataStore = clearOnQuit ? .nonPersistent() : .default()
        super.init()

        if clearOnQuit {
            // Every launch is a new session: no old pages, new fingerprints.
            UserDefaults.standard.removeObject(forKey: Self.savedTabsKey)
            FingerprintProtection.newSeeds(FingerprintProtection.Kind.allCases)
            WKWebsiteDataStore.default().removeData(
                ofTypes: WKWebsiteDataStore.allWebsiteDataTypes(),
                modifiedSince: .distantPast
            ) {}
        }
        restoreTabs()
        applyPrivacySettings()
        ExtensionManager.shared.attach(to: self)
        tabs.forEach { ExtensionManager.shared.tabOpened($0) }

        Task { [weak self] in
            let rules = await TrackerBlocker.compile()
            self?.trackerRulesDidLoad(rules)
        }
    }

    // MARK: - Tabs

    /// The tab on screen. There is always at least one normal tab.
    var selectedTab: BrowserTab {
        tabs.first { $0.id == selectedID } ?? privateTabs.first { $0.id == selectedID } ?? tabs[tabs.count - 1]
    }

    var allTabs: [BrowserTab] {
        tabs + privateTabs
    }

    /// Opens a new tab, empty (the start page) or loading `url`.
    @discardableResult
    func newTab(isPrivate: Bool = false, url: URL? = nil) -> BrowserTab {
        let tab = BrowserTab(model: self, isPrivate: isPrivate)
        insert(tab, after: selectedTab)
        select(tab)
        if let url {
            tab.load(url)
        }
        return tab
    }

    /// Opens `url` in a new tab from a link's menu.
    @discardableResult
    func openTab(url: URL, isPrivate: Bool) -> BrowserTab {
        newTab(isPrivate: isPrivate, url: url)
    }

    /// The tab for a window a page opens, created with WebKit's configuration
    /// so the page can talk to it. It is private if its opener is.
    func openTab(configuration: WKWebViewConfiguration, from opener: BrowserTab) -> BrowserTab? {
        let tab = BrowserTab(model: self, isPrivate: opener.isPrivate, configuration: configuration)
        insert(tab, after: opener)
        select(tab)
        return tab
    }

    private func insert(_ tab: BrowserTab, after neighbor: BrowserTab) {
        if tab.isPrivate {
            let index = privateTabs.firstIndex { $0 === neighbor }.map { $0 + 1 } ?? privateTabs.count
            privateTabs.insert(tab, at: index)
        } else {
            let index = tabs.firstIndex { $0 === neighbor }.map { $0 + 1 } ?? tabs.count
            tabs.insert(tab, at: index)
            ExtensionManager.shared.tabOpened(tab)
        }
        saveTabs()
    }

    func select(_ tab: BrowserTab) {
        let previous = selectedTab
        guard previous !== tab else {
            tab.loadIfNeeded()
            return
        }
        previous.takeSnapshot()
        selectedID = tab.id
        tab.loadIfNeeded()
        ExtensionManager.shared.tabActivated(tab, previous: previous)
        saveTabs()
    }

    func close(_ tab: BrowserTab) {
        let wasSelected = selectedTab === tab
        if tab.isPrivate {
            guard let index = privateTabs.firstIndex(where: { $0 === tab }) else { return }
            privateTabs.remove(at: index)
            if wasSelected {
                selectedID = privateTabs.isEmpty ? tabs[tabs.count - 1].id : privateTabs[min(index, privateTabs.count - 1)].id
            }
            if privateTabs.isEmpty {
                // Nothing of the private session is kept.
                privateDataStore = nil
            }
        } else {
            guard let index = tabs.firstIndex(where: { $0 === tab }) else { return }
            tabs.remove(at: index)
            // There is always a normal tab, before extensions hear of the change.
            if tabs.isEmpty {
                let blank = BrowserTab(model: self, isPrivate: false)
                tabs = [blank]
                ExtensionManager.shared.tabOpened(blank)
                if wasSelected {
                    selectedID = blank.id
                }
            } else if wasSelected {
                selectedID = tabs[min(index, tabs.count - 1)].id
            }
            ExtensionManager.shared.tabClosed(tab)
        }
        tab.close()
        selectedTab.loadIfNeeded()
        saveTabs()
    }

    /// Closes all normal or all private tabs.
    func closeAll(isPrivate: Bool) {
        for tab in isPrivate ? privateTabs : tabs {
            close(tab)
        }
    }

    /// Remembers the open normal tabs for the next launch, unless "Clear
    /// Everything on Quit" is on.
    func saveTabs() {
        guard !UserDefaults.standard.bool(forKey: Self.clearOnQuitKey) else {
            UserDefaults.standard.removeObject(forKey: Self.savedTabsKey)
            return
        }
        let saved = tabs.compactMap(\.saved)
        if let data = try? JSONEncoder().encode(saved) {
            UserDefaults.standard.set(data, forKey: Self.savedTabsKey)
        }
        let selected = tabs.filter { $0.saved != nil }.firstIndex { $0.id == selectedID }
        UserDefaults.standard.set(selected ?? saved.count - 1, forKey: Self.selectedTabKey)
    }

    private func restoreTabs() {
        var saved: [SavedTab] = []
        if let data = UserDefaults.standard.data(forKey: Self.savedTabsKey),
           let tabs = try? JSONDecoder().decode([SavedTab].self, from: data) {
            saved = tabs
        } else if let url = UserDefaults.standard.url(forKey: Self.lastURLKey) {
            saved = [SavedTab(url: url, title: "")]
        }
        UserDefaults.standard.removeObject(forKey: Self.lastURLKey)
        if UserDefaults.standard.bool(forKey: Self.clearOnQuitKey) {
            saved = []
        }

        tabs = saved.map { BrowserTab(model: self, isPrivate: false, restoring: $0) }
        if tabs.isEmpty {
            tabs = [BrowserTab(model: self, isPrivate: false)]
        }
        let index = UserDefaults.standard.object(forKey: Self.selectedTabKey) as? Int ?? tabs.count - 1
        selectedID = tabs[max(0, min(index, tabs.count - 1))].id
    }

    // MARK: - Configuration

    /// A configuration for a new tab's web view.
    func makeConfiguration(isPrivate: Bool) -> WKWebViewConfiguration {
        let configuration = WKWebViewConfiguration()
        configuration.allowsInlineMediaPlayback = true
        if #available(iOS 14.5, *) {
            configuration.upgradeKnownHostsToHTTPS = true
        }
        if isPrivate {
            let store = privateDataStore ?? .nonPersistent()
            privateDataStore = store
            configuration.websiteDataStore = store
        } else {
            configuration.websiteDataStore = dataStore
            ExtensionManager.shared.configure(configuration)
        }
        return configuration
    }

    /// Pages wait for the tracker rules, so they never load unprotected, and
    /// for a new session to finish deleting the old data.
    var isReadyToLoad: Bool {
        (trackerRulesLoaded || !TrackerBlocker.isEnabled) && !isClearingData
    }

    private func trackerRulesDidLoad(_ rules: WKContentRuleList?) {
        trackerRules = rules
        trackerRulesLoaded = true
        applyPrivacySettings()
        selectedTab.loadIfNeeded()
    }

    // MARK: - New session

    /// Deletes cookies, cache, all other website data and history, closes
    /// every tab, gives every site new fingerprints and opens an empty tab.
    /// Bookmarks and pinned links are kept.
    func startNewSession() {
        for tab in allTabs {
            if !tab.isPrivate {
                ExtensionManager.shared.tabClosed(tab)
            }
            tab.close()
        }
        privateTabs = []
        privateDataStore = nil
        httpOnlyHosts = []
        history.clear()
        if UserDefaults.standard.bool(forKey: Self.clearOnQuitKey) {
            dataStore = .nonPersistent()
        }
        isUpdatingPrivacy = true
        FingerprintProtection.newSeeds(FingerprintProtection.Kind.allCases)
        isUpdatingPrivacy = false

        let blank = BrowserTab(model: self, isPrivate: false)
        tabs = [blank]
        selectedID = blank.id
        ExtensionManager.shared.tabOpened(blank)
        applyPrivacySettings()
        saveTabs()

        // Load only once the old data is gone, so no cookie can carry over.
        isClearingData = true
        WKWebsiteDataStore.default().removeData(
            ofTypes: WKWebsiteDataStore.allWebsiteDataTypes(),
            modifiedSince: .distantPast
        ) { [weak self] in
            self?.isClearingData = false
            self?.selectedTab.loadIfNeeded()
        }
    }

    // MARK: - Privacy settings

    /// Changes whenever a setting a tab's pages depend on changes.
    var settingsSignature: String {
        FingerprintProtection.signature + "|\(TrackerBlocker.isEnabled)|\(trackerRules != nil)|\(NightMode.isEnabled)"
    }

    /// Also changes with settings that only matter for the next navigation.
    private var privacySignature: String {
        settingsSignature + "|\(HTTPSUpgrade.isEnabled)|" + Shields.downSites.joined(separator: ",")
    }

    /// Installs the current settings in every tab. Pages pick up the change
    /// when they next load.
    func applyPrivacySettings() {
        isUpdatingPrivacy = true
        defer { isUpdatingPrivacy = false }
        enabledProtections = Set(FingerprintProtection.Kind.allCases.filter(FingerprintProtection.isActive))
        isIPadMode = FingerprintProtection.isIPadMode
        for tab in allTabs {
            tab.applySettings(for: tab.webView.url ?? tab.pendingURL)
        }
        appliedPrivacySignature = privacySignature
    }

    /// Re-applies the settings and reloads the page if a switch changed in
    /// Settings or the shields panel.
    func privacySettingsMayHaveChanged() {
        guard !isUpdatingPrivacy, privacySignature != appliedPrivacySignature else { return }
        applyPrivacySettings()
        selectedTab.reload()
    }

    /// Gives every site new values for `kinds` and reloads the page with them.
    func newFingerprint(_ kinds: [FingerprintProtection.Kind]) {
        isUpdatingPrivacy = true
        FingerprintProtection.newSeeds(kinds)
        isUpdatingPrivacy = false
        applyPrivacySettings()
        selectedTab.reload()
    }

    /// Turns iPad mode on or off and reloads the page. Turning it on leaves
    /// desktop mode, which would replace the iPad's user agent with a Mac's.
    func setIPadMode(_ isOn: Bool) {
        isUpdatingPrivacy = true
        FingerprintProtection.setIPadMode(isOn)
        isUpdatingPrivacy = false
        if isOn {
            selectedTab.setDesktopMode(false, reload: false)
        }
        applyPrivacySettings()
        selectedTab.reload()
    }

    /// Turns shields up or down for the selected tab's site and reloads it.
    func setShieldsUp(_ isUp: Bool) {
        guard let site = Shields.site(of: selectedTab.webView.url) else { return }
        isUpdatingPrivacy = true
        Shields.setUp(isUp, for: site)
        isUpdatingPrivacy = false
        applyPrivacySettings()
        selectedTab.reload()
    }

    // MARK: - Tab events

    func tabDidChange(_ tab: BrowserTab) {
        ExtensionManager.shared.tabChanged(tab)
    }

    func tabDidFinishLoading(_ tab: BrowserTab) {
        if !tab.isPrivate, let url = tab.webView.url {
            history.record(url: url, title: tab.title)
            saveTabs()
        }
        ExtensionManager.shared.tabChanged(tab)
    }

    func tabDidUpdateTitle(_ tab: BrowserTab, url: URL) {
        if !tab.isPrivate {
            history.updateTitle(tab.title, for: url)
        }
        ExtensionManager.shared.tabChanged(tab)
    }

    // MARK: - Presenting

    /// Presents `controller` above whatever is on screen and returns true, or
    /// returns false if that isn't possible right now (for example a sheet is
    /// mid-animation, when UIKit would silently drop the presentation).
    @discardableResult
    func present(_ controller: UIViewController) -> Bool {
        let window = UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .flatMap(\.windows)
            .first(where: \.isKeyWindow)
        guard var top = window?.rootViewController else { return false }
        while let presented = top.presentedViewController {
            if presented.isBeingDismissed { return false }
            top = presented
        }
        guard !top.isBeingPresented, !top.isBeingDismissed else { return false }
        if let popover = controller.popoverPresentationController, popover.sourceView == nil {
            popover.sourceView = top.view
            popover.sourceRect = CGRect(x: top.view.bounds.midX, y: top.view.bounds.maxY - 60, width: 1, height: 1)
        }
        top.present(controller, animated: true)
        return true
    }
}
