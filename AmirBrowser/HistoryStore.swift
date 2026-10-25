import SwiftUI

struct HistoryEntry: Identifiable, Codable, Equatable {
    var id = UUID()
    var title: String
    var url: URL
    var date: Date
}

/// The pages visited in normal tabs, newest first, saved in a file in
/// Application Support. With "Clear Everything on Quit" on, history stays
/// in memory only.
@MainActor
final class HistoryStore: ObservableObject {
    @Published private(set) var entries: [HistoryEntry] = []

    private static let limit = 2000
    private let fileURL: URL?
    private var saveTask: Task<Void, Never>?

    init() {
        let folder = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
        fileURL = folder?.appendingPathComponent("History.json")
        if let folder {
            try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        }
        if isPersistent {
            if let fileURL, let data = try? Data(contentsOf: fileURL),
               let saved = try? JSONDecoder().decode([HistoryEntry].self, from: data) {
                entries = saved
            }
        } else if let fileURL {
            try? FileManager.default.removeItem(at: fileURL)
        }
    }

    private var isPersistent: Bool {
        !UserDefaults.standard.bool(forKey: BrowserModel.clearOnQuitKey)
    }

    /// Adds a visit. Reloading the page you just visited only updates it.
    func record(url: URL, title: String) {
        guard ["http", "https"].contains(url.scheme?.lowercased() ?? "") else { return }
        let name = title.isEmpty ? (url.host ?? url.absoluteString) : title
        if let first = entries.first, first.url == url {
            entries[0].title = name
            entries[0].date = Date()
        } else {
            entries.insert(HistoryEntry(title: name, url: url, date: Date()), at: 0)
            if entries.count > Self.limit {
                entries.removeLast(entries.count - Self.limit)
            }
        }
        scheduleSave()
    }

    /// Pages often set their title after they load.
    func updateTitle(_ title: String, for url: URL) {
        guard !title.isEmpty, let index = entries.firstIndex(where: { $0.url == url }),
              entries[index].title != title
        else { return }
        entries[index].title = title
        scheduleSave()
    }

    func remove(_ entry: HistoryEntry) {
        entries.removeAll { $0.id == entry.id }
        scheduleSave()
    }

    func clear() {
        entries = []
        scheduleSave()
    }

    /// Entries whose title or address contains `text`, newest first.
    func search(_ text: String) -> [HistoryEntry] {
        let text = text.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty else { return entries }
        return entries.filter {
            $0.title.localizedCaseInsensitiveContains(text) || $0.url.absoluteString.localizedCaseInsensitiveContains(text)
        }
    }

    /// Up to `limit` different pages for the address bar to suggest: first
    /// those whose site starts with `text`, then those that contain it.
    func suggestions(for text: String, limit: Int = 6) -> [HistoryEntry] {
        let text = text.trimmingCharacters(in: .whitespaces).lowercased()
        guard !text.isEmpty else { return [] }
        var seen = Set<URL>()
        var starting: [HistoryEntry] = []
        var containing: [HistoryEntry] = []
        for entry in entries where !seen.contains(entry.url) {
            let site = Shields.site(of: entry.url) ?? ""
            if site.hasPrefix(text) {
                starting.append(entry)
            } else if entry.title.localizedCaseInsensitiveContains(text) || entry.url.absoluteString.lowercased().contains(text) {
                containing.append(entry)
            } else {
                continue
            }
            seen.insert(entry.url)
            if starting.count >= limit { break }
        }
        return Array((starting + containing).prefix(limit))
    }

    /// Writes once things settle, not on every page load.
    private func scheduleSave() {
        guard isPersistent, let fileURL else { return }
        saveTask?.cancel()
        saveTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 1_000_000_000)
            guard let self, !Task.isCancelled else { return }
            if let data = try? JSONEncoder().encode(self.entries) {
                try? data.write(to: fileURL, options: .atomic)
            }
        }
    }
}
