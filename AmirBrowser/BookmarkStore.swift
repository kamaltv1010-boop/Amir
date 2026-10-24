import SwiftUI

struct Bookmark: Identifiable, Codable, Equatable {
    var id = UUID()
    var title: String
    var url: URL
}

/// The bookmark list, saved in UserDefaults so it survives app restarts.
@MainActor
final class BookmarkStore: ObservableObject {
    @Published private(set) var bookmarks: [Bookmark] = []

    private let defaults: UserDefaults
    private static let key = "bookmarks"

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        if let data = defaults.data(forKey: Self.key),
           let saved = try? JSONDecoder().decode([Bookmark].self, from: data) {
            bookmarks = saved
        }
    }

    func contains(_ url: URL) -> Bool {
        bookmarks.contains { $0.url == url }
    }

    /// Adds the page, or removes it if it is already bookmarked.
    func toggle(title: String, url: URL) {
        if contains(url) {
            bookmarks.removeAll { $0.url == url }
        } else {
            let name = title.isEmpty ? (url.host ?? url.absoluteString) : title
            bookmarks.append(Bookmark(title: name, url: url))
        }
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
        defaults.set(data, forKey: Self.key)
    }
}
