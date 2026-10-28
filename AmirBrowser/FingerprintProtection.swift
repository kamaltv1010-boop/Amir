import SwiftUI
import WebKit

/// Fingerprint protection, in the spirit of Brave's "farbling". Pages can
/// recognize a device from what it draws (canvas, WebGL), how it renders
/// audio, the exact sizes it lays out text and elements at (ClientRects), its
/// screen size and its user agent, even without cookies. With a protection
/// on, pages read invisibly changed pixels, samples and sizes, or a common
/// screen size and user agent, so these no longer identify the device.
///
/// Every kind has its own switch and its own seed. A site sees stable values
/// until the seed changes, which keeps sites that read twice and compare
/// working; a new seed gives every site new values for that kind. Each
/// profile has its own seeds.
enum FingerprintProtection {
    enum Kind: String, CaseIterable, Identifiable {
        case canvas, webGL, audio, clientRects, screen, userAgent

        var id: Self { self }

        var enabledKey: String {
            self == .canvas ? "canvasProtection" : "protection.\(rawValue)"
        }

        /// The key of this kind's seed, in the profile in use.
        fileprivate var seedKey: String {
            Profiles.key(self == .canvas ? "canvasSeed" : "seed.\(rawValue)")
        }

        var title: LocalizedStringKey {
            switch self {
            case .canvas: return "Canvas"
            case .webGL: return "WebGL"
            case .audio: return "Audio"
            case .clientRects: return "ClientRects"
            case .screen: return "Screen Size"
            case .userAgent: return "User Agent"
            }
        }

        var newTitle: LocalizedStringKey {
            switch self {
            case .canvas: return "New Canvas Fingerprint"
            case .webGL: return "New WebGL Fingerprint"
            case .audio: return "New Audio Fingerprint"
            case .clientRects: return "New ClientRects Fingerprint"
            case .screen: return "New Screen Size"
            case .userAgent: return "New User Agent"
            }
        }

        var changedMessage: LocalizedStringKey {
            switch self {
            case .canvas: return "Canvas fingerprint changed"
            case .webGL: return "WebGL fingerprint changed"
            case .audio: return "Audio fingerprint changed"
            case .clientRects: return "ClientRects fingerprint changed"
            case .screen: return "Screen size changed"
            case .userAgent: return "User agent changed"
            }
        }

        var symbol: String {
            switch self {
            case .canvas: return "paintbrush"
            case .webGL: return "cube"
            case .audio: return "waveform"
            case .clientRects: return "ruler"
            case .screen: return "iphone"
            case .userAgent: return "globe"
            }
        }
    }

    static func isEnabled(_ kind: Kind) -> Bool {
        UserDefaults.standard.object(forKey: kind.enabledKey) as? Bool ?? true
    }

    /// Whether pages see a changed or common value for `kind`. iPad mode
    /// always shows an iPad's user agent, even with that protection off.
    static func isActive(_ kind: Kind) -> Bool {
        isEnabled(kind) || (kind == .userAgent && isIPadMode)
    }

    static func seed(_ kind: Kind) -> UInt32 {
        if let saved = UserDefaults.standard.object(forKey: kind.seedKey) as? Int {
            return UInt32(truncatingIfNeeded: saved)
        }
        return newSeed(kind)
    }

    @discardableResult
    static func newSeed(_ kind: Kind) -> UInt32 {
        let old = UserDefaults.standard.object(forKey: kind.seedKey) as? Int
        // A new screen size or user agent must actually differ, when there
        // is another one to pick.
        let canChange = choiceCount(for: kind) > 1
        var seed: UInt32
        repeat {
            seed = .random(in: .min ... .max)
        } while canChange && old.map { visibleValue(UInt32(truncatingIfNeeded: $0), for: kind) == visibleValue(seed, for: kind) } ?? false
        UserDefaults.standard.set(Int(seed), forKey: kind.seedKey)
        return seed
    }

    /// New seeds for `kinds`. Changing the screen size and the user agent
    /// together picks one real device for both, so they match.
    static func newSeeds(_ kinds: [Kind]) {
        kinds.forEach { newSeed($0) }
        if kinds.contains(.screen) && kinds.contains(.userAgent) {
            matchScreenToUserAgent()
        }
    }

    private static func matchScreenToUserAgent() {
        UserDefaults.standard.set(Int(seed(.userAgent)), forKey: Kind.screen.seedKey)
    }

    /// Changes whenever a switch, a seed or iPad mode changes.
    static var signature: String {
        Kind.allCases.map { "\(isEnabled($0)):\(seed($0))" }.joined(separator: ",") + ",iPad:\(isIPadMode)"
    }

    // MARK: - iPad mode

    /// The UserDefaults key of iPad mode, in which pages see one of the
    /// `iPads` instead of an iPhone.
    static let iPadModeKey = "iPadMode"

    static var isIPadMode: Bool {
        UserDefaults.standard.bool(forKey: iPadModeKey)
    }

    /// Turns iPad mode on or off. The screen size then comes from the same
    /// device as the user agent, so the two match.
    static func setIPadMode(_ isOn: Bool) {
        UserDefaults.standard.set(isOn, forKey: iPadModeKey)
        matchScreenToUserAgent()
    }

    // MARK: - Screen size and user agent

    /// A real iPhone or iPad: its screen size in points, a system version it
    /// can run, and the user agent Safari sends there.
    struct Device {
        let name: String
        let width: Int
        let height: Int
        /// For example "iOS 17.4.1" or "iPadOS 17.4.1".
        let system: String
        let userAgent: String

        init(_ name: String, _ width: Int, _ height: Int, iOS: String, uaOS: String, safari: String) {
            self.name = name
            self.width = width
            self.height = height
            system = "iOS \(iOS)"
            userAgent = "Mozilla/5.0 (iPhone; CPU iPhone OS \(uaOS) like Mac OS X) AppleWebKit/605.1.15 "
                + "(KHTML, like Gecko) Version/\(safari) Mobile/15E148 Safari/604.1"
        }

        /// An iPad, with the user agent Safari sends there when "Request
        /// Desktop Website" is off (with it on, Safari claims to be a Mac).
        init(_ name: String, _ width: Int, _ height: Int, iPadOS: String, uaOS: String, safari: String) {
            self.name = name
            self.width = width
            self.height = height
            system = "iPadOS \(iPadOS)"
            userAgent = "Mozilla/5.0 (iPad; CPU OS \(uaOS) like Mac OS X) AppleWebKit/605.1.15 "
                + "(KHTML, like Gecko) Version/\(safari) Mobile/15E148 Safari/604.1"
        }
    }

    /// Real iPhones with an iOS version each one supports. Safari on iOS 26
    /// reports a frozen "iPhone OS 18_6" (18_7 from 26.2) and the real
    /// version only in "Version/".
    static let iPhones: [Device] = [
        Device("iPhone SE (2nd generation)", 375, 667, iOS: "16.6.1", uaOS: "16_6_1", safari: "16.6"),
        Device("iPhone 11 Pro", 375, 812, iOS: "16.7.10", uaOS: "16_7_10", safari: "16.6"),
        Device("iPhone XS", 375, 812, iOS: "17.0.3", uaOS: "17_0_3", safari: "17.0"),
        Device("iPhone XR", 414, 896, iOS: "17.1.2", uaOS: "17_1_2", safari: "17.1"),
        Device("iPhone 11 Pro Max", 414, 896, iOS: "17.2.1", uaOS: "17_2_1", safari: "17.2"),
        Device("iPhone 12 mini", 375, 812, iOS: "17.3.1", uaOS: "17_3_1", safari: "17.3"),
        Device("iPhone 12", 390, 844, iOS: "17.4.1", uaOS: "17_4_1", safari: "17.4"),
        Device("iPhone SE (3rd generation)", 375, 667, iOS: "17.5.1", uaOS: "17_5_1", safari: "17.5"),
        Device("iPhone 15", 393, 852, iOS: "17.6.1", uaOS: "17_6_1", safari: "17.6"),
        Device("iPhone 11", 414, 896, iOS: "18.0.1", uaOS: "18_0_1", safari: "18.0"),
        Device("iPhone 12 Pro Max", 428, 926, iOS: "18.1.1", uaOS: "18_1_1", safari: "18.1"),
        Device("iPhone 13", 390, 844, iOS: "18.2.1", uaOS: "18_2_1", safari: "18.2"),
        Device("iPhone 13 Pro Max", 428, 926, iOS: "18.3.2", uaOS: "18_3_2", safari: "18.3"),
        Device("iPhone 14 Plus", 428, 926, iOS: "18.4.1", uaOS: "18_4_1", safari: "18.4"),
        Device("iPhone 14 Pro", 393, 852, iOS: "18.5", uaOS: "18_5", safari: "18.5"),
        Device("iPhone 16", 393, 852, iOS: "18.6", uaOS: "18_6", safari: "18.6"),
        Device("iPhone 15 Pro Max", 430, 932, iOS: "18.6.2", uaOS: "18_6_2", safari: "18.6"),
        Device("iPhone 14", 390, 844, iOS: "26.0", uaOS: "18_6", safari: "26.0"),
        Device("iPhone 14 Pro Max", 430, 932, iOS: "26.1", uaOS: "18_6", safari: "26.1"),
        Device("iPhone 16 Pro Max", 440, 956, iOS: "26.2", uaOS: "18_7", safari: "26.2"),
    ]

    /// Real iPads with an iPadOS version each one supports, for iPad mode.
    /// Safari on iPadOS 26 freezes the version like on iPhone.
    static let iPads: [Device] = [
        Device("iPad (9th generation)", 810, 1080, iPadOS: "16.7.10", uaOS: "16_7_10", safari: "16.6"),
        Device("iPad mini (6th generation)", 744, 1133, iPadOS: "17.1.2", uaOS: "17_1_2", safari: "17.1"),
        Device("iPad Pro 12.9-inch (5th generation)", 1024, 1366, iPadOS: "17.3.1", uaOS: "17_3_1", safari: "17.3"),
        Device("iPad Air (5th generation)", 820, 1180, iPadOS: "17.5.1", uaOS: "17_5_1", safari: "17.5"),
        Device("iPad (10th generation)", 820, 1180, iPadOS: "17.6.1", uaOS: "17_6_1", safari: "17.6"),
        Device("iPad Pro 11-inch (4th generation)", 834, 1194, iPadOS: "18.1.1", uaOS: "18_1_1", safari: "18.1"),
        Device("iPad Air 13-inch (M2)", 1024, 1366, iPadOS: "18.3.2", uaOS: "18_3_2", safari: "18.3"),
        Device("iPad Pro 11-inch (M4)", 834, 1210, iPadOS: "18.5", uaOS: "18_5", safari: "18.5"),
        Device("iPad mini (A17 Pro)", 744, 1133, iPadOS: "26.0", uaOS: "18_6", safari: "26.0"),
        Device("iPad Pro 13-inch (M4)", 1032, 1376, iPadOS: "26.1", uaOS: "18_6", safari: "26.1"),
    ]

    /// The devices pages can see: the iPads in iPad mode, the iPhones otherwise.
    static var devices: [Device] {
        isIPadMode ? iPads : iPhones
    }

    /// This phone's screen in points, portrait, set at launch.
    static var realScreen = (width: 0, height: 0)

    /// The devices whose screen size pages may see: those at least as big as
    /// this phone's. A page wider than its screen happens on no real phone,
    /// and sites that check the browser closely notice it.
    static var screenDevices: [Device] {
        let all = devices
        let fitting = all.filter { $0.width >= realScreen.width && $0.height >= realScreen.height }
        if !fitting.isEmpty {
            return fitting
        }
        return all.max { $0.width * $0.height < $1.width * $1.height }.map { [$0] } ?? all
    }

    /// The device whose screen size pages see.
    static var screenDevice: Device {
        device(for: seed(.screen), in: screenDevices)
    }

    /// The device whose user agent pages see.
    static var userAgentDevice: Device {
        device(for: seed(.userAgent), in: devices)
    }

    static var screenSize: (width: Int, height: Int) {
        (screenDevice.width, screenDevice.height)
    }

    static var userAgent: String {
        userAgentDevice.userAgent
    }

    /// The user agent for a page: another device's with the user agent
    /// protection on (unless `protections` is off for the site) and in iPad
    /// mode, or this device's own. Desktop mode keeps WebKit's own.
    @MainActor
    static func userAgent(protections: Bool, desktopMode: Bool) -> String? {
        if desktopMode {
            return nil
        }
        if isIPadMode || (protections && isEnabled(.userAgent)) {
            return userAgent
        }
        return safariUserAgent
    }

    /// What Safari sends on this iPhone: WebKit's own user agent, which has
    /// the system version as Safari reports it (frozen at an iOS 18 version
    /// since iOS 26), with the "Version/" and "Safari/" parts WebKit leaves
    /// out, which some sign-in pages refuse as an app's built-in browser.
    /// Built from a web view the first time, on the main thread.
    @MainActor
    static let safariUserAgent: String = {
        let version = ProcessInfo.processInfo.operatingSystemVersion
        let safari = "\(version.majorVersion).\(version.minorVersion)"
        if let webKit = WKWebView(frame: .zero).value(forKey: "userAgent") as? String,
           webKit.hasPrefix("Mozilla/5.0 (iPhone;"), !webKit.contains("Version/"),
           let mobile = webKit.range(of: " Mobile/") {
            var agent = webKit
            agent.insert(contentsOf: " Version/\(safari)", at: mobile.lowerBound)
            return agent + " Safari/604.1"
        }
        let system: String
        if version.majorVersion >= 26 {
            // Safari freezes the system version: 18_6 on 26.0, 18_6_2 on 26.1, 18_7 from 26.2.
            if version.majorVersion == 26 && version.minorVersion == 0 {
                system = "18_6"
            } else if version.majorVersion == 26 && version.minorVersion == 1 {
                system = "18_6_2"
            } else {
                system = "18_7"
            }
        } else {
            let parts = [version.majorVersion, version.minorVersion] + (version.patchVersion > 0 ? [version.patchVersion] : [])
            system = parts.map(String.init).joined(separator: "_")
        }
        return "Mozilla/5.0 (iPhone; CPU iPhone OS \(system) like Mac OS X) AppleWebKit/605.1.15 "
            + "(KHTML, like Gecko) Version/\(safari) Mobile/15E148 Safari/604.1"
    }()

    private static func device(for seed: UInt32, in list: [Device]) -> Device {
        list[Int(seed % UInt32(list.count))]
    }

    /// What a seed shows the user for a kind; a new seed must change it.
    private static func visibleValue(_ seed: UInt32, for kind: Kind) -> String {
        switch kind {
        case .screen:
            let device = device(for: seed, in: screenDevices)
            return "\(device.width)x\(device.height)"
        case .userAgent:
            return device(for: seed, in: devices).userAgent
        default:
            return String(seed)
        }
    }

    /// How many different values a new seed can pick from for a kind.
    private static func choiceCount(for kind: Kind) -> Int {
        switch kind {
        case .screen: return Set(screenDevices.map { "\($0.width)x\($0.height)" }).count
        case .userAgent: return Set(devices.map(\.userAgent)).count
        default: return Int.max
        }
    }

    // MARK: - Page script

    /// The script for the protections that are on (the user agent is set on
    /// the web view instead), or nil if none of them is. Without
    /// `protections` (shields down for the site) only iPad mode is left. With
    /// `realDevice` (a sign-in site) the screen size stays as it is, like
    /// the user agent, since such sites check both against the device. In
    /// desktop mode WebKit reports a Mac on its own, so iPad mode leaves it
    /// alone there.
    ///
    /// The script protects the page's window, and from there the empty
    /// frames (about:blank) the page makes, where WebKit runs no user
    /// scripts (see `framesScript`), so `protect` takes the window to work on.
    @MainActor
    static func userScript(desktopMode: Bool, protections: Bool = true, realDevice: Bool = false) -> WKUserScript? {
        var parts: [String] = [browserScript]
        if protections {
            let canvasSeed = isEnabled(.canvas) ? seed(.canvas) : nil
            let webGLSeed = isEnabled(.webGL) ? seed(.webGL) : nil
            if let canvasSeed = canvasSeed { parts.append(canvasScript(seed: canvasSeed)) }
            if let webGLSeed = webGLSeed { parts.append(webGLScript(seed: webGLSeed)) }
            if canvasSeed != nil || webGLSeed != nil {
                parts.append(canvasExportScript(canvasSeed: canvasSeed, webGLSeed: webGLSeed))
            }
            if isEnabled(.audio) { parts.append(audioScript(seed: seed(.audio))) }
            if isEnabled(.clientRects) { parts.append(clientRectsScript(seed: seed(.clientRects))) }
            if isEnabled(.screen) && !realDevice { parts.append(screenScript(screenSize)) }
        }
        if isIPadMode && !desktopMode { parts.append(iPadScript) }
        // Each part runs on its own, so a part that fails in some WebKit
        // version leaves the others working.
        let guarded = (parts + [framesScript]).map { "try {\n" + $0 + "} catch (e) {}\n" }.joined()
        let source = "(() => {\n" + shared
            + "const protect = (window) => {\n" + helpers + guarded + "protectedWindows.add(window);\n};\n"
            // A window another copy of this script protected (its page's,
            // when the frame started empty) is left as it is.
            + "if (!isProtected(window)) protect(window);\n})();"
        return WKUserScript(source: source, injectionTime: .atDocumentStart, forMainFrameOnly: false)
    }

    /// What the protection of every window this script reaches shares.
    private static let shared = #"""
    // The page runs after this script and could change Object and Math, so
    // what is needed later (for the frames the page makes) is kept from here.
    const { defineProperty, getOwnPropertyDescriptor, getOwnPropertyNames, getPrototypeOf, setPrototypeOf } = Object;
    const { imul, floor, min, max, clz32 } = Math;
    const { isFinite } = Number;
    const Uint8 = Uint8Array;
    const Uint32 = Uint32Array;
    const now = Date.now;
    // Typed arrays are read through %TypedArray%.prototype's own getters and
    // method, which report what an array really is from any window, so a
    // page can't change what they say to send the noise elsewhere.
    const typedArray = getPrototypeOf(Uint8Array.prototype);
    const typedArrayGetter = (name) => getOwnPropertyDescriptor(typedArray, name).get;
    const kindOf = typedArrayGetter(Symbol.toStringTag);
    const lengthOf = typedArrayGetter("length");
    const bufferOf = typedArrayGetter("buffer");
    const byteOffsetOf = typedArrayGetter("byteOffset");
    const subarray = typedArray.subarray;
    // The kind of a typed array, like "Uint8Array", or undefined for anything else.
    const tagOf = (array) => {
      try { return kindOf.call(array); } catch (e) { return undefined; }
    };

    // Each replacement's real built-in, for its toString() and for calling it.
    const originals = new WeakMap();
    const native = (fn) => originals.get(fn) || fn;

    // An error thrown by a native function a page calls through one of
    // the lookalikes carries their frames in its stack, between the page's
    // and the native one's; a site that compares stacks would see them.
    // The frames are known by this script's own location (a file in the
    // app, or none for a script WebKit injects) and taken out, so the
    // stack reads as the native function's own.
    const ownLocation = (() => {
      try {
        throw new Error();
      } catch (error) {
        const line = String(error.stack || "").split("\n").find((l) => /^\s+at |@/.test(l)) || "";
        const match = line.match(/\(([^()]*?)(?::\d+){0,2}\)\s*$/) || line.match(/@(.*?)(?::\d+){0,2}\s*$/) || line.match(/^\s+at\s+(.*?)(?::\d+){0,2}\s*$/);
        return match ? match[1] : "";
      }
    })();
    const isOwnFrame = (line) => ownLocation ? line.includes(ownLocation) : /^[^@]*@$/.test(line.trim());
    // Only the innermost frames can be this script's: those just after the
    // message (V8 shows no frame for the native function itself; WebKit
    // shows it as "[native code]", kept).
    const scrubbed = (error) => {
      try {
        if (error && typeof error === "object" && typeof error.stack === "string") {
          const lines = error.stack.split("\n");
          let first = 1;
          while (first < lines.length && /\[native code\]/.test(lines[first])) first++;
          let last = first;
          while (last < lines.length && isOwnFrame(lines[last])) last++;
          if (last > first) {
            lines.splice(first, last - first);
            error.stack = lines.join("\n");
          }
        }
      } catch (e) {}
      return error;
    };
    // Every replacement's source carries this mark, so a copy of this script
    // in another window (WebKit runs one per page) recognizes it too.
    const MARK = "/* noor lookalike */";
    const nativeToString = Function.prototype.toString;
    // What a built-in's toString() looks like here, with "toString" for the name.
    const nativeShape = nativeToString.call(nativeToString);
    // Whether a window is protected already, by this or another copy of
    // this script: its toString() then hides the mark in this probe.
    const probe = function () { /* noor lookalike */ };
    const isProtected = (win) => {
      try { return win.Function.prototype.toString.call(probe).indexOf(MARK) === -1; } catch (e) { return false; }
    };
    // The windows protected from this script, each once.
    const protectedWindows = new WeakSet();
    // The audio buffers the browser rendered or decoded, from any window, and
    // the channels of them already changed.
    const rendered = new WeakSet();
    const nudged = new WeakMap();
    // Each canvas's context: its kind, "webgl" or "canvas", and the settings
    // it was made with, from any window.
    const kinds = new WeakMap();
    // Each canvas's (or WebGL context's) candidate pixels, computed lately.
    const marks = new WeakMap();

    // Integer hash, so a given pixel or sample always gets the same tweak.
    const mix = (n) => {
      n = imul(n ^ (n >>> 16), 0x7feb352d);
      n = imul(n ^ (n >>> 15), 0x846ca68b);
      return (n ^ (n >>> 16)) >>> 0;
    };

    // The 32-bit pixels of 8-bit RGBA data, as a view on it or a copy.
    const wordsOf = (data, count) => {
      try {
        return new Uint32(bufferOf.call(data), byteOffsetOf.call(data), count);
      } catch (e) {
        return new Uint32(new Uint8(data).buffer, 0, count);
      }
    };

    // Which pixels of an image may get noise, one bit each in the pixels'
    // order: the visible ones whose color is rare in the image (seen in less
    // than 1 in 64 pixels, so not a fill) and differs from a neighbor's: the
    // antialiased edges, blends and gradients where a device shows itself.
    // Flat shapes, however small, stay exactly as drawn, so a page reading
    // what it drew (a shape in its own color under a tap) gets it back, and a
    // site checking a plain drawing sees nothing.
    const counts = new Uint32(65536);
    const candidateBits = (data, width, height) => {
      const count = width * height;
      const pixels = wordsOf(data, count);
      const bits = new Uint8((count + 7) >> 3);
      const mask = (1 << min(16, 33 - clz32(count))) - 1;
      counts.fill(0, 0, mask + 1);
      for (let i = 0; i < count; i++) counts[mix(pixels[i]) & mask]++;
      const threshold = max(4, count >> 6);
      for (let y = 0, i = 0; y < height; y++) {
        for (let x = 0; x < width; x++, i++) {
          if (data[i * 4 + 3] === 0) continue;
          const pixel = pixels[i];
          if (counts[mix(pixel) & mask] > threshold) continue;
          if ((x > 0 && pixels[i - 1] !== pixel) || (x + 1 < width && pixels[i + 1] !== pixel)
            || (y > 0 && pixels[i - width] !== pixel) || (y + 1 < height && pixels[i + width] !== pixel)) {
            bits[i >> 3] |= 1 << (i & 7);
          }
        }
      }
      return bits;
    };

    // The candidate pixels of the whole image a read of `width` by `height`
    // at (left, top) comes from, so a part reads the same as the whole:
    // from `data` when the read is the whole image, else from the pixels
    // computed for `key` (the canvas or WebGL context) in the last quarter
    // second, else from `readAll()`, a native read of the whole image.
    const candidatesFor = (key, data, width, height, left, top, fullWidth, fullHeight, readAll) => {
      if (tagOf(data) !== "Uint8ClampedArray" && tagOf(data) !== "Uint8Array") return null;
      if (lengthOf.call(data) < width * height * 4) return null;
      if (left === 0 && top === 0 && width === fullWidth && height === fullHeight) {
        const bits = candidateBits(data, width, height);
        if (key) marks.set(key, { time: now(), width, height, bits });
        return bits;
      }
      const cached = key && marks.get(key);
      if (cached && cached.width === fullWidth && cached.height === fullHeight && now() - cached.time < 250) {
        return cached.bits;
      }
      const whole = readAll();
      if (!whole) return null;
      const bits = candidateBits(whole, fullWidth, fullHeight);
      if (key) marks.set(key, { time: now(), width: fullWidth, height: fullHeight, bits });
      return bits;
    };

    // Changes about 1 in 16 of the candidate pixels (`bits`, from
    // candidatesFor; all visible pixels when null): invisible, but it
    // changes every hash a fingerprinter takes. Of a chosen pixel the lowest
    // bit of one color channel is set (not flipped: a second pass then
    // changes nothing, so a frame the protection reaches twice stays
    // protected). Pixels are keyed by their position in the whole image,
    // counted from the top, so reading part of an image, or exporting it,
    // gives the same noise as reading all of it. WebGL's readPixels hands
    // rows bottom-up; `flipped` turns them into rows from the top, so pixels
    // read that way match the same pixels in an exported image. Only the
    // `width` by `height` pixels read are touched; 16-bit float pixels are
    // scaled by 1/1024 instead.
    const addPixelNoise = (seed, data, width, height, left, top, fullWidth, fullHeight, flipped, bits) => {
      const tag = tagOf(data);
      const bytes = tag === "Uint8ClampedArray" || tag === "Uint8Array";
      if (!bytes && tag !== "Float16Array") return;
      if (!(width > 0 && height > 0)) return;
      const count = min(lengthOf.call(data) >> 2, width * height);
      for (let i = 0, end = count * 4; i < end; i += 4) {
        const alpha = data[i + 3];
        if (alpha === 0) continue;
        const p = i >> 2;
        const x = left + (p % width);
        const row = top + floor(p / width);
        if (x < 0 || x >= fullWidth || row < 0 || row >= fullHeight) continue;
        if (bits) {
          const index = row * fullWidth + x;
          if (!(bits[index >> 3] & (1 << (index & 7)))) continue;
        }
        const y = flipped ? fullHeight - 1 - row : row;
        const h = mix(seed ^ imul(y * fullWidth + x + 1, 0x9e3779b1));
        if ((h & 15) !== 0) continue;
        const j = i + ((h >>> 4) % 3);
        const bit = (h >>> 6) & 1;
        if (!bytes) {
          data[j] *= 1 + (bit ? 1 : -1) / 1024;
        } else if (alpha === 255) {
          data[j] = (data[j] & ~1) | bit;
        } else {
          // The canvas stores a translucent pixel's colors multiplied by its
          // alpha, so set the bit in that stored value and write back the
          // color it reads as, which the canvas keeps through that
          // multiplication; an exported image then shows the same pixel.
          const stored = min(alpha, ((((data[j] * alpha + 127) / 255) | 0) & ~1) | bit);
          data[j] = ((stored * 255 + (alpha >> 1)) / alpha) | 0;
        }
      }
    };

    """#

    /// The start of `protect(window)`: how built-ins are replaced, and the
    /// site key.
    private static let helpers = #"""
    // Protects `window`: the page's own, or an empty frame it made. It is
    // marked protected once everything is in place (at the end), so a run
    // that fails is tried again.
    const document = window.document;

    // Keeps every built-in we replace indistinguishable from the original, so
    // a site that checks for a tampered browser sees nothing changed and works
    // as it would in Safari. A site reads a function's toString() to tell a
    // patched function from a real one, checks that it has no "prototype"
    // and can't be constructed, and compares its own properties with a
    // built-in's; without this the protections themselves give the browser
    // away. `originals` sends each replacement's (and the patched toString's
    // own) toString() to the real function it stands for; a replacement made
    // by another copy of this script, which a page can reach through a
    // frame's toString, is recognized by its mark and shown as a built-in.
    const windowToString = window.Function.prototype.toString;

    // A function that stands in for `original` and runs `impl` with the same
    // this and arguments. A method of an object literal has no "prototype"
    // and throws "not a constructor" like a built-in, and being strict it
    // has no "arguments" or "caller" of its own; it belongs to this window
    // like the built-in, and gets the built-in's own properties (name and
    // length), in the same order, and its toString().
    const lookalike = (original, impl) => {
      const replacement = {
        [original.name]() {
          "use strict"; /* noor lookalike */
          try {
            return impl.apply(this, arguments);
          } catch (error) {
            throw scrubbed(error);
          }
        },
      }[original.name];
      setPrototypeOf(replacement, window.Function.prototype);
      for (const key of ["name", "length"]) {
        try { delete replacement[key]; } catch (e) {}
      }
      for (const key of getOwnPropertyNames(original)) {
        try { defineProperty(replacement, key, getOwnPropertyDescriptor(original, key)); } catch (e) {}
      }
      originals.set(replacement, original);
      return replacement;
    };

    window.Function.prototype.toString = lookalike(windowToString, function () {
      const source = windowToString.apply(native(this), arguments);
      if (typeof source === "string" && source.indexOf(MARK) !== -1) {
        return nativeShape.replace("toString", this.name);
      }
      return source;
    });

    // A method of a built-in that doesn't exist here: `name` and `length`
    // as a built-in's, no "prototype", and the mark, so toString() shows it
    // as a built-in.
    const method = (name, length, impl) => {
      const fn = {
        [name]() {
          "use strict"; /* noor lookalike */
          try {
            return impl.apply(this, arguments);
          } catch (error) {
            throw scrubbed(error);
          }
        },
      }[name];
      setPrototypeOf(fn, window.Function.prototype);
      defineProperty(fn, "length", { value: length, configurable: true });
      return fn;
    };

    // A built-in class that doesn't exist here, on `window`: constructing
    // it throws like a built-in, its prototype chain follows `parent`'s,
    // and it has a built-in's own properties and toString().
    const nativeClass = (name, parent) => {
      const C = {
        [name]: function () {
          "use strict"; /* noor lookalike */
          throw new window.TypeError("Illegal constructor");
        },
      }[name];
      setPrototypeOf(C, parent);
      setPrototypeOf(C.prototype, parent.prototype);
      defineProperty(C, "prototype", { writable: false });
      defineProperty(C.prototype, Symbol.toStringTag, { value: name, configurable: true });
      defineProperty(window, name, { value: C, writable: true, enumerable: false, configurable: true });
      return C;
    };

    // Replaces object[name] (a method) with make(original).
    const define = (object, name, make) => {
      const original = object && object[name];
      if (typeof original !== "function") return;
      object[name] = lookalike(original, make(original));
    };

    // Replaces a native property's getter, keeping the enumerability and
    // making the getter look like the native one: it still refuses a wrong
    // `this` ("Illegal invocation") as the native getter does, since a site
    // calls getters on the wrong object to find replaced ones. A property
    // the browser doesn't have is left missing.
    const defineGetter = (object, name, get) => {
      const descriptor = getOwnPropertyDescriptor(object, name);
      if (!descriptor || !descriptor.get) return;
      const original = descriptor.get;
      defineProperty(object, name, {
        get: lookalike(original, function () {
          original.call(this);
          return get.call(this);
        }),
        set: descriptor.set,
        configurable: true,
        enumerable: descriptor.enumerable,
      });
    };

    // The host the noise is keyed by: the top page's, as in Brave, so a
    // frame sees the same values as the page it is in (a site compares the
    // two to catch noise), and a third party's frame sees different values
    // on every site, so it can't follow a visitor from one to the next. A
    // cross-origin frame reads the top page's origin from ancestorOrigins,
    // or failing that its host from the referrer; last comes its own host.
    const host = (() => {
      try { if (window.top.location.hostname) return window.top.location.hostname; } catch (e) {}
      try {
        const origins = window.location.ancestorOrigins;
        if (origins && origins.length) return new URL(origins[origins.length - 1]).hostname;
      } catch (e) {}
      try { const h = new URL(document.referrer).hostname; if (h) return h; } catch (e) {}
      try { return window.location.hostname; } catch (e) { return ""; }
    })();

    // Mixes a seed with the site's host, so each site sees different, stable
    // values (FNV-1a).
    const forSite = (seed) => {
      let value = (seed ^ 0x811c9dc5) >>> 0;
      for (const ch of host) {
        value = imul(value ^ ch.charCodeAt(0), 0x01000193) >>> 0;
      }
      return value;
    };

    """#

    /// The end of `protect(window)`: the frames the page makes.
    private static let framesScript = #"""
    // WebKit runs this script in every frame that loads a page, but not in
    // the empty document a frame, or a window the page opens, starts with
    // (about:blank) and keeps when it has no address. There a page finds
    // untouched built-ins, and could read the real fingerprint through them,
    // or compare them with its own and notice the protection. Such windows
    // are protected from here: when the page reaches a frame's through
    // contentWindow or contentDocument, soon after a frame is added to the
    // document, and when window.open returns one. Windows that load a page
    // get the script from WebKit, and one protected before is left as it is.
    {
      const protectWindow = (other) => {
        try {
          if (!other || protectedWindows.has(other) || other.location.href !== "about:blank") return;
          // Protected by another copy of this script already.
          if (isProtected(other)) return;
        } catch (e) {
          return;
        }
        try { protect(other); } catch (e) {}
      };
      define(window, "open", (open) => function () {
        const other = open.apply(this, arguments);
        protectWindow(other);
        return other;
      });
      // The elements that hold a frame, and their windows' getters.
      const owners = [];
      for (const name of ["HTMLIFrameElement", "HTMLFrameElement", "HTMLObjectElement"]) {
        const proto = window[name] && window[name].prototype;
        const contentWindow = proto && getOwnPropertyDescriptor(proto, "contentWindow");
        if (contentWindow && contentWindow.get) owners.push([proto, contentWindow]);
      }
      const protectFrame = (frame) => {
        for (const [proto, contentWindow] of owners) {
          try { protectWindow(contentWindow.get.call(frame)); } catch (e) {}
        }
      };
      for (const [proto, contentWindow] of owners) {
        defineGetter(proto, "contentWindow", function () {
          protectFrame(this);
          return contentWindow.get.call(this);
        });
        const contentDocument = getOwnPropertyDescriptor(proto, "contentDocument");
        if (contentDocument && contentDocument.get) {
          defineGetter(proto, "contentDocument", function () {
            protectFrame(this);
            return contentDocument.get.call(this);
          });
        }
      }
      if (owners.length) {
        const names = ["iframe", "frame", "object"];
        try {
          new window.MutationObserver((records) => {
            for (const record of records) {
              for (const node of record.addedNodes) {
                if (node.nodeType !== 1) continue;
                if (names.indexOf(node.localName) !== -1) {
                  protectFrame(node);
                } else if (node.getElementsByTagName) {
                  for (const name of names) {
                    for (const frame of node.getElementsByTagName(name)) protectFrame(frame);
                  }
                }
              }
            }
          }).observe(document, { childList: true, subtree: true });
        } catch (e) {}
      }
    }

    """#

    /// What tells an app's web view from Safari, on every page. Apple gives
    /// service workers to Safari and to browsers with its browser entitlement
    /// (Opera, Chrome, Firefox), not to other apps' web views, and gives
    /// those web views a quarter of the storage quota (15% of the disk
    /// instead of 60%). A site that sees Safari's user agent with either
    /// takes the browser for an app's built-in one and treats it with
    /// suspicion (Instagram asked every new account for a "confirm you're a
    /// real person" check, and not in Opera). Pages get the service worker
    /// API's shape, with registrations that fail as in a browser that keeps
    /// service workers from a page, and a browser's quota.
    private static let browserScript = #"""
    // Storage: the quota a browser reports.
    {
      const proto = window.StorageManager && window.StorageManager.prototype;
      if (proto) {
        define(proto, "estimate", (original) => function () {
          const result = original.apply(this, arguments);
          return result && typeof result.then === "function" ? result.then((estimate) => {
            try { if (estimate && estimate.quota > 0) estimate.quota = estimate.quota * 4; } catch (e) {}
            return estimate;
          }) : result;
        });
      }
    }

    // Service workers: the API's shape, where WebKit gives apps none. A
    // registration succeeds, as in a browser, with a worker that reports
    // itself active but never controls the page or runs; pushManager is
    // absent, as in Safari outside a home-screen web app.
    {
      const nav = window.Navigator && window.Navigator.prototype;
      if (nav && window.EventTarget && window.Promise && window.URL && !("serviceWorker" in nav)) {
        const Container = nativeClass("ServiceWorkerContainer", window.EventTarget);
        const Registration = nativeClass("ServiceWorkerRegistration", window.EventTarget);
        const Worker = nativeClass("ServiceWorker", window.EventTarget);
        const states = new WeakMap();
        const accessor = (proto, name, get) => defineProperty(proto, name, {
          get: method("get " + name, 0, get), enumerable: true, configurable: true,
        });
        const handler = (proto, name) => defineProperty(proto, name, {
          get: method("get " + name, 0, function () { return (states.get(this) || {})[name] || null; }),
          set: method("set " + name, 1, function (value) { const state = states.get(this); if (state) state[name] = value; }),
          enumerable: true, configurable: true,
        });
        const func = (proto, name, length, impl) => defineProperty(proto, name, {
          value: method(name, length, impl), writable: true, enumerable: true, configurable: true,
        });
        const fail = (error) => new window.Promise((resolve, reject) => reject(error));

        accessor(Worker.prototype, "scriptURL", function () { return (states.get(this) || {}).scriptURL || ""; });
        accessor(Worker.prototype, "state", function () { return "activated"; });
        handler(Worker.prototype, "onstatechange");
        func(Worker.prototype, "postMessage", 1, function () {});

        const registrations = [];
        accessor(Registration.prototype, "scope", function () { return (states.get(this) || {}).scope || ""; });
        accessor(Registration.prototype, "installing", function () { return null; });
        accessor(Registration.prototype, "waiting", function () { return null; });
        accessor(Registration.prototype, "active", function () { return (states.get(this) || {}).worker || null; });
        accessor(Registration.prototype, "updateViaCache", function () { return "imports"; });
        handler(Registration.prototype, "onupdatefound");
        func(Registration.prototype, "update", 0, function () { return window.Promise.resolve(this); });
        func(Registration.prototype, "unregister", 0, function () {
          const index = registrations.indexOf(this);
          if (index !== -1) registrations.splice(index, 1);
          return window.Promise.resolve(index !== -1);
        });

        const proto = Container.prototype;
        let ready, resolveReady;
        accessor(proto, "controller", function () { return null; });
        accessor(proto, "ready", function () {
          if (!ready) ready = new window.Promise((resolve) => { resolveReady = resolve; });
          return ready;
        });
        handler(proto, "oncontrollerchange");
        handler(proto, "onmessage");
        handler(proto, "onmessageerror");
        func(proto, "register", 1, function (url, options) {
          let script, scope;
          try {
            script = new window.URL(url, document.baseURI);
            if (script.protocol !== "https:" && script.protocol !== "http:") {
              return fail(new window.TypeError("serviceWorker.register() must be called with a script URL whose protocol is either HTTP or HTTPS"));
            }
            if (script.origin !== window.location.origin) {
              return fail(new window.DOMException("Script origin does not match the registering document's origin", "SecurityError"));
            }
            scope = new window.URL(options && options.scope != null ? String(options.scope) : "./", script.href).href;
          } catch (e) {
            return fail(e);
          }
          let registration = registrations.find((r) => states.get(r).scope === scope);
          if (!registration) {
            registration = Object.create(Registration.prototype);
            const worker = Object.create(Worker.prototype);
            states.set(worker, { scriptURL: script.href });
            states.set(registration, { scope, worker });
            registrations.push(registration);
          }
          this.ready;
          resolveReady(registration);
          return window.Promise.resolve(registration);
        });
        func(proto, "getRegistration", 0, function (clientURL) {
          let href;
          try { href = new window.URL(clientURL === undefined ? "./" : String(clientURL), document.baseURI).href; } catch (e) { return fail(e); }
          const found = registrations.filter((r) => href.indexOf(states.get(r).scope) === 0).sort((a, b) => states.get(b).scope.length - states.get(a).scope.length)[0];
          return window.Promise.resolve(found);
        });
        func(proto, "getRegistrations", 0, function () { return window.Promise.resolve(registrations.slice()); });
        func(proto, "startMessages", 0, function () {});

        let container;
        defineProperty(nav, "serviceWorker", {
          get: method("get serviceWorker", 0, function () {
            return container || (container = Object.create(proto));
          }),
          enumerable: true,
          configurable: true,
        });
        // Where the built-in sits: after pdfViewerEnabled (or mimeTypes), so
        // the properties that follow it there are put back after it.
        const names = getOwnPropertyNames(nav);
        const anchor = names.indexOf("pdfViewerEnabled") !== -1 ? names.indexOf("pdfViewerEnabled") : names.indexOf("mimeTypes");
        if (anchor !== -1) {
          for (const name of names.slice(anchor + 1)) {
            if (name === "serviceWorker") continue;
            const descriptor = getOwnPropertyDescriptor(nav, name);
            try { delete nav[name]; defineProperty(nav, name, descriptor); } catch (e) {}
          }
        }
      }
    }

    """#

    private static func canvasScript(seed: UInt32) -> String {
        #"""
        // Canvas: pixels read with getImageData get pixel noise, decided from
        // the whole canvas. The image's and the canvas's properties are read
        // with the built-ins as they are now, so a page can't redirect the
        // noise by changing them later.
        {
          const canvasSeed = forSite(\#(seed));
          const getter = (proto, name) => {
            const descriptor = proto && getOwnPropertyDescriptor(proto, name);
            return descriptor && descriptor.get ? (object) => descriptor.get.call(object) : (object) => object[name];
          };
          const imageProto = window.ImageData && window.ImageData.prototype;
          const imageData = getter(imageProto, "data");
          const imageWidth = getter(imageProto, "width");
          const imageHeight = getter(imageProto, "height");
          const patchGetImageData = (proto, canvasProto) => {
            const contextCanvas = getter(proto, "canvas");
            const canvasWidth = getter(canvasProto, "width");
            const canvasHeight = getter(canvasProto, "height");
            const getImageData = native(proto.getImageData);
            define(proto, "getImageData", (original) => function (sx, sy, sw, sh) {
              const image = original.apply(this, arguments);
              try {
                // A negative width or height reads to the left of, or above, (sx, sy).
                const left = (sx | 0) + (sw < 0 ? (sw | 0) : 0);
                const top = (sy | 0) + (sh < 0 ? (sh | 0) : 0);
                const data = imageData(image);
                const width = imageWidth(image);
                const height = imageHeight(image);
                let canvas, fullWidth = width, fullHeight = height;
                try {
                  canvas = contextCanvas(this);
                  fullWidth = canvasWidth(canvas);
                  fullHeight = canvasHeight(canvas);
                } catch (e) {}
                const bits = candidatesFor(canvas, data, width, height, left, top, fullWidth, fullHeight, () => {
                  try { return imageData(getImageData.call(this, 0, 0, fullWidth, fullHeight)); } catch (e) { return null; }
                });
                addPixelNoise(canvasSeed, data, width, height, left, top, fullWidth, fullHeight, false, bits);
              } catch (e) {}
              return image;
            });
          };
          patchGetImageData(window.CanvasRenderingContext2D.prototype, window.HTMLCanvasElement.prototype);
          if (window.OffscreenCanvasRenderingContext2D && window.OffscreenCanvas) {
            patchGetImageData(window.OffscreenCanvasRenderingContext2D.prototype, window.OffscreenCanvas.prototype);
          }
        }

        """#
    }

    private static func webGLScript(seed: UInt32) -> String {
        #"""
        // WebGL: pixels read back with readPixels get pixel noise, decided
        // from the whole drawing buffer.
        {
          const webGLSeed = forSite(\#(seed));
          const RGBA = 0x1908;
          const UNSIGNED_BYTE = 0x1401;
          for (const name of ["WebGLRenderingContext", "WebGL2RenderingContext"]) {
            const proto = window[name] && window[name].prototype;
            if (!proto) continue;
            const getter = (name) => {
              const descriptor = getOwnPropertyDescriptor(proto, name);
              return descriptor && descriptor.get ? (context) => descriptor.get.call(context) : (context) => context[name];
            };
            const bufferWidth = getter("drawingBufferWidth");
            const bufferHeight = getter("drawingBufferHeight");
            const readPixels = native(proto.readPixels);
            define(proto, "readPixels", (original) => function (x, y, width, height, format, type, pixels, offset) {
              original.apply(this, arguments);
              try {
                const tag = tagOf(pixels);
                if ((tag !== "Uint8Array" && tag !== "Uint8ClampedArray") || Number(format) !== RGBA) return;
                // WebGL2 can read into the array from `offset` on.
                const data = offset > 0 ? subarray.call(pixels, offset) : pixels;
                const fullWidth = bufferWidth(this);
                const fullHeight = bufferHeight(this);
                const bits = candidatesFor(this, data, width | 0, height | 0, x | 0, y | 0, fullWidth, fullHeight, () => {
                  try {
                    const whole = new Uint8(fullWidth * fullHeight * 4);
                    readPixels.call(this, 0, 0, fullWidth, fullHeight, RGBA, UNSIGNED_BYTE, whole);
                    return whole;
                  } catch (e) {
                    return null;
                  }
                });
                addPixelNoise(webGLSeed, data, width | 0, height | 0, x | 0, y | 0, fullWidth, fullHeight, true, bits);
              } catch (e) {}
            });
          }
        }

        """#
    }

    /// The exports of canvases (toDataURL, toBlob, convertToBlob), for the
    /// canvas and WebGL protections. A canvas drawn with WebGL gets the WebGL
    /// noise (or the canvas noise, with only that protection on), so a new
    /// WebGL fingerprint changes the WebGL images sites read, and any other
    /// canvas gets the canvas noise. A nil seed is a protection that is off.
    private static func canvasExportScript(canvasSeed: UInt32?, webGLSeed: UInt32?) -> String {
        let canvas = canvasSeed.map { "forSite(\($0))" } ?? "null"
        let webgl = webGLSeed.map { "forSite(\($0))" } ?? "null"
        return #"""
        // Canvas exports: toDataURL, toBlob and convertToBlob read a noisy
        // copy, so the canvas on screen is never changed. The copy gets the
        // WebGL noise for a canvas drawn with WebGL, which getContext
        // remembers, and the canvas noise otherwise. The copy is made with
        // the built-ins as they are now, so a page can't change them later
        // to get the real pixels. A canvas tainted by another site's image
        // can't be copied; the call then fails as it normally would.
        {
          const seeds = { canvas: \#(canvas), webgl: \#(webgl) };
          // The built-ins a copy is made with: [getContext, drawImage, getImageData, putImageData].
          const tools = (canvasProto, contextProto) => contextProto && [
            native(canvasProto.getContext), native(contextProto.drawImage),
            native(contextProto.getImageData), native(contextProto.putImageData),
          ];
          const rememberContext = (proto) => {
            define(proto, "getContext", (getContext) => function (type, settings) {
              const context = getContext.apply(this, arguments);
              if (context) {
                const webgl = /^(experimental-)?webgl/i.test("" + type);
                kinds.set(this, { kind: webgl ? "webgl" : "canvas", settings: !webgl && settings && typeof settings === "object" ? settings : undefined });
              }
              return context;
            });
          };
          // A canvas's size through the built-in getters: a page can't hide
          // it, and anything but a canvas throws, as the export itself would.
          const sizeOf = (proto) => {
            const width = getOwnPropertyDescriptor(proto, "width");
            const height = getOwnPropertyDescriptor(proto, "height");
            return (canvas) => [width.get.call(canvas), height.get.call(canvas)];
          };
          const canvasProto = window.HTMLCanvasElement.prototype;
          const canvasTools = tools(canvasProto, window.CanvasRenderingContext2D.prototype);
          const canvasSize = sizeOf(canvasProto);
          const offscreenTools = window.OffscreenCanvas
            && tools(window.OffscreenCanvas.prototype, window.OffscreenCanvasRenderingContext2D
              && window.OffscreenCanvasRenderingContext2D.prototype);
          const offscreenSize = window.OffscreenCanvas && sizeOf(window.OffscreenCanvas.prototype);
          rememberContext(canvasProto);
          if (window.OffscreenCanvas) rememberContext(window.OffscreenCanvas.prototype);

          const seedFor = (canvas) => {
            const made = kinds.get(canvas);
            if (made && made.kind === "webgl") {
              return seeds.webgl === null ? seeds.canvas : seeds.webgl;
            }
            return seeds.canvas;
          };
          const noisyCopy = (canvas, makeCanvas, tools, sizeOf) => {
            let width, height;
            try {
              [width, height] = sizeOf(canvas);
            } catch (e) {
              return null;
            }
            const seed = seedFor(canvas);
            if (seed === null || !width || !height || !tools) return null;
            try {
              const [getContext, drawImage, getImageData, putImageData] = tools;
              const made = kinds.get(canvas);
              const copy = makeCanvas(width, height);
              // The copy keeps the canvas's color space, so colors don't shift.
              const context = getContext.call(copy, "2d", made && made.settings);
              drawImage.call(context, canvas, 0, 0);
              const image = getImageData.call(context, 0, 0, width, height);
              const bits = candidatesFor(canvas, image.data, width, height, 0, 0, width, height, () => null);
              addPixelNoise(seed, image.data, width, height, 0, 0, width, height, false, bits);
              putImageData.call(context, image, 0, 0);
              return copy;
            } catch (e) {
              return null;
            }
          };

          const createElement = document.createElement;
          const makeCanvas = (width, height) => {
            const canvas = createElement.call(document, "canvas");
            canvas.width = width;
            canvas.height = height;
            return canvas;
          };
          for (const name of ["toDataURL", "toBlob"]) {
            define(canvasProto, name, (original) => function () {
              const copy = noisyCopy(this, makeCanvas, canvasTools, canvasSize);
              return original.apply(copy || this, arguments);
            });
          }
          if (window.OffscreenCanvas && window.OffscreenCanvas.prototype.convertToBlob) {
            define(window.OffscreenCanvas.prototype, "convertToBlob", (convertToBlob) => function () {
              const copy = noisyCopy(this, (width, height) => new window.OffscreenCanvas(width, height), offscreenTools, offscreenSize);
              return convertToBlob.apply(copy || this, arguments);
            });
          }
        }

        """#
    }

    private static func audioScript(seed: UInt32) -> String {
        #"""
        // Audio: the samples the browser renders or decodes (an
        // OfflineAudioContext's result, decoded audio, a ScriptProcessorNode's
        // input, an AnalyserNode's data) get the lowest four bits of their
        // mantissa set from a hash: a change of at most 2 parts in a million,
        // about -115 dB, far below hearing, but it changes the sums audio
        // fingerprinting scripts compute. Setting bits, rather than adding or
        // scaling, survives the rounding of 32-bit floats and leaves a second
        // pass nothing to change; silence and infinities stay as they are. A
        // buffer the page filled itself is left alone: it holds no trace of
        // the device, and a site compares it with what it wrote to catch
        // noise. Each rendered buffer's channel is changed once, not on every
        // read; a ScriptProcessorNode brings new samples in the same buffer
        // with every event, so it is changed again each time.
        {
          const audioSeed = forSite(\#(seed));
          const nudge = (data, length) => {
            if (tagOf(data) !== "Float32Array") return;
            const count = min(lengthOf.call(data), length);
            let words;
            try {
              words = new Uint32(bufferOf.call(data), byteOffsetOf.call(data), count);
            } catch (e) {
              return;
            }
            for (let i = 0; i < count; i++) {
              const word = words[i];
              const exponent = word & 0x7f800000;
              if (exponent === 0 || exponent === 0x7f800000) continue;
              words[i] = (word & ~15) | (mix(audioSeed ^ imul(i + 1, 0x9e3779b1)) & 15);
            }
          };
          const mark = (buffer) => {
            if (buffer && typeof buffer === "object") rendered.add(buffer);
            return buffer;
          };
          const bufferProto = window.AudioBuffer && window.AudioBuffer.prototype;
          if (bufferProto) {
            const getChannelData = native(bufferProto.getChannelData);
            const nudgeChannel = (buffer, index) => {
              let channels = nudged.get(buffer);
              if (!channels) nudged.set(buffer, (channels = new Set()));
              if (channels.has(index)) return;
              channels.add(index);
              nudge(getChannelData.call(buffer, index), Infinity);
            };
            define(bufferProto, "getChannelData", (original) => function (channel) {
              const data = original.apply(this, arguments);
              try { if (rendered.has(this)) nudgeChannel(this, channel >>> 0); } catch (e) {}
              return data;
            });
            define(bufferProto, "copyFromChannel", (original) => function (destination, channel) {
              if (rendered.has(this) && tagOf(destination) === "Float32Array") {
                try { nudgeChannel(this, channel >>> 0); } catch (e) {}
              }
              return original.apply(this, arguments);
            });
          }

          // What the browser renders or decodes.
          const thenMark = (result) => result && typeof result.then === "function" ? result.then(mark) : result;
          if (window.OfflineAudioContext) {
            define(window.OfflineAudioContext.prototype, "startRendering", (original) => function () {
              return thenMark(original.apply(this, arguments));
            });
          }
          if (window.BaseAudioContext) {
            define(window.BaseAudioContext.prototype, "decodeAudioData", (original) => function (data, success) {
              if (typeof success === "function") {
                arguments[1] = function (buffer) { return success.call(this, mark(buffer)); };
              }
              return thenMark(original.apply(this, arguments));
            });
          }
          const markGetter = (proto, name, before) => {
            const descriptor = proto && getOwnPropertyDescriptor(proto, name);
            if (!descriptor || !descriptor.get) return;
            defineGetter(proto, name, function () {
              const buffer = descriptor.get.call(this);
              if (before) before(this, buffer);
              return mark(buffer);
            });
          };
          markGetter(window.OfflineAudioCompletionEvent && window.OfflineAudioCompletionEvent.prototype, "renderedBuffer");
          const events = new WeakSet();
          markGetter(window.AudioProcessingEvent && window.AudioProcessingEvent.prototype, "inputBuffer", (event, buffer) => {
            if (buffer && !events.has(event)) {
              events.add(event);
              nudged.delete(buffer);
            }
          });

          if (window.AnalyserNode) {
            const proto = window.AnalyserNode.prototype;
            const getter = (name) => {
              const descriptor = getOwnPropertyDescriptor(proto, name);
              return descriptor && descriptor.get ? (node) => descriptor.get.call(node) : (node) => node[name];
            };
            const sizes = { getFloatFrequencyData: getter("frequencyBinCount"), getFloatTimeDomainData: getter("fftSize") };
            for (const name in sizes) {
              if (!proto[name]) continue;
              define(proto, name, (original) => function (array) {
                original.apply(this, arguments);
                try { nudge(array, sizes[name](this)); } catch (e) {}
              });
            }
          }
        }

        """#
    }

    private static func clientRectsScript(seed: UInt32) -> String {
        #"""
        // ClientRects: the edges of the boxes getBoundingClientRect() and
        // getClientRects() report move by 0.00001 to 0.00002 pixels, far below
        // anything visible, but it changes the hashes fingerprinting scripts
        // take of these sizes. An edge is moved by its own value, so measuring
        // twice, or an edge two boxes share, still agrees; zero stays zero, so
        // hidden elements still measure 0. The browser returns new rects on
        // every call, so they are changed in place and keep their types.
        {
          const rectsSeed = forSite(\#(seed));
          const bits = new Float64Array(1);
          const words = new Uint32Array(bits.buffer);
          const shift = (value) => {
            if (value === 0 || !isFinite(value)) return value;
            bits[0] = value;
            const h = mix(mix(rectsSeed ^ words[1]) ^ words[0]);
            return value + (h & 1 ? 1e-5 : -1e-5) * (1 + (h >>> 1) / 2147483648);
          };
          const shiftRect = (rect) => {
            const left = shift(rect.left);
            const top = shift(rect.top);
            const right = max(shift(rect.right), left);
            const bottom = max(shift(rect.bottom), top);
            rect.x = left;
            rect.y = top;
            rect.width = right - left;
            rect.height = bottom - top;
            return rect;
          };
          for (const proto of [window.Element.prototype, window.Range.prototype]) {
            define(proto, "getBoundingClientRect", (original) => function () {
              const rect = original.apply(this, arguments);
              try { shiftRect(rect); } catch (e) {}
              return rect;
            });
            define(proto, "getClientRects", (original) => function () {
              const rects = original.apply(this, arguments);
              try { for (let i = 0; i < rects.length; i++) shiftRect(rects[i]); } catch (e) {}
              return rects;
            });
          }
        }

        """#
    }

    private static func screenScript(_ size: (width: Int, height: Int)) -> String {
        #"""
        // Screen: pages see a real iPhone's or, in iPad mode, iPad's screen size.
        {
          const width = \#(size.width);
          const height = \#(size.height);
          for (const name of ["width", "availWidth"]) defineGetter(window.Screen.prototype, name, () => width);
          for (const name of ["height", "availHeight"]) defineGetter(window.Screen.prototype, name, () => height);
        }

        """#
    }

    /// WebKit takes navigator.platform from the real device, not from the
    /// user agent, so an iPhone would still say "iPhone" next to an iPad's
    /// user agent.
    private static let iPadScript = #"""
    // iPad mode: pages see the platform Safari reports on an iPad.
    defineGetter(window.Navigator.prototype, "platform", () => "iPad");

    """#
}
