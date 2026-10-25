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
        var seed: UInt32
        repeat {
            seed = .random(in: .min ... .max)
            // A new screen size or user agent must actually differ.
        } while old.map { visibleValue(UInt32(truncatingIfNeeded: $0), for: kind) == visibleValue(seed, for: kind) } ?? false
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

    /// The device whose screen size pages see.
    static var screenDevice: Device {
        device(for: seed(.screen))
    }

    /// The device whose user agent pages see.
    static var userAgentDevice: Device {
        device(for: seed(.userAgent))
    }

    static var screenSize: (width: Int, height: Int) {
        (screenDevice.width, screenDevice.height)
    }

    static var userAgent: String {
        userAgentDevice.userAgent
    }

    private static func device(for seed: UInt32) -> Device {
        let all = devices
        return all[Int(seed % UInt32(all.count))]
    }

    /// What a seed shows the user for a kind; a new seed must change it.
    private static func visibleValue(_ seed: UInt32, for kind: Kind) -> String {
        let device = device(for: seed)
        switch kind {
        case .screen: return "\(device.width)x\(device.height)"
        case .userAgent: return device.userAgent
        default: return String(seed)
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
            const getImageData = proto.getImageData;
            proto.getImageData = function (sx, sy) {
              const image = getImageData.apply(this, arguments);
              addPixelNoise(canvasSeed, image.data, image.width, sx | 0, sy | 0, this.canvas.width);
              return image;
            };
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
            const original = canvasProto[name];
            canvasProto[name] = function () {
              return original.apply(noisyCopy(this, makeCanvas) || this, arguments);
            };
          }
          if (typeof OffscreenCanvas !== "undefined" && OffscreenCanvas.prototype.convertToBlob) {
            const convertToBlob = OffscreenCanvas.prototype.convertToBlob;
            OffscreenCanvas.prototype.convertToBlob = function () {
              const copy = noisyCopy(this, (width, height) => new OffscreenCanvas(width, height));
              return convertToBlob.apply(copy || this, arguments);
            };
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
            const readPixels = proto.readPixels;
            proto.readPixels = function (x, y, width, height, format, type, pixels) {
              readPixels.apply(this, arguments);
              if (pixels instanceof Uint8Array && format === this.RGBA) {
                addPixelNoise(webGLSeed, pixels, width, x | 0, y | 0, this.drawingBufferWidth);
              }
            };
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
            const getChannelData = AudioBuffer.prototype.getChannelData;
            AudioBuffer.prototype.getChannelData = function (channel) {
              const data = getChannelData.apply(this, arguments);
              let channels = nudged.get(this);
              if (!channels) nudged.set(this, (channels = new Set()));
              if (!channels.has(channel)) {
                channels.add(channel);
                nudge(data, channel);
              }
              return data;
            };
            const copyFromChannel = AudioBuffer.prototype.copyFromChannel;
            if (copyFromChannel) {
              AudioBuffer.prototype.copyFromChannel = function (destination, channel) {
                this.getChannelData(channel);
                return copyFromChannel.apply(this, arguments);
              };
            }
          }
          if (typeof AnalyserNode !== "undefined") {
            for (const name of ["getFloatFrequencyData", "getFloatTimeDomainData"]) {
              const original = AnalyserNode.prototype[name];
              if (!original) continue;
              AnalyserNode.prototype[name] = function (array) {
                original.apply(this, arguments);
                nudge(array, 0x51ed270b);
              };
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
            const getBoundingClientRect = proto.getBoundingClientRect;
            proto.getBoundingClientRect = function () {
              return shiftRect(getBoundingClientRect.apply(this, arguments));
            };
            const getClientRects = proto.getClientRects;
            proto.getClientRects = function () {
              const rects = getClientRects.apply(this, arguments);
              for (let i = 0; i < rects.length; i++) shiftRect(rects[i]);
              return rects;
            };
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
            Object.defineProperty(Screen.prototype, name, { get: () => value, configurable: true, enumerable: true });
          }
        }

        """#
    }

    /// WebKit takes navigator.platform from the real device, not from the
    /// user agent, so an iPhone would still say "iPhone" next to an iPad's
    /// user agent.
    private static let iPadScript = #"""
    // iPad mode: pages see the platform Safari reports on an iPad.
    Object.defineProperty(Navigator.prototype, "platform", { get: () => "iPad", configurable: true, enumerable: true });

    """#
}
