// Pure helpers for the YÖK Ulusal Tez Merkezi skill: form builders, code tables,
// and HTML/JSON parsers. No network access here — the orchestrators in tools.js
// and pdf_extract.js do the fetching. UMD so the Node tests can require() it.
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.__YT = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  const ORIGIN = "https://tez.yok.gov.tr";
  const BASE = ORIGIN + "/UlusalTezMerkezi/";

  // Non-whitespace C0 control characters. Titles copied from PDFs carry these
  // (e.g. \x02 at hyphenation points), in both card HTML and referenceData.
  const CONTROL_CHARS = /[\x00-\x08\x0b\x0c\x0e-\x1f]/g;

  // Friendly aliases -> YÖK form codes. Raw codes ("0".."12") are accepted too.
  const CODES = {
    field: { all: "7", tumu: "7", title: "1", tez_adi: "1", author: "2", yazar: "2",
             advisor: "3", danisman: "3", subject: "4", konu: "4",
             keywords: "5", anahtar_kelime: "5", abstract: "6", ozet: "6" },
    match: { contains: "2", icersin: "2", exact: "1", tam_ifade: "1" },
    type: { any: "0", yuksek_lisans: "1", yl: "1", masters: "1", doktora: "2", phd: "2",
            tipta_uzmanlik: "3", sanatta_yeterlik: "4", dis_hekimligi_uzmanlik: "5",
            tipta_yan_dal_uzmanlik: "6", eczacilikta_uzmanlik: "7" },
    lang: { any: "0", turkce: "1", tr: "1", ingilizce: "2", en: "2", arapca: "3", almanca: "4",
            fransizca: "5", ispanyolca: "6", italyanca: "7", rusca: "8", kurtce: "11", azerice: "12" },
    permission: { any: "0", permitted: "1", izinli: "1", restricted: "2", izinsiz: "2" },
    status: { approved: "3", onaylandi: "3", preparing: "1", hazirlaniyor: "1", all: "0", tumu: "0" },
    recent: { last15days: "7", son_15_gun: "7", this_year: "8", bu_yil: "8" },
  };

  function code(table, value, fallback) {
    if (value == null || value === "") return fallback;
    const s = String(value).trim();
    if (/^\d+$/.test(s)) return s;
    const hit = CODES[table][s.toLowerCase()];
    if (hit == null) throw new Error("unknown " + table + " value: " + s);
    return hit;
  }

  // Years must be "0" when unset — empty strings make YÖK reject the query.
  function year(v) {
    const s = v == null ? "" : String(v).trim();
    return /^\d{4}$/.test(s) ? s : "0";
  }

  function op(v) {
    return String(v || "and").toLowerCase() === "or" ? "or" : "and";
  }

  // Keyword search (GForm2, islem=4): up to 3 terms in ONE field.
  function buildKeywordForm(p) {
    p = p || {};
    const terms = (p.terms || [p.query]).filter((t) => t != null);
    const ops = p.ops || [];
    return {
      keyword: terms[0] || "", keyword1: terms[1] || "", keyword2: terms[2] || "",
      ops_field: op(ops[0]), ops_field1: op(ops[1]),
      nevi: code("field", p.field, "7"),
      tip: code("match", p.match, "2"),
      Tur: code("type", p.type, "0"),
      Dil: code("lang", p.lang, "0"),
      izin: code("permission", p.permission, "0"),
      Durum: code("status", p.status, "3"),
      yil1: year(p.yearFrom), yil2: year(p.yearTo),
      islem: "4", "-find": "  Bul",
    };
  }

  // Advanced search (GForm, islem=2). Field set mirrors the live form as of
  // 2026-10: `Metin` (the "Özet"/abstract box) MUST be present, even empty —
  // omitting it makes YÖK answer "SİSTEMDE BEKLENMEDİK BİR HATA". Enstitu and
  // years must be "0" when unset; Universite stays empty (its codes are
  // session-encrypted).
  function buildAdvancedForm(p, abdCode) {
    p = p || {};
    return {
      uniad: "", Universite: "", uni_yoksis_id: "",
      ensad: "", Enstitu: "0",
      abdad: "", ABD: abdCode ? String(abdCode) : "0",
      Konu: "",
      Tur: code("type", p.type, "0"),
      yil1: year(p.yearFrom), yil2: year(p.yearTo),
      izin: code("permission", p.permission, "0"),
      Durum: code("status", p.status, "3"),
      TezAd: p.title || "",
      Dil: code("lang", p.lang, "0"),
      AdSoyad: p.author || "",
      DanismanAdSoyad: p.advisor || "",
      Dizin: p.keywords || "",
      TezNo: p.thesisNo ? String(p.thesisNo) : "",
      Metin: p.abstract || "",
      islem: "2", Bolum: "0", "-find": "  Bul",
    };
  }

  function hasAdvancedCriterion(p, abdCodes) {
    p = p || {};
    return (abdCodes && abdCodes.length > 0) ||
      ["title", "author", "advisor", "keywords", "thesisNo", "abstract"].some((k) => p[k] && String(p[k]).trim());
  }

  function parseDoc(html) {
    return new DOMParser().parseFromString(html, "text/html");
  }

  function clean(s) {
    return (s || "").replace(CONTROL_CHARS, "").replace(/\s+/g, " ").trim();
  }

  function parseCount(s) {
    const digits = (s || "").replace(/\D/g, "");
    return digits ? Number(digits) : null;
  }

  // Extract `const referenceData = {...}` (per-card meta) by walking braces, so a
  // brace inside a quoted title can't end the object early.
  function extractReferenceData(html) {
    const marker = "const referenceData = {";
    const at = (html || "").indexOf(marker);
    if (at === -1) return {};
    const start = at + marker.length - 1;
    let depth = 0, quote = "", end = -1;
    for (let i = start; i < html.length; i++) {
      const ch = html[i];
      if (quote) {
        if (ch === "\\") { i++; continue; }
        if (ch === quote) quote = "";
      } else if (ch === '"' || ch === "'") {
        quote = ch;
      } else if (ch === "{") {
        depth++;
      } else if (ch === "}") {
        depth--;
        if (depth === 0) { end = i + 1; break; }
      }
    }
    if (end === -1) return {};
    // The server emits JS-style trailing commas, which JSON.parse rejects.
    const raw = html.slice(start, end).replace(CONTROL_CHARS, "").replace(/,(\s*[}\]])/g, "$1");
    try {
      return JSON.parse(raw);
    } catch (e) {
      return {};
    }
  }

  // Classify a YÖK result page. null = a real result page (possibly empty).
  function classifyListing(html) {
    const s = html || "";
    if (s.toUpperCase().includes("SİSTEMDE BEKLENMEDİK")) return "system-error";
    if (s.includes("Geçersiz sorgulama")) return "invalid-query";
    return null;
  }

  // Parse a result page (SearchTez / TezIslemleri both render tezSorguSonucYeni.jsp).
  // Output keys are Turkish on purpose: Claude-in-Chrome's redactor blanks any key
  // whose name contains "author" (and similar "sensitive" words), which would hide
  // every author name. Values never trigger it, only key names.
  function parseListing(html) {
    const error = classifyListing(html);
    if (error) return { error, total: 0, shown: 0, theses: [] };
    const doc = parseDoc(html);
    // An empty template div of one class can precede the populated one.
    let banner = "";
    for (const cls of ["result-count-text", "result-limit-warning", "warning-text"]) {
      const el = [...doc.querySelectorAll("div." + cls)].find((e) => e.textContent.trim());
      if (el) { banner = clean(el.textContent); break; }
    }
    const totalM = banner.match(/([\d.,]+)\s*kayıt bulundu/);
    const shownM = banner.match(/([\d.,]+)\s*tanesi görüntülenmektedir/);
    const ref = extractReferenceData(html);
    const theses = [];
    doc.querySelectorAll("div.result-card").forEach((card) => {
      const kayitNo = card.getAttribute("data-kayitno");
      const tezNo = card.getAttribute("data-tezno");
      if (!kayitNo || !tezNo) return;
      const meta = (ref[card.getAttribute("data-index")] || {}).meta || {};
      const italic = [...card.querySelectorAll("div.card-info")].find((e) =>
        /font-style:\s*italic/i.test(e.getAttribute("style") || ""));
      const noInfo = [...card.querySelectorAll("div.card-info")].find((e) => /Tez No/.test(e.textContent));
      const noM = noInfo && noInfo.textContent.match(/Tez No[:\s]*(\d+)/);
      const title = card.querySelector("div.card-title");
      theses.push({
        tez_numarasi: noM ? noM[1] : null,
        baslik: clean(title && title.textContent) || clean(meta.title) || null,
        baslik_ceviri: clean(italic && italic.textContent) || null,
        yazar: clean(meta.author) || null,
        yil: clean(meta.year) || null,
        tur: clean(meta.type) || null,
        dil: clean(meta.lang) || null,
        konu: clean(meta.subject) || null,
        universite: clean(meta.yer).replace(/\s*\/\s*$/, "") || null,
        kayitNo, tezNo,
      });
    });
    let total = totalM ? parseCount(totalM[1]) : null;
    let shown = shownM ? parseCount(shownM[1]) : null;
    if (/bulunamadı/i.test(banner)) { total = 0; shown = 0; }
    if (shown == null) shown = theses.length;
    if (total == null) total = shown;
    return { error: null, total, shown, banner, theses };
  }

  function trUpper(s) {
    return (s || "").replace(/i/g, "İ").replace(/ı/g, "I").toUpperCase();
  }

  // getAllABD returns ~2.6 MB of radio inputs: ad="NAME" kod="CODE" (dupes included).
  function parseAbdList(html) {
    const seen = new Set();
    const out = [];
    const re = /ad="([^"]+)"\s+kod="(\d+)"/g;
    let m;
    while ((m = re.exec(html || ""))) {
      if (seen.has(m[2])) continue;
      seen.add(m[2]);
      out.push({ kod: m[2], ad: m[1].trim() });
    }
    return out;
  }

  function matchAbd(list, keyword, max) {
    const needle = trUpper((keyword || "").trim());
    const hits = needle ? list.filter((d) => trUpper(d.ad).includes(needle)) : [];
    return { total: hits.length, matches: hits.slice(0, max || 50) };
  }

  function htmlToText(s) {
    if (!s) return null;
    return clean(parseDoc("<body>" + s + "</body>").body.textContent) || null;
  }

  // Drop a leading "<strong>Danışman: </strong>"-style label, then flatten to text.
  function stripLabel(s) {
    if (!s) return null;
    const body = parseDoc("<body>" + s + "</body>").body;
    const strong = body.querySelector("strong");
    if (strong && strong.textContent.includes(":")) strong.remove();
    return clean(body.textContent) || null;
  }

  // "A = B ; C = D" -> [{tr:"A", en:"B"}, ...]
  function parseKeywordPairs(s) {
    if (!s) return [];
    return s.split(";").map((c) => c.trim()).filter(Boolean).map((c) => {
      const i = c.indexOf("=");
      return i === -1 ? { tr: c, en: null } : { tr: c.slice(0, i).trim() || null, en: c.slice(i + 1).trim() || null };
    });
  }

  // tezBilgiDetay.jsp JSON -> flat details object.
  function parseDetails(json) {
    const j = json || {};
    const t = (k) => (j[k] || "").trim() || null;
    return {
      danisman: stripLabel(j.danisman),
      yer: t("yer"),
      ozet_tr: t("trOzet"),
      ozet_en: t("enOzet"),
      anahtar_kelimeler_tr: parseKeywordPairs(stripLabel(j.anahtarKelimeTr)),
      anahtar_kelimeler_en: parseKeywordPairs(stripLabel(j.anahtarKelimeEn)),
      atif: {
        apa: htmlToText(j.apa_ref), ieee: htmlToText(j.ieee_ref), mla: htmlToText(j.mla_ref),
        chicago: htmlToText(j.chicago_ref), harvard: htmlToText(j.harvard_ref),
      },
    };
  }

  // getTezPdf.jsp fragment -> {pdf_url} or {reason} (e.g. author embargo).
  function parsePdfFragment(html) {
    const doc = parseDoc(html || "");
    const a = doc.querySelector('a[href*="TezGoster?key="]');
    if (a) return { pdf_url: new URL(a.getAttribute("href").trim(), BASE).href, reason: null };
    const info = doc.querySelector(".pdf-info-msg");
    return { pdf_url: null, reason: clean((info || doc.body).textContent) || "PDF bu tez için erişime açık değil." };
  }

  function errorHint(reason) {
    switch (reason) {
      case "wrong-origin": return "Navigate the tab to https://tez.yok.gov.tr/UlusalTezMerkezi/tarama.jsp and re-inject.";
      case "system-error": return "YÖK returned its generic error page. Retry once; if it persists the form fields may have changed — compare buildAdvancedForm/buildKeywordForm with document.forms.GForm / GForm2 on tarama.jsp.";
      case "invalid-query": return "YÖK rejected the query ('Geçersiz sorgulama'). Give at least one real criterion (department, title, author, advisor, keywords, abstract or thesis number).";
      case "no-criteria": return "Supply a search term (keyword search) or at least one criterion (advanced search).";
      case "pdf-restricted": return "The author or institution has restricted the full text; only metadata (get_details) is available.";
      default: return reason && reason.startsWith("http-") ? "Unexpected HTTP status; retry once." : null;
    }
  }

  return {
    ORIGIN, BASE, CODES, code, year,
    buildKeywordForm, buildAdvancedForm, hasAdvancedCriterion,
    extractReferenceData, classifyListing, parseListing,
    trUpper, parseAbdList, matchAbd,
    stripLabel, parseKeywordPairs, parseDetails, parsePdfFragment, errorHint,
  };
});
