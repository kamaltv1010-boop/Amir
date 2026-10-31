import Foundation

// Made by tools/gen-cookie-sites.js from Noor for Windows' main/warmup.js:
// change them there, and run it again.

/// Where "Collect Cookies" goes (see CookieCollector): popular sites, the
/// world's and a region's by the time zone, as Noor for Windows visits.
enum CookieSites {
    /// Popular sites, by where their visitors are: the world's ("global"),
    /// and a country's (or the Arab world's). A visit starts at the home page.
    static let popular: [String: [String]] = [
        "global": [
            "https://www.google.com/", "https://www.youtube.com/", "https://www.wikipedia.org/",
            "https://www.amazon.com/", "https://www.ebay.com/", "https://www.bing.com/",
            "https://www.yahoo.com/", "https://www.msn.com/", "https://www.reddit.com/",
            "https://www.linkedin.com/", "https://www.pinterest.com/", "https://www.instagram.com/",
            "https://www.facebook.com/", "https://www.tiktok.com/", "https://www.netflix.com/",
            "https://open.spotify.com/", "https://www.apple.com/", "https://www.microsoft.com/",
            "https://www.imdb.com/", "https://stackoverflow.com/", "https://github.com/",
            "https://www.twitch.tv/", "https://www.quora.com/", "https://medium.com/",
            "https://www.booking.com/", "https://www.tripadvisor.com/", "https://www.aliexpress.com/",
            "https://weather.com/", "https://www.bbc.com/", "https://edition.cnn.com/",
            "https://www.theguardian.com/", "https://www.nytimes.com/", "https://www.forbes.com/",
            "https://www.espn.com/", "https://www.accuweather.com/", "https://duckduckgo.com/",
            "https://x.com/", "https://www.canva.com/", "https://www.paypal.com/",
            "https://www.shein.com/", "https://www.temu.com/", "https://www.whatsapp.com/",
            "https://www.airbnb.com/", "https://www.dailymotion.com/", "https://www.samsung.com/",
        ],
        "MA": [
            "https://www.hespress.com/", "https://le360.ma/", "https://www.avito.ma/",
            "https://www.jumia.ma/", "https://lematin.ma/", "https://www.alyaoum24.com/",
            "https://www.hibapress.com/", "https://medias24.com/", "https://www.goud.ma/",
            "https://www.elbotola.com/", "https://www.yabiladi.com/", "https://www.moroccoworldnews.com/",
            "https://www.mubawab.ma/", "https://telquel.ma/", "https://www.marocannonces.com/",
            "https://www.chouftv.ma/", "https://www.barlamane.com/", "https://snrtnews.com/",
            "https://www.lesiteinfo.com/",
        ],
        "AR": [
            "https://www.aljazeera.net/", "https://www.skynewsarabia.com/", "https://www.alarabiya.net/",
            "https://www.kooora.com/", "https://www.youm7.com/", "https://arabic.cnn.com/",
            "https://www.almaany.com/", "https://mawdoo3.com/", "https://www.masrawy.com/",
            "https://arabic.rt.com/", "https://www.independentarabia.com/", "https://www.alquds.co.uk/",
            "https://www.yallakora.com/",
        ],
        "FR": [
            "https://www.lemonde.fr/", "https://www.lefigaro.fr/", "https://www.leboncoin.fr/",
            "https://www.francetvinfo.fr/", "https://www.20minutes.fr/", "https://www.orange.fr/",
            "https://www.allocine.fr/", "https://www.marmiton.org/", "https://www.doctissimo.fr/",
            "https://www.ouest-france.fr/", "https://www.lequipe.fr/", "https://www.amazon.fr/",
            "https://www.cdiscount.com/", "https://www.fnac.com/", "https://www.liberation.fr/",
            "https://www.lepoint.fr/", "https://www.bfmtv.com/",
        ],
        "ES": [
            "https://elpais.com/", "https://www.elmundo.es/", "https://www.marca.com/",
            "https://as.com/", "https://www.amazon.es/", "https://www.idealista.com/",
            "https://www.20minutos.es/", "https://www.rtve.es/", "https://www.abc.es/",
            "https://es.wallapop.com/", "https://www.lavanguardia.com/",
        ],
        "DE": [
            "https://www.spiegel.de/", "https://www.bild.de/", "https://www.amazon.de/",
            "https://www.ebay.de/", "https://web.de/", "https://www.gmx.net/",
            "https://www.t-online.de/", "https://www.zeit.de/", "https://www.chip.de/",
            "https://www.kicker.de/", "https://www.otto.de/",
        ],
        "UK": [
            "https://www.bbc.co.uk/", "https://www.dailymail.co.uk/", "https://www.amazon.co.uk/",
            "https://www.ebay.co.uk/", "https://www.rightmove.co.uk/", "https://www.sky.com/",
            "https://www.argos.co.uk/", "https://www.independent.co.uk/", "https://www.telegraph.co.uk/",
            "https://www.gov.uk/", "https://www.autotrader.co.uk/",
        ],
        "US": [
            "https://www.walmart.com/", "https://www.target.com/", "https://www.foxnews.com/",
            "https://www.usatoday.com/", "https://www.washingtonpost.com/", "https://www.craigslist.org/",
            "https://www.zillow.com/", "https://www.yelp.com/", "https://www.homedepot.com/",
            "https://www.bestbuy.com/", "https://www.nbcnews.com/", "https://www.etsy.com/",
            "https://www.costco.com/", "https://www.indeed.com/", "https://www.npr.org/",
        ],
        "IT": [
            "https://www.repubblica.it/", "https://www.corriere.it/", "https://www.amazon.it/",
            "https://www.subito.it/", "https://www.gazzetta.it/", "https://www.ansa.it/",
            "https://www.libero.it/", "https://www.ilmeteo.it/",
        ],
        "NL": [
            "https://www.nu.nl/", "https://www.bol.com/", "https://www.marktplaats.nl/",
            "https://nos.nl/", "https://www.telegraaf.nl/", "https://www.ad.nl/",
        ],
        "TR": [
            "https://www.hurriyet.com.tr/", "https://www.sahibinden.com/", "https://www.trendyol.com/",
            "https://www.milliyet.com.tr/", "https://www.sozcu.com.tr/", "https://www.hepsiburada.com/",
        ],
    ]

    /// The regions whose sites a time zone's visitors go to, besides the
    /// world's, the first the most.
    static let zones: [(pattern: String, regions: [String])] = [
        (#"^Africa\/(Casablanca|El_Aaiun)$"#, ["MA", "FR", "AR"]),
        (#"^Africa\/(Algiers|Tunis)$"#, ["FR", "AR"]),
        (#"^(Africa\/(Cairo|Tripoli|Khartoum)|Asia\/(Riyadh|Dubai|Qatar|Kuwait|Bahrain|Muscat|Baghdad|Amman|Beirut|Damascus|Aden|Gaza|Hebron))$"#, ["AR"]),
        (#"^Europe\/(Paris|Brussels|Luxembourg|Monaco)$"#, ["FR"]),
        (#"^(Europe\/Madrid|Atlantic\/Canary|Africa\/Ceuta)$"#, ["ES"]),
        (#"^Europe\/(Berlin|Vienna|Zurich|Busingen)$"#, ["DE"]),
        (#"^Europe\/(London|Dublin|Isle_of_Man|Jersey|Guernsey)$"#, ["UK"]),
        (#"^Europe\/(Rome|Vatican|San_Marino)$"#, ["IT"]),
        (#"^Europe\/Amsterdam$"#, ["NL"]),
        (#"^(Europe|Asia)\/Istanbul$"#, ["TR"]),
        (#"^(America\/(New_York|Chicago|Denver|Los_Angeles|Phoenix|Anchorage|Detroit|Boise|Indiana\/\w+|Kentucky\/\w+|Toronto|Vancouver|Edmonton|Winnipeg|Halifax|Regina|St_Johns)|Pacific\/Honolulu)$"#, ["US"]),
    ]

    /// Presses the button that accepts the page's cookie banner, if there is
    /// one; what it found it by, or null. Runs in a world of its own.
    static let acceptBannerScript = #"""
(() => {
  const SELECTORS = ["#onetrust-accept-btn-handler","#accept-recommended-btn-handler","#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll","#CybotCookiebotDialogBodyButtonAccept","#didomi-notice-agree-button","#didomi-popup .didomi-button-highlight",".qc-cmp2-summary-buttons button[mode='primary']","#qc-cmp2-ui button[mode='primary']",".fc-cta-consent","#truste-consent-button","#axeptio_btn_acceptAll",".cky-btn-accept",".cmplz-btn.cmplz-accept",".osano-cm-accept-all","[data-tid='banner-accept']",".cm-btn-accept-all",".iubenda-cs-accept-btn","#tarteaucitronPersonalize2","#tarteaucitronAllAllowed",".moove-gdpr-infobar-allow-all","#c-p-bn",".cc-allow","[data-testid='uc-accept-all-button']","#sp-cc-accept","#L2AGLb","#bnp_btn_accept","button[data-cookiebanner='accept_button']","[data-testid='cookie-policy-manage-dialog-accept-button']","#cookie-accept","#accept-cookies","#acceptCookies","#cookieAccept",".accept-cookies",".js-accept-cookies"];
  const WORDS = new RegExp("^(accept|accept all|accept all cookies|accept cookies|accept and close|allow|allow all|allow all cookies|allow cookies|agree|i agree|agree and close|agree & close|agree and continue|got it|ok|okay|i accept|yes, i accept|accepter|tout accepter|accepter tout|accepter et fermer|accepter et continuer|accepter les cookies|j'accepte|j’accepte|autoriser|tout autoriser|autoriser tous les cookies|d'accord|ok, j'ai compris|aceptar|aceptar todo|aceptar todas|aceptar cookies|aceptar y cerrar|alle akzeptieren|akzeptieren|alle zulassen|zustimmen|einverstanden|accetta|accetta tutto|accetta tutti|accetto|kabul et|tümünü kabul et|kabul ediyorum|alles accepteren|accepteren|akkoord|موافق|أوافق|اوافق|قبول|قبول الكل|قبول الجميع|اقبل|أقبل|حسنا|حسناً|السماح بالكل)$", "i");
  const ABOUT = new RegExp("cookie|consent|gdpr|rgpd|privacy|privacidad|confidentialit|vie privée|datenschutz|çerez|kvkk|الكوكيز|ملفات تعريف الارتباط|ملفات الارتباط|الخصوصية", "i");
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
      const text = String(el.innerText || el.value || el.getAttribute("aria-label") || "").trim().replace(/\s+/g, " ");
      if (!text || text.length > 40 || !WORDS.test(text) || !visible(el)) continue;
      let box = el.parentElement;
      for (let i = 0; i < 6 && box && box !== document.body && box !== document.documentElement; i++, box = box.parentElement) {
        const said = (box.id || "") + " " + (typeof box.className === "string" ? box.className : "") + " " + (box.getAttribute("aria-label") || "");
        if (ABOUT.test(said) || ABOUT.test(String(box.innerText || "").slice(0, 600))) return press(el, "words");
      }
    }
  }
  return null;
})()
"""#

    /// Another page of the page's site a reader might open (an article, a
    /// product, a section; never one that signs in or out, buys, deletes or
    /// downloads), or null. Runs in a world of its own.
    static let pickLinkScript = #"""
(() => {
  const AVOID_PATH = new RegExp("(^|[\\/_\\-.?=&#])(log-?in|log-?out|log-?off|sign-?in|sign-?out|sign-?up|sign-?off|signin|signout|signup|register|registration|inscription|connexion|deconnexion|déconnexion|auth|oauth|sso|account|accounts|compte|myaccount|profile|profil|settings|preferences|password|cart|basket|panier|checkout|commande|order|orders|subscribe|subscription|abonnement|unsubscribe|delete|remove|supprimer|download|telecharger|télécharger|print|share|admin|wp-admin|wp-login|cdn-cgi|api|captcha|newsletter)([\\/_\\-.?=&#]|$)|خروج|تسجيل|حذف|حساب|سلة|اشتراك|اشترك", "i");
  const AVOID_TEXT = new RegExp("\\b(log ?in|log ?out|sign ?in|sign ?out|sign ?up|register|subscribe|unsubscribe|my account|account|cart|checkout|delete|download)\\b|s'inscrire|se connecter|se déconnecter|déconnexion|connexion|mon compte|panier|supprimer|télécharger|تسجيل|الدخول|الخروج|اشترك|حسابي|حذف|تحميل", "i");
  const FILES = new RegExp("\\.(pdf|zip|rar|7z|gz|exe|msi|dmg|apk|ipa|iso|mp3|mp4|m4a|avi|mov|wav|jpe?g|png|gif|webp|svg|ico|docx?|xlsx?|pptx?|csv|txt|xml|json|rss|torrent)$", "i");
  const siteKey = (host) => {
  const name = String(host || "").toLowerCase().replace(/\.$/, "");
  if (/^\d+(\.\d+){3}$/.test(name) || name.indexOf(":") !== -1) {
    return name;
  }
  const parts = name.split(".").filter(Boolean);
  if (parts.length <= 2) {
    return parts.join(".");
  }
  const second = parts[parts.length - 2];
  const top = parts[parts.length - 1];
  const keep = top.length === 2 && /^(co|com|net|org|gov|ac|edu|gob|or|ne|go)$/.test(second) ? 3 : 2;
  return parts.slice(-keep).join(".");
};
  const pickLink = (links, pageURL, random = Math.random) => {
  let page;
  try {
    page = new URL(pageURL);
  } catch (error) {
    return null;
  }
  const site = siteKey(page.hostname);
  const here = page.href.split("#")[0];
  const fine = [];
  for (const link of Array.isArray(links) ? links : []) {
    if (!link || typeof link.href !== "string" || link.download) {
      continue;
    }
    let url;
    try {
      url = new URL(link.href);
    } catch (error) {
      continue;
    }
    if ((url.protocol !== "https:" && url.protocol !== "http:") || url.username || url.password || siteKey(url.hostname) !== site) {
      continue;
    }
    if (url.href.split("#")[0] === here) {
      continue;
    }
    let path = url.pathname + url.search;
    try {
      path = decodeURIComponent(path);
    } catch (error) {
      // As it is.
    }
    const text = String(link.text || "").trim();
    if (AVOID_PATH.test(path) || FILES.test(url.pathname) || AVOID_TEXT.test(text)) {
      continue;
    }
    fine.push({ href: url.href, text });
  }
  if (!fine.length) {
    return null;
  }
  // Headlines and product names first: what a reader opens.
  const titled = fine.filter((link) => link.text.length >= 12);
  const pool = titled.length ? titled : fine;
  return pool[Math.floor(random() * pool.length)].href;
};
  const links = [];
  for (const a of document.querySelectorAll("a[href]")) {
    if (links.length >= 300) break;
    const r = a.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    const s = getComputedStyle(a);
    if (s.visibility === "hidden" || s.display === "none") continue;
    links.push({ href: a.href, text: String(a.innerText || a.getAttribute("aria-label") || a.title || "").trim().replace(/\s+/g, " ").slice(0, 120), download: a.hasAttribute("download") });
  }
  return pickLink(links, location.href) || null;
})()
"""#
}
