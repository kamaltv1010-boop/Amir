import SwiftUI

/// What a new tab shows: a search field, privacy stats like Brave's, and
/// the bookmarks as favorites.
struct StartPage: View {
    @ObservedObject var stats: PrivacyStats
    @ObservedObject var bookmarks: BookmarkStore
    let isPrivate: Bool
    let onSearch: () -> Void
    let onOpen: (URL) -> Void

    private let columns = [GridItem(.adaptive(minimum: 72, maximum: 96), spacing: 12)]

    var body: some View {
        ScrollView {
            VStack(spacing: 22) {
                header
                searchField
                if isPrivate {
                    privateCard
                } else {
                    statsCard
                }
                favorites
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 28)
            .frame(maxWidth: 560)
            .frame(maxWidth: .infinity)
        }
        .background(background.ignoresSafeArea())
    }

    private var background: some View {
        ZStack {
            Color(.systemGroupedBackground)
            LinearGradient(
                colors: [(isPrivate ? Theme.privateTint : Color.accentColor).opacity(0.18), .clear],
                startPoint: .top,
                endPoint: .center
            )
        }
    }

    private var header: some View {
        VStack(spacing: 10) {
            Image(systemName: isPrivate ? "eyeglasses" : "globe")
                .font(.system(size: 30, weight: .semibold))
                .foregroundColor(.white)
                .frame(width: 64, height: 64)
                .background(Theme.brand, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                .shadow(color: .black.opacity(0.15), radius: 8, y: 4)
            Text(isPrivate ? "Private Browsing" : "Amir")
                .font(.system(.largeTitle, design: .rounded).weight(.bold))
        }
    }

    private var searchField: some View {
        Button(action: onSearch) {
            HStack(spacing: 8) {
                Image(systemName: "magnifyingglass")
                Text("Search or enter address")
                Spacer()
            }
            .foregroundColor(.secondary)
            .padding(.horizontal, 16)
            .frame(height: 50)
            .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .shadow(color: .black.opacity(0.06), radius: 6, y: 2)
        }
        .buttonStyle(.plain)
    }

    private var statsCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Privacy Stats", systemImage: "shield.fill")
                .font(.subheadline.weight(.semibold))
                .foregroundColor(Theme.shields)
            HStack(alignment: .top, spacing: 8) {
                stat(value: stats.trackersBlocked.formatted(), title: "Trackers blocked", color: Theme.shields)
                stat(value: stats.httpsUpgrades.formatted(), title: "HTTPS upgrades", color: .green)
                stat(value: Theme.duration(stats.timeSaved), title: "Time saved", color: .accentColor)
            }
        }
        .padding(16)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    private func stat(value: String, title: LocalizedStringKey, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(verbatim: value)
                .font(.system(.title2, design: .rounded).weight(.bold))
                .foregroundColor(color)
                .lineLimit(1)
                .minimumScaleFactor(0.6)
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var privateCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Private tabs", systemImage: "eyeglasses")
                .font(.subheadline.weight(.semibold))
                .foregroundColor(Theme.privateTint)
            Text("Pages you open in private tabs aren't saved in your history, and their cookies and website data are deleted when you close the last private tab. Extensions don't run here.")
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    @ViewBuilder
    private var favorites: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Favorites")
                .font(.title3.weight(.bold))
            if bookmarks.bookmarks.isEmpty {
                Text("Your bookmarks appear here. Add one from the ⋯ menu.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            } else {
                LazyVGrid(columns: columns, alignment: .leading, spacing: 16) {
                    ForEach(bookmarks.bookmarks.prefix(16)) { bookmark in
                        Button {
                            onOpen(bookmark.url)
                        } label: {
                            VStack(spacing: 6) {
                                SiteIcon(url: bookmark.url)
                                Text(verbatim: bookmark.title)
                                    .font(.caption)
                                    .foregroundColor(.primary)
                                    .lineLimit(1)
                            }
                            .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.plain)
                        .contextMenu {
                            Button(role: .destructive) {
                                bookmarks.remove(bookmark.url)
                            } label: {
                                Label("Remove Bookmark", systemImage: "star.slash")
                            }
                        }
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
