import SwiftUI
import WebKit

/// Fingerprint protection, in the spirit of Brave's "farbling". Pages can
/// recognize a device from what it draws (canvas, WebGL), how it renders
/// audio, its screen size and its user agent, even without cookies. With a
/// protection on, pages read invisibly changed pixels and samples, or a common
/// screen size and user agent, so these no longer identify the device.
///
/// Every kind has its own switch and its own seed. A site sees stable values
/// until the seed changes, which keeps sites that read twice and compare
/// working; a new seed gives every site new values for that kind.
enum FingerprintProtection {
    enum Kind: String, CaseIterable, Identifiable {
        case canvas, webGL, audio, screen, userAgent

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
            case .screen: return "Screen Size"
            case .userAgent: return "User Agent"
            }
        }

        var newTitle: LocalizedStringKey {
            switch self {
            case .canvas: return "New Canvas Fingerprint"
            case .webGL: return "New WebGL Fingerprint"
            case .audio: return "New Audio Fingerprint"
            case .screen: return "New Screen Size"
            case .userAgent: return "New User Agent"
            }
        }

        var changedMessage: LocalizedStringKey {
            switch self {
            case .canvas: return "Canvas fingerprint changed"
            case .webGL: return "WebGL fingerprint changed"
            case .audio: return "Audio fingerprint changed"
            case .screen: return "Screen size changed"
            case .userAgent: return "User agent changed"
            }
        }

        var symbol: String {
            switch self {
            case .canvas: return "paintbrush"
            case .webGL: return "cube"
            case .audio: return "waveform"
            case .screen: return "iphone"
            case .userAgent: return "globe"
            }
        }
    }

    static func isEnabled(_ kind: Kind) -> Bool {
        UserDefaults.standard.object(forKey: kind.enabledKey) as? Bool ?? true
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
        } while old.map { pick(UInt32(truncatingIfNeeded: $0), for: kind) == pick(seed, for: kind) } ?? false
        UserDefaults.standard.set(Int(seed), forKey: kind.seedKey)
        return seed
    }

    /// Changes whenever a switch or a seed changes.
    static var signature: String {
        Kind.allCases.map { "\(isEnabled($0)):\(seed($0))" }.joined(separator: ",")
    }

    // MARK: - Screen size and user agent

    /// Screen sizes of common iPhones, in points.
    static let screenSizes: [(width: Int, height: Int)] = [
        (375, 667), (375, 812), (390, 844), (393, 852), (402, 874),
        (414, 896), (428, 926), (430, 932), (440, 956),
    ]

    /// User agents of common iPhone browsers.
    static let userAgents = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.7 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/140.0.7339.122 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/143.0 Mobile/15E148 Safari/605.1.15",
    ]

    static var screenSize: (width: Int, height: Int) {
        screenSizes[pick(seed(.screen), for: .screen)]
    }

    static var userAgent: String {
        userAgents[pick(seed(.userAgent), for: .userAgent)]
    }

    private static func pick(_ seed: UInt32, for kind: Kind) -> Int {
        switch kind {
        case .screen: return Int(seed % UInt32(screenSizes.count))
        case .userAgent: return Int(seed % UInt32(userAgents.count))
        default: return Int(seed)
        }
    }

    // MARK: - Page script

    /// The script for the protections that are on (the user agent is set on
    /// the web view instead), or nil if none of them is.
    @MainActor
    static func userScript() -> WKUserScript? {
        var parts: [String] = []
        if isEnabled(.canvas) { parts.append(canvasScript(seed: seed(.canvas))) }
        if isEnabled(.webGL) { parts.append(webGLScript(seed: seed(.webGL))) }
        if isEnabled(.audio) { parts.append(audioScript(seed: seed(.audio))) }
        if isEnabled(.screen) { parts.append(screenScript(screenSize)) }
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

    private static func screenScript(_ size: (width: Int, height: Int)) -> String {
        #"""
        // Screen: pages see a common iPhone screen size.
        {
          const size = { width: \#(size.width), height: \#(size.height), availWidth: \#(size.width), availHeight: \#(size.height) };
          for (const [name, value] of Object.entries(size)) {
            Object.defineProperty(Screen.prototype, name, { get: () => value, configurable: true, enumerable: true });
          }
        }

        """#
    }
}
