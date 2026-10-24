import SwiftUI

struct BookmarksView: View {
    @ObservedObject var store: BookmarkStore
    let onSelect: @MainActor (URL) -> Void

    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationView {
            Group {
                if store.bookmarks.isEmpty {
                    emptyState
                } else {
                    list
                }
            }
            .navigationTitle("Bookmarks")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    if !store.bookmarks.isEmpty {
                        EditButton()
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
        .navigationViewStyle(.stack)
    }

    private var list: some View {
        List {
            ForEach(store.bookmarks) { bookmark in
                Button {
                    onSelect(bookmark.url)
                    dismiss()
                } label: {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(bookmark.title)
                            .foregroundColor(.primary)
                            .lineLimit(1)
                        Text(bookmark.url.absoluteString)
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                    }
                }
            }
            .onDelete { store.remove(at: $0) }
            .onMove { store.move(from: $0, to: $1) }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 12) {
            Image(systemName: "star")
                .font(.system(size: 40))
                .foregroundColor(.secondary)
            Text("No bookmarks yet")
                .font(.headline)
            Text("Tap ⋯ then “Add Bookmark” to save the current page.")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(32)
    }
}
