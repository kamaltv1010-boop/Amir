import SwiftUI

struct Bookmark: Identifiable, Codable, Equatable {
    var id = UUID()
    var title: String
    var url: URL
}

/// A list of saved links (the bookmarks, or the pinned links), kept in
/// UserDefaults so it survives app restarts.
@MainActor
final class BookmarkStore: ObservableObject {
    @Published private(set) var bookmarks: [Bookmark] = []

    private let defaults: UserDefaults
    private let key: String

    init(key: String = "bookmarks", defaults: UserDefaults = .standard) {
        self.key = key
        self.defaults = defaults
        if let data = defaults.data(forKey: key),
           let saved = try? JSONDecoder().decode([Bookmark].self, from: data) {
            bookmarks = saved
        }
    }

    func contains(_ url: URL) -> Bool {
        bookmarks.contains { $0.url == url }
    }

    /// Adds the page, or removes it if it is already in the list.
    func toggle(title: String, url: URL) {
        if contains(url) {
            remove(url)
        } else {
            add(title: title, url: url)
        }
    }

    func add(title: String, url: URL) {
        guard !contains(url) else { return }
        let name = title.isEmpty ? (url.host ?? url.absoluteString) : title
        bookmarks.append(Bookmark(title: name, url: url))
        save()
    }

    func remove(_ url: URL) {
        bookmarks.removeAll { $0.url == url }
        save()
    }

    func remove(at offsets: IndexSet) {
        bookmarks.remove(atOffsets: offsets)
        save()
    }

    func move(from source: IndexSet, to destination: Int) {
        bookmarks.move(fromOffsets: source, toOffset: destination)
        save()
    }

    private func save() {
        guard let data = try? JSONEncoder().encode(bookmarks) else { return }
        defaults.set(data, forKey: key)
    }
}
