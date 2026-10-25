import SwiftUI

/// Colors and small pieces of UI the screens share.
enum Theme {
    static let shields = Color.orange
    static let privateTint = Color(red: 0.48, green: 0.17, blue: 0.95)
    /// The indigo of the app icon.
    static let brandColor = Color(red: 0.16, green: 0.12, blue: 0.72)
    /// The app icon's background, from night blue to violet.
    static let brand = LinearGradient(
        colors: [Color(red: 0.04, green: 0.04, blue: 0.18), Color(red: 0.16, green: 0.12, blue: 0.72), Color(red: 0.48, green: 0.17, blue: 0.95)],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )

    /// A color for a site's letter icon, the same every time for that site.
    static func color(for site: String) -> Color {
        let palette: [Color] = [.blue, .purple, .pink, .orange, .green, .teal, .indigo, .red, .mint, .cyan]
        let sum = site.unicodeScalars.reduce(0) { ($0 &* 31 &+ Int($1.value)) & 0xffff }
        return palette[sum % palette.count]
    }

    /// "12 s", "3 min", "2 h" in the user's language.
    static func duration(_ seconds: TimeInterval) -> String {
        let formatter = DateComponentsFormatter()
        formatter.unitsStyle = .abbreviated
        formatter.maximumUnitCount = 1
        formatter.allowedUnits = seconds < 60 ? [.second] : [.second, .minute, .hour, .day]
        return formatter.string(from: seconds) ?? ""
    }
}

/// The colored square icons of the settings screens.
struct SettingsIcon: View {
    let systemName: String
    let color: Color

    var body: some View {
        Image(systemName: systemName)
            .font(.system(size: 14, weight: .semibold))
            .foregroundColor(.white)
            .frame(width: 29, height: 29)
            .background(color, in: RoundedRectangle(cornerRadius: 7, style: .continuous))
    }
}

/// A settings row title with its colored icon.
struct SettingsLabel: View {
    let title: LocalizedStringKey
    let systemName: String
    let color: Color

    init(_ title: LocalizedStringKey, systemName: String, color: Color) {
        self.title = title
        self.systemName = systemName
        self.color = color
    }

    var body: some View {
        Label {
            Text(title)
        } icon: {
            SettingsIcon(systemName: systemName, color: color)
        }
    }
}

/// A site's first letter in a colored circle, for sites without a picture.
struct SiteIcon: View {
    let url: URL?
    var size: CGFloat = 52

    var body: some View {
        let site = Shields.site(of: url) ?? ""
        Text(site.first.map { String($0).uppercased() } ?? "•")
            .font(.system(size: size * 0.42, weight: .bold, design: .rounded))
            .foregroundColor(.white)
            .frame(width: size, height: size)
            .background(Theme.color(for: site), in: RoundedRectangle(cornerRadius: size * 0.28, style: .continuous))
    }
}

/// The tabs button: a rounded square with the number of tabs in it.
struct TabCountIcon: View {
    let count: Int

    var body: some View {
        Text(verbatim: count > 99 ? "∞" : "\(count)")
            .font(.system(size: 12, weight: .bold, design: .rounded))
            .frame(width: 22, height: 22)
            .overlay(RoundedRectangle(cornerRadius: 5, style: .continuous).stroke(lineWidth: 2))
    }
}
