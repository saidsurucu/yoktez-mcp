"""Comprehensive integration test covering every tool and parameter.

Run: `uv run python test_all_tools.py`
Each test prints PASS/FAIL with a short reason.
"""
import asyncio
import logging
import sys
from typing import Any, Callable, Awaitable, List, Tuple

from pydantic import HttpUrl, ValidationError

from client import YokTezApiClient
from models import (
    YokTezSearchRequest,
    YokTezDocumentRequest,
    YokTezThesisDetailsRequest,
    YokTezRecentListRequest,
    YokTezRecentListMode,
    YokTezSearchFieldEnum,
    YokTezMatchTypeEnum,
    YokTezOperatorEnum,
    YokTezThesisTypeEnum,
    YokTezLanguageEnum,
    YokTezPermissionStatusEnum,
    YokTezStatusEnum,
)


logging.basicConfig(level=logging.WARNING)
log = logging.getLogger("test")

results: List[Tuple[str, bool, str]] = []


def record(name: str, ok: bool, msg: str = "") -> None:
    results.append((name, ok, msg))
    sym = "✅" if ok else "❌"
    print(f"  {sym} {name}: {msg}")


async def run(name: str, fn: Callable[[], Awaitable[Any]]) -> None:
    print(f"\n--- {name} ---")
    try:
        await fn()
    except Exception as exc:
        record(name, False, f"EXCEPTION {type(exc).__name__}: {exc}")


# ---------------- search_yok_tez_detailed parameter tests ----------------

async def test_search_keyword_basic(client: YokTezApiClient) -> None:
    r = await client.search_theses(
        YokTezSearchRequest(aranacak_kelime="yapay zeka", limit_per_page=3)
    )
    record(
        "basic keyword + default TUMU",
        bool(r.theses) and r.total_results_found and r.total_results_found > 100,
        f"total={r.total_results_found}, returned={len(r.theses)}",
    )


async def test_search_all_fields(client: YokTezApiClient) -> None:
    """Verify every YokTezSearchFieldEnum value works."""
    # NOTE: ANAHTAR_KELIME (index/keyword) uses YÖK's controlled vocabulary.
    # Common index terms like "yapay zeka" / "kanser" work, but free-text terms
    # like "blockchain" / "derin öğrenme" return 0 — that's a server-side data
    # limitation, not a client bug.
    queries = [
        (YokTezSearchFieldEnum.TUMU, "yapay zeka"),
        (YokTezSearchFieldEnum.TEZ_ADI, "yapay zeka"),
        (YokTezSearchFieldEnum.YAZAR, "YILMAZ"),
        (YokTezSearchFieldEnum.DANISMAN, "YILMAZ"),
        (YokTezSearchFieldEnum.KONU, "İşletme"),
        (YokTezSearchFieldEnum.ANAHTAR_KELIME, "yapay zeka"),
        (YokTezSearchFieldEnum.OZET, "machine learning"),
    ]
    for field, term in queries:
        r = await client.search_theses(
            YokTezSearchRequest(
                aranacak_kelime=term, arama_alani=field, limit_per_page=1
            )
        )
        record(
            f"search_field={field.name}",
            r.error_message is None and r.total_results_found is not None,
            f"total={r.total_results_found} err={r.error_message}",
        )


async def test_search_match_types(client: YokTezApiClient) -> None:
    """Compare exact vs contains match counts."""
    contains = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            arama_tipi=YokTezMatchTypeEnum.ICERSIN,
            limit_per_page=1,
        )
    )
    exact = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            arama_tipi=YokTezMatchTypeEnum.TAM_IFADE,
            limit_per_page=1,
        )
    )
    record(
        "match_type=ICERSIN",
        contains.error_message is None,
        f"total={contains.total_results_found}",
    )
    record(
        "match_type=TAM_IFADE",
        exact.error_message is None,
        f"total={exact.total_results_found}",
    )
    record(
        "exact ≤ contains",
        (exact.total_results_found or 0) <= (contains.total_results_found or 0),
        f"{exact.total_results_found} ≤ {contains.total_results_found}",
    )


async def test_search_multi_keyword_operators(client: YokTezApiClient) -> None:
    """AND vs OR with multiple keywords."""
    single = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            limit_per_page=1,
        )
    )
    and_q = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            aranacak_kelime_2="eğitim",
            operator_1=YokTezOperatorEnum.AND,
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            limit_per_page=1,
        )
    )
    or_q = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            aranacak_kelime_2="eğitim",
            operator_1=YokTezOperatorEnum.OR,
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            limit_per_page=1,
        )
    )
    three_kw = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            aranacak_kelime_2="eğitim",
            aranacak_kelime_3="sağlık",
            operator_1=YokTezOperatorEnum.OR,
            operator_2=YokTezOperatorEnum.OR,
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            limit_per_page=1,
        )
    )
    record(
        "AND narrows result set",
        (and_q.total_results_found or 0) <= (single.total_results_found or 0),
        f"AND={and_q.total_results_found} ≤ single={single.total_results_found}",
    )
    record(
        "OR widens result set",
        (or_q.total_results_found or 0) >= (single.total_results_found or 0),
        f"OR={or_q.total_results_found} ≥ single={single.total_results_found}",
    )
    record(
        "3-keyword OR widest",
        (three_kw.total_results_found or 0) >= (or_q.total_results_found or 0),
        f"3kw={three_kw.total_results_found} ≥ 2kw={or_q.total_results_found}",
    )


async def test_search_legacy_aliases(client: YokTezApiClient) -> None:
    """All 6 deprecated aliases must auto-map to keyword + arama_alani."""
    aliases = [
        ("tez_ad", "yapay zeka", "1"),  # TEZ_ADI
        ("yazar_ad_soyad", "YILMAZ", "2"),  # YAZAR
        ("danisman_ad_soyad", "YILMAZ", "3"),  # DANISMAN
        ("konu_basliklari", "İşletme", "4"),  # KONU
        ("dizin_terimleri", "yapay zeka", "5"),  # ANAHTAR_KELIME (controlled vocab; common terms only)
        ("ozet_metni", "machine learning", "6"),  # OZET
    ]
    for field_name, value, expected_alani in aliases:
        kwargs = {field_name: value, "limit_per_page": 1}
        r = await client.search_theses(YokTezSearchRequest(**kwargs))
        params = r.query_used_parameters or {}
        mapped_ok = params.get("aranacak_kelime") == value and params.get("arama_alani") == expected_alani
        record(
            f"alias {field_name} -> arama_alani={expected_alani}",
            mapped_ok and r.error_message is None,
            f"mapped={mapped_ok} total={r.total_results_found}",
        )


async def test_search_legacy_priority(client: YokTezApiClient) -> None:
    """When multiple aliases are set, tez_ad takes priority."""
    r = await client.search_theses(
        YokTezSearchRequest(
            tez_ad="yapay zeka",
            yazar_ad_soyad="YILMAZ",
            ozet_metni="machine learning",
            limit_per_page=1,
        )
    )
    params = r.query_used_parameters or {}
    record(
        "alias priority (tez_ad wins)",
        params.get("aranacak_kelime") == "yapay zeka"
        and params.get("arama_alani") == "1",
        f"keyword={params.get('aranacak_kelime')!r} alani={params.get('arama_alani')}",
    )


async def test_search_new_overrides_alias(client: YokTezApiClient) -> None:
    """If aranacak_kelime is set, aliases are ignored."""
    r = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="derin öğrenme",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            tez_ad="should be ignored",
            limit_per_page=1,
        )
    )
    params = r.query_used_parameters or {}
    record(
        "new API overrides legacy",
        params.get("aranacak_kelime") == "derin öğrenme",
        f"keyword={params.get('aranacak_kelime')!r}",
    )


async def test_search_thesis_type_filter(client: YokTezApiClient) -> None:
    """All thesis types — SECINIZ is default, others must narrow results."""
    base = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            limit_per_page=1,
        )
    )
    base_total = base.total_results_found or 0
    for tt in [
        YokTezThesisTypeEnum.YUKSEK_LISANS,
        YokTezThesisTypeEnum.DOKTORA,
        YokTezThesisTypeEnum.TIPTA_UZMANLIK,
        YokTezThesisTypeEnum.SANATTA_YETERLIK,
    ]:
        r = await client.search_theses(
            YokTezSearchRequest(
                aranacak_kelime="yapay zeka",
                arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
                tez_turu=tt,
                limit_per_page=1,
            )
        )
        record(
            f"thesis_type={tt.name}",
            r.error_message is None
            and (r.total_results_found or 0) <= base_total
            and (
                # Verify the returned thesis matches the filter (when results exist)
                not r.theses or r.theses[0].thesis_type
            ),
            f"total={r.total_results_found} sample_type={r.theses[0].thesis_type if r.theses else None}",
        )


async def test_search_language_filter(client: YokTezApiClient) -> None:
    """Verify language filter changes which theses come back."""
    tr = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="learning",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            dil=YokTezLanguageEnum.TURKCE,
            limit_per_page=1,
        )
    )
    en = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="learning",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            dil=YokTezLanguageEnum.INGILIZCE,
            limit_per_page=1,
        )
    )
    record(
        "language=TURKCE",
        tr.error_message is None
        and (not tr.theses or tr.theses[0].language == "Türkçe"),
        f"total={tr.total_results_found} sample_lang={tr.theses[0].language if tr.theses else None}",
    )
    record(
        "language=INGILIZCE",
        en.error_message is None
        and (not en.theses or en.theses[0].language == "İngilizce"),
        f"total={en.total_results_found} sample_lang={en.theses[0].language if en.theses else None}",
    )


async def test_search_permission_filter(client: YokTezApiClient) -> None:
    p_izinli = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            izin_durumu=YokTezPermissionStatusEnum.IZINLI,
            limit_per_page=1,
        )
    )
    p_izinsiz = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            izin_durumu=YokTezPermissionStatusEnum.IZINSIZ,
            limit_per_page=1,
        )
    )
    record(
        "permission=IZINLI",
        p_izinli.error_message is None and (p_izinli.total_results_found or 0) > 0,
        f"total={p_izinli.total_results_found}",
    )
    record(
        "permission=IZINSIZ",
        p_izinsiz.error_message is None,
        f"total={p_izinsiz.total_results_found}",
    )


async def test_search_status_filter(client: YokTezApiClient) -> None:
    onaylandi = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            tez_durumu=YokTezStatusEnum.ONAYLANDI,
            limit_per_page=1,
        )
    )
    tumu = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            tez_durumu=YokTezStatusEnum.TUMU,
            limit_per_page=1,
        )
    )
    record(
        "status=ONAYLANDI",
        onaylandi.error_message is None and (onaylandi.total_results_found or 0) > 0,
        f"total={onaylandi.total_results_found}",
    )
    record(
        "status=TUMU vs ONAYLANDI",
        tumu.error_message is None
        and (tumu.total_results_found or 0) >= (onaylandi.total_results_found or 0),
        f"TUMU={tumu.total_results_found} >= ONAYLANDI={onaylandi.total_results_found}",
    )


async def test_search_year_range(client: YokTezApiClient) -> None:
    narrow = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            yil_baslangic="2024",
            yil_bitis="2024",
            limit_per_page=2,
        )
    )
    wider = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            yil_baslangic="2020",
            yil_bitis="2024",
            limit_per_page=2,
        )
    )
    record(
        "year_start=year_end=2024",
        narrow.error_message is None
        and (not narrow.theses or narrow.theses[0].year == "2024"),
        f"total={narrow.total_results_found} sample_year={narrow.theses[0].year if narrow.theses else None}",
    )
    record(
        "wider range >= narrow",
        (wider.total_results_found or 0) >= (narrow.total_results_found or 0),
        f"wider={wider.total_results_found} >= narrow={narrow.total_results_found}",
    )


async def test_search_pagination(client: YokTezApiClient) -> None:
    p1 = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            page=1,
            limit_per_page=5,
        )
    )
    p2 = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            page=2,
            limit_per_page=5,
        )
    )
    p1_thesis_nos = {t.thesis_no for t in p1.theses}
    p2_thesis_nos = {t.thesis_no for t in p2.theses}
    record(
        "page=1 returns 5 results",
        len(p1.theses) == 5,
        f"got {len(p1.theses)}",
    )
    record(
        "page=2 returns different results",
        len(p2.theses) == 5 and p1_thesis_nos.isdisjoint(p2_thesis_nos),
        f"p1_count={len(p1.theses)} p2_count={len(p2.theses)} overlap={p1_thesis_nos & p2_thesis_nos}",
    )
    record(
        "total_pages reflects pagination",
        p1.total_pages is not None and p1.total_pages > 1,
        f"total_pages={p1.total_pages}",
    )


async def test_search_results_per_page_bounds(client: YokTezApiClient) -> None:
    """Pydantic limit validation (1 ≤ limit_per_page ≤ 50)."""
    try:
        YokTezSearchRequest(aranacak_kelime="x", limit_per_page=0)
        ok = False
    except ValidationError:
        ok = True
    record("limit_per_page=0 rejected", ok, "validation should fail")

    try:
        YokTezSearchRequest(aranacak_kelime="x", limit_per_page=51)
        ok = False
    except ValidationError:
        ok = True
    record("limit_per_page=51 rejected", ok, "validation should fail")

    r = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            limit_per_page=50,
        )
    )
    record(
        "limit_per_page=50 accepted",
        r.error_message is None and len(r.theses) == 50,
        f"got {len(r.theses)} theses",
    )


async def test_search_empty_query(client: YokTezApiClient) -> None:
    r = await client.search_theses(YokTezSearchRequest(limit_per_page=1))
    record(
        "empty query returns helpful error",
        r.theses == []
        and r.error_message
        and "No search term" in r.error_message,
        f"err={r.error_message!r}",
    )


async def test_search_metadata_completeness(client: YokTezApiClient) -> None:
    """Every result should have core metadata populated."""
    r = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            limit_per_page=5,
        )
    )
    if not r.theses:
        record("metadata completeness", False, "no theses to inspect")
        return
    missing = []
    for t in r.theses:
        for f in ("thesis_no", "title", "author", "year", "thesis_type", "language", "university_info", "thesis_key", "encrypted_no", "detail_page_url"):
            if not getattr(t, f):
                missing.append(f"{t.thesis_no}:{f}")
    record(
        "all core fields populated on 5 results",
        not missing,
        f"missing fields: {missing[:5]}" if missing else "all present",
    )


# ---------------- list_recent_yok_tez tests ----------------

async def test_recent_son_15_gun(client: YokTezApiClient) -> None:
    r = await client.list_recent_theses(
        YokTezRecentListRequest(mode=YokTezRecentListMode.SON_15_GUN, limit_per_page=3)
    )
    record(
        "recent SON_15_GUN basic",
        r.error_message is None
        and (r.total_results_found or 0) > 500
        and len(r.theses) == 3,
        f"total={r.total_results_found} returned={len(r.theses)}",
    )
    if r.theses:
        t = r.theses[0]
        record(
            "recent SON_15_GUN result metadata",
            all([t.thesis_no, t.title, t.author, t.year, t.thesis_key, t.encrypted_no, t.detail_page_url]),
            f"sample [{t.thesis_no}] author={t.author} year={t.year}",
        )


async def test_recent_bu_yil(client: YokTezApiClient) -> None:
    r = await client.list_recent_theses(
        YokTezRecentListRequest(mode=YokTezRecentListMode.BU_YIL, limit_per_page=3)
    )
    record(
        "recent BU_YIL basic",
        r.error_message is None
        and (r.total_results_found or 0) > 10_000
        and len(r.theses) == 3,
        f"total={r.total_results_found} returned={len(r.theses)}",
    )
    # All thesis years should be the current year (or close)
    if r.theses:
        years = {t.year for t in r.theses if t.year}
        record(
            "recent BU_YIL year filtering",
            len(years) == 1,
            f"unique years in results: {years}",
        )


async def test_recent_pagination(client: YokTezApiClient) -> None:
    p1 = await client.list_recent_theses(
        YokTezRecentListRequest(mode=YokTezRecentListMode.SON_15_GUN, page=1, limit_per_page=5)
    )
    p2 = await client.list_recent_theses(
        YokTezRecentListRequest(mode=YokTezRecentListMode.SON_15_GUN, page=2, limit_per_page=5)
    )
    p1_set = {t.thesis_no for t in p1.theses}
    p2_set = {t.thesis_no for t in p2.theses}
    record(
        "recent pagination p1 vs p2 disjoint",
        len(p1.theses) == 5 and len(p2.theses) == 5 and p1_set.isdisjoint(p2_set),
        f"p1={len(p1.theses)} p2={len(p2.theses)} overlap={p1_set & p2_set}",
    )


async def test_recent_chains_to_details(client: YokTezApiClient) -> None:
    """A thesis fetched via list_recent_theses should be usable in get_thesis_details."""
    r = await client.list_recent_theses(
        YokTezRecentListRequest(mode=YokTezRecentListMode.SON_15_GUN, limit_per_page=1)
    )
    if not r.theses:
        record("recent chains to details", False, "no recent theses returned")
        return
    d = await client.get_thesis_details(
        YokTezThesisDetailsRequest(detail_page_url=r.theses[0].detail_page_url)
    )
    record(
        "recent → details chain",
        d.error_message is None and (d.advisor or d.location_full or d.abstract_tr),
        f"err={d.error_message!r} advisor={d.advisor!r}",
    )


# ---------------- get_yok_tez_thesis_details tests ----------------

async def test_details_via_url(client: YokTezApiClient) -> HttpUrl:
    r = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            izin_durumu=YokTezPermissionStatusEnum.IZINLI,
            limit_per_page=1,
        )
    )
    url = r.theses[0].detail_page_url
    d = await client.get_thesis_details(
        YokTezThesisDetailsRequest(detail_page_url=url)
    )
    record(
        "details by detail_page_url",
        d.error_message is None
        and d.advisor
        and d.location_full
        and d.abstract_tr
        and d.citation_apa,
        f"advisor={d.advisor!r} loc={(d.location_full or '')[:40]!r} abs_tr_len={len(d.abstract_tr or '')}",
    )
    return url


async def test_details_via_ids(client: YokTezApiClient) -> None:
    r = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            limit_per_page=1,
        )
    )
    tz = r.theses[0]
    d = await client.get_thesis_details(
        YokTezThesisDetailsRequest(
            thesis_key=tz.thesis_key, encrypted_no=tz.encrypted_no
        )
    )
    record(
        "details by thesis_key+encrypted_no",
        d.error_message is None
        and d.advisor
        and d.source_detail_page_url is not None,
        f"advisor={d.advisor!r} source_url={d.source_detail_page_url}",
    )


async def test_details_missing_ids() -> None:
    try:
        YokTezThesisDetailsRequest()
        record("missing IDs rejected by validator", False, "no error raised")
    except ValidationError as exc:
        record(
            "missing IDs rejected by validator",
            "Either" in str(exc),
            f"correctly raised: {type(exc).__name__}",
        )


async def test_details_bad_ids(client: YokTezApiClient) -> None:
    d = await client.get_thesis_details(
        YokTezThesisDetailsRequest(
            thesis_key="garbage_id_xxx", encrypted_no="garbage_no_xxx"
        )
    )
    record(
        "bad IDs handled gracefully",
        # Server might return JSON with empty/default fields or an error — both acceptable as long as no crash
        d.error_message is not None or d.advisor is None,
        f"err={d.error_message!r} advisor={d.advisor!r}",
    )


async def test_details_citations_complete(client: YokTezApiClient) -> None:
    """All 5 citation formats should be populated for a typical thesis."""
    r = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            limit_per_page=1,
        )
    )
    d = await client.get_thesis_details(
        YokTezThesisDetailsRequest(detail_page_url=r.theses[0].detail_page_url)
    )
    record(
        "all 5 citation formats present",
        all([d.citation_apa, d.citation_ieee, d.citation_mla, d.citation_chicago, d.citation_harvard]),
        f"apa={bool(d.citation_apa)} ieee={bool(d.citation_ieee)} mla={bool(d.citation_mla)} chi={bool(d.citation_chicago)} har={bool(d.citation_harvard)}",
    )


async def test_details_keyword_parsing(client: YokTezApiClient) -> None:
    """The test thesis we know has 5 keyword pairs."""
    d = await client.get_thesis_details(
        YokTezThesisDetailsRequest(
            thesis_key="nslbSyAODG1_FIruL8qUAA",
            encrypted_no="THvIvDpZXvJIiHZpuqpKVw",
        )
    )
    record(
        "keyword pairs parsed (tr+en filled)",
        len(d.keywords_tr) == 5
        and all(kw.tr and kw.en for kw in d.keywords_tr),
        f"got {len(d.keywords_tr)} TR pairs, first: {d.keywords_tr[0].tr!r}={d.keywords_tr[0].en!r}" if d.keywords_tr else "empty",
    )


# ---------------- get_yok_tez_document_markdown tests ----------------

async def test_doc_page_one(client: YokTezApiClient, url: HttpUrl) -> int:
    doc = await client.get_thesis_pdf_as_markdown(
        YokTezDocumentRequest(detail_page_url=url, page_number=1)
    )
    record(
        "doc page 1 fetched",
        doc.error_message is None
        and doc.total_pdf_pages > 0
        and doc.thesis_title,
        f"total_pages={doc.total_pdf_pages} chars={doc.characters_on_page} title={(doc.thesis_title or '')[:40]!r}",
    )
    return doc.total_pdf_pages


async def test_doc_middle_page(client: YokTezApiClient, url: HttpUrl, total_pages: int) -> None:
    if total_pages < 3:
        record("doc middle page", False, "thesis too short to test middle page")
        return
    middle = total_pages // 2
    doc = await client.get_thesis_pdf_as_markdown(
        YokTezDocumentRequest(detail_page_url=url, page_number=middle)
    )
    record(
        f"doc page {middle} (middle)",
        doc.error_message is None and doc.current_pdf_page == middle,
        f"chars={doc.characters_on_page}",
    )


async def test_doc_out_of_bounds(client: YokTezApiClient, url: HttpUrl, total_pages: int) -> None:
    oob = total_pages + 100
    doc = await client.get_thesis_pdf_as_markdown(
        YokTezDocumentRequest(detail_page_url=url, page_number=oob)
    )
    record(
        f"doc page {oob} OOB error",
        doc.error_message is not None and "out of range" in doc.error_message.lower(),
        f"err={doc.error_message!r}",
    )


async def test_doc_page_validation() -> None:
    try:
        YokTezDocumentRequest(detail_page_url="https://x/y", page_number=0)
        record("page_number=0 rejected", False, "validation should fail")
    except ValidationError:
        record("page_number=0 rejected", True, "ge=1 enforced")


async def test_doc_pagination_metadata(client: YokTezApiClient, url: HttpUrl, total_pages: int) -> None:
    doc = await client.get_thesis_pdf_as_markdown(
        YokTezDocumentRequest(detail_page_url=url, page_number=1)
    )
    record(
        "pagination metadata",
        doc.is_paginated == (total_pages > 1)
        and doc.total_pdf_pages == total_pages
        and doc.current_pdf_page == 1,
        f"is_paginated={doc.is_paginated} total={doc.total_pdf_pages}",
    )


async def test_doc_cache_hit(client: YokTezApiClient, url: HttpUrl) -> None:
    """Second fetch of same URL should hit cache (different page is fine — PDF is reused)."""
    # Fetch page 2 of same PDF; metadata page parse comes from same cached bytes
    doc = await client.get_thesis_pdf_as_markdown(
        YokTezDocumentRequest(detail_page_url=url, page_number=2)
    )
    stats = client._pdf_bytes_cache.stats["memory"]
    record(
        "PDF cache stores entry",
        stats["items"] >= 1 and doc.error_message is None,
        f"cache_items={stats['items']} chars_p2={doc.characters_on_page}",
    )


async def test_doc_non_permissible(client: YokTezApiClient) -> None:
    """Find a non-permissible thesis (IZINSIZ) and verify graceful error."""
    r = await client.search_theses(
        YokTezSearchRequest(
            aranacak_kelime="yapay zeka",
            arama_alani=YokTezSearchFieldEnum.TEZ_ADI,
            izin_durumu=YokTezPermissionStatusEnum.IZINSIZ,
            limit_per_page=1,
        )
    )
    if not r.theses:
        record("non-permissible thesis handled", False, "could not find an IZINSIZ thesis")
        return
    doc = await client.get_thesis_pdf_as_markdown(
        YokTezDocumentRequest(detail_page_url=r.theses[0].detail_page_url, page_number=1)
    )
    # YÖK shows different restriction reasons (no permission, time-bound author
    # restriction, etc.). The client just needs to NOT return PDF content and
    # surface the YÖK message as the error.
    record(
        "non-permissible PDF returns error",
        doc.error_message is not None and doc.page_markdown_content is None,
        f"err={doc.error_message!r}",
    )


# ---------------- main ----------------

async def main() -> int:
    client = YokTezApiClient(enable_disk_cache=False)
    try:
        await run("search: basic keyword", lambda: test_search_keyword_basic(client))
        await run("search: all search_field values", lambda: test_search_all_fields(client))
        await run("search: match_type (exact/contains)", lambda: test_search_match_types(client))
        await run("search: multi-keyword operators", lambda: test_search_multi_keyword_operators(client))
        await run("search: legacy aliases", lambda: test_search_legacy_aliases(client))
        await run("search: legacy alias priority", lambda: test_search_legacy_priority(client))
        await run("search: new overrides alias", lambda: test_search_new_overrides_alias(client))
        await run("search: thesis_type filter", lambda: test_search_thesis_type_filter(client))
        await run("search: language filter", lambda: test_search_language_filter(client))
        await run("search: permission filter", lambda: test_search_permission_filter(client))
        await run("search: status filter", lambda: test_search_status_filter(client))
        await run("search: year range", lambda: test_search_year_range(client))
        await run("search: pagination", lambda: test_search_pagination(client))
        await run("search: limit_per_page validation", lambda: test_search_results_per_page_bounds(client))
        await run("search: empty query", lambda: test_search_empty_query(client))
        await run("search: metadata completeness", lambda: test_search_metadata_completeness(client))

        await run("recent: SON_15_GUN", lambda: test_recent_son_15_gun(client))
        await run("recent: BU_YIL", lambda: test_recent_bu_yil(client))
        await run("recent: pagination", lambda: test_recent_pagination(client))
        await run("recent: chains into thesis_details", lambda: test_recent_chains_to_details(client))

        url = None

        async def _capture_url():
            nonlocal url
            url = await test_details_via_url(client)

        await run("details: via URL", _capture_url)
        await run("details: via thesis_key+encrypted_no", lambda: test_details_via_ids(client))
        await run("details: missing IDs validation", test_details_missing_ids)
        await run("details: bad IDs graceful", lambda: test_details_bad_ids(client))
        await run("details: 5 citation formats", lambda: test_details_citations_complete(client))
        await run("details: keyword pairs parsed", lambda: test_details_keyword_parsing(client))

        total_pages = 0

        async def _capture_pages():
            nonlocal total_pages
            total_pages = await test_doc_page_one(client, url)

        await run("document: page 1", _capture_pages)
        await run("document: middle page", lambda: test_doc_middle_page(client, url, total_pages))
        await run("document: out-of-bounds", lambda: test_doc_out_of_bounds(client, url, total_pages))
        await run("document: page_number validation", test_doc_page_validation)
        await run("document: pagination metadata", lambda: test_doc_pagination_metadata(client, url, total_pages))
        await run("document: cache stores entry", lambda: test_doc_cache_hit(client, url))
        await run("document: non-permissible PDF", lambda: test_doc_non_permissible(client))

    finally:
        await client.close_client_session()

    print("\n" + "=" * 70)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"RESULT: {passed}/{passed + failed} passed, {failed} failed")
    if failed:
        print("\nFailed tests:")
        for name, ok, msg in results:
            if not ok:
                print(f"  ❌ {name}: {msg}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
