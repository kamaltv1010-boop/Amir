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
/// working; a new seed gives every site new values for that kind.
enum FingerprintProtection {
    enum Kind: String, CaseIterable, Identifiable {
        case canvas, webGL, audio, clientRects, screen, userAgent

        var id: Self { self }

        var enabledKey: String {
            self == .canvas ? "canvasProtection" : "protection.\(rawValue)"
        }

        fileprivate var seedKey: String {
            self == .canvas ? "canvasSeed" : "seed.\(rawValue)"
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
    /// mode, or the one Safari itself sends here. Desktop mode keeps
    /// WebKit's own.
    static func userAgent(protections: Bool, desktopMode: Bool) -> String? {
        if desktopMode {
            return nil
        }
        if isIPadMode || (protections && isEnabled(.userAgent)) {
            return userAgent
        }
        return safariUserAgent
    }

    /// What Safari sends on this iPhone. WebKit's own user agent leaves out
    /// Safari's "Version/" and "Safari/" parts, which some sign-in pages
    /// refuse as an app's built-in browser.
    static let safariUserAgent: String = {
        let version = ProcessInfo.processInfo.operatingSystemVersion
        let system: String
        if version.majorVersion >= 26 {
            // Safari freezes the system version at 18.6, and 18.7 from 26.2.
            system = version.majorVersion == 26 && version.minorVersion < 2 ? "18_6" : "18_7"
        } else {
            let parts = [version.majorVersion, version.minorVersion] + (version.patchVersion > 0 ? [version.patchVersion] : [])
            system = parts.map(String.init).joined(separator: "_")
        }
        return "Mozilla/5.0 (iPhone; CPU iPhone OS \(system) like Mac OS X) AppleWebKit/605.1.15 "
            + "(KHTML, like Gecko) Version/\(version.majorVersion).\(version.minorVersion) Mobile/15E148 Safari/604.1"
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
    /// `protections` (shields down for the site) only iPad mode is left. In
    /// desktop mode WebKit reports a Mac on its own, so iPad mode leaves it
    /// alone there.
    @MainActor
    static func userScript(desktopMode: Bool, protections: Bool = true) -> WKUserScript? {
        var parts: [String] = []
        if protections {
            if isEnabled(.canvas) { parts.append(canvasScript(seed: seed(.canvas))) }
            if isEnabled(.webGL) { parts.append(webGLScript(seed: seed(.webGL))) }
            if isEnabled(.audio) { parts.append(audioScript(seed: seed(.audio))) }
            if isEnabled(.clientRects) { parts.append(clientRectsScript(seed: seed(.clientRects))) }
            if isEnabled(.screen) { parts.append(screenScript(screenSize)) }
        }
        if isIPadMode && !desktopMode { parts.append(iPadScript) }
        guard !parts.isEmpty else { return nil }
        let source = "(() => {\n" + helpers + parts.joined(separator: "\n") + "})();"
        return WKUserScript(source: source, injectionTime: .atDocumentStart, forMainFrameOnly: false)
    }

    private static let helpers = #"""
    // Keeps every built-in we replace indistinguishable from the original, so
    // a site that checks for a tampered browser sees nothing changed and works
    // as it would in Safari. Each replacement keeps the native name and length,
    // and reports the same "[native code]" from toString(): a site reads
    // toString() to tell a patched function from a real one, so without this
    // the protections themselves give the browser away. A WeakMap sends each
    // replacement's (and the patched toString's own) toString() to the real
    // function it stands for.
    const nativeToString = Function.prototype.toString;
    const originals = new WeakMap();
    const patchedToString = function toString() {
      return nativeToString.apply(originals.get(this) || this, arguments);
    };
    originals.set(patchedToString, nativeToString);
    Function.prototype.toString = patchedToString;

    // Replaces object[name] (a method) with make(original), keeping the native
    // name, length and "[native code]".
    const define = (object, name, make) => {
      const original = object && object[name];
      if (typeof original !== "function") return;
      const replacement = make(original);
      for (const key of ["name", "length"]) {
        const descriptor = Object.getOwnPropertyDescriptor(original, key);
        if (descriptor) {
          try { Object.defineProperty(replacement, key, descriptor); } catch (e) {}
        }
      }
      originals.set(replacement, original);
      object[name] = replacement;
    };

    // Replaces a property's getter, keeping the native enumerability and the
    // native "[native code]" on the getter.
    const defineGetter = (object, name, get) => {
      const descriptor = Object.getOwnPropertyDescriptor(object, name);
      if (descriptor && descriptor.get) originals.set(get, descriptor.get);
      Object.defineProperty(object, name, {
        get,
        configurable: true,
        enumerable: descriptor ? descriptor.enumerable : true,
      });
    };

    // Mixes a seed with the site's host, so each site sees different, stable
    // values (FNV-1a).
    const forSite = (seed) => {
      let value = (seed ^ 0x811c9dc5) >>> 0;
      for (const ch of location.hostname) {
        value = Math.imul(value ^ ch.charCodeAt(0), 0x01000193) >>> 0;
      }
      return value;
    };

    // Integer hash, so a given pixel or sample always gets the same tweak.
    const mix = (n) => {
      n = Math.imul(n ^ (n >>> 16), 0x7feb352d);
      n = Math.imul(n ^ (n >>> 15), 0x846ca68b);
      return (n ^ (n >>> 16)) >>> 0;
    };

    // Flips the lowest bit of one color channel in about 1 of 32 visible
    // pixels: invisible, but it changes every hash a fingerprinter takes.
    // Pixels are keyed by their position, so reading part of an image gives
    // the same noise as reading all of it.
    const addPixelNoise = (seed, data, width, left, top, fullWidth) => {
      for (let i = 0; i < data.length; i += 4) {
        if (data[i + 3] === 0) continue;
        const p = i >> 2;
        const x = left + (p % width);
        const y = top + Math.floor(p / width);
        const h = mix(seed ^ Math.imul(y * fullWidth + x + 1, 0x9e3779b1));
        if ((h & 31) === 0) data[i + ((h >>> 5) % 3)] ^= 1;
      }
    };

    """#

    private static func canvasScript(seed: UInt32) -> String {
        #"""
        // Canvas: reads get pixel noise. Exports read a noisy copy, so the
        // canvas on screen is never changed. A canvas tainted by another
        // site's image can't be copied; the call then fails as it normally would.
        {
          const canvasSeed = forSite(\#(seed));
          const patchGetImageData = (proto) => {
            define(proto, "getImageData", (getImageData) => function (sx, sy) {
              const image = getImageData.apply(this, arguments);
              addPixelNoise(canvasSeed, image.data, image.width, sx | 0, sy | 0, this.canvas.width);
              return image;
            });
          };
          patchGetImageData(CanvasRenderingContext2D.prototype);
          if (typeof OffscreenCanvasRenderingContext2D !== "undefined") {
            patchGetImageData(OffscreenCanvasRenderingContext2D.prototype);
          }

          const noisyCopy = (canvas, makeCanvas) => {
            const { width, height } = canvas;
            if (!width || !height) return null;
            try {
              const copy = makeCanvas(width, height);
              const context = copy.getContext("2d");
              context.drawImage(canvas, 0, 0);
              context.putImageData(context.getImageData(0, 0, width, height), 0, 0);
              return copy;
            } catch (e) {
              return null;
            }
          };
          const makeCanvas = (width, height) =>
            Object.assign(document.createElement("canvas"), { width, height });

          const canvasProto = HTMLCanvasElement.prototype;
          for (const name of ["toDataURL", "toBlob"]) {
            define(canvasProto, name, (original) => function () {
              return original.apply(noisyCopy(this, makeCanvas) || this, arguments);
            });
          }
          if (typeof OffscreenCanvas !== "undefined" && OffscreenCanvas.prototype.convertToBlob) {
            define(OffscreenCanvas.prototype, "convertToBlob", (convertToBlob) => function () {
              const copy = noisyCopy(this, (width, height) => new OffscreenCanvas(width, height));
              return convertToBlob.apply(copy || this, arguments);
            });
          }
        }

        """#
    }

    private static func webGLScript(seed: UInt32) -> String {
        #"""
        // WebGL: pixels read back with readPixels get pixel noise.
        {
          const webGLSeed = forSite(\#(seed));
          for (const name of ["WebGLRenderingContext", "WebGL2RenderingContext"]) {
            const proto = window[name] && window[name].prototype;
            if (!proto) continue;
            define(proto, "readPixels", (readPixels) => function (x, y, width, height, format, type, pixels) {
              readPixels.apply(this, arguments);
              if (pixels instanceof Uint8Array && format === this.RGBA) {
                addPixelNoise(webGLSeed, pixels, width, x | 0, y | 0, this.drawingBufferWidth);
              }
            });
          }
        }

        """#
    }

    private static func audioScript(seed: UInt32) -> String {
        #"""
        // Audio: about 1 in 16 rendered samples moves by about 0.00000005 at
        // most, far below hearing, but it changes the sums audio fingerprinting
        // scripts compute. Each buffer channel is changed once, not on every read.
        {
          const audioSeed = forSite(\#(seed));
          const nudge = (data, salt) => {
            for (let i = 0; i < data.length; i++) {
              const h = mix(audioSeed ^ salt ^ Math.imul(i + 1, 0x9e3779b1));
              if ((h & 15) === 0) data[i] += ((h >>> 4) / 268435456 - 0.5) * 1e-7;
            }
          };
          if (typeof AudioBuffer !== "undefined") {
            const nudged = new WeakMap();
            define(AudioBuffer.prototype, "getChannelData", (getChannelData) => function (channel) {
              const data = getChannelData.apply(this, arguments);
              let channels = nudged.get(this);
              if (!channels) nudged.set(this, (channels = new Set()));
              if (!channels.has(channel)) {
                channels.add(channel);
                nudge(data, channel);
              }
              return data;
            });
            if (AudioBuffer.prototype.copyFromChannel) {
              define(AudioBuffer.prototype, "copyFromChannel", (copyFromChannel) => function (destination, channel) {
                this.getChannelData(channel);
                return copyFromChannel.apply(this, arguments);
              });
            }
          }
          if (typeof AnalyserNode !== "undefined") {
            for (const name of ["getFloatFrequencyData", "getFloatTimeDomainData"]) {
              if (!AnalyserNode.prototype[name]) continue;
              define(AnalyserNode.prototype, name, (original) => function (array) {
                original.apply(this, arguments);
                nudge(array, 0x51ed270b);
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
            if (value === 0 || !Number.isFinite(value)) return value;
            bits[0] = value;
            const h = mix(mix(rectsSeed ^ words[1]) ^ words[0]);
            return value + (h & 1 ? 1e-5 : -1e-5) * (1 + (h >>> 1) / 2147483648);
          };
          const shiftRect = (rect) => {
            const left = shift(rect.left);
            const top = shift(rect.top);
            const right = Math.max(shift(rect.right), left);
            const bottom = Math.max(shift(rect.bottom), top);
            rect.x = left;
            rect.y = top;
            rect.width = right - left;
            rect.height = bottom - top;
            return rect;
          };
          for (const proto of [Element.prototype, Range.prototype]) {
            define(proto, "getBoundingClientRect", (original) => function () {
              return shiftRect(original.apply(this, arguments));
            });
            define(proto, "getClientRects", (original) => function () {
              const rects = original.apply(this, arguments);
              for (let i = 0; i < rects.length; i++) shiftRect(rects[i]);
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
          const size = { width: \#(size.width), height: \#(size.height), availWidth: \#(size.width), availHeight: \#(size.height) };
          for (const [name, value] of Object.entries(size)) {
            defineGetter(Screen.prototype, name, () => value);
          }
        }

        """#
    }

    /// WebKit takes navigator.platform from the real device, not from the
    /// user agent, so an iPhone would still say "iPhone" next to an iPad's
    /// user agent.
    private static let iPadScript = #"""
    // iPad mode: pages see the platform Safari reports on an iPad.
    defineGetter(Navigator.prototype, "platform", () => "iPad");

    """#
}
