// Thesis PDF -> text. Inject scripts/lib.js first. tez.yok.gov.tr sends no CSP,
// so pdf.js (v3 UMD, exposes window.pdfjsLib) is loaded from a CDN and its worker
// is run from a blob URL. Pre-set window.pdfjsLib (and optionally
// window.__YT_PDF_WORKER) to skip the network fetch.
//
// Theses are long (often 100-300 pages, several MB), so the default range is the
// first 10 pages; read `page_count` and pull further ranges with
// {firstPage, lastPage}. The parsed document is cached per thesis, so later
// ranges don't re-download the file.
(function () {
  const YT = window.__YT;
  const CDNS = [
    ["https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/legacy/build/pdf.min.js",
     "https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/legacy/build/pdf.worker.min.js"],
    ["https://unpkg.com/pdfjs-dist@3.11.174/legacy/build/pdf.min.js",
     "https://unpkg.com/pdfjs-dist@3.11.174/legacy/build/pdf.worker.min.js"],
  ];
  const DEFAULT_PAGES = 10;
  const docs = (window.__YT_pdf_docs = window.__YT_pdf_docs || new Map());

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = src;
      s.onload = resolve;
      s.onerror = () => reject(new Error("pdfjs-load-failed"));
      document.head.appendChild(s);
    });
  }

  async function pdfjs() {
    let lastErr;
    for (const [lib, worker] of CDNS) {
      try {
        if (!window.pdfjsLib) await loadScript(lib);
        const p = window.pdfjsLib;
        if (!p || !p.getDocument) throw new Error("pdfjs-not-loaded");
        if (p.GlobalWorkerOptions && !p.GlobalWorkerOptions.workerSrc) {
          let src = window.__YT_PDF_WORKER;
          if (!src) {
            const res = await fetch(worker);
            if (!res.ok) throw new Error("pdfjs-worker-load-failed");
            src = URL.createObjectURL(new Blob([await res.text()], { type: "text/javascript" }));
          }
          p.GlobalWorkerOptions.workerSrc = src;
        }
        return p;
      } catch (e) {
        lastErr = e;
      }
    }
    throw lastErr;
  }

  async function open(id) {
    if (docs.has(id.kayitNo)) return docs.get(id.kayitNo);
    const q = "kayitNo=" + encodeURIComponent(id.kayitNo) + "&tezNo=" + encodeURIComponent(id.tezNo);
    const fragRes = await fetch(YT.BASE + "getTezPdf.jsp?" + q);
    if (!fragRes.ok) throw new Error("http-" + fragRes.status);
    const link = YT.parsePdfFragment(await fragRes.text());
    if (!link.pdf_url) return { restricted: link.reason };
    const lib = await pdfjs();
    const res = await fetch(link.pdf_url);
    if (!res.ok) throw new Error("download-failed:" + res.status);
    const data = new Uint8Array(await res.arrayBuffer());
    // Read the size first: getDocument transfers the buffer to the worker,
    // which detaches it (data.length becomes 0).
    const bytes = data.length;
    const pdf = await lib.getDocument({ data }).promise;
    const entry = { pdf, pdf_url: link.pdf_url, bytes };
    docs.set(id.kayitNo, entry);
    while (docs.size > 3) docs.delete(docs.keys().next().value);
    return entry;
  }

  // id: {kayitNo, tezNo} from a search result. opts: {firstPage, lastPage}, 1-based inclusive.
  window.__YT_pdf = async function (id, opts) {
    opts = opts || {};
    if (location.origin !== YT.ORIGIN) return { error: "wrong-origin", hint: YT.errorHint("wrong-origin"), text: "" };
    if (!id || !id.kayitNo || !id.tezNo) return { error: "missing-ids", hint: "Pass {kayitNo, tezNo} from a search result.", text: "" };
    try {
      const entry = await open(id);
      if (entry.restricted) {
        return { error: "pdf-restricted", reason: entry.restricted, hint: YT.errorHint("pdf-restricted"), kayitNo: id.kayitNo, text: "" };
      }
      const n = entry.pdf.numPages;
      const first = Math.min(n, Math.max(1, Number(opts.firstPage) || 1));
      const last = Math.min(n, Math.max(first, Number(opts.lastPage) || first + DEFAULT_PAGES - 1));
      const pages = [];
      for (let i = first; i <= last; i++) {
        const content = await (await entry.pdf.getPage(i)).getTextContent();
        const body = content.items.map((it) => it.str + (it.hasEOL ? "\n" : " ")).join("");
        pages.push("--- Sayfa " + i + " ---\n" + body.replace(/[ \t]{2,}/g, " ").replace(/ +\n/g, "\n"));
      }
      const text = pages.join("\n\n");
      const out = { error: null, kayitNo: id.kayitNo, pdf_url: entry.pdf_url, bytes: entry.bytes,
                    page_count: n, first_page: first, last_page: last, chars: text.length, text };
      // Older theses are often scanned images with no text layer.
      if (text.replace(/--- Sayfa \d+ ---|\s/g, "").length < 50 * (last - first + 1)) {
        out.warning = "Very little text on these pages — the PDF is probably a scan without a text layer (no OCR here).";
      }
      return out;
    } catch (e) {
      return { error: String((e && e.message) || e), kayitNo: id.kayitNo, text: "" };
    }
  };
})();
