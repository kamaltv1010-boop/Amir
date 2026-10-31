import SwiftUI
import UIKit

/// The profiles as menu items, for the ⋯ menu and the start page: tap one
/// to switch to it, make a new one or many at once, or delete every one but
/// the first.
struct ProfileMenuItems: View {
    @ObservedObject var browser: BrowserModel
    /// Called with the profile just switched to.
    var didSwitch: (Profile) -> Void = { _ in }
    /// Called with the profiles just made at once.
    var didMake: ([Profile]) -> Void = { _ in }

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
            Button {
                ProfilePrompts.newProfiles(in: browser, didMake: didMake)
            } label: {
                Label("Create Multiple Profiles", systemImage: "plus.square.on.square")
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

    /// Asks how many profiles to make, and their name, then makes them, each
    /// with its own cookies and fingerprints ("Profile 3", "Profile 4"…, or
    /// the name given, numbered); the profile in use stays.
    static func newProfiles(in browser: BrowserModel, didMake: @escaping ([Profile]) -> Void = { _ in }) {
        let alert = UIAlertController(
            title: String(localized: "Create Multiple Profiles"),
            message: String(localized: "Up to 100 at once, each with its own cookies and fingerprints, named “Profile 3”, “Profile 4”… or after the name you give, numbered."),
            preferredStyle: .alert
        )
        alert.addTextField { field in
            field.placeholder = String(localized: "How many")
            field.text = "10"
            field.keyboardType = .numberPad
        }
        alert.addTextField { field in
            field.placeholder = String(localized: "Name")
            field.text = String(localized: "Profile")
            field.autocapitalizationType = .words
            field.clearButtonMode = .whileEditing
        }
        alert.addAction(UIAlertAction(title: String(localized: "Cancel"), style: .cancel))
        alert.addAction(UIAlertAction(title: String(localized: "Create"), style: .default) { _ in
            let count = number(in: alert.textFields?.first?.text ?? "") ?? 0
            let name = alert.textFields?.last?.text ?? ""
            let made = browser.createProfiles(count: count, named: name)
            if !made.isEmpty {
                didMake(made)
            }
        })
        Presenter.presentSoon(alert)
    }

    /// A number as typed, in Western or Arabic digits.
    private static func number(in text: String) -> Int? {
        let western = String(text.unicodeScalars.map { scalar -> Character in
            switch scalar.value {
            case 0x0660...0x0669: return Character(UnicodeScalar(scalar.value - 0x0660 + 0x30) ?? "0")
            case 0x06F0...0x06F9: return Character(UnicodeScalar(scalar.value - 0x06F0 + 0x30) ?? "0")
            default: return Character(scalar)
            }
        })
        return Int(western.trimmingCharacters(in: .whitespacesAndNewlines))
    }

    /// Asks, then deletes `profile` with everything it kept; with "Replace a
    /// Profile When Deleted" on, a new one takes its place, and says which
    /// (see BrowserModel.deleteProfile). Calls `didDelete` with the new one.
    static func confirmDelete(_ profile: Profile, in browser: BrowserModel, didDelete: @escaping (Profile?) -> Void = { _ in }) {
        guard !profile.isDefault else { return }
        let name = profile.name
        var message = String(localized: "This deletes the profile’s cookies, website data, history and tabs. Bookmarks and pinned links are kept.")
        if UserDefaults.standard.bool(forKey: BrowserModel.replaceDeletedKey) {
            let next = Profiles.nextInSeries(name)
            message += "\n\n" + String(localized: "“\(next)” takes its place, with new fingerprints and no cookies.")
        }
        let alert = UIAlertController(title: String(localized: "Delete “\(name)”?"), message: message, preferredStyle: .actionSheet)
        alert.addAction(UIAlertAction(title: String(localized: "Delete Profile"), style: .destructive) { _ in
            didDelete(browser.deleteProfile(profile))
        })
        alert.addAction(UIAlertAction(title: String(localized: "Cancel"), style: .cancel))
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
