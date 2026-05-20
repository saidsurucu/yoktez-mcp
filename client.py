# client.py
import asyncio
import json
import logging
import re
import math
import urllib.parse
from typing import Dict, List, Optional, Any
import io

from pydantic import HttpUrl

import httpx
from bs4 import BeautifulSoup

from pypdf import PdfReader, PdfWriter
from markitdown import MarkItDown

from models import (
    YokTezSearchRequest, YokTezCompactThesisDetail, YokTezSearchResult,
    YokTezDocumentRequest, YokTezDocumentMarkdown, InternalThesisDetail,
    YokTezThesisDetailsRequest, YokTezThesisDetails, YokTezKeywordPair,
    YokTezRecentListRequest, YokTezRecentListMode,
    YokTezAnabilimDali, YokTezAnabilimDaliListResult, YokTezAnabilimDaliSearchRequest,
)
from cache import MultiTierCache, AIOFILES_AVAILABLE

logger = logging.getLogger(__name__)

if not logger.hasHandlers():  # Pragma: no cover
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


class YokTezApiClient:
    """
    API Client for interacting with the YÖK National Thesis Center.
    Handles searching theses and extracting content from their PDFs.
    Uses HTTPX for all HTTP operations (no Playwright/browser dependency).
    """
    YOK_TEZ_BASE_URL = "https://tez.yok.gov.tr"
    YOK_TEZ_SEARCH_PAGE_URL = f"{YOK_TEZ_BASE_URL}/UlusalTezMerkezi/tarama.jsp"
    YOK_TEZ_SEARCH_ACTION_URL = f"{YOK_TEZ_BASE_URL}/UlusalTezMerkezi/SearchTez"
    YOK_TEZ_DETAIL_URL_TEMPLATE = f"{YOK_TEZ_BASE_URL}/UlusalTezMerkezi/tezDetay.jsp?id={{thesis_key}}"
    YOK_TEZ_DETAIL_URL_WITH_NO_TEMPLATE = f"{YOK_TEZ_BASE_URL}/UlusalTezMerkezi/tezDetay.jsp?id={{thesis_key}}&no={{encrypted_no}}"
    YOK_TEZ_BILGI_DETAY_URL = f"{YOK_TEZ_BASE_URL}/UlusalTezMerkezi/tezBilgiDetay.jsp"
    YOK_TEZ_ISLEMLERI_URL = f"{YOK_TEZ_BASE_URL}/UlusalTezMerkezi/TezIslemleri"
    YOK_TEZ_ALL_ABD_URL = (
        f"{YOK_TEZ_BASE_URL}/UlusalTezMerkezi/tarama.jsp?ajax=getAllABD&ensGrubu="
    )
    # Cap on how many departments are searched-and-merged in a single advanced search.
    MAX_ABD_PER_SEARCH = 15

    def __init__(
        self,
        request_timeout: float = 60.0,
        cache_max_items: int = 50,
        cache_max_size_mb: int = 100,
        enable_disk_cache: bool = True,
        disk_cache_max_size_mb: int = 500,
        disk_cache_ttl_days: int = 30
    ):
        """
        Initializes the YokTezApiClient.

        Args:
            request_timeout: Timeout for HTTP requests in seconds.
            cache_max_items: Maximum number of PDFs to cache in memory.
            cache_max_size_mb: Maximum total memory cache size in megabytes.
            enable_disk_cache: Whether to enable persistent disk caching.
            disk_cache_max_size_mb: Maximum disk cache size in megabytes.
            disk_cache_ttl_days: Time-to-live for disk cached items in days.
        """
        self._request_timeout = request_timeout

        # Multi-tier cache: Memory (L1) -> Disk (L2)
        self._pdf_bytes_cache = MultiTierCache(
            memory_max_items=cache_max_items,
            memory_max_size_mb=cache_max_size_mb,
            enable_disk_cache=enable_disk_cache and AIOFILES_AVAILABLE,
            disk_max_size_mb=disk_cache_max_size_mb,
            disk_ttl_days=disk_cache_ttl_days
        )

        # Optimized HTTP client with connection pooling and HTTP/2
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=request_timeout * 2,
                write=30.0,
                pool=5.0
            ),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=30.0
            ),
            http2=True,
            follow_redirects=True,
            verify=False,  # Disable SSL verification (YÖK cert issues on macOS)
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br"
            }
        )
        self._md_converter = MarkItDown()

        # Lazily-loaded cache of YÖK's full department (anabilim dalı) list.
        # The list is large (~2500 entries) but effectively static, so it is
        # fetched once per process and reused.
        self._abd_list_cache: Optional[List[YokTezAnabilimDali]] = None
        self._abd_list_lock = asyncio.Lock()

    async def close_client_session(self):
        """Closes the HTTPX client session and clears cache."""
        logger.info("YokTezApiClient: Closing resources...")

        # Log cache stats before clearing
        cache_stats = self._pdf_bytes_cache.stats
        logger.info(f"Cache stats before close: {cache_stats}")
        await self._pdf_bytes_cache.clear()

        if self._http_client and not self._http_client.is_closed:
            logger.info("Closing HTTPX client session...")
            await self._http_client.aclose()
        logger.info("YokTezApiClient: Resources closed.")

    def _parse_thesis_detail_html(self, soup: BeautifulSoup, detail_page_url_str: str) -> Dict[str, Any]:
        """
        Parses the HTML of a thesis detail page to extract metadata and PDF link information.
        """
        data = {
            "pdf_download_href": None, "retrieved_pdf_url": None,
            "thesis_no": None, "title_combined": None, "title_tr": None, "title_en": None,
            "author": None, "advisor": None, "location_info": None, "subject_info": None,
            "index_terms": None, "status_text": None, "thesis_type_text": None,
            "language_text": None, "year_text": None, "pages_text": None,
            "abstract_tr": None, "abstract_en": None,
            "metadata_error_message": None, "pdf_permission_error_message": None,
            "is_pdf_permissible": False
        }
        main_table = soup.find('table', attrs={'width': "100%", 'cellspacing': "0", 'cellpadding': "1"})
        if not main_table:
            logger.warning(f"Main detail table not found: {detail_page_url_str}")
            data["metadata_error_message"] = "Main detail page table not found."
            return data
        rows = main_table.find_all('tr', recursive=False)
        if len(rows) < 2:
            data["metadata_error_message"] = "Not enough rows (data row) in detail table."
            return data
        data_row = rows[1]
        cells = data_row.find_all('td', valign="top", recursive=False)
        if len(cells) < 4:
            data["metadata_error_message"] = "Missing cells in detail data row."
            return data
        data["thesis_no"] = cells[0].get_text(strip=True)
        download_cell = cells[1]
        pdf_link_tag = download_cell.find("a", href=re.compile(r"TezGoster\?key="))
        if pdf_link_tag and pdf_link_tag.has_attr('href'):
            data["pdf_download_href"] = pdf_link_tag['href']
            data["retrieved_pdf_url"] = urllib.parse.urljoin(self.YOK_TEZ_BASE_URL + "/UlusalTezMerkezi/", data["pdf_download_href"])
            data["is_pdf_permissible"] = True
        else:
            # No PDF link in the download cell → PDF is not accessible. YÖK shows different
            # explanations depending on why (author-imposed time restriction, no permission, etc).
            # Capture whatever text is present so the caller gets the real reason.
            data["is_pdf_permissible"] = False
            cell_text = download_cell.get_text(" ", strip=True)
            if cell_text:
                data["pdf_permission_error_message"] = cell_text
            else:
                data["pdf_permission_error_message"] = "PDF is not available for this thesis (no download link)."
        kunye_cell = cells[2]
        for br in kunye_cell.find_all("br"):
            br.replace_with("\n")
        kunye_parts = [part.strip() for part in kunye_cell.get_text(separator="\n").split('\n') if part.strip()]
        current_part_index = 0
        if kunye_parts:
            title_candidates = []
            while current_part_index < len(kunye_parts) and \
                  not any(kunye_parts[current_part_index].startswith(lbl) for lbl in ["Yazar:", "Danışman:", "Yer Bilgisi:", "Konu:", "Dizin:"]):
                title_candidates.append(kunye_parts[current_part_index])
                current_part_index += 1
            if title_candidates:
                data["title_combined"] = " ".join(title_candidates)
                title_split = data["title_combined"].split('/')
                data["title_tr"] = title_split[0].strip()
                if len(title_split) > 1:
                    data["title_en"] = " / ".join(ts.strip() for ts in title_split[1:])
            for i in range(current_part_index, len(kunye_parts)):
                part = kunye_parts[i]
                if part.startswith("Yazar:"):
                    data["author"] = part.replace("Yazar:", "", 1).strip()
                elif part.startswith("Danışman:"):
                    data["advisor"] = part.replace("Danışman:", "", 1).strip()
                elif part.startswith("Yer Bilgisi:"):
                    data["location_info"] = part.replace("Yer Bilgisi:", "", 1).strip()
                elif part.startswith("Konu:"):
                    data["subject_info"] = part.replace("Konu:", "", 1).strip()
                elif part.startswith("Dizin:"):
                    data["index_terms"] = part.replace("Dizin:", "", 1).strip()
        durum_cell = cells[3]
        for br in durum_cell.find_all("br"):
            br.replace_with("\n")
        durum_parts = [part.strip() for part in durum_cell.get_text(separator="\n").split('\n') if part.strip()]
        if len(durum_parts) > 0:
            data["status_text"] = durum_parts[0]
        if len(durum_parts) > 1:
            data["thesis_type_text"] = durum_parts[1]
        if len(durum_parts) > 2:
            data["language_text"] = durum_parts[2]
        if len(durum_parts) > 3:
            data["year_text"] = durum_parts[3]
        if len(durum_parts) > 4:
            data["pages_text"] = durum_parts[4]
        abstract_tr_td = main_table.find("td", id="td0")
        if abstract_tr_td:
            data["abstract_tr"] = abstract_tr_td.get_text(strip=True)
        abstract_en_td = main_table.find("td", id="td1")
        if abstract_en_td:
            data["abstract_en"] = abstract_en_td.get_text(strip=True)
        return data

    async def _fetch_thesis_details_from_key(self, thesis_key: str, encrypted_no: Optional[str] = None) -> Optional[InternalThesisDetail]:
        """
        Fetches and parses comprehensive thesis details from its detail page using a thesis key.
        """
        if encrypted_no:
            detail_page_url_str = self.YOK_TEZ_DETAIL_URL_WITH_NO_TEMPLATE.format(
                thesis_key=thesis_key, encrypted_no=encrypted_no
            )
        else:
            detail_page_url_str = self.YOK_TEZ_DETAIL_URL_TEMPLATE.format(thesis_key=thesis_key)
        try:
            response = await self._http_client.get(detail_page_url_str, timeout=self._request_timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            parsed_data = self._parse_thesis_detail_html(soup, detail_page_url_str)
            return InternalThesisDetail(
                thesis_no=parsed_data.get("thesis_no"), title=parsed_data.get("title_tr"),
                title_en=parsed_data.get("title_en"), author=parsed_data.get("author"),
                advisor=parsed_data.get("advisor"), university_info=parsed_data.get("location_info"),
                subject=parsed_data.get("subject_info"), status=parsed_data.get("status_text"),
                thesis_type=parsed_data.get("thesis_type_text"), language=parsed_data.get("language_text"),
                year=parsed_data.get("year_text"), pages=parsed_data.get("pages_text"),
                abstract_tr=parsed_data.get("abstract_tr"), detail_page_url=HttpUrl(detail_page_url_str),
                thesis_key=thesis_key
            )
        except httpx.RequestError as e:
            logger.error(f"HTTPX Error fetching thesis details: {e} URL: {detail_page_url_str}")
            return None
        except Exception as e:
            logger.error(f"Parsing Error fetching thesis details: {e} URL: {detail_page_url_str}", exc_info=True)
            return None

    @staticmethod
    def _parse_int_with_thousands(text: str) -> Optional[int]:
        """Parse '6.818' or '6,818' style thousand-separated integers."""
        if not text:
            return None
        cleaned = re.sub(r"[^\d]", "", text)
        try:
            return int(cleaned) if cleaned else None
        except ValueError:
            return None

    def _extract_reference_data(self, page_source: str) -> Dict[str, Dict[str, Any]]:
        """Extract the `const referenceData = { ... }` JS object from the search HTML.

        The object maps string indices ('0', '1', ...) to per-result metadata under a
        'meta' key (author, year, subject, type, lang, yer). We parse it by locating
        the opening brace and walking braces with simple state tracking so we don't
        depend on a fragile single regex.
        """
        marker = "const referenceData = {"
        start = page_source.find(marker)
        if start == -1:
            return {}
        brace_start = page_source.find("{", start + len(marker) - 1)
        if brace_start == -1:
            return {}

        depth = 0
        in_string = False
        string_char = ""
        i = brace_start
        end = -1
        while i < len(page_source):
            ch = page_source[i]
            if in_string:
                if ch == "\\":
                    i += 2
                    continue
                if ch == string_char:
                    in_string = False
            else:
                if ch in ('"', "'"):
                    in_string = True
                    string_char = ch
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            i += 1

        if end == -1:
            return {}

        raw = page_source[brace_start:end]
        # The server emits JS-style trailing commas (e.g. `},\n    }`) which break json.loads.
        cleaned = re.sub(r",(\s*[}\]])", r"\1", raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.warning("referenceData JSON parse failed (%s); metadata fields will be empty.", exc)
            return {}

    def _parse_result_cards(
        self,
        soup: BeautifulSoup,
        reference_data: Dict[str, Dict[str, Any]],
    ) -> List[YokTezCompactThesisDetail]:
        """Parse all <div class='result-card'> elements into compact thesis details."""
        results: List[YokTezCompactThesisDetail] = []
        cards = soup.find_all("div", class_="result-card")
        for card in cards:
            try:
                kayit_no = card.get("data-kayitno") or None
                tez_no_enc = card.get("data-tezno") or None
                idx = card.get("data-index")
                if not kayit_no or not tez_no_enc:
                    continue

                title_tr = None
                title_en = None
                title_div = card.find("div", class_="card-title")
                if title_div:
                    title_tr = title_div.get_text(strip=True) or None

                # English translation is in a card-info with italic style
                italic_info = card.find(
                    "div",
                    class_="card-info",
                    style=lambda s: bool(s) and "font-style: italic" in s.lower(),
                )
                if italic_info:
                    title_en = italic_info.get_text(strip=True) or None

                # Visible thesis number lives in another card-info with a <strong>Tez No:</strong> label
                visible_tez_no: Optional[str] = None
                for ci in card.find_all("div", class_="card-info"):
                    strong = ci.find("strong")
                    if strong and "Tez No" in strong.get_text():
                        text = ci.get_text(strip=True)
                        # Format: "Tez No: 1003627"
                        m = re.search(r"Tez No[:\s]*([0-9]+)", text)
                        if m:
                            visible_tez_no = m.group(1)
                        break

                meta = reference_data.get(str(idx), {}).get("meta", {}) if idx is not None else {}
                author = (meta.get("author") or "").strip() or None
                year = (meta.get("year") or "").strip() or None
                subject = (meta.get("subject") or "").strip() or None
                thesis_type = (meta.get("type") or "").strip() or None
                language = (meta.get("lang") or "").strip() or None
                # 'yer' often comes back like 'MARMARA ÜNİVERSİTESİ / ' — collapse trailing separators
                yer_raw = (meta.get("yer") or "").strip()
                university_info = re.sub(r"\s*/\s*$", "", yer_raw) if yer_raw else None

                detail_page_url_str = self.YOK_TEZ_DETAIL_URL_WITH_NO_TEMPLATE.format(
                    thesis_key=kayit_no, encrypted_no=tez_no_enc
                )

                results.append(
                    YokTezCompactThesisDetail(
                        thesis_no=visible_tez_no,
                        title=title_tr,
                        title_translated=title_en,
                        author=author,
                        year=year,
                        university_info=university_info,
                        thesis_type=thesis_type,
                        language=language,
                        subject=subject,
                        thesis_key=kayit_no,
                        encrypted_no=tez_no_enc,
                        detail_page_url=HttpUrl(detail_page_url_str),
                    )
                )
            except Exception as exc:
                logger.error("Error parsing a result-card: %s", exc, exc_info=False)
        return results

    @staticmethod
    def _build_search_form_data(request: YokTezSearchRequest) -> Dict[str, str]:
        """Build the multipart form-data payload for the new (2026) keyword search."""
        return {
            "keyword": request.aranacak_kelime or "",
            "keyword1": request.aranacak_kelime_2 or "",
            "keyword2": request.aranacak_kelime_3 or "",
            "ops_field": request.operator_1.value,
            "ops_field1": request.operator_2.value,
            "nevi": request.arama_alani.value,
            "tip": request.arama_tipi.value,
            "Tur": request.tez_turu.value,
            "Dil": request.dil.value,
            "izin": request.izin_durumu.value,
            "Durum": request.tez_durumu.value,
            "yil1": request.yil_baslangic or "0",
            "yil2": request.yil_bitis or "0",
            "islem": "4",
            "-find": "  Bul",
        }

    async def search_theses(self, request: YokTezSearchRequest) -> YokTezSearchResult:
        """Search YÖK National Thesis Center using the 2026 keyword-based search API."""
        request_params_dict = request.model_dump(exclude_defaults=True, mode="json")
        logger.info(f"[SEARCH] Search request parameters: {request_params_dict}")

        if not request.aranacak_kelime:
            return YokTezSearchResult(
                theses=[],
                total_results_found=0,
                results_in_batch=0,
                current_page=request.page,
                total_pages=0,
                query_used_parameters=request_params_dict,
                error_message=(
                    "No search term provided. Set 'aranacak_kelime' (or one of the legacy "
                    "field-specific parameters such as 'tez_ad', 'yazar_ad_soyad')."
                ),
            )

        try:
            logger.info("[SEARCH] Visiting tarama.jsp to establish session...")
            await self._http_client.get(self.YOK_TEZ_SEARCH_PAGE_URL, timeout=self._request_timeout)

            form_data = self._build_search_form_data(request)

            logger.info("[SEARCH] POSTing search request to SearchTez...")
            post_response = await self._http_client.post(
                self.YOK_TEZ_SEARCH_ACTION_URL,
                data=form_data,
                timeout=self._request_timeout,
                headers={
                    "Referer": self.YOK_TEZ_SEARCH_PAGE_URL,
                    "Origin": self.YOK_TEZ_BASE_URL,
                },
                follow_redirects=False,
            )

            if post_response.status_code in (301, 302, 303, 307, 308):
                redirect_url = post_response.headers.get("location", "")
                if redirect_url.startswith("http://"):
                    redirect_url = redirect_url.replace("http://", "https://", 1)
                elif redirect_url.startswith("/"):
                    redirect_url = urllib.parse.urljoin(self.YOK_TEZ_BASE_URL, redirect_url)
                elif not redirect_url.startswith("https://"):
                    redirect_url = urllib.parse.urljoin(
                        self.YOK_TEZ_SEARCH_ACTION_URL, redirect_url
                    )
                logger.info(f"[SEARCH] Following redirect to: {redirect_url}")
                response = await self._http_client.get(redirect_url, timeout=self._request_timeout)
            else:
                response = post_response

            response.raise_for_status()
            page_source = response.text
        except asyncio.TimeoutError:
            return YokTezSearchResult(
                theses=[],
                current_page=request.page,
                query_used_parameters=request_params_dict,
                error_message="Timeout during HTTP request.",
            )
        except httpx.RequestError as exc:
            return YokTezSearchResult(
                theses=[],
                current_page=request.page,
                query_used_parameters=request_params_dict,
                error_message=f"HTTP request error: {exc}",
            )
        except Exception as exc:
            logger.exception("Unexpected error in search_theses")
            return YokTezSearchResult(
                theses=[],
                current_page=request.page,
                query_used_parameters=request_params_dict,
                error_message=f"Unexpected error during search: {exc}",
            )

        return self._build_listing_from_html(
            page_source=page_source,
            request_page=request.page,
            limit_per_page=request.limit_per_page,
            query_params=request_params_dict,
        )

    def _build_listing_from_html(
        self,
        page_source: str,
        request_page: int,
        limit_per_page: int,
        query_params: Dict[str, Any],
    ) -> YokTezSearchResult:
        """Parse a YÖK results HTML page into a YokTezSearchResult.

        Shared between live search (search_theses) and TezIslemleri listings,
        since both pages return the same result-card / referenceData layout.
        """
        if "SİSTEMDE BEKLENMEDİK BİR HATA" in page_source.upper() or (
            "Hata Oluştu" in page_source and "result-card" not in page_source
        ):
            return YokTezSearchResult(
                theses=[],
                total_results_found=0,
                results_in_batch=0,
                current_page=request_page,
                total_pages=0,
                query_used_parameters=query_params,
                error_message="YÖK returned a system error page for this query.",
            )

        soup = BeautifulSoup(page_source, "lxml")

        # The count banner lives in different classes across YÖK layouts, and an empty
        # template div of one class can precede the populated one — so pick the first
        # candidate that actually has text.
        warning_div = None
        for _cls in ("result-count-text", "result-limit-warning", "warning-text"):
            _cand = soup.find("div", class_=_cls)
            if _cand and _cand.get_text(strip=True):
                warning_div = _cand
                break
        warning_text = warning_div.get_text(" ", strip=True) if warning_div else ""

        total_results_on_yok: Optional[int] = None
        results_in_batch: Optional[int] = None

        total_match = re.search(r"([\d.,]+)\s*kayıt bulundu", warning_text)
        if total_match:
            total_results_on_yok = self._parse_int_with_thousands(total_match.group(1))

        shown_match = re.search(r"([\d.,]+)\s*tanesi görüntülenmektedir", warning_text)
        if shown_match:
            results_in_batch = self._parse_int_with_thousands(shown_match.group(1))

        if "bulunamadı" in warning_text.lower() or total_results_on_yok == 0:
            total_results_on_yok = 0
            results_in_batch = 0

        reference_data = self._extract_reference_data(page_source)
        all_cards = self._parse_result_cards(soup, reference_data)

        if results_in_batch is None:
            results_in_batch = len(all_cards)
        if total_results_on_yok is None:
            total_results_on_yok = results_in_batch

        error_msg: Optional[str] = None
        if not all_cards and total_results_on_yok and total_results_on_yok > 0:
            error_msg = "YÖK reports results but no result-card elements were parsed."
        elif total_results_on_yok == 0:
            error_msg = "No theses found for the given criteria."

        pageable = results_in_batch if results_in_batch else len(all_cards)
        total_pages = math.ceil(pageable / limit_per_page) if pageable > 0 else 0

        paginated: List[YokTezCompactThesisDetail] = []
        if all_cards:
            start = (request_page - 1) * limit_per_page
            end = start + limit_per_page
            paginated = all_cards[start:end]
            if not paginated and request_page > 1:
                error_msg = (
                    (error_msg + "; " if error_msg else "")
                    + f"Page {request_page} is beyond the available batch ({total_pages} pages)."
                )

        if (
            total_results_on_yok
            and results_in_batch
            and total_results_on_yok > results_in_batch
        ):
            logger.info(
                "YÖK total=%s but only %s included in this batch (server-side cap).",
                total_results_on_yok,
                results_in_batch,
            )

        return YokTezSearchResult(
            theses=paginated,
            total_results_found=total_results_on_yok,
            results_in_batch=results_in_batch,
            current_page=request_page,
            total_pages=total_pages,
            query_used_parameters=query_params,
            error_message=error_msg,
        )

    # --- Anabilim Dalı (department) list + advanced search (islem=2) ---

    @staticmethod
    def _tr_upper(text: str) -> str:
        """Uppercase with Turkish rules (i→İ, ı→I) for case-insensitive matching."""
        return text.replace("i", "İ").replace("ı", "I").upper()

    async def get_anabilim_dali_list(
        self, force_refresh: bool = False
    ) -> List[YokTezAnabilimDali]:
        """Fetch (and cache) YÖK's full list of departments (anabilim dalı).

        Parses name+code pairs from YÖK's getAllABD endpoint. Cached for the
        process lifetime since the list rarely changes.
        """
        if self._abd_list_cache is not None and not force_refresh:
            return self._abd_list_cache
        async with self._abd_list_lock:
            if self._abd_list_cache is not None and not force_refresh:
                return self._abd_list_cache
            logger.info("[ABD] Fetching full department list from YÖK...")
            await self._http_client.get(
                self.YOK_TEZ_SEARCH_PAGE_URL, timeout=self._request_timeout
            )
            response = await self._http_client.get(
                self.YOK_TEZ_ALL_ABD_URL, timeout=self._request_timeout
            )
            response.raise_for_status()
            pairs = re.findall(r'ad="([^"]+)"\s+kod="(\d+)"', response.text)
            seen: set = set()
            items: List[YokTezAnabilimDali] = []
            for name, code in pairs:
                if code in seen:
                    continue
                seen.add(code)
                items.append(YokTezAnabilimDali(code=code, name=name.strip()))
            self._abd_list_cache = items
            logger.info("[ABD] Cached %d departments.", len(items))
            return items

    async def search_anabilim_dali(
        self, keyword: str, max_results: int = 50
    ) -> YokTezAnabilimDaliListResult:
        """Search YÖK's department list for names containing the given keyword."""
        kw = (keyword or "").strip()
        if not kw:
            return YokTezAnabilimDaliListResult(
                keyword=keyword, error_message="A non-empty keyword is required."
            )
        try:
            all_items = await self.get_anabilim_dali_list()
        except Exception as exc:
            logger.exception("[ABD] Failed to fetch department list")
            return YokTezAnabilimDaliListResult(
                keyword=keyword, error_message=f"Could not fetch department list: {exc}"
            )
        needle = self._tr_upper(kw)
        matches = [i for i in all_items if needle in self._tr_upper(i.name)]
        result = YokTezAnabilimDaliListResult(
            matches=matches[: max(1, max_results)],
            total_matches=len(matches),
            returned=min(len(matches), max(1, max_results)),
            keyword=keyword,
        )
        if not matches:
            result.error_message = f"No department names contain '{keyword}'."
        return result

    @staticmethod
    def _build_advanced_search_form_data(
        request: YokTezAnabilimDaliSearchRequest, abd_code: str
    ) -> Dict[str, str]:
        """Build the GForm (advanced, islem=2) payload for a single department code.

        Empty Enstitu/yil values MUST be sent as '0' — YÖK's Bul button normalises
        them to 0 before submit, and the server rejects empty values
        ("Geçersiz sorgulama").
        """
        return {
            "uniad": "", "Universite": "", "uni_yoksis_id": "", "source": "TR",
            "ensad": "", "Enstitu": "0", "ens_grubu": "",
            "abdad": "", "ABD": abd_code,
            "Konu": "",
            "Tur": request.tez_turu.value,
            "yil1": request.yil_baslangic or "0",
            "yil2": request.yil_bitis or "0",
            "izin": request.izin_durumu.value,
            "Durum": request.tez_durumu.value,
            "TezAd": request.tez_adi or "",
            "Dil": request.dil.value,
            "AdSoyad": request.yazar or "",
            "DanismanAdSoyad": request.danisman or "",
            "Dizin": request.dizin_terimleri or "",
            "TezNo": "",
            "Bolum": "0",
            "islem": "2",
            "-find": "  Bul",
        }

    async def _post_advanced_search(self, form_data: Dict[str, str]) -> str:
        """POST one advanced search and return the result HTML (session established first)."""
        await self._http_client.get(
            self.YOK_TEZ_SEARCH_PAGE_URL, timeout=self._request_timeout
        )
        response = await self._http_client.post(
            self.YOK_TEZ_SEARCH_ACTION_URL,
            data=form_data,
            timeout=self._request_timeout,
            headers={
                "Referer": self.YOK_TEZ_SEARCH_PAGE_URL,
                "Origin": self.YOK_TEZ_BASE_URL,
            },
        )
        response.raise_for_status()
        return response.text

    async def search_theses_by_anabilim_dali(
        self, request: YokTezAnabilimDaliSearchRequest
    ) -> YokTezSearchResult:
        """Advanced search (islem=2) filtered by one or more department codes.

        Each code is searched separately and the resulting theses are merged and
        deduplicated. Pagination is applied client-side over the merged list.
        """
        params_dict = request.model_dump(exclude_defaults=True, mode="json")
        codes = [c.strip() for c in request.anabilim_dali_kodlari if c and c.strip()]
        if not codes:
            return YokTezSearchResult(
                theses=[], total_results_found=0, results_in_batch=0,
                current_page=request.page, total_pages=0,
                query_used_parameters=params_dict,
                error_message="No department codes provided.",
            )
        if len(codes) > self.MAX_ABD_PER_SEARCH:
            return YokTezSearchResult(
                theses=[], current_page=request.page,
                query_used_parameters=params_dict,
                error_message=(
                    f"Too many department codes ({len(codes)}). Provide at most "
                    f"{self.MAX_ABD_PER_SEARCH}; narrow your selection."
                ),
            )

        logger.info("[ABD-SEARCH] Searching %d department(s): %s", len(codes), codes)
        merged: List[YokTezCompactThesisDetail] = []
        seen_keys: set = set()
        total_reported = 0
        errors: List[str] = []

        for code in codes:
            form_data = self._build_advanced_search_form_data(request, code)
            try:
                html = await self._post_advanced_search(form_data)
            except Exception as exc:
                logger.error("[ABD-SEARCH] code=%s failed: %s", code, exc)
                errors.append(f"code {code}: {exc}")
                continue
            if "Geçersiz sorgulama" in html:
                logger.error("[ABD-SEARCH] code=%s rejected by YÖK (Geçersiz sorgulama).", code)
                errors.append(f"code {code}: rejected by YÖK")
                continue
            partial = self._build_listing_from_html(
                page_source=html, request_page=1, limit_per_page=10_000,
                query_params=params_dict,
            )
            if partial.total_results_found:
                total_reported += partial.total_results_found
            for thesis in partial.theses:
                key = (
                    thesis.thesis_key or thesis.encrypted_no
                    or thesis.thesis_no or f"_idx_{id(thesis)}"
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                merged.append(thesis)

        if not merged and errors:
            return YokTezSearchResult(
                theses=[], current_page=request.page,
                query_used_parameters=params_dict,
                error_message="; ".join(errors),
            )

        results_in_batch = len(merged)
        total_pages = (
            math.ceil(results_in_batch / request.limit_per_page)
            if results_in_batch else 0
        )
        start = (request.page - 1) * request.limit_per_page
        end = start + request.limit_per_page
        paginated = merged[start:end]

        error_msg: Optional[str] = None
        if not merged:
            error_msg = "No theses found for the given department(s) and filters."
        elif not paginated and request.page > 1:
            error_msg = (
                f"Page {request.page} is beyond the available results "
                f"({total_pages} pages)."
            )
        if errors:
            error_msg = (
                (error_msg + "; " if error_msg else "")
                + "Some departments failed: " + "; ".join(errors)
            )

        return YokTezSearchResult(
            theses=paginated,
            total_results_found=total_reported or results_in_batch,
            results_in_batch=results_in_batch,
            current_page=request.page,
            total_pages=total_pages,
            query_used_parameters=params_dict,
            error_message=error_msg,
        )

    async def list_recent_theses(
        self, request: YokTezRecentListRequest
    ) -> YokTezSearchResult:
        """Fetch a system-curated list of recent theses via TezIslemleri.

        Two modes (selectable on the request):
          - SON_15_GUN: theses uploaded to YÖK in the last 15 days.
          - BU_YIL: all theses with the current publication year.

        The response shape is the same as search_theses (YokTezSearchResult).
        Cannot be replicated via search_theses because the regular search endpoint
        rejects empty keywords.
        """
        params_dict = request.model_dump(mode="json")
        logger.info(f"[RECENT] Fetching recent list: {params_dict}")

        try:
            # Establish session — TezIslemleri requires it (returns 302 otherwise)
            await self._http_client.get(
                self.YOK_TEZ_SEARCH_PAGE_URL, timeout=self._request_timeout
            )

            response = await self._http_client.get(
                self.YOK_TEZ_ISLEMLERI_URL,
                params={"islem": request.mode.value},
                timeout=self._request_timeout,
                headers={"Referer": self.YOK_TEZ_SEARCH_PAGE_URL},
            )
            response.raise_for_status()
            page_source = response.text
        except httpx.RequestError as exc:
            return YokTezSearchResult(
                theses=[],
                current_page=request.page,
                query_used_parameters=params_dict,
                error_message=f"HTTP request error: {exc}",
            )
        except Exception as exc:
            logger.exception("Unexpected error in list_recent_theses")
            return YokTezSearchResult(
                theses=[],
                current_page=request.page,
                query_used_parameters=params_dict,
                error_message=f"Unexpected error: {exc}",
            )

        return self._build_listing_from_html(
            page_source=page_source,
            request_page=request.page,
            limit_per_page=request.limit_per_page,
            query_params=params_dict,
        )

    @staticmethod
    def _strip_label_prefix(text: Optional[str]) -> Optional[str]:
        """Strip leading HTML label like '<strong>Anahtar Kelime: </strong>' from a string."""
        if not text:
            return text
        soup = BeautifulSoup(text, "lxml")
        # Remove the leading <strong>...:</strong> if present
        strong = soup.find("strong")
        if strong and ":" in strong.get_text():
            strong.decompose()
        cleaned = soup.get_text().strip()
        # Collapse internal whitespace runs
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned or None

    @staticmethod
    def _parse_keyword_pairs(raw: Optional[str]) -> List[YokTezKeywordPair]:
        """Parse YÖK's bilingual keyword string ('A = B ; C = D ; ...') into pairs."""
        if not raw:
            return []
        pairs: List[YokTezKeywordPair] = []
        for chunk in raw.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            if "=" in chunk:
                left, _, right = chunk.partition("=")
                pairs.append(
                    YokTezKeywordPair(
                        tr=left.strip() or None,
                        en=right.strip() or None,
                    )
                )
            else:
                # Single-language entry — keep as the original-side keyword only
                pairs.append(YokTezKeywordPair(tr=chunk, en=None))
        return pairs

    def _extract_ids_from_detail_url(self, url: str) -> tuple[Optional[str], Optional[str]]:
        """Pull thesis_key (id) and encrypted_no (no) out of a tezDetay.jsp URL."""
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        thesis_key = (qs.get("id") or [None])[0]
        encrypted_no = (qs.get("no") or [None])[0]
        return thesis_key, encrypted_no

    async def get_thesis_details(
        self, request: YokTezThesisDetailsRequest
    ) -> YokTezThesisDetails:
        """Fetch rich thesis metadata + citations from YÖK's tezBilgiDetay.jsp endpoint.

        Returns advisor, full location hierarchy, both abstracts, both keyword sets,
        and citations in APA / IEEE / MLA / Chicago / Harvard formats. No PDF download
        required — much cheaper than get_thesis_pdf_as_markdown when you only need
        metadata.
        """
        thesis_key = request.thesis_key
        encrypted_no = request.encrypted_no
        source_url: Optional[HttpUrl] = request.detail_page_url

        if source_url and (not thesis_key or not encrypted_no):
            k, n = self._extract_ids_from_detail_url(str(source_url))
            thesis_key = thesis_key or k
            encrypted_no = encrypted_no or n

        if not thesis_key or not encrypted_no:
            return YokTezThesisDetails(
                source_detail_page_url=source_url,
                error_message=(
                    "Could not determine thesis_key/encrypted_no. Supply them directly "
                    "or pass a detail_page_url containing 'id' and 'no' query params."
                ),
            )

        # If only IDs were given, reconstruct the source URL for downstream use.
        if source_url is None:
            source_url = HttpUrl(
                self.YOK_TEZ_DETAIL_URL_WITH_NO_TEMPLATE.format(
                    thesis_key=thesis_key, encrypted_no=encrypted_no
                )
            )

        try:
            response = await self._http_client.get(
                self.YOK_TEZ_BILGI_DETAY_URL,
                params={"kayitNo": thesis_key, "tezNo": encrypted_no},
                timeout=self._request_timeout,
                headers={"Referer": self.YOK_TEZ_SEARCH_PAGE_URL},
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            return YokTezThesisDetails(
                source_detail_page_url=source_url,
                error_message=f"HTTP {exc.response.status_code} from tezBilgiDetay.jsp.",
            )
        except (httpx.RequestError, json.JSONDecodeError, ValueError) as exc:
            return YokTezThesisDetails(
                source_detail_page_url=source_url,
                error_message=f"Failed to fetch/parse thesis details: {exc}",
            )

        advisor = self._strip_label_prefix(payload.get("danisman"))
        keywords_tr = self._parse_keyword_pairs(
            self._strip_label_prefix(payload.get("anahtarKelimeTr"))
        )
        keywords_en = self._parse_keyword_pairs(
            self._strip_label_prefix(payload.get("anahtarKelimeEn"))
        )

        return YokTezThesisDetails(
            advisor=advisor,
            location_full=(payload.get("yer") or "").strip() or None,
            abstract_tr=(payload.get("trOzet") or "").strip() or None,
            abstract_en=(payload.get("enOzet") or "").strip() or None,
            keywords_tr=keywords_tr,
            keywords_en=keywords_en,
            citation_apa=(payload.get("apa_ref") or "").strip() or None,
            citation_ieee=(payload.get("ieee_ref") or "").strip() or None,
            citation_mla=(payload.get("mla_ref") or "").strip() or None,
            citation_chicago=(payload.get("chicago_ref") or "").strip() or None,
            citation_harvard=(payload.get("harvard_ref") or "").strip() or None,
            source_detail_page_url=source_url,
        )

    async def get_thesis_pdf_as_markdown(self, request: YokTezDocumentRequest) -> YokTezDocumentMarkdown:
        """
        Retrieves a specific YÖK thesis, fetches metadata, downloads PDF (if permissible & not cached),
        isolates the specified PDF page using pypdf, and converts that page to Markdown using MarkItDown.
        """
        detail_page_url_str = str(request.detail_page_url)
        original_pdf_bytes = await self._pdf_bytes_cache.get(detail_page_url_str)
        metadata: Dict[str, Any] = {}
        error_msg: Optional[str] = None
        actual_pdf_url_str: Optional[str] = None
        extracted_thesis_title: Optional[str] = None
        extracted_thesis_author: Optional[str] = None
        is_pdf_permissible: bool = False
        page_markdown_content: Optional[str] = None
        total_pdf_pages: int = 0
        characters_on_page: Optional[int] = None

        try:
            response = await self._http_client.get(detail_page_url_str, timeout=self._request_timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            metadata = self._parse_thesis_detail_html(soup, detail_page_url_str)
            actual_pdf_url_str = metadata.get("retrieved_pdf_url")
            extracted_thesis_title = metadata.get("title_tr") or metadata.get("title_combined")
            extracted_thesis_author = metadata.get("author")
            is_pdf_permissible = metadata.get("is_pdf_permissible", False)
            if metadata.get("metadata_error_message"):
                error_msg = (error_msg + "; " if error_msg else "") + metadata["metadata_error_message"]
            if metadata.get("pdf_permission_error_message"):
                error_msg = (error_msg + "; " if error_msg else "") + metadata["pdf_permission_error_message"]
        except httpx.RequestError as e:
            error_msg = (error_msg + "; " if error_msg else "") + f"Failed to fetch detail page: {e}"
        except Exception as e:
            error_msg = (error_msg + "; " if error_msg else "") + f"Error parsing detail page: {e}"

        if is_pdf_permissible and actual_pdf_url_str and not original_pdf_bytes:
            try:
                async with self._http_client.stream("GET", actual_pdf_url_str, timeout=self._request_timeout * 2) as pdf_response:
                    pdf_response.raise_for_status()
                    original_pdf_bytes = await pdf_response.aread()
                if not original_pdf_bytes:
                    error_msg = (error_msg + "; " if error_msg else "") + "PDF empty or download failed."
                else:
                    await self._pdf_bytes_cache.set(detail_page_url_str, original_pdf_bytes)
            except Exception as e:
                error_msg = (error_msg + "; " if error_msg else "") + f"PDF download error: {e}"
        elif is_pdf_permissible and original_pdf_bytes:
            logger.info(f"CACHE Hit for PDF: {detail_page_url_str}")
        elif not is_pdf_permissible and not error_msg:
            error_msg = (error_msg + "; " if error_msg else "") + metadata.get("pdf_permission_error_message", "PDF not permissible.")

        if original_pdf_bytes and is_pdf_permissible:
            try:
                reader = PdfReader(io.BytesIO(original_pdf_bytes))
                total_pdf_pages = len(reader.pages)
                if not (0 < request.page_number <= total_pdf_pages):
                    error_msg = (error_msg + "; " if error_msg else "") + f"Page {request.page_number} out of range (1-{total_pdf_pages})."
                else:
                    writer = PdfWriter()
                    writer.add_page(reader.pages[request.page_number - 1])
                    single_pg_io = io.BytesIO()
                    writer.write(single_pg_io)
                    single_pg_bytes = single_pg_io.getvalue()
                    if single_pg_bytes:
                        try:
                            conv_res = self._md_converter.convert(io.BytesIO(single_pg_bytes))
                            page_markdown_content = conv_res.text_content
                            if page_markdown_content is not None:
                                characters_on_page = len(page_markdown_content)
                                if not page_markdown_content.strip() and characters_on_page == 0:
                                    logger.warning(f"MarkItDown: Empty content page {request.page_number}.")
                            else:
                                characters_on_page = 0
                                page_markdown_content = None
                                error_msg = (error_msg + "; " if error_msg else "") + f"MarkItDown: No content for page {request.page_number}."
                        except Exception as e:
                            error_msg = (error_msg + "; " if error_msg else "") + f"MarkItDown conversion error: {e}"
                    else:
                        error_msg = (error_msg + "; " if error_msg else "") + "pypdf: Failed to isolate page."
            except Exception as e:
                error_msg = (error_msg + "; " if error_msg else "") + f"pypdf processing error: {e}"
        elif not error_msg and is_pdf_permissible and not original_pdf_bytes:
            error_msg = (error_msg + "; " if error_msg else "") + "PDF content unavailable."

        return YokTezDocumentMarkdown(
            page_markdown_content=page_markdown_content, source_detail_page_url=request.detail_page_url,
            retrieved_pdf_url=HttpUrl(actual_pdf_url_str) if actual_pdf_url_str else None,
            current_pdf_page=request.page_number, total_pdf_pages=total_pdf_pages,
            is_paginated=total_pdf_pages > 1, characters_on_page=characters_on_page,
            error_message=error_msg.strip("; ") if error_msg else None,
            thesis_title=extracted_thesis_title, thesis_author=extracted_thesis_author
        )
