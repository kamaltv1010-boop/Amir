import SwiftUI
import UIKit

/// The profiles as menu items, for the ⋯ menu and the start page: tap one
/// to switch to it, make a new one, or delete every one but the first.
struct ProfileMenuItems: View {
    @ObservedObject var browser: BrowserModel
    /// Called with the profile just switched to.
    var didSwitch: (Profile) -> Void = { _ in }

    var body: some View {
        Section {
            ForEach(browser.profiles) { profile in
                Button {
                    guard profile.id != browser.profile.id else { return }
                    browser.switchProfile(to: profile)
                    didSwitch(profile)
                } label: {
                    if profile.id == browser.profile.id {
                        Label {
                            Text(verbatim: profile.name)
                        } icon: {
                            Image(systemName: "checkmark")
                        }
                    } else {
                        Text(verbatim: profile.name)
                    }
                }
            }
        }
        Section {
            Button {
                ProfilePrompts.newProfile(in: browser)
            } label: {
                Label("New Profile", systemImage: "plus")
            }
            if browser.profiles.count > 1 {
                Button(role: .destructive) {
                    ProfilePrompts.confirmDeleteAll(in: browser)
                } label: {
                    Label("Delete All Profiles", systemImage: "trash")
                }
            }
        }
    }
}

/// The alerts about profiles, shown above whatever is on screen: a menu
/// that is closing, the settings sheet or the start page.
@MainActor
enum ProfilePrompts {
    /// Asks for a name, then makes the profile and switches to it.
    static func newProfile(in browser: BrowserModel) {
        let number = browser.profiles.count + 1
        let alert = UIAlertController(title: String(localized: "New Profile"), message: nil, preferredStyle: .alert)
        alert.addTextField { field in
            field.placeholder = String(localized: "Name")
            field.text = String(localized: "Profile \(number)")
            field.autocapitalizationType = .words
            field.clearButtonMode = .whileEditing
        }
        alert.addAction(UIAlertAction(title: String(localized: "Cancel"), style: .cancel))
        alert.addAction(UIAlertAction(title: String(localized: "Create"), style: .default) { _ in
            let typed = alert.textFields?.first?.text?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            browser.createProfile(named: typed.isEmpty ? String(localized: "Profile \(number)") : typed)
        })
        Presenter.presentSoon(alert)
    }

    /// Asks, then deletes every profile but the first with everything each
    /// kept, and shows the first profile.
    static func confirmDeleteAll(in browser: BrowserModel) {
        let kept = browser.profiles.first { $0.isDefault } ?? browser.profiles[0]
        let alert = UIAlertController(
            title: String(localized: "Delete All Profiles?"),
            message: String(localized: "This deletes every profile except “\(kept.name)”, with its cookies, website data, history and tabs. Bookmarks and pinned links are kept."),
            preferredStyle: .actionSheet
        )
        alert.addAction(UIAlertAction(title: String(localized: "Delete All Profiles"), style: .destructive) { _ in
            browser.deleteAllProfiles()
        })
        alert.addAction(UIAlertAction(title: String(localized: "Cancel"), style: .cancel))
        Presenter.presentSoon(alert)
    }
}
