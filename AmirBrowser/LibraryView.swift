import SwiftUI

/// Bookmarks and history, one at a time.
struct LibraryView: View {
    @ObservedObject var bookmarks: BookmarkStore
    @ObservedObject var history: HistoryStore
    let onSelect: @MainActor (URL) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var page = Page.bookmarks
    @State private var query = ""
    @State private var isConfirmingClear = false

    private enum Page {
        case bookmarks, history
    }

    var body: some View {
        NavigationView {
            Group {
                switch page {
                case .bookmarks:
                    BookmarkList(store: bookmarks, open: open)
                case .history:
                    HistoryList(history: history, query: $query, open: open)
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Picker("Library", selection: $page) {
                        Text("Bookmarks").tag(Page.bookmarks)
                        Text("History").tag(Page.history)
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 220)
                }
                ToolbarItem(placement: .navigationBarLeading) {
                    switch page {
                    case .bookmarks:
                        if !bookmarks.bookmarks.isEmpty {
                            EditButton()
                        }
                    case .history:
                        Button("Clear", role: .destructive) {
                            isConfirmingClear = true
                        }
                        .disabled(history.entries.isEmpty)
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
            .confirmationDialog("Clear History?", isPresented: $isConfirmingClear, titleVisibility: .visible) {
                Button("Clear History", role: .destructive) {
                    history.clear()
                }
            }
        }
        .navigationViewStyle(.stack)
    }

    private func open(_ url: URL) {
        onSelect(url)
        dismiss()
    }
}

private struct BookmarkList: View {
    @ObservedObject var store: BookmarkStore
    let open: (URL) -> Void

    var body: some View {
        if store.bookmarks.isEmpty {
            EmptyLibrary(
                systemName: "star",
                title: "No bookmarks yet",
                message: "Tap ⋯ then “Add Bookmark” to save the current page."
            )
        } else {
            List {
                ForEach(store.bookmarks) { bookmark in
                    Button {
                        open(bookmark.url)
                    } label: {
                        LibraryRow(title: bookmark.title, url: bookmark.url, detail: nil)
                    }
                }
                .onDelete { store.remove(at: $0) }
                .onMove { store.move(from: $0, to: $1) }
            }
        }
    }
}

private struct HistoryList: View {
    @ObservedObject var history: HistoryStore
    @Binding var query: String
    let open: (URL) -> Void

    var body: some View {
        Group {
            if history.entries.isEmpty {
                EmptyLibrary(
                    systemName: "clock",
                    title: "No history yet",
                    message: "Pages you visit in normal tabs appear here."
                )
            } else {
                List {
                    ForEach(days) { group in
                        Section(header: Text(Self.dayFormatter.string(from: group.day))) {
                            ForEach(group.entries) { entry in
                                Button {
                                    open(entry.url)
                                } label: {
                                    LibraryRow(
                                        title: entry.title,
                                        url: entry.url,
                                        detail: Self.timeFormatter.string(from: entry.date)
                                    )
                                }
                                .swipeActions {
                                    Button(role: .destructive) {
                                        history.remove(entry)
                                    } label: {
                                        Label("Delete", systemImage: "trash")
                                    }
                                }
                            }
                        }
                    }
                }
                .listStyle(.plain)
            }
        }
        .searchable(text: $query, prompt: Text("Search History"))
    }

    private struct Day: Identifiable {
        let day: Date
        var entries: [HistoryEntry]

        var id: Date { day }
    }

    /// The matching entries by day, newest first.
    private var days: [Day] {
        let calendar = Calendar.current
        var groups: [Day] = []
        for entry in history.search(query) {
            let day = calendar.startOfDay(for: entry.date)
            if groups.last?.day == day {
                groups[groups.count - 1].entries.append(entry)
            } else {
                groups.append(Day(day: day, entries: [entry]))
            }
        }
        return groups
    }

    /// "Today", "Yesterday" or the date.
    private static let dayFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateStyle = .full
        formatter.timeStyle = .none
        formatter.doesRelativeDateFormatting = true
        return formatter
    }()

    private static let timeFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateStyle = .none
        formatter.timeStyle = .short
        return formatter
    }()
}

private struct LibraryRow: View {
    let title: String
    let url: URL
    let detail: String?

    var body: some View {
        HStack(spacing: 12) {
            SiteIcon(url: url, size: 34)
            VStack(alignment: .leading, spacing: 2) {
                Text(verbatim: title)
                    .foregroundColor(.primary)
                    .lineLimit(1)
                Text(verbatim: Shields.site(of: url) ?? url.absoluteString)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(1)
            }
            Spacer(minLength: 0)
            if let detail {
                Text(verbatim: detail)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
    }
}

private struct EmptyLibrary: View {
    let systemName: String
    let title: LocalizedStringKey
    let message: LocalizedStringKey

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: systemName)
                .font(.system(size: 40))
                .foregroundColor(.secondary)
            Text(title)
                .font(.headline)
            Text(message)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
