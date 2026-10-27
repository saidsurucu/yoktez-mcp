const { test } = require("node:test");
const assert = require("node:assert");
const YT = require("../scripts/lib.js");

// Trimmed copy of a live tezSorguSonucYeni.jsp page (2026-10).
const LISTING = `
<div class="result-count-text">Arama sonucunda  7.835 kayıt bulundu.
            2.000 tanesi görüntülenmektedir.</div>
<div class="result-limit-warning"></div>
<div class="result-card" data-index="0" data-kayitno="q-BL9z" data-tezno="9l5h">
  <div class="card-title">
     Yapay zeka\x02 yaklaşımları
  </div>
  <div class="card-info" style="font-style: italic">AI approaches</div>
  <div class="card-info" style="white-space: nowrap;"><strong>Tez No:</strong> 928032</div>
</div>
<div class="result-card" data-index="1" data-kayitno="" data-tezno="x"></div>
<script>
  const referenceData = {
    "0": {
      "meta": {
        "author": "SÜLEYMAN ÇEVEN",
        "year": "2024",
        "subject": "Mekatronik {Mühendisliği}",
        "type": "Doktora",
        "lang": "Türkçe",
        "yer": "KARABÜK ÜNİVERSİTESİ / ",
        "title": "Yapay zeka"
      }
    },
  };
</script>`;

test("parseListing reads banner counts, card fields and referenceData meta", () => {
  const r = YT.parseListing(LISTING);
  assert.equal(r.error, null);
  assert.equal(r.total, 7835);
  assert.equal(r.shown, 2000);
  assert.equal(r.theses.length, 1, "card without kayitno is skipped");
  assert.deepEqual(r.theses[0], {
    tez_numarasi: "928032",
    baslik: "Yapay zeka yaklaşımları",
    baslik_ceviri: "AI approaches",
    yazar: "SÜLEYMAN ÇEVEN",
    yil: "2024",
    tur: "Doktora",
    dil: "Türkçe",
    konu: "Mekatronik {Mühendisliği}",
    universite: "KARABÜK ÜNİVERSİTESİ",
    kayitNo: "q-BL9z",
    tezNo: "9l5h",
  });
});

test("parseListing treats 'Sonuç bulunamadı' as a real empty result", () => {
  const r = YT.parseListing('<div class="result-count-text"></div><div class="warning-text">Sonuç bulunamadı</div>');
  assert.equal(r.error, null);
  assert.equal(r.total, 0);
  assert.equal(r.theses.length, 0);
});

test("parseListing classifies YÖK error pages", () => {
  assert.equal(YT.parseListing("<p>SİSTEMDE BEKLENMEDİK BİR HATA OLUŞTU.</p>").error, "system-error");
  assert.equal(YT.parseListing("<p>Geçersiz sorgulama</p>").error, "invalid-query");
});

test("buildAdvancedForm always sends Metin and zero-fills unset numeric fields", () => {
  const f = YT.buildAdvancedForm({ abstract: "anayasa", type: "doktora" }, 41);
  assert.equal(f.Metin, "anayasa");
  assert.equal(f.ABD, "41");
  assert.equal(f.Tur, "2");
  assert.equal(f.Enstitu, "0");
  assert.equal(f.yil1, "0");
  assert.equal(f.yil2, "0");
  assert.equal(f.islem, "2");
  assert.ok("Metin" in YT.buildAdvancedForm({}), "Metin present even when empty");
  assert.equal(YT.buildAdvancedForm({}).ABD, "0");
});

test("buildKeywordForm maps aliases and accepts raw codes", () => {
  const f = YT.buildKeywordForm({ terms: ["a", "b"], ops: ["OR"], field: "advisor", match: "exact", lang: "12", yearFrom: "2020", yearTo: "20" });
  assert.equal(f.keyword, "a");
  assert.equal(f.keyword1, "b");
  assert.equal(f.ops_field, "or");
  assert.equal(f.ops_field1, "and");
  assert.equal(f.nevi, "3");
  assert.equal(f.tip, "1");
  assert.equal(f.Dil, "12");
  assert.equal(f.yil1, "2020");
  assert.equal(f.yil2, "0", "non-4-digit year falls back to 0");
  assert.throws(() => YT.buildKeywordForm({ query: "x", field: "nope" }), /unknown field/);
});

test("hasAdvancedCriterion requires a department or a non-empty text field", () => {
  assert.equal(YT.hasAdvancedCriterion({}, []), false);
  assert.equal(YT.hasAdvancedCriterion({ title: "  " }, []), false);
  assert.equal(YT.hasAdvancedCriterion({ thesisNo: "928032" }, []), true);
  assert.equal(YT.hasAdvancedCriterion({}, ["41"]), true);
});

test("parseAbdList dedupes codes; matchAbd uses Turkish case folding", () => {
  const html = `<input ad="KAMU HUKUKU ANABİLİM DALI" kod="41"><input ad="KAMU HUKUKU ANABİLİM DALI" kod="41">
                <input ad="BİLGİSAYAR MÜHENDİSLİĞİ ANABİLİM DALI" kod="7">`;
  const list = YT.parseAbdList(html);
  assert.equal(list.length, 2);
  assert.deepEqual(YT.matchAbd(list, "bilgisayar").matches, [{ kod: "7", ad: "BİLGİSAYAR MÜHENDİSLİĞİ ANABİLİM DALI" }]);
  assert.equal(YT.matchAbd(list, "").total, 0);
});

test("parseDetails strips labels, splits keyword pairs and flattens citation HTML", () => {
  const d = YT.parseDetails({
    danisman: "<strong>Danışman: </strong>PROF. DR. RAİF BAYIR",
    yer: " KARABÜK ÜNİVERSİTESİ / ENSTİTÜ ",
    trOzet: "Özet", enOzet: "",
    anahtarKelimeTr: "<strong>Anahtar Kelime: </strong>Bakış = Gaze ; Tekil ;",
    apa_ref: "ÇEVEN, S. (2024). <i>Başlık</i>.",
  });
  assert.equal(d.danisman, "PROF. DR. RAİF BAYIR");
  assert.equal(d.yer, "KARABÜK ÜNİVERSİTESİ / ENSTİTÜ");
  assert.equal(d.ozet_en, null);
  assert.deepEqual(d.anahtar_kelimeler_tr, [{ tr: "Bakış", en: "Gaze" }, { tr: "Tekil", en: null }]);
  assert.deepEqual(d.anahtar_kelimeler_en, []);
  assert.equal(d.atif.apa, "ÇEVEN, S. (2024). Başlık.");
});

test("parsePdfFragment returns an absolute TezGoster link or the embargo reason", () => {
  const ok = YT.parsePdfFragment(`<a href="TezGoster?key=abc" target="_blank"><img src="image/pdfizinli.png"></a>`);
  assert.equal(ok.pdf_url, "https://tez.yok.gov.tr/UlusalTezMerkezi/TezGoster?key=abc");
  const no = YT.parsePdfFragment(`<div class='pdf-container'><span class='pdf-info-msg'>28.02.2027 tarihine kadar kullanımı yazar tarafından kısıtlanmıştır.</span></div>`);
  assert.equal(no.pdf_url, null);
  assert.match(no.reason, /kısıtlanmıştır/);
});
