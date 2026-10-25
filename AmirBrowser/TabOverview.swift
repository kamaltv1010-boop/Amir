import SwiftUI

/// All open tabs as cards, like Safari: normal tabs, or private ones.
struct TabOverview: View {
    @ObservedObject var browser: BrowserModel
    @Binding var isPresented: Bool

    @State private var showsPrivate = false
    @State private var isConfirmingCloseAll = false

    private let columns = [GridItem(.flexible(), spacing: 14), GridItem(.flexible(), spacing: 14)]

    var body: some View {
        VStack(spacing: 0) {
            Picker("Tabs", selection: $showsPrivate) {
                Text("Tabs").tag(false)
                Text("Private").tag(true)
            }
            .pickerStyle(.segmented)
            .padding(.horizontal)
            .padding(.vertical, 10)

            ScrollView {
                if shownTabs.isEmpty {
                    emptyPrivate
                } else {
                    LazyVGrid(columns: columns, spacing: 14) {
                        ForEach(shownTabs) { tab in
                            TabCard(tab: tab, isSelected: tab === browser.selectedTab) {
                                browser.select(tab)
                                isPresented = false
                            } onClose: {
                                withAnimation {
                                    browser.close(tab)
                                }
                            }
                        }
                    }
                    .padding(14)
                }
            }

            HStack {
                Button(role: .destructive) {
                    isConfirmingCloseAll = true
                } label: {
                    Text("Close All")
                }
                .disabled(shownTabs.isEmpty)

                Spacer()

                Button {
                    browser.newTab(isPrivate: showsPrivate)
                    isPresented = false
                } label: {
                    Image(systemName: "plus")
                        .font(.system(size: 22, weight: .medium))
                        .frame(width: 44, height: 44)
                }
                .accessibilityLabel(Text("New Tab"))

                Spacer()

                Button {
                    // Keep showing a tab of the kind the user chose.
                    if let tab = shownTabs.last, browser.selectedTab.isPrivate != showsPrivate {
                        browser.select(tab)
                    }
                    isPresented = false
                } label: {
                    Text("Done")
                        .fontWeight(.semibold)
                }
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 6)
            .background(.bar)
        }
        .background(Color(.systemGroupedBackground).ignoresSafeArea())
        .environment(\.colorScheme, showsPrivate ? .dark : colorScheme)
        .confirmationDialog(
            showsPrivate ? "Close All Private Tabs?" : "Close All Tabs?",
            isPresented: $isConfirmingCloseAll,
            titleVisibility: .visible
        ) {
            Button("Close All", role: .destructive) {
                withAnimation {
                    browser.closeAll(isPrivate: showsPrivate)
                }
            }
        }
        .onAppear {
            showsPrivate = browser.selectedTab.isPrivate
        }
    }

    @Environment(\.colorScheme) private var colorScheme

    private var shownTabs: [BrowserTab] {
        showsPrivate ? browser.privateTabs : browser.tabs
    }

    private var emptyPrivate: some View {
        VStack(spacing: 12) {
            Image(systemName: "eyeglasses")
                .font(.system(size: 44))
                .foregroundColor(Theme.privateTint)
            Text("Private Browsing")
                .font(.title3.weight(.bold))
            Text("Pages you open in private tabs aren't saved in your history, and their cookies and website data are deleted when you close the last private tab.")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            Button {
                browser.newTab(isPrivate: true)
                isPresented = false
            } label: {
                Label("New Private Tab", systemImage: "plus")
            }
            .buttonStyle(.borderedProminent)
            .tint(Theme.privateTint)
        }
        .padding(32)
        .frame(maxWidth: .infinity)
        .padding(.top, 60)
    }
}

/// A tab's card: its title, a close button and a picture of the page.
private struct TabCard: View {
    @ObservedObject var tab: BrowserTab
    let isSelected: Bool
    let onSelect: () -> Void
    let onClose: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 6) {
                if tab.isBlank {
                    Image(systemName: "star.circle.fill")
                        .foregroundColor(.accentColor)
                } else {
                    SiteIcon(url: tab.displayedURL, size: 18)
                }
                Text(verbatim: tab.isBlank ? String(localized: "Start Page") : tab.displayTitle)
                    .font(.caption.weight(.semibold))
                    .lineLimit(1)
                Spacer(minLength: 0)
                Button(action: onClose) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 18))
                        .symbolRenderingMode(.hierarchical)
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(Text("Close Tab"))
            }
            .padding(.horizontal, 8)
            .frame(height: 34)
            .background(Color(.secondarySystemGroupedBackground))

            Color(.systemBackground)
                .frame(height: 200)
                .overlay(alignment: .top) {
                    if let snapshot = tab.snapshot, !tab.isBlank {
                        Image(uiImage: snapshot)
                            .resizable()
                            .scaledToFill()
                    } else if tab.isBlank {
                        Image(systemName: "globe")
                            .font(.system(size: 36))
                            .foregroundStyle(Theme.brand)
                            .frame(maxHeight: .infinity)
                    } else {
                        SiteIcon(url: tab.displayedURL, size: 56)
                            .frame(maxHeight: .infinity)
                    }
                }
                .clipped()
        }
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(isSelected ? (tab.isPrivate ? Theme.privateTint : Color.accentColor) : Color(.separator), lineWidth: isSelected ? 3 : 0.5)
        )
        .shadow(color: .black.opacity(0.12), radius: 6, y: 3)
        .contentShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .onTapGesture(perform: onSelect)
        .contextMenu {
            Button(role: .destructive, action: onClose) {
                Label("Close Tab", systemImage: "xmark")
            }
        }
    }
}
