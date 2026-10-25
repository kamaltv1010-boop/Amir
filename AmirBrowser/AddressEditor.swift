import SwiftUI
import UIKit

/// Typing an address or a search, over the page: the text field sits above
/// the keyboard, with suggestions from bookmarks and history above it.
struct AddressEditor: View {
    @ObservedObject var tab: BrowserTab
    @ObservedObject var history: HistoryStore
    @ObservedObject var bookmarks: BookmarkStore
    let searchEngine: SearchEngine
    @Binding var isPresented: Bool

    @State private var text = ""

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 0) {
                    ForEach(suggestions) { suggestion in
                        Button {
                            open(suggestion.url)
                        } label: {
                            SuggestionRow(suggestion: suggestion)
                        }
                        .buttonStyle(.plain)
                        Divider()
                            .padding(.leading, 56)
                    }
                }
            }
            .frame(maxHeight: .infinity)

            HStack(spacing: 10) {
                HStack(spacing: 6) {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(.secondary)
                    AddressField(
                        text: $text,
                        placeholder: String(localized: "Search or enter address"),
                        onSubmit: submit
                    )
                    .frame(height: 22)
                }
                .padding(.horizontal, 12)
                .frame(height: 44)
                .background(Color(.tertiarySystemFill), in: RoundedRectangle(cornerRadius: 14, style: .continuous))

                Button("Cancel") {
                    isPresented = false
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(.bar)
        }
        .background(Color(.systemBackground).ignoresSafeArea())
        .environment(\.colorScheme, tab.isPrivate ? .dark : colorScheme)
        .onAppear {
            text = tab.displayedURL?.absoluteString ?? ""
        }
    }

    @Environment(\.colorScheme) private var colorScheme

    private var suggestions: [Suggestion] {
        let query = text.trimmingCharacters(in: .whitespaces)
        guard !query.isEmpty, query != tab.displayedURL?.absoluteString else {
            // Before typing: the bookmarks.
            return bookmarks.bookmarks.prefix(8).map { Suggestion(kind: .bookmark, title: $0.title, url: $0.url) }
        }
        var list: [Suggestion] = []
        if let url = AddressResolver.url(for: query, searchEngine: searchEngine) {
            let isSearch = searchEngine.searchURL(for: query) == url
            list.append(Suggestion(kind: isSearch ? .search : .address, title: query, url: url))
        }
        let matchingBookmarks = bookmarks.bookmarks.filter {
            $0.title.localizedCaseInsensitiveContains(query) || $0.url.absoluteString.localizedCaseInsensitiveContains(query)
        }
        list += matchingBookmarks.prefix(3).map { Suggestion(kind: .bookmark, title: $0.title, url: $0.url) }
        if !tab.isPrivate {
            let shown = Set(list.map(\.url))
            list += history.suggestions(for: query)
                .filter { !shown.contains($0.url) }
                .map { Suggestion(kind: .history, title: $0.title, url: $0.url) }
        }
        return list
    }

    private func submit() {
        tab.open(text, searchEngine: searchEngine)
        isPresented = false
    }

    private func open(_ url: URL) {
        tab.load(url)
        isPresented = false
    }
}

private struct Suggestion: Identifiable {
    enum Kind {
        case search, address, bookmark, history
    }

    let kind: Kind
    let title: String
    let url: URL

    var id: String { "\(kind)|\(url.absoluteString)" }
}

private struct SuggestionRow: View {
    let suggestion: Suggestion

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 15, weight: .semibold))
                .foregroundColor(color)
                .frame(width: 32, height: 32)
                .background(color.opacity(0.15), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            VStack(alignment: .leading, spacing: 2) {
                Text(verbatim: suggestion.title)
                    .lineLimit(1)
                    .foregroundColor(.primary)
                if suggestion.kind != .search {
                    Text(verbatim: suggestion.url.absoluteString)
                        .font(.caption)
                        .lineLimit(1)
                        .foregroundColor(.secondary)
                }
            }
            Spacer(minLength: 0)
            Image(systemName: "arrow.up.left")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .contentShape(Rectangle())
    }

    private var icon: String {
        switch suggestion.kind {
        case .search: return "magnifyingglass"
        case .address: return "globe"
        case .bookmark: return "star.fill"
        case .history: return "clock"
        }
    }

    private var color: Color {
        switch suggestion.kind {
        case .search, .address: return .accentColor
        case .bookmark: return .yellow
        case .history: return .gray
        }
    }
}

/// A UIKit text field, because SwiftUI's can't select all its text when it
/// gets focus, which lets typing replace the current address.
private struct AddressField: UIViewRepresentable {
    @Binding var text: String
    let placeholder: String
    let onSubmit: () -> Void

    func makeUIView(context: Context) -> UITextField {
        let field = UITextField()
        field.placeholder = placeholder
        field.text = text
        field.keyboardType = .webSearch
        field.returnKeyType = .go
        field.autocapitalizationType = .none
        field.autocorrectionType = .no
        field.spellCheckingType = .no
        field.clearButtonMode = .whileEditing
        field.textContentType = .URL
        field.font = .preferredFont(forTextStyle: .body)
        field.adjustsFontForContentSizeCategory = true
        field.setContentHuggingPriority(.defaultLow, for: .horizontal)
        field.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        field.delegate = context.coordinator
        field.addTarget(context.coordinator, action: #selector(Coordinator.textChanged(_:)), for: .editingChanged)
        DispatchQueue.main.async {
            field.becomeFirstResponder()
            DispatchQueue.main.async {
                field.selectAll(nil)
            }
        }
        return field
    }

    func updateUIView(_ field: UITextField, context: Context) {
        context.coordinator.parent = self
        if field.text != text {
            field.text = text
        }
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(parent: self)
    }

    @MainActor
    final class Coordinator: NSObject, UITextFieldDelegate {
        var parent: AddressField

        init(parent: AddressField) {
            self.parent = parent
        }

        @objc func textChanged(_ field: UITextField) {
            parent.text = field.text ?? ""
        }

        func textFieldShouldReturn(_ textField: UITextField) -> Bool {
            parent.onSubmit()
            return false
        }
    }
}
