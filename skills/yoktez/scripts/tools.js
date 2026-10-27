// Orchestrators for the YÖK Tez skill. Inject scripts/lib.js first (defines
// window.__YT), then this file, then end the injection with
// `await window.__YT_xxx(...)` as the last expression. The tab must be on
// https://tez.yok.gov.tr (same-origin fetch carries the JSESSIONID cookie).
//
// Listings are fetched once and cached on window.__YT_cache, so paging through a
// result set ({start, size}) does not re-run the YÖK query.
(function () {
  const YT = window.__YT;
  const cache = (window.__YT_cache = window.__YT_cache || new Map());
  const CACHE_MAX = 6;
  const MAX_ABD = 15;

  function fail(reason, extra) {
    return Object.assign({ error: reason, hint: YT.errorHint(reason) }, extra || {});
  }

  function onYok() {
    return location.origin === YT.ORIGIN;
  }

  // TezIslemleri and SearchTez need a live session; tarama.jsp establishes it.
  async function warm() {
    if (window.__YT_warm) return;
    await fetch(YT.BASE + "tarama.jsp");
    window.__YT_warm = true;
  }

  async function getText(url, init) {
    const res = await fetch(url, init);
    if (!res.ok) throw new Error("http-" + res.status);
    return res.text();
  }

  function post(form) {
    return getText(YT.BASE + "SearchTez", { method: "POST", body: new URLSearchParams(form) });
  }

  async function cached(key, run) {
    if (cache.has(key)) return cache.get(key);
    const value = await run();
    if (!value.error) {
      cache.set(key, value);
      while (cache.size > CACHE_MAX) cache.delete(cache.keys().next().value);
    }
    return value;
  }

  function page(listing, batch, extra) {
    batch = batch || {};
    const start = Math.max(0, Number(batch.start) || 0);
    const size = Math.max(1, Math.min(100, Number(batch.size) || 20));
    const theses = listing.theses.slice(start, start + size);
    const out = Object.assign({
      error: listing.error || null,
      hint: listing.error ? YT.errorHint(listing.error) : null,
      total: listing.total, shown: listing.shown, available: listing.theses.length,
      start, size, returned: theses.length, theses,
    }, extra || {});
    if (listing.total > listing.shown) {
      out.note = "YÖK lists at most " + listing.shown + " of " + listing.total + " matches; narrow the filters to see the rest.";
    }
    return out;
  }

  async function guarded(run) {
    if (!onYok()) return fail("wrong-origin", { total: 0, theses: [] });
    try {
      await warm();
      return await run();
    } catch (e) {
      const msg = String((e && e.message) || e);
      return fail(/^http-\d+$/.test(msg) ? msg : "exception", { detail: msg, total: 0, theses: [] });
    }
  }

  // Keyword search: up to 3 terms, one field. params: {query | terms[], ops[],
  // field, match, type, lang, permission, status, yearFrom, yearTo}.
  window.__YT_search = (params, batch) => guarded(async () => {
    const form = YT.buildKeywordForm(params);
    if (!form.keyword.trim()) return fail("no-criteria", { total: 0, theses: [] });
    const listing = await cached("kw:" + JSON.stringify(form), async () => YT.parseListing(await post(form)));
    return page(listing, batch);
  });

  // Advanced search: any of {abd[], title, author, advisor, keywords, abstract,
  // thesisNo} + {type, lang, permission, status, yearFrom, yearTo}. Several
  // department codes are searched one by one and merged (deduped by kayitNo).
  window.__YT_advanced_search = (params, batch) => guarded(async () => {
    params = params || {};
    const codes = [].concat(params.abd || []).map((c) => String(c).trim()).filter(Boolean);
    if (!YT.hasAdvancedCriterion(params, codes)) return fail("no-criteria", { total: 0, theses: [] });
    if (codes.length > MAX_ABD) {
      return fail("too-many-departments", { hint: "Pass at most " + MAX_ABD + " department codes.", total: 0, theses: [] });
    }
    const key = "adv:" + JSON.stringify(YT.buildAdvancedForm(params)) + "|" + codes.join(",");
    const listing = await cached(key, async () => {
      const runs = codes.length ? codes : [null];
      const merged = { error: null, total: 0, shown: 0, theses: [] };
      const seen = new Set();
      const failures = [];
      for (const c of runs) {
        const part = YT.parseListing(await post(YT.buildAdvancedForm(params, c)));
        if (part.error) { failures.push((c || "-") + ":" + part.error); continue; }
        merged.total += part.total;
        merged.shown += part.shown;
        for (const t of part.theses) {
          if (seen.has(t.kayitNo)) continue;
          seen.add(t.kayitNo);
          merged.theses.push(t);
        }
      }
      if (failures.length === runs.length) merged.error = failures[0].split(":")[1];
      if (failures.length) merged.failures = failures;
      return merged;
    });
    return page(listing, batch, listing.failures ? { failures: listing.failures } : null);
  });

  // Department (Anabilim Dalı) lookup. The full list (~2.6 MB, ~2.5k entries) is
  // fetched once per page load.
  window.__YT_abd = (keyword, opts) => guarded(async () => {
    if (!window.__YT_abd_list) {
      window.__YT_abd_list = YT.parseAbdList(await getText(YT.BASE + "tarama.jsp?ajax=getAllABD&ensGrubu="));
    }
    const r = YT.matchAbd(window.__YT_abd_list, keyword, (opts && opts.max) || 50);
    return { error: r.total ? null : "no-match", keyword, total: r.total, returned: r.matches.length, matches: r.matches };
  });

  // Recently added theses: mode "last15days" (TezIslemleri islem=7) or
  // "this_year" (islem=8, capped at 2000 visible).
  window.__YT_recent = (mode, batch) => guarded(async () => {
    const islem = YT.code("recent", mode, "7");
    const listing = await cached("recent:" + islem, async () =>
      YT.parseListing(await getText(YT.BASE + "TezIslemleri?islem=" + islem)));
    return page(listing, batch, { mode: islem === "8" ? "this_year" : "last15days" });
  });

  // Rich metadata (advisor, abstracts, keywords, citations) for one thesis
  // {kayitNo, tezNo}, or an array of them.
  window.__YT_details = (ids) => guarded(async () => {
    const one = async (id) => {
      if (!id || !id.kayitNo || !id.tezNo) return fail("missing-ids", { hint: "Pass {kayitNo, tezNo} from a search result." });
      const q = "kayitNo=" + encodeURIComponent(id.kayitNo) + "&tezNo=" + encodeURIComponent(id.tezNo);
      const text = await getText(YT.BASE + "tezBilgiDetay.jsp?" + q);
      let json;
      try { json = JSON.parse(text); } catch (e) { return fail("parse-failed", { kayitNo: id.kayitNo }); }
      return Object.assign({ error: null, kayitNo: id.kayitNo, tezNo: id.tezNo }, YT.parseDetails(json));
    };
    if (Array.isArray(ids)) return { error: null, items: await Promise.all(ids.map(one)) };
    return one(ids);
  });
})();
