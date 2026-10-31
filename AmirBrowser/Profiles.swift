import Foundation
import WebKit

/// A browsing profile: its own cookies and website data, history, open tabs
/// and fingerprints, so one person's accounts, or one purpose, stay apart
/// from another's. Bookmarks, pinned links, extensions and the settings
/// are shared.
struct Profile: Identifiable, Codable, Equatable {
    let id: UUID
    var name: String

    /// The profile the app started with. It keeps the data and fingerprints
    /// of earlier versions, and can't be deleted.
    var isDefault: Bool { id == Profiles.defaultID }
}

/// The profiles, the one in use, and what each keeps.
enum Profiles {
    static let defaultID = UUID(uuidString: "00000000-0000-0000-0000-000000000001")!
    private static let listKey = "profiles"
    private static let currentKey = "currentProfile"
    /// In-memory website data stores: for every profile with "Clear
    /// Everything on Quit" on, and before iOS 17 (which brought persistent
    /// stores besides the default one) for the other profiles.
    private static var sessionStores: [UUID: WKWebsiteDataStore] = [:]

    /// Every profile, the default one first.
    static var all: [Profile] {
        get {
            var list: [Profile] = []
            if let data = UserDefaults.standard.data(forKey: listKey),
               let saved = try? JSONDecoder().decode([Profile].self, from: data) {
                list = saved
            }
            if !list.contains(where: \.isDefault) {
                list.insert(Profile(id: defaultID, name: String(localized: "Personal")), at: 0)
            }
            return list
        }
        set {
            if let data = try? JSONEncoder().encode(newValue) {
                UserDefaults.standard.set(data, forKey: listKey)
            }
        }
    }

    /// The profile in use.
    static var current: Profile {
        let all = all
        let id = UserDefaults.standard.string(forKey: currentKey).flatMap(UUID.init(uuidString:))
        return all.first { $0.id == id } ?? all[0]
    }

    static func select(_ profile: Profile) {
        UserDefaults.standard.set(profile.id.uuidString, forKey: currentKey)
    }

    @discardableResult
    static func add(named name: String) -> Profile {
        let profile = Profile(id: UUID(), name: name)
        all = all + [profile]
        return profile
    }

    /// The most profiles made at once.
    static let maxAtOnce = 100

    /// `count` new profiles at once (100 at most), named `name 1`, `name 2`…
    /// ("Profile 3", "Profile 4"… after the profiles there are), with
    /// numbers no profile has yet; the profile in use stays. The new ones.
    @discardableResult
    static func addMany(_ count: Int, named name: String) -> [Profile] {
        let wanted = max(0, min(maxAtOnce, count))
        guard wanted > 0 else { return [] }
        let defaultBase = String(localized: "Profile")
        var base = name.trimmingCharacters(in: .whitespacesAndNewlines)
        if let number = base.range(of: #"\s+\d+$"#, options: .regularExpression) {
            base.removeSubrange(number)
        }
        base = String(base.prefix(40))
        if base.isEmpty {
            base = defaultBase
        }
        let list = all
        var taken = Set(list.map(\.name))
        var highest = 0
        for profile in list where profile.name.hasPrefix(base + " ") {
            if let number = Int(profile.name.dropFirst(base.count + 1)) {
                highest = max(highest, number)
            }
        }
        var number = max(highest + 1, base == defaultBase ? list.count + 1 : 1)
        var made: [Profile] = []
        while made.count < wanted {
            let candidate = "\(base) \(number)"
            number += 1
            if taken.insert(candidate).inserted {
                made.append(Profile(id: UUID(), name: candidate))
            }
        }
        all = list + made
        return made
    }

    /// The UserDefaults key of a value kept per profile: `base` itself for
    /// the default profile, as earlier versions stored it, and a prefixed
    /// key for any other.
    static func key(_ base: String, for profile: Profile? = nil) -> String {
        let profile = profile ?? current
        return profile.isDefault ? base : "profile.\(profile.id.uuidString).\(base)"
    }

    /// The file a profile's history is saved in, in Application Support.
    static func historyFileName(for profile: Profile) -> String {
        profile.isDefault ? "History.json" : "History-\(profile.id.uuidString).json"
    }

    /// Whether every profile keeps its website data on the phone. Before iOS
    /// 17 only the default profile can; the others keep theirs while the
    /// app runs.
    static var keepsDataOfEveryProfile: Bool {
        if #available(iOS 17.0, *) {
            return true
        }
        return false
    }

    /// The website data store of a profile: the one kept on the phone, or
    /// with `inMemory` (Clear Everything on Quit) one that lasts while the
    /// app runs.
    static func dataStore(for profile: Profile, inMemory: Bool = false) -> WKWebsiteDataStore {
        if !inMemory {
            if profile.isDefault {
                return .default()
            }
            if #available(iOS 17.0, *) {
                return WKWebsiteDataStore(forIdentifier: profile.id)
            }
        }
        if let store = sessionStores[profile.id] {
            return store
        }
        let store = WKWebsiteDataStore.nonPersistent()
        sessionStores[profile.id] = store
        return store
    }

    /// The profiles besides the default one whose data is kept on the phone.
    static var storedProfiles: [Profile] {
        keepsDataOfEveryProfile ? all.filter { !$0.isDefault } : []
    }

    /// Deletes a profile with everything it kept: website data, history,
    /// remembered tabs and fingerprints. The default profile stays. Call it
    /// with no tab of the profile open, so its data store is free.
    static func delete(_ profile: Profile, completion: @escaping () -> Void) {
        guard !profile.isDefault else {
            completion()
            return
        }
        all = all.filter { $0.id != profile.id }
        if current.id == profile.id {
            select(all[0])
        }
        let defaults = UserDefaults.standard
        let prefix = "profile.\(profile.id.uuidString)."
        for key in defaults.dictionaryRepresentation().keys where key.hasPrefix(prefix) {
            defaults.removeObject(forKey: key)
        }
        if let folder = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first {
            try? FileManager.default.removeItem(at: folder.appendingPathComponent(historyFileName(for: profile)))
        }
        sessionStores[profile.id] = nil
        if #available(iOS 17.0, *) {
            // The store can only go once no web view uses it; the closed
            // tabs' views may take a moment to go away, so try again once.
            removeStore(for: profile.id, attempts: 2, completion: completion)
        } else {
            completion()
        }
    }

    /// Deletes every profile but the default one, with everything each
    /// kept, and selects the default profile. Call it with no tab of those
    /// profiles open.
    static func deleteAll(completion: @escaping () -> Void) {
        let doomed = all.filter { !$0.isDefault }
        let group = DispatchGroup()
        for profile in doomed {
            group.enter()
            delete(profile) { group.leave() }
        }
        group.notify(queue: .main, execute: completion)
    }

    @available(iOS 17.0, *)
    private static func removeStore(for id: UUID, attempts: Int, completion: @escaping () -> Void) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
            WKWebsiteDataStore.remove(forIdentifier: id) { error in
                DispatchQueue.main.async {
                    if error != nil, attempts > 1 {
                        removeStore(for: id, attempts: attempts - 1, completion: completion)
                    } else {
                        completion()
                    }
                }
            }
        }
    }
}
