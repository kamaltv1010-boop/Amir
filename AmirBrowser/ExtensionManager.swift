import SwiftUI
import WebKit

/// An installed web extension, as the extensions list shows it.
struct ExtensionInfo: Identifiable {
    let id: String
    var name: String
    var version: String
    var summary: String
    var icon: UIImage?
    var isEnabled: Bool
    var hasOptionsPage: Bool
    var error: String?
}

/// An extension's toolbar button, for the ⋯ menu.
struct ExtensionAction: Identifiable {
    let id: String
    let label: String
    let icon: UIImage?
    let badge: String
}

/// Chrome and Safari web extensions (the WebExtensions format), run by
/// WebKit itself on iOS 18.4 and later. They are installed from a .zip, a
/// .crx or a folder, kept in Application Support/Extensions, and run in
/// normal tabs, not private ones.
@MainActor
final class ExtensionManager: ObservableObject {
    static let shared = ExtensionManager()

    @Published private(set) var extensions: [ExtensionInfo] = []
    /// Changes when an extension's button changes (title, badge…), so menus
    /// showing it update.
    @Published private(set) var actionsRevision = 0
    /// An extension waiting for the user to allow what it asks for.
    @Published private(set) var pendingInstall: PendingInstall?
    @Published var errorMessage: String?

    struct PendingInstall: Identifiable {
        let id: String
        let name: String
        /// What it may do, in words.
        let permissions: [String]
        /// The sites it may read and change, or nil for all of them.
        let sites: [String]?
    }

    static var isSupported: Bool {
        if #available(iOS 18.4, *) {
            return true
        }
        return false
    }

    fileprivate struct Record: Codable {
        var id: String
        var fileName: String
        var isEnabled: Bool
    }

    private var records: [Record] = []
    private var pendingRecord: Record?
    private static let recordsKey = "webExtensions"
    private let folder: URL
    /// The WebKit side (a `WebExtensionHost`), which only exists on iOS 18.4
    /// and later.
    private var hostObject: AnyObject?

    private init() {
        let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        folder = support.appendingPathComponent("Extensions", isDirectory: true)
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        if let data = UserDefaults.standard.data(forKey: Self.recordsKey),
           let saved = try? JSONDecoder().decode([Record].self, from: data) {
            records = saved
        }
        if #available(iOS 18.4, *) {
            let host = WebExtensionHost(manager: self)
            hostObject = host
            Task { await self.loadInstalled(in: host) }
        }
    }

    @available(iOS 18.4, *)
    private var host: WebExtensionHost? {
        hostObject as? WebExtensionHost
    }

    // MARK: - Tabs and windows

    /// Lets extensions run in web views made with `configuration`.
    func configure(_ configuration: WKWebViewConfiguration) {
        if #available(iOS 18.4, *), let host {
            configuration.webExtensionController = host.controller
        }
    }

    func attach(to window: BrowserModel) {
        if #available(iOS 18.4, *) {
            host?.window = window
        }
    }

    func tabOpened(_ tab: BrowserTab) {
        guard !tab.isPrivate else { return }
        if #available(iOS 18.4, *) {
            host?.controller.didOpenTab(tab)
        }
    }

    func tabClosed(_ tab: BrowserTab) {
        guard !tab.isPrivate else { return }
        if #available(iOS 18.4, *) {
            host?.controller.didCloseTab(tab, windowIsClosing: false)
        }
    }

    func tabActivated(_ tab: BrowserTab, previous: BrowserTab) {
        guard !tab.isPrivate else { return }
        if #available(iOS 18.4, *) {
            host?.controller.didActivateTab(tab, previousActiveTab: previous.isPrivate ? nil : previous)
        }
    }

    func tabChanged(_ tab: BrowserTab) {
        guard !tab.isPrivate else { return }
        if #available(iOS 18.4, *) {
            host?.controller.didChangeTabProperties([.URL, .title, .loading], for: tab)
        }
    }

    // MARK: - Actions

    /// The buttons of the enabled extensions, for `tab`.
    func actions(for tab: BrowserTab) -> [ExtensionAction] {
        guard !tab.isPrivate else { return [] }
        if #available(iOS 18.4, *), let host {
            return records.filter(\.isEnabled).compactMap { record in
                guard let context = host.contexts[record.id], context.isLoaded,
                      let action = context.action(for: tab)
                else { return nil }
                let name = context.webExtension.displayShortName ?? context.webExtension.displayName ?? ""
                return ExtensionAction(
                    id: record.id,
                    label: action.label.isEmpty ? name : action.label,
                    icon: action.icon(for: CGSize(width: 24, height: 24)).map(Self.menuIcon),
                    badge: action.badgeText
                )
            }
        }
        return []
    }

    /// Clicks an extension's button: it opens its pop-up or acts on the page.
    func performAction(_ id: String, for tab: BrowserTab) {
        if #available(iOS 18.4, *) {
            host?.contexts[id]?.performAction(for: tab)
        }
    }

    func openOptions(_ id: String) {
        if #available(iOS 18.4, *), let host, let url = host.contexts[id]?.optionsPageURL {
            host.window?.newTab(url: url)
        }
    }

    /// Menus show images at their own size, so icons are drawn at 24 points.
    private static func menuIcon(_ image: UIImage) -> UIImage {
        let size = CGSize(width: 24, height: 24)
        return UIGraphicsImageRenderer(size: size).image { _ in
            image.draw(in: CGRect(origin: .zero, size: size))
        }
        .withRenderingMode(.alwaysOriginal)
    }

    fileprivate func actionsDidChange() {
        actionsRevision += 1
    }

    // MARK: - Installing

    /// Copies the extension at `url` (a .zip, a .crx or a folder) into the
    /// app and asks the user to allow what it asks for.
    func install(from url: URL) {
        let isScoped = url.startAccessingSecurityScopedResource()
        defer {
            if isScoped {
                url.stopAccessingSecurityScopedResource()
            }
        }
        let id = UUID().uuidString.lowercased()
        let fileName: String
        do {
            fileName = try copyIn(url, id: id)
        } catch {
            errorMessage = String(localized: "This file isn't a web extension. Choose a .zip or .crx file, or a folder with a manifest.json file.")
            return
        }
        let record = Record(id: id, fileName: fileName, isEnabled: true)
        if #available(iOS 18.4, *), let host {
            Task {
                do {
                    let webExtension = try await host.open(record, in: folder)
                    pendingRecord = record
                    pendingInstall = PendingInstall(
                        id: id,
                        name: webExtension.displayName ?? fileName,
                        permissions: describe(webExtension.requestedPermissions),
                        sites: describe(webExtension.requestedPermissionMatchPatterns.union(webExtension.allRequestedMatchPatterns))
                    )
                } catch {
                    removeFile(of: record)
                    errorMessage = error.localizedDescription
                }
            }
        }
    }

    func confirmInstall() {
        guard let record = pendingRecord else { return }
        pendingRecord = nil
        pendingInstall = nil
        records.append(record)
        save()
        if #available(iOS 18.4, *) {
            host?.enable(record.id)
        }
        refresh()
    }

    func cancelInstall() {
        guard let record = pendingRecord else { return }
        pendingRecord = nil
        pendingInstall = nil
        if #available(iOS 18.4, *) {
            host?.forget(record.id)
        }
        removeFile(of: record)
    }

    func setEnabled(_ isEnabled: Bool, id: String) {
        guard let index = records.firstIndex(where: { $0.id == id }) else { return }
        records[index].isEnabled = isEnabled
        save()
        if #available(iOS 18.4, *) {
            if isEnabled {
                host?.enable(id)
            } else {
                host?.disable(id)
            }
        }
        refresh()
    }

    func remove(_ id: String) {
        guard let index = records.firstIndex(where: { $0.id == id }) else { return }
        let record = records.remove(at: index)
        save()
        if #available(iOS 18.4, *) {
            host?.uninstall(id)
        }
        removeFile(of: record)
        refresh()
    }

    // MARK: - Helpers

    @available(iOS 18.4, *)
    private func loadInstalled(in host: WebExtensionHost) async {
        for record in records {
            _ = try? await host.open(record, in: folder)
            if record.isEnabled {
                host.enable(record.id)
            }
        }
        refresh()
    }

    /// Rebuilds `extensions` from the records and what WebKit read from them.
    fileprivate func refresh() {
        guard #available(iOS 18.4, *), let host else { return }
        extensions = records.map { record in
            guard let webExtension = host.extensions[record.id] else {
                return ExtensionInfo(
                    id: record.id, name: record.fileName, version: "", summary: "", icon: nil,
                    isEnabled: record.isEnabled, hasOptionsPage: false,
                    error: String(localized: "This extension couldn't be loaded.")
                )
            }
            let context = host.contexts[record.id]
            let problem = (context?.errors ?? webExtension.errors).first
            return ExtensionInfo(
                id: record.id,
                name: webExtension.displayName ?? record.fileName,
                version: webExtension.displayVersion ?? webExtension.version ?? "",
                summary: webExtension.displayDescription ?? "",
                icon: webExtension.icon(for: CGSize(width: 48, height: 48)),
                isEnabled: record.isEnabled,
                hasOptionsPage: record.isEnabled && context?.optionsPageURL != nil,
                error: problem?.localizedDescription
            )
        }
    }

    /// Copies an extension into the extensions folder and returns its file
    /// name there. A .crx is a .zip with a header, which is dropped.
    private func copyIn(_ url: URL, id: String) throws -> String {
        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: url.path, isDirectory: &isDirectory) else {
            throw CocoaError(.fileNoSuchFile)
        }
        if isDirectory.boolValue {
            guard FileManager.default.fileExists(atPath: url.appendingPathComponent("manifest.json").path) else {
                throw CocoaError(.fileReadCorruptFile)
            }
            try FileManager.default.copyItem(at: url, to: folder.appendingPathComponent(id, isDirectory: true))
            return id
        }
        let data = try Data(contentsOf: url)
        guard let zip = Self.zipData(from: data) else {
            throw CocoaError(.fileReadCorruptFile)
        }
        let fileName = id + ".zip"
        try zip.write(to: folder.appendingPathComponent(fileName), options: .atomic)
        return fileName
    }

    /// The zip archive in `data`: all of it for a .zip, or what follows the
    /// header of a Chrome .crx (version 2 or 3).
    static func zipData(from data: Data) -> Data? {
        let bytes = [UInt8](data)
        let zipMagic: [UInt8] = [0x50, 0x4B, 0x03, 0x04]
        if bytes.starts(with: zipMagic) {
            return data
        }
        guard bytes.count > 16, bytes.starts(with: Array("Cr24".utf8)) else { return nil }
        func uint32(at index: Int) -> Int {
            Int(bytes[index]) | Int(bytes[index + 1]) << 8 | Int(bytes[index + 2]) << 16 | Int(bytes[index + 3]) << 24
        }
        let start: Int
        switch uint32(at: 4) {
        case 2: start = 16 + uint32(at: 8) + uint32(at: 12)
        case 3: start = 12 + uint32(at: 8)
        default: return nil
        }
        guard start + 4 <= bytes.count, bytes[start..<(start + 4)].elementsEqual(zipMagic) else { return nil }
        return Data(bytes[start...])
    }

    private func removeFile(of record: Record) {
        try? FileManager.default.removeItem(at: folder.appendingPathComponent(record.fileName))
    }

    private func save() {
        if let data = try? JSONEncoder().encode(records) {
            UserDefaults.standard.set(data, forKey: Self.recordsKey)
        }
    }

    @available(iOS 18.4, *)
    private func describe(_ permissions: Set<WKWebExtension.Permission>) -> [String] {
        permissions.map { permission in
            switch permission {
            case .activeTab: return String(localized: "Act on the page when you use it")
            case .alarms: return String(localized: "Run on a schedule")
            case .clipboardWrite: return String(localized: "Copy to the clipboard")
            case .contextMenus, .menus: return String(localized: "Add menu items")
            case .cookies: return String(localized: "Read and change cookies")
            case .declarativeNetRequest, .declarativeNetRequestWithHostAccess, .declarativeNetRequestFeedback:
                return String(localized: "Block content on pages")
            case .nativeMessaging: return String(localized: "Talk to apps")
            case .scripting: return String(localized: "Change pages")
            case .storage, .unlimitedStorage: return String(localized: "Store data")
            case .tabs: return String(localized: "See your tabs")
            case .webNavigation, .webRequest: return String(localized: "See the pages you visit")
            default: return permission.rawValue
            }
        }
        .reduce(into: [String]()) { list, text in
            if !list.contains(text) {
                list.append(text)
            }
        }
        .sorted()
    }

    /// The sites, or nil when the patterns cover all of them.
    @available(iOS 18.4, *)
    private func describe(_ patterns: Set<WKWebExtension.MatchPattern>) -> [String]? {
        if patterns.contains(where: { $0.matchesAllHosts || $0.matchesAllURLs || $0.host == "*" }) {
            return nil
        }
        return Set(patterns.compactMap(\.host)).sorted()
    }
}

/// The WebKit side of the extensions: the controller every normal tab uses,
/// the parsed extensions and their running contexts. It also answers the
/// controller's questions about windows and tabs, and shows pop-ups and
/// permission requests.
@available(iOS 18.4, *)
@MainActor
final class WebExtensionHost: NSObject, WKWebExtensionControllerDelegate {
    let controller: WKWebExtensionController
    private(set) var extensions: [String: WKWebExtension] = [:]
    private(set) var contexts: [String: WKWebExtensionContext] = [:]
    weak var window: BrowserModel?
    private weak var manager: ExtensionManager?

    init(manager: ExtensionManager) {
        self.manager = manager
        controller = WKWebExtensionController(configuration: .default())
        super.init()
        controller.delegate = self
    }

    /// Reads the extension of `record`.
    fileprivate func open(_ record: ExtensionManager.Record, in folder: URL) async throws -> WKWebExtension {
        let webExtension = try await WKWebExtension(resourceBaseURL: folder.appendingPathComponent(record.fileName))
        extensions[record.id] = webExtension
        return webExtension
    }

    /// Starts the extension with everything it asked for at install, which
    /// the user allowed. Its identifier and address stay the same across
    /// launches, so it keeps its data.
    func enable(_ id: String) {
        guard let webExtension = extensions[id] else { return }
        let context = contexts[id] ?? WKWebExtensionContext(for: webExtension)
        if !context.isLoaded {
            if contexts[id] == nil {
                context.uniqueIdentifier = id
                if let baseURL = URL(string: "webkit-extension://\(id)/") {
                    context.baseURL = baseURL
                }
            }
            for permission in webExtension.requestedPermissions {
                context.setPermissionStatus(.grantedExplicitly, for: permission)
            }
            for pattern in webExtension.requestedPermissionMatchPatterns.union(webExtension.allRequestedMatchPatterns) {
                context.setPermissionStatus(.grantedExplicitly, for: pattern)
            }
            try? controller.load(context)
        }
        contexts[id] = context
    }

    func disable(_ id: String) {
        guard let context = contexts[id], context.isLoaded else { return }
        try? controller.unload(context)
    }

    /// Stops the extension and deletes its data.
    func uninstall(_ id: String) {
        if let context = contexts[id], context.isLoaded {
            let types = WKWebExtensionController.allExtensionDataTypes
            controller.fetchDataRecord(ofTypes: types, for: context) { [weak self] record in
                if let record {
                    self?.controller.removeData(ofTypes: types, from: [record]) {}
                }
            }
            try? controller.unload(context)
        }
        forget(id)
    }

    func forget(_ id: String) {
        contexts[id] = nil
        extensions[id] = nil
    }

    // MARK: - WKWebExtensionControllerDelegate

    func webExtensionController(
        _ controller: WKWebExtensionController,
        openWindowsFor extensionContext: WKWebExtensionContext
    ) -> [any WKWebExtensionWindow] {
        window.map { [$0] } ?? []
    }

    func webExtensionController(
        _ controller: WKWebExtensionController,
        focusedWindowFor extensionContext: WKWebExtensionContext
    ) -> (any WKWebExtensionWindow)? {
        window
    }

    func webExtensionController(
        _ controller: WKWebExtensionController,
        openNewTabUsing configuration: WKWebExtension.TabConfiguration,
        for extensionContext: WKWebExtensionContext,
        completionHandler: @escaping ((any WKWebExtensionTab)?, (any Error)?) -> Void
    ) {
        guard let window else { return completionHandler(nil, nil) }
        let previous = window.selectedTab
        let tab = window.newTab(url: configuration.url)
        if !configuration.shouldBeActive {
            window.select(previous)
        }
        completionHandler(tab, nil)
    }

    func webExtensionController(
        _ controller: WKWebExtensionController,
        openNewWindowUsing configuration: WKWebExtension.WindowConfiguration,
        for extensionContext: WKWebExtensionContext,
        completionHandler: @escaping ((any WKWebExtensionWindow)?, (any Error)?) -> Void
    ) {
        // There is one window, so its tabs open there.
        guard let window else { return completionHandler(nil, nil) }
        for url in configuration.tabURLs {
            window.newTab(isPrivate: configuration.shouldBePrivate, url: url)
        }
        completionHandler(window, nil)
    }

    func webExtensionController(
        _ controller: WKWebExtensionController,
        openOptionsPageFor extensionContext: WKWebExtensionContext,
        completionHandler: @escaping ((any Error)?) -> Void
    ) {
        if let url = extensionContext.optionsPageURL {
            window?.newTab(url: url)
        }
        completionHandler(nil)
    }

    func webExtensionController(
        _ controller: WKWebExtensionController,
        presentActionPopup action: WKWebExtension.Action,
        for context: WKWebExtensionContext,
        completionHandler: @escaping ((any Error)?) -> Void
    ) {
        guard let popup = action.popupViewController, window?.present(popup) == true else {
            return completionHandler(CocoaError(.featureUnsupported))
        }
        completionHandler(nil)
    }

    func webExtensionController(
        _ controller: WKWebExtensionController,
        didUpdate action: WKWebExtension.Action,
        forExtensionContext context: WKWebExtensionContext
    ) {
        manager?.actionsDidChange()
    }

    func webExtensionController(
        _ controller: WKWebExtensionController,
        promptForPermissions permissions: Set<WKWebExtension.Permission>,
        in tab: (any WKWebExtensionTab)?,
        for extensionContext: WKWebExtensionContext,
        completionHandler: @escaping (Set<WKWebExtension.Permission>, Date?) -> Void
    ) {
        ask(extensionContext, toAllow: permissions.map(\.rawValue)) { allowed in
            completionHandler(allowed ? permissions : [], nil)
        }
    }

    func webExtensionController(
        _ controller: WKWebExtensionController,
        promptForPermissionToAccess urls: Set<URL>,
        in tab: (any WKWebExtensionTab)?,
        for extensionContext: WKWebExtensionContext,
        completionHandler: @escaping (Set<URL>, Date?) -> Void
    ) {
        ask(extensionContext, toAllow: urls.compactMap(\.host)) { allowed in
            completionHandler(allowed ? urls : [], nil)
        }
    }

    func webExtensionController(
        _ controller: WKWebExtensionController,
        promptForPermissionMatchPatterns matchPatterns: Set<WKWebExtension.MatchPattern>,
        in tab: (any WKWebExtensionTab)?,
        for extensionContext: WKWebExtensionContext,
        completionHandler: @escaping (Set<WKWebExtension.MatchPattern>, Date?) -> Void
    ) {
        ask(extensionContext, toAllow: matchPatterns.map(\.string)) { allowed in
            completionHandler(allowed ? matchPatterns : [], nil)
        }
    }

    /// Asks whether the extension may have more access, and answers no if
    /// the question can't be shown.
    private func ask(_ context: WKWebExtensionContext, toAllow items: [String], answer: @escaping (Bool) -> Void) {
        let name = context.webExtension.displayName ?? ""
        let alert = UIAlertController(
            title: String(localized: "Allow “\(name)” more access?"),
            message: items.sorted().joined(separator: "\n"),
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: String(localized: "Don’t Allow"), style: .cancel) { _ in answer(false) })
        alert.addAction(UIAlertAction(title: String(localized: "Allow"), style: .default) { _ in answer(true) })
        if window?.present(alert) != true {
            answer(false)
        }
    }
}

// MARK: - Windows and tabs for extensions

@available(iOS 18.4, *)
extension BrowserModel: WKWebExtensionWindow {
    func tabs(for context: WKWebExtensionContext) -> [any WKWebExtensionTab] {
        tabs
    }

    func activeTab(for context: WKWebExtensionContext) -> (any WKWebExtensionTab)? {
        selectedTab.isPrivate ? nil : selectedTab
    }

    func windowType(for context: WKWebExtensionContext) -> WKWebExtension.WindowType {
        .normal
    }

    func windowState(for context: WKWebExtensionContext) -> WKWebExtension.WindowState {
        .normal
    }

    func isPrivate(for context: WKWebExtensionContext) -> Bool {
        false
    }

    func frame(for context: WKWebExtensionContext) -> CGRect {
        UIScreen.main.bounds
    }

    func screenFrame(for context: WKWebExtensionContext) -> CGRect {
        UIScreen.main.bounds
    }

    func focus(for context: WKWebExtensionContext, completionHandler: @escaping ((any Error)?) -> Void) {
        completionHandler(nil)
    }
}

@available(iOS 18.4, *)
extension BrowserTab: WKWebExtensionTab {
    func window(for context: WKWebExtensionContext) -> (any WKWebExtensionWindow)? {
        isPrivate ? nil : model
    }

    func indexInWindow(for context: WKWebExtensionContext) -> Int {
        model?.tabs.firstIndex { $0 === self } ?? NSNotFound
    }

    func title(for context: WKWebExtensionContext) -> String? {
        displayTitle
    }

    func url(for context: WKWebExtensionContext) -> URL? {
        self.webView.url ?? pendingURL
    }

    func webView(for context: WKWebExtensionContext) -> WKWebView? {
        self.webView
    }

    func isSelected(for context: WKWebExtensionContext) -> Bool {
        model?.selectedTab === self
    }

    func isLoadingComplete(for context: WKWebExtensionContext) -> Bool {
        !isLoading
    }

    func activate(for context: WKWebExtensionContext, completionHandler: @escaping ((any Error)?) -> Void) {
        model?.select(self)
        completionHandler(nil)
    }

    func close(for context: WKWebExtensionContext, completionHandler: @escaping ((any Error)?) -> Void) {
        model?.close(self)
        completionHandler(nil)
    }

    func loadURL(_ url: URL, for context: WKWebExtensionContext, completionHandler: @escaping ((any Error)?) -> Void) {
        load(url)
        completionHandler(nil)
    }

    func reload(fromOrigin: Bool, for context: WKWebExtensionContext, completionHandler: @escaping ((any Error)?) -> Void) {
        if fromOrigin {
            self.webView.reloadFromOrigin()
        } else {
            reload()
        }
        completionHandler(nil)
    }

    func goBack(for context: WKWebExtensionContext, completionHandler: @escaping ((any Error)?) -> Void) {
        goBack()
        completionHandler(nil)
    }

    func goForward(for context: WKWebExtensionContext, completionHandler: @escaping ((any Error)?) -> Void) {
        goForward()
        completionHandler(nil)
    }

    func zoomFactor(for context: WKWebExtensionContext) -> Double {
        zoom
    }

    func setZoomFactor(_ zoomFactor: Double, for context: WKWebExtensionContext, completionHandler: @escaping ((any Error)?) -> Void) {
        setZoom(zoomFactor)
        completionHandler(nil)
    }

    func size(for context: WKWebExtensionContext) -> CGSize {
        self.webView.bounds.size
    }

    func takeSnapshot(
        using configuration: WKSnapshotConfiguration,
        for context: WKWebExtensionContext,
        completionHandler: @escaping (UIImage?, (any Error)?) -> Void
    ) {
        self.webView.takeSnapshot(with: configuration) { image, error in
            completionHandler(image, error)
        }
    }
}
