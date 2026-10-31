import SwiftUI

/// "Collect Cookies": the visits of this profile and of every profile, and
/// what they do: which sites, how many, every new profile, how many at once.
/// Saved as they change.
@MainActor
struct CookieCollectView: View {
    @ObservedObject var browser: BrowserModel
    @ObservedObject private var collector = CookieCollector.shared
    @State private var settings = CookieCollector.shared.settings
    @State private var sitesText = ""

    var body: some View {
        Form {
            Section {
                CookieCollectRow(profile: browser.profile)
            } header: {
                Text("This Profile")
            }

            Section {
                AllProfilesCollectRow(browser: browser)
            } header: {
                Text("All Profiles")
            }

            Section {
                Picker("Sites to Visit", selection: $settings.mine) {
                    Text("Popular Sites").tag(false)
                    Text("My Sites").tag(true)
                }
                if settings.mine {
                    TextEditor(text: $sitesText)
                        .font(.callout.monospaced())
                        .frame(minHeight: 140)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                } else {
                    Stepper(value: $settings.count, in: 1...CookieCollectSettings.maxSites, step: settings.count < 10 ? 1 : 5) {
                        Text("How many sites: \(settings.count)")
                    }
                }
            } header: {
                Text("Sites")
            } footer: {
                if settings.mine {
                    Text("One per line: an address (hespress.com) or a page (https://www.youtube.com/). They are visited in a new order each time.")
                } else {
                    Text("A new random mix each time: the world's, and those of the country of your time zone. Each site takes about 20 seconds.")
                }
            }

            Section {
                Toggle("Collect in Every New Profile", isOn: $settings.auto)
                Picker("At Once", selection: $settings.parallel) {
                    Text("All (up to \(CookieCollector.deviceLimit))").tag(0)
                    ForEach([1, 2, 3, 5, 10], id: \.self) { number in
                        Text(verbatim: "\(number)").tag(number)
                    }
                }
            } footer: {
                Text("A new profile starts collecting as soon as it is made, in the background; profiles made together collect together. “At Once” is how many profiles collect at the same time; the others wait their turn.")
            }

            Section {
                NavigationLink(destination: ProfileCookiesView(browser: browser)) {
                    Label("See Cookies", systemImage: "list.bullet.rectangle")
                }
            } footer: {
                Text("So that a site that checks finds a profile in daily use, not an empty one: Noor visits sites in a web view you don't see, in the profile's own cookies, with its own fingerprints and shields, while you use this profile or any other. It reads each page a little, scrolls, accepts the cookie banner, and sometimes opens another page of the site, as a person would. It never signs in or out, buys or downloads anything, and nothing goes into the history. Keep Noor open while it collects: iOS pauses pages in the background.")
            }
        }
        .navigationTitle("Collect Cookies")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            settings = collector.settings
            sitesText = settings.sites.map(CookieSites.plain).joined(separator: "\n")
        }
        .onChange(of: settings) { next in
            collector.save(next)
        }
        .onChange(of: sitesText) { text in
            settings.sites = CookieSites.normalize(text).map(\.absoluteString)
        }
    }
}

/// A profile's cookies: how far its collection is, or how many it has, and
/// Collect or Stop.
@MainActor
struct CookieCollectRow: View {
    let profile: Profile
    @ObservedObject private var collector = CookieCollector.shared
    @State private var counted: (cookies: Int, sites: Int)?

    var body: some View {
        let status = collector.status(for: profile)
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Collect Cookies")
                describe(status)
                    .font(.footnote)
                    .foregroundColor(.secondary)
                if status.running && !status.region.isEmpty {
                    Text("Sites of the world and of \(status.region).")
                        .font(.footnote)
                        .foregroundColor(.secondary)
                }
            }
            Spacer()
            if status.running || status.waiting {
                Button("Stop", role: .destructive) {
                    collector.stop(profile.id)
                }
                .buttonStyle(.bordered)
            } else {
                Button("Collect") {
                    collector.start([profile])
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .task(id: "\(profile.id)|\(status.running)|\(status.finished)|\(status.done)") {
            counted = await CookieCollector.count(profile)
        }
    }

    @ViewBuilder
    private func describe(_ status: CookieCollectStatus) -> some View {
        if status.waiting {
            Text("Waiting its turn (\(status.position) in line): \(collector.atOnce) profiles collect at a time.")
        } else if status.running && status.current.isEmpty {
            Text("Starting… \(status.cookies) cookies.")
        } else if status.running {
            Text("Visiting \(min(status.done + 1, status.total)) of \(status.total): \(status.current). \(status.cookies) cookies (+\(status.added)).")
        } else if status.finished && status.stopped {
            Text("Stopped: \(status.opened) of \(status.total) sites visited. This profile has \(status.cookies) cookies from \(status.sites) sites now (+\(status.added)).")
        } else if status.finished {
            Text("Done: \(status.opened) of \(status.total) sites visited. This profile has \(status.cookies) cookies from \(status.sites) sites now (+\(status.added)).")
        } else if let counted {
            Text("This profile has \(counted.cookies) cookies from \(counted.sites) sites.")
        } else {
            Text("Visits sites in this profile in the background, with its own fingerprints.")
        }
    }
}

/// Every profile's cookies at once, and which profiles are collecting or
/// waiting their turn.
@MainActor
private struct AllProfilesCollectRow: View {
    @ObservedObject var browser: BrowserModel
    @ObservedObject private var collector = CookieCollector.shared

    var body: some View {
        let running = browser.profiles.filter { collector.statuses[$0.id]?.running == true }
        let waiting = browser.profiles.filter { collector.statuses[$0.id]?.waiting == true }
        let busy = !running.isEmpty || !waiting.isEmpty
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 12) {
                Text("Every Profile")
                Spacer()
                if busy {
                    Button("Stop All", role: .destructive) {
                        collector.stopAll()
                    }
                    .buttonStyle(.bordered)
                } else {
                    Button("Collect in All") {
                        collector.start(browser.profiles)
                    }
                    .buttonStyle(.bordered)
                }
            }
            Group {
                if !busy {
                    Text("Every profile collects its cookies at the same time (\(collector.atOnce) at most, see “At Once”), each in the background with its own fingerprints.")
                }
                if !running.isEmpty {
                    Text("Collecting in \(running.count) profiles at once: \(names(running))")
                }
                if !waiting.isEmpty {
                    Text("Waiting their turn (\(collector.atOnce) at a time): \(names(waiting))")
                }
            }
            .font(.footnote)
            .foregroundColor(.secondary)
        }
    }

    /// A few names of a long list, and how many more.
    private func names(_ list: [Profile]) -> String {
        let shown = list.prefix(5).map(\.name).joined(separator: ", ")
        return list.count > 5 ? shown + " +\(list.count - 5)" : shown
    }
}
