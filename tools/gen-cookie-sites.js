// Writes AmirBrowser/CookieSites.swift from Noor for Windows' main/warmup.js
// (github.com/kamaltv1010-boop/noor-windows): the popular sites by region,
// the time zones' regions, and the scripts run in the page (the cookie
// banner's button, a link worth following), so both apps visit alike.
//   node tools/gen-cookie-sites.js ../noor-windows/main/warmup.js AmirBrowser/CookieSites.swift
"use strict";
const fs = require("fs");
const path = require("path");
const [, , warmupPath, outPath] = process.argv;
const w = require(path.resolve(warmupPath));
const src = fs.readFileSync(path.resolve(warmupPath), "utf8");

// The ZONES list isn't exported: read it from the source.
const zonesBlock = src.slice(src.indexOf("const ZONES = ["), src.indexOf("];", src.indexOf("const ZONES = [")) + 2);
const ZONES = eval(zonesBlock.replace("const ZONES = ", "(") .replace(/;$/, ")"));
// The link rules aren't exported either.
const grab = (name) => {
  const start = src.indexOf(`const ${name} = `);
  const end = src.indexOf(";\n", start);
  return eval(src.slice(start + `const ${name} = `.length, end));
};
const AVOID_PATH = grab("AVOID_PATH");
const AVOID_TEXT = grab("AVOID_TEXT");
const FILES = grab("FILES");

const swiftString = (s) => JSON.stringify(s); // plain ASCII-safe-ish; JSON escapes are valid in Swift strings except \/ and \u
const check = (s) => {
  if (/\\u|\\\//.test(JSON.stringify(s))) throw new Error("Escape not valid in Swift: " + s);
  return JSON.stringify(s);
};
const raw = (s) => {
  if (s.includes('"#')) throw new Error("Can't put in a raw string: " + s);
  return `#"${s}"#`;
};
const rawBlock = (s) => {
  if (s.includes('"""#')) throw new Error("Can't put in a raw block");
  return `#"""\n${s}\n"""#`;
};

const regions = Object.keys(w.SITES);
const sitesSwift = regions.map((region) => {
  const list = w.SITES[region].map(check);
  const lines = [];
  for (let i = 0; i < list.length; i += 3) lines.push("            " + list.slice(i, i + 3).join(", ") + ",");
  return `        ${check(region)}: [\n${lines.join("\n")}\n        ],`;
}).join("\n");

const zonesSwift = ZONES.map(([pattern, list]) => `        (${raw(pattern.source)}, [${list.map(check).join(", ")}]),`).join("\n");

// The banner's button, pressed: the same buttons and words as Windows',
// clicked in the page (no real tap reaches a page from an app on iOS).
const consentJS = `(() => {
  const SELECTORS = ${JSON.stringify(w.CONSENT_SELECTORS)};
  const WORDS = new RegExp(${JSON.stringify(w.CONSENT_WORDS.source)}, "i");
  const ABOUT = new RegExp(${JSON.stringify(w.CONSENT_ABOUT.source)}, "i");
  const visible = (el) => {
    if (!el || typeof el.getBoundingClientRect !== "function") return false;
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4 || r.bottom <= 0 || r.right <= 0 || r.top >= innerHeight || r.left >= innerWidth) return false;
    const s = getComputedStyle(el);
    return s.visibility !== "hidden" && s.display !== "none" && Number(s.opacity) > 0.1 && s.pointerEvents !== "none";
  };
  const press = (el, how) => {
    try { el.focus({ preventScroll: true }); } catch (e) {}
    el.click();
    return how;
  };
  const roots = [document];
  for (const host of document.querySelectorAll("#usercentrics-root, #usercentrics-cmp-ui")) {
    if (host.shadowRoot) roots.push(host.shadowRoot);
  }
  for (const root of roots) {
    for (const selector of SELECTORS) {
      let el = null;
      try { el = root.querySelector(selector); } catch (e) {}
      if (visible(el)) return press(el, selector);
    }
  }
  for (const root of roots) {
    for (const el of root.querySelectorAll("button, [role=button], input[type=button], input[type=submit]")) {
      const text = String(el.innerText || el.value || el.getAttribute("aria-label") || "").trim().replace(/\\s+/g, " ");
      if (!text || text.length > 40 || !WORDS.test(text) || !visible(el)) continue;
      let box = el.parentElement;
      for (let i = 0; i < 6 && box && box !== document.body && box !== document.documentElement; i++, box = box.parentElement) {
        const said = (box.id || "") + " " + (typeof box.className === "string" ? box.className : "") + " " + (box.getAttribute("aria-label") || "");
        if (ABOUT.test(said) || ABOUT.test(String(box.innerText || "").slice(0, 600))) return press(el, "words");
      }
    }
  }
  return null;
})()`;

// Another page of the site a reader might open: the same rules as
// Windows' pickLink, run in the page.
const linksJS = `(() => {
  const AVOID_PATH = new RegExp(${JSON.stringify(AVOID_PATH.source)}, "i");
  const AVOID_TEXT = new RegExp(${JSON.stringify(AVOID_TEXT.source)}, "i");
  const FILES = new RegExp(${JSON.stringify(FILES.source)}, "i");
  const siteKey = ${w.siteKey.toString()};
  const pickLink = ${w.pickLink.toString()};
  const links = [];
  for (const a of document.querySelectorAll("a[href]")) {
    if (links.length >= 300) break;
    const r = a.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    const s = getComputedStyle(a);
    if (s.visibility === "hidden" || s.display === "none") continue;
    links.push({ href: a.href, text: String(a.innerText || a.getAttribute("aria-label") || a.title || "").trim().replace(/\\s+/g, " ").slice(0, 120), download: a.hasAttribute("download") });
  }
  return pickLink(links, location.href) || null;
})()`;

// Both scripts must run as they are.
new Function(`return ${consentJS}`);
new Function(`return ${linksJS}`);

const out = `import Foundation

// Made by tools/gen-cookie-sites.js from Noor for Windows' main/warmup.js:
// change them there, and run it again.

/// Where "Collect Cookies" goes (see CookieCollector): popular sites, the
/// world's and a region's by the time zone, as Noor for Windows visits.
enum CookieSites {
    /// Popular sites, by where their visitors are: the world's ("global"),
    /// and a country's (or the Arab world's). A visit starts at the home page.
    static let popular: [String: [String]] = [
${sitesSwift}
    ]

    /// The regions whose sites a time zone's visitors go to, besides the
    /// world's, the first the most.
    static let zones: [(pattern: String, regions: [String])] = [
${zonesSwift}
    ]

    /// Presses the button that accepts the page's cookie banner, if there is
    /// one; what it found it by, or null. Runs in a world of its own.
    static let acceptBannerScript = ${rawBlock(consentJS)}

    /// Another page of the page's site a reader might open (an article, a
    /// product, a section; never one that signs in or out, buys, deletes or
    /// downloads), or null. Runs in a world of its own.
    static let pickLinkScript = ${rawBlock(linksJS)}
}
`;
fs.writeFileSync(path.resolve(outPath), out);
console.log(`Wrote ${outPath}: ${regions.length} regions, ${regions.reduce((n, r) => n + w.SITES[r].length, 0)} sites, ${ZONES.length} zone rules`);
