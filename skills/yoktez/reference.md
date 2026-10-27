# YÖK Tez skill — reference

All endpoints live under `https://tez.yok.gov.tr/UlusalTezMerkezi/`. They need
the JSESSIONID cookie that `tarama.jsp` sets; `tools.js` fetches `tarama.jsp`
once per page load before its first call.

## Endpoints
| Purpose | Request | Response |
|---|---|---|
| Keyword search | `POST SearchTez` (urlencoded, `islem=4`) | 302 → `tezSorguSonucYeni.jsp` result page |
| Advanced search | `POST SearchTez` (urlencoded, `islem=2`) | same result page |
| Recent theses | `GET TezIslemleri?islem=7` (last 15 days) / `islem=8` (this year) | same result page |
| Department list | `GET tarama.jsp?ajax=getAllABD&ensGrubu=` | ~2.6 MB of `<input ad="…" kod="…">` (dupes included) |
| Metadata | `GET tezBilgiDetay.jsp?kayitNo=…&tezNo=…` | JSON: `danisman, yer, trOzet, enOzet, anahtarKelimeTr, anahtarKelimeEn, apa_ref, ieee_ref, mla_ref, chicago_ref, harvard_ref` |
| PDF link | `GET getTezPdf.jsp?kayitNo=…&tezNo=…` | HTML fragment: `<a href="TezGoster?key=…">` or `.pdf-info-msg` with the embargo reason |
| PDF | `GET TezGoster?key=…` | `application/pdf` |

The POST body **must be `application/x-www-form-urlencoded`** (`URLSearchParams`).
A `FormData` (multipart) body gets YÖK's generic error page.

## Result page
- Cards: `div.result-card[data-index][data-kayitno][data-tezno]`
  - `div.card-title` — original title
  - `div.card-info[style*="italic"]` — translated title
  - `div.card-info` containing `<strong>Tez No:</strong> 928032` — public number
- Per-card meta: inline `const referenceData = { "0": {meta: {author, year,
  subject, type, lang, yer, title}}, … }` — JS object literal with trailing commas
  and stray control characters; `extractReferenceData` brace-walks and cleans it.
- Count banner: first non-empty of `div.result-count-text`,
  `div.result-limit-warning`, `div.warning-text`:
  "Arama sonucunda 7.835 kayıt bulundu. 2.000 tanesi görüntülenmektedir." /
  "Sonuç bulunamadı". YÖK renders at most 2000 cards per query.
- Error pages: "SİSTEMDE BEKLENMEDİK BİR HATA OLUŞTU" (`system-error`),
  "Geçersiz sorgulama" (`invalid-query`).

## Keyword form (GForm2, islem=4)
`keyword, keyword1, keyword2, ops_field, ops_field1 (and|or), nevi (field), tip
(match), Tur, Dil, izin, Durum, yil1, yil2, islem=4, -find="  Bul"`.

## Advanced form (GForm, islem=2) — as of 2026-10
`uniad, Universite, uni_yoksis_id, ensad, Enstitu, abdad, ABD, Konu, Tur, yil1,
yil2, izin, Durum, TezAd, Dil, AdSoyad, DanismanAdSoyad, Dizin, TezNo, Metin,
islem=2, Bolum=0, -find="  Bul"`.
- **`Metin` (the "Özet"/abstract box) must be sent, even empty** — without it YÖK
  answers with `system-error`. It was added to the form in 2026.
- `Enstitu`, `ABD`, `yil1`, `yil2` must be `"0"` when unset; empty strings give
  `invalid-query`. All criteria empty also gives `invalid-query`.
- `Universite` codes are session-encrypted; leave it empty.
- If YÖK changes the form again, diff `buildAdvancedForm` against
  `[...document.forms.GForm.elements].map(e => e.name)` on `tarama.jsp`.

## Code tables (friendly alias → code; raw codes accepted too)
| Param | Values |
|---|---|
| `field` (nevi) | all 7 · title 1 · author 2 · advisor 3 · subject 4 · keywords 5 · abstract 6 |
| `match` (tip) | contains 2 · exact 1 |
| `type` (Tur) | any 0 · yuksek_lisans 1 · doktora 2 · tipta_uzmanlik 3 · sanatta_yeterlik 4 · dis_hekimligi_uzmanlik 5 · tipta_yan_dal_uzmanlik 6 · eczacilikta_uzmanlik 7 |
| `lang` (Dil) | any 0 · turkce 1 · ingilizce 2 · arapca 3 · almanca 4 · fransizca 5 · ispanyolca 6 · italyanca 7 · rusca 8 · kurtce 11 · azerice 12 |
| `permission` (izin) | any 0 · permitted 1 · restricted 2 |
| `status` (Durum) | approved 3 (default) · preparing 1 · all 0 |
| `recent` (TezIslemleri islem) | last15days 7 · this_year 8 |

English aliases (`masters`, `phd`, `tr`, `en`) and Turkish ones (`tez_adi`,
`yazar`, `danisman`, `izinli`, …) both work; an unknown alias throws.

## Redactor notes (Claude in Chrome)
- Keys containing "author" (and other "sensitive" words) are blanked → output keys
  are Turkish (`yazar`, `danisman`, …).
- A returned string with 2+ `k=v` pairs joined by `&` is blanked → no
  `tezBilgiDetay.jsp?kayitNo=…&tezNo=…` URLs in results; IDs are separate fields.
  `pdf_url` (`TezGoster?key=…`) has one pair and passes.
- Return objects, never `JSON.stringify` output.

## PDF
pdf.js 3.11.174 (legacy UMD) is loaded from jsDelivr, falling back to unpkg; the
worker runs from a blob URL. tez.yok.gov.tr sends no CSP. Offline: inject a pdf.js
build yourself so `window.pdfjsLib` exists, and optionally set
`window.__YT_PDF_WORKER` to a worker URL.

## Verified live (2026-10-27)
- Keyword search "yapay zeka" / title / doktora / 2023–2024 → 143 results with full meta.
- `find_departments("kamu hukuku")` → 5 departments (KAMU HUKUKU = 41, GENEL KAMU HUKUKU = 993, …).
- Advanced: ABD 41 + 993, abstract "anayasa", 2023–2024 → 302 merged; `thesisNo: "928032"` → 1.
- `recent("this_year")` → 136,811 total, 2000 shown. `last15days` returned 0 that
  day (also 0 through the Python MCP client — site-side).
- Details JSON → advisor, both abstracts, keyword pairs, 5 citation styles.
- PDF: 449-page doctoral thesis (7.9 MB) → pages 5–6 in 3.6 s cold, cached re-read
  6 ms. Embargoed thesis → `pdf-restricted` with the author's restriction date.
