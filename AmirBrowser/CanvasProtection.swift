import WebKit

/// Canvas fingerprint protection. When a page reads pixels back from a canvas
/// (toDataURL, toBlob, getImageData, WebGL readPixels), it gets a copy with an
/// invisible per-site noise, so the fingerprint it computes from them isn't the
/// device's real one. What the page draws on screen is never changed.
///
/// The noise comes from a seed: the same site sees the same fingerprint until
/// the seed changes, which keeps sites that draw and compare twice working.
/// "New Canvas Fingerprint" picks a new seed, so every site sees a new one.
enum CanvasProtection {
    /// The UserDefaults key of the on/off switch in Settings (via @AppStorage).
    static let enabledKey = "canvasProtection"
    private static let seedKey = "canvasSeed"

    static var isEnabled: Bool {
        UserDefaults.standard.object(forKey: enabledKey) as? Bool ?? true
    }

    static var seed: UInt32 {
        if let saved = UserDefaults.standard.object(forKey: seedKey) as? Int {
            return UInt32(truncatingIfNeeded: saved)
        }
        return newSeed()
    }

    @discardableResult
    static func newSeed() -> UInt32 {
        let seed = UInt32.random(in: .min ... .max)
        UserDefaults.standard.set(Int(seed), forKey: seedKey)
        return seed
    }

    @MainActor
    static func userScript(seed: UInt32) -> WKUserScript {
        WKUserScript(source: source(seed: seed), injectionTime: .atDocumentStart, forMainFrameOnly: false)
    }

    static func source(seed: UInt32) -> String {
        #"""
        (() => {
          // Mix the seed with the site's host, so each site sees a different,
          // stable fingerprint (FNV-1a).
          let siteSeed = (\#(seed) ^ 0x811c9dc5) >>> 0;
          for (const ch of location.hostname) {
            siteSeed = Math.imul(siteSeed ^ ch.charCodeAt(0), 0x01000193) >>> 0;
          }

          // Integer hash, so a given pixel always gets the same tweak.
          const mix = (n) => {
            n = Math.imul(n ^ (n >>> 16), 0x7feb352d);
            n = Math.imul(n ^ (n >>> 15), 0x846ca68b);
            return (n ^ (n >>> 16)) >>> 0;
          };

          // Flips the lowest bit of one color channel in about 1 of 32 visible
          // pixels: invisible, but it changes every hash a fingerprinter takes.
          // Pixels are keyed by their position on the canvas, so reading a part
          // of the canvas gives the same noise as reading all of it.
          const addNoise = (data, width, left, top, canvasWidth) => {
            for (let i = 0; i < data.length; i += 4) {
              if (data[i + 3] === 0) continue;
              const p = i >> 2;
              const x = left + (p % width);
              const y = top + Math.floor(p / width);
              const h = mix(siteSeed ^ Math.imul(y * canvasWidth + x + 1, 0x9e3779b1));
              if ((h & 31) === 0) data[i + ((h >>> 5) % 3)] ^= 1;
            }
          };

          const patchGetImageData = (proto) => {
            const getImageData = proto.getImageData;
            proto.getImageData = function (sx, sy) {
              const image = getImageData.apply(this, arguments);
              addNoise(image.data, image.width, sx | 0, sy | 0, this.canvas.width);
              return image;
            };
          };
          patchGetImageData(CanvasRenderingContext2D.prototype);
          if (typeof OffscreenCanvasRenderingContext2D !== "undefined") {
            patchGetImageData(OffscreenCanvasRenderingContext2D.prototype);
          }

          // Exports read a noisy copy, so the canvas on screen stays untouched.
          // A canvas tainted by another site's image can't be copied; the
          // original call then fails exactly as it would without protection.
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

          for (const name of ["WebGLRenderingContext", "WebGL2RenderingContext"]) {
            const proto = window[name] && window[name].prototype;
            if (!proto) continue;
            const readPixels = proto.readPixels;
            proto.readPixels = function (x, y, width, height, format, type, pixels) {
              readPixels.apply(this, arguments);
              if (pixels instanceof Uint8Array && format === this.RGBA) {
                addNoise(pixels, width, x | 0, y | 0, this.drawingBufferWidth);
              }
            };
          }
        })();
        """#
    }
}
