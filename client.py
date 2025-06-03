# client.py
import asyncio
import logging
import os
import re
import math
import html
import urllib.parse
from typing import Dict, List, Optional, Any, Tuple
import io

from pydantic import HttpUrl # Ensure HttpUrl is imported

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Playwright, Browser, Page

from pypdf import PdfReader, PdfWriter
from markitdown import MarkItDown
import ftfy

from models import (
    YokTezSearchRequest, YokTezCompactThesisDetail, YokTezSearchResult,
    YokTezDocumentRequest, YokTezDocumentMarkdown, InternalThesisDetail
)

logger = logging.getLogger(__name__)

if not logger.hasHandlers(): # Pragma: no cover
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

class YokTezApiClient:
    """
    API Client for interacting with the YÖK National Thesis Center.
    Handles searching theses and extracting content from their PDFs.
    """
    YOK_TEZ_BASE_URL = "https://tez.yok.gov.tr"
    YOK_TEZ_SEARCH_PAGE_URL = f"{YOK_TEZ_BASE_URL}/UlusalTezMerkezi/tarama.jsp"
    YOK_TEZ_SEARCH_ACTION_URL = f"{YOK_TEZ_BASE_URL}/UlusalTezMerkezi/SearchTez"
    YOK_TEZ_DETAIL_URL_TEMPLATE = f"{YOK_TEZ_BASE_URL}/UlusalTezMerkezi/tezDetay.jsp?id={{thesis_key}}"

    def __init__(self, request_timeout: float = 60.0, playwright_headless: bool = True):
        """
        Initializes the YokTezApiClient.

        Args:
            request_timeout: Timeout for HTTP requests in seconds.
            playwright_headless: Whether to run the Playwright browser in headless mode.
        """
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._headless = playwright_headless
        self._request_timeout = request_timeout
        self._pdf_bytes_cache: Dict[str, bytes] = {}
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(request_timeout, read=request_timeout * 2),
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
        self._md_converter = MarkItDown()

    async def _start_playwright(self) -> Browser:
        """Starts Playwright and launches a browser instance if not already started."""
        if not self._playwright:
            logger.info("Initializing Playwright...")
            self._playwright = await async_playwright().start()
        if not self._browser or not self._browser.is_connected():
            logger.info(f"Launching Chromium browser (headless: {self._headless})...")
            if not self._playwright:
                raise RuntimeError("Playwright not initialized before browser launch.")
            self_playwright_chromium = getattr(self._playwright, 'chromium', None)
            if not self_playwright_chromium :
                raise RuntimeError("Playwright chromium attribute not found.")
            self._browser = await self_playwright_chromium.launch(headless=self._headless)
        if not self._browser:
            raise RuntimeError("Browser could not be initialized.")
        return self._browser

    async def _get_playwright_page(self) -> Page:
        """Gets a new Playwright page from the managed browser instance."""
        browser = await self._start_playwright()
        context_options: Dict[str, Any] = {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'java_script_enabled': True
        }
        context = await browser.new_context(**context_options)
        page = await context.new_page()
        return page

    async def close_client_session(self):
        """Closes the Playwright browser and HTTPX client session."""
        logger.info("YokTezApiClient: Closing resources...")
        if self._browser and self._browser.is_connected():
            logger.info("Closing Playwright browser...")
            await self._browser.close()
            self._browser = None
        if self._playwright:
            logger.info("Stopping Playwright...")
            await self._playwright.stop()
            self._playwright = None
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
            no_permission_text = "Bu tezin, veri tabanı üzerinden yayınlanma izni bulunmamaktadır."
            if no_permission_text in download_cell.get_text(strip=True):
                data["pdf_permission_error_message"] = no_permission_text
            else:
                data["pdf_permission_error_message"] = "PDF download link or known 'no permission' message not found."
            data["is_pdf_permissible"] = False
        kunye_cell = cells[2]
        for br in kunye_cell.find_all("br"): br.replace_with("\n")
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
                if len(title_split) > 1: data["title_en"] = " / ".join(ts.strip() for ts in title_split[1:])
            for i in range(current_part_index, len(kunye_parts)):
                part = kunye_parts[i]
                if part.startswith("Yazar:"): data["author"] = part.replace("Yazar:", "",1).strip()
                elif part.startswith("Danışman:"): data["advisor"] = part.replace("Danışman:", "",1).strip()
                elif part.startswith("Yer Bilgisi:"): data["location_info"] = part.replace("Yer Bilgisi:", "",1).strip()
                elif part.startswith("Konu:"): data["subject_info"] = part.replace("Konu:", "",1).strip()
                elif part.startswith("Dizin:"): data["index_terms"] = part.replace("Dizin:", "",1).strip()
        durum_cell = cells[3]
        for br in durum_cell.find_all("br"): br.replace_with("\n")
        durum_parts = [part.strip() for part in durum_cell.get_text(separator="\n").split('\n') if part.strip()]
        if len(durum_parts) > 0: data["status_text"] = durum_parts[0]
        if len(durum_parts) > 1: data["thesis_type_text"] = durum_parts[1]
        if len(durum_parts) > 2: data["language_text"] = durum_parts[2]
        if len(durum_parts) > 3: data["year_text"] = durum_parts[3]
        if len(durum_parts) > 4: data["pages_text"] = durum_parts[4]
        abstract_tr_td = main_table.find("td", id="td0")
        if abstract_tr_td: data["abstract_tr"] = abstract_tr_td.get_text(strip=True)
        abstract_en_td = main_table.find("td", id="td1")
        if abstract_en_td: data["abstract_en"] = abstract_en_td.get_text(strip=True)
        return data

    async def _fetch_thesis_details_from_key(self, thesis_key: str) -> Optional[InternalThesisDetail]:
        """
        Fetches and parses comprehensive thesis details from its detail page using a thesis key.
        """
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

    def _parse_watable_js_data(self, js_content: str) -> List[YokTezCompactThesisDetail]:
        """
        Parses the JavaScript content from the WATable initialization to extract thesis data.
        """
        theses_details: List[YokTezCompactThesisDetail] = []
        doc_matches = re.finditer(r'var doc = {(.+?)};', js_content, re.DOTALL)
        
        for match in doc_matches:
            doc_str = "{" + match.group(1) + "}"
            try:
                tez_no_val: Optional[str] = None
                thesis_key_val: Optional[str] = None
                author_val: Optional[str] = None
                year_val: Optional[str] = None
                title_original_val: str = "N/A"
                title_translated_val: Optional[str] = None
                university_val: Optional[str] = None
                thesis_type_val: Optional[str] = None
                subject_val: Optional[str] = None

                user_id_match = re.search(r'userId:\s*"<span[^>]*onclick=tezDetay\(\s*\'([^\']+)\'\s*,\s*\'([^\']+)\'\s*\)>([^<]+)</span>"', doc_str, re.DOTALL)
                if user_id_match:
                    thesis_key_val = user_id_match.group(1).strip()
                    tez_no_val = user_id_match.group(3).strip()

                name_match = re.search(r'name:\s*"([^"]*)"', doc_str)
                if name_match: author_val = html.unescape(name_match.group(1).strip())

                age_match = re.search(r'age:\s*"([^"]*)"', doc_str)
                if age_match: year_val = age_match.group(1).strip()
                
                weight_match = re.search(r'weight:\s*"((?:[^"\\]|\\.)*)"', doc_str, re.DOTALL)
                if weight_match:
                    weight_html_raw = weight_match.group(1)
                    decoded_text = ""
                    try:
                        decoded_text = bytes(weight_html_raw, "utf-8").decode("unicode_escape", errors='replace')
                    except Exception as e_decode_js:
                        logger.warning(f"JS unicode_escape failed for title part: {e_decode_js}. Using raw string for ftfy.")
                        decoded_text = weight_html_raw
                    fixed_text_after_ftfy = ftfy.fix_text(decoded_text)
                    final_text_for_soup = html.unescape(fixed_text_after_ftfy)
                    title_soup = BeautifulSoup(final_text_for_soup, 'lxml')
                    br_tag = title_soup.find('br')
                    if br_tag:
                        original_title_parts = []
                        current_node = br_tag.previous_sibling
                        while current_node:
                            node_text = ""
                            if isinstance(current_node, str): node_text = current_node.strip()
                            elif hasattr(current_node, 'get_text'): node_text = current_node.get_text(strip=True)
                            if node_text: original_title_parts.insert(0, node_text)
                            current_node = current_node.previous_sibling
                        title_original_val = " ".join(original_title_parts).strip("'").strip()
                        if not title_original_val and title_soup.contents:
                             first_content = title_soup.contents[0]
                             if isinstance(first_content, str): title_original_val = first_content.strip("'").strip()
                             elif hasattr(first_content, 'get_text'): title_original_val = first_content.get_text(strip=True).strip("'").strip()
                        italic_span = title_soup.find('span', style=lambda value: value and 'font-style: italic' in value.lower())
                        if italic_span: title_translated_val = italic_span.get_text(strip=True)
                        else:
                            next_node = br_tag.next_sibling
                            if next_node and isinstance(next_node, str) and next_node.strip(): title_translated_val = next_node.strip()
                            elif next_node and hasattr(next_node, 'get_text'): title_translated_val = next_node.get_text(strip=True)
                    else:
                        title_original_val = title_soup.get_text(strip=True).strip("'").strip()

                uni_match = re.search(r'uni:\s*"([^"]*)"', doc_str)
                if uni_match: university_val = html.unescape(uni_match.group(1).strip())

                important_match = re.search(r'important:\s*"([^"]*)"', doc_str)
                if important_match: thesis_type_val = html.unescape(important_match.group(1).strip())

                some_date_match = re.search(r'someDate:\s*"([^"]*)"', doc_str)
                if some_date_match:
                    subject_raw = html.unescape(some_date_match.group(1).strip())
                    subject_val = "; ".join([s.strip() for s in subject_raw.split(';') if s.strip()]) if subject_raw else None
                
                if tez_no_val and thesis_key_val:
                    detail_page_url_str = self.YOK_TEZ_DETAIL_URL_TEMPLATE.format(thesis_key=thesis_key_val)
                    display_title = title_original_val if title_original_val and title_original_val != "N/A" else "Title Not Parsed"
                    if title_translated_val:
                        display_title = f"{display_title} / {title_translated_val}"
                    
                    compact_detail = YokTezCompactThesisDetail(
                        thesis_no=tez_no_val, title=display_title, author=author_val,
                        university_info=university_val, thesis_key=thesis_key_val,
                        detail_page_url=HttpUrl(detail_page_url_str), year=year_val,
                        thesis_type=thesis_type_val, subject=subject_val 
                    )
                    theses_details.append(compact_detail)
                else:
                    logger.warning(f"Skipping a JS 'doc' entry: missing tez_no or thesis_key. Fragment: {doc_str[:200]}...")
            except Exception as e_parse:
                logger.error(f"Error parsing a 'doc' object from JS: {e_parse}. Fragment: {doc_str[:200]}", exc_info=False)
        return theses_details

    async def search_theses(self, request: YokTezSearchRequest) -> YokTezSearchResult:
        """
        Performs a search on YÖK National Thesis Center using the 'Detailed Search' form.
        """
        pw_page: Optional[Page] = None
        all_compact_details: List[YokTezCompactThesisDetail] = []
        total_results_on_yok: Optional[int] = None
        results_displayed_in_js: Optional[int] = None
        error_msg: Optional[str] = None
        request_params_dict = request.model_dump(exclude_defaults=True)
        logger.info(f"[SEARCH] Attempting detailed search with parameters: {request_params_dict}")

        try:
            pw_page = await self._get_playwright_page()
            await pw_page.goto(self.YOK_TEZ_SEARCH_PAGE_URL, timeout=self._request_timeout * 1000)
            form_locator = pw_page.locator('form[name="GForm"]')
            
            if request.universite_ad: await form_locator.locator('input[name="uniad"]').fill(request.universite_ad.upper())
            if request.enstitu_ad: await form_locator.locator('input[name="ensad"]').fill(request.enstitu_ad.upper())
            if request.anabilim_dal_ad: await form_locator.locator('input[name="abdad"]').fill(request.anabilim_dal_ad)
            if request.bilim_dal_ad: await form_locator.locator('input[name="bilim"]').fill(request.bilim_dal_ad)
            if request.tez_turu and hasattr(request.tez_turu, 'value') and request.tez_turu.value != "0":
                await form_locator.locator('select[name="Tur"]').select_option(value=request.tez_turu.value)
            if request.yil_baslangic and request.yil_baslangic != "0":
                await form_locator.locator('select[name="yil1"]').select_option(value=str(request.yil_baslangic))
            if request.yil_bitis and request.yil_bitis != "0":
                await form_locator.locator('select[name="yil2"]').select_option(value=str(request.yil_bitis))
            if request.izin_durumu and hasattr(request.izin_durumu, 'value') and request.izin_durumu.value != "0":
                await form_locator.locator('select[name="izin"]').select_option(value=request.izin_durumu.value)
            if request.tez_no: await form_locator.locator('input[name="TezNo"]').fill(request.tez_no)
            if request.tez_durumu and hasattr(request.tez_durumu, 'value'):
                await form_locator.locator('select[name="Durum"]').select_option(value=request.tez_durumu.value)
            if request.tez_ad: await form_locator.locator('input[name="TezAd"]').fill(request.tez_ad)
            if request.dil and hasattr(request.dil, 'value') and request.dil.value != "0":
                await form_locator.locator('select[name="Dil"]').select_option(value=request.dil.value)
            if request.yazar_ad_soyad: await form_locator.locator('input[name="AdSoyad"]').fill(request.yazar_ad_soyad.upper())
            if request.konu_basliklari: await form_locator.locator('input[name="Konu"]').fill(request.konu_basliklari)
            if request.enstitu_grubu and hasattr(request.enstitu_grubu, 'value') and request.enstitu_grubu.value != "":
                await form_locator.locator('select[name="EnstituGrubu"]').select_option(value=request.enstitu_grubu.value)
            if request.danisman_ad_soyad: await form_locator.locator('input[name="DanismanAdSoyad"]').fill(request.danisman_ad_soyad.upper())
            if request.dizin_terimleri: await form_locator.locator('input[name="Dizin"]').fill(request.dizin_terimleri)
            if request.ozet_metni: await form_locator.locator('input[name="Metin"]').fill(request.ozet_metni)
            
            await form_locator.locator('input[name="islem"]').evaluate("node => node.value = '2'") # Hidden field for detailed search
            logger.info("[SEARCH] Form fields filled. Submitting GForm...")
            
            async with pw_page.expect_navigation(wait_until="networkidle", timeout=self._request_timeout * 1000):
                await form_locator.locator('input[name="-find"]').click()

            logger.info(f"[SEARCH] Navigation complete. Current URL: {pw_page.url}")
            page_source = await pw_page.content()
            soup = BeautifulSoup(page_source, 'lxml')

            div_uyari = soup.find("div", id="divuyari")
            if div_uyari:
                div_text = div_uyari.get_text(strip=True, separator=" ")
                total_match = re.search(r"(\d+)\s*kayıt bulundu", div_text)
                if total_match: total_results_on_yok = int(total_match.group(1))
                displayed_match = re.search(r"(\d+)\s*tanesi görüntülenmektedir", div_text)
                if displayed_match: results_displayed_in_js = int(displayed_match.group(1))
                if "kayıt bulunamadı" in div_text.lower() or "tez bulunamadı" in div_text.lower():
                    total_results_on_yok = 0; results_displayed_in_js = 0
            else: logger.warning("divuyari (result count) not found.")

            scripts = soup.find_all("script", type="text/javascript")
            selected_script_content = next((s.string for s in scripts if s.string and "var waTable = emre(\"#div1\").WATable({" in s.string and "function getData()" in s.string), None)
            
            if selected_script_content:
                all_compact_details = self._parse_watable_js_data(selected_script_content)
                if results_displayed_in_js is None: results_displayed_in_js = len(all_compact_details)
                elif len(all_compact_details) != results_displayed_in_js :
                    logger.warning(f"Mismatch: Parsed {len(all_compact_details)} from JS, divuyari stated {results_displayed_in_js}.")
            elif total_results_on_yok is not None and total_results_on_yok > 0: error_msg = "YÖK indicates results, but WATable JS data not found."
            elif total_results_on_yok == 0: error_msg = "No theses found (confirmed by YÖK)."
            else: error_msg = "Could not determine result count and no WATable JS data found."
        
        except asyncio.TimeoutError: error_msg = "Timeout during Playwright operation."
        except Exception as e: error_msg = f"Unexpected error during search: {str(e)}"
        finally:
            if pw_page:
                try: await pw_page.close()
                except Exception as e_close: logger.error(f"Error closing playwright context: {e_close}")

        if total_results_on_yok is None: total_results_on_yok = len(all_compact_details)
        available_for_pagination = results_displayed_in_js if results_displayed_in_js is not None else len(all_compact_details)
        total_pages_in_js_batch = math.ceil(available_for_pagination / request.limit_per_page) if available_for_pagination > 0 else 0
        
        if total_results_on_yok == 0 and not error_msg: error_msg = "No theses found for criteria."

        paginated_results: List[YokTezCompactThesisDetail] = []
        if request.page > total_pages_in_js_batch and total_pages_in_js_batch > 0:
            error_msg = (error_msg + "; " if error_msg else "") + f"Page {request.page} exceeds pages ({total_pages_in_js_batch}) in current batch."
        elif not all_compact_details and not error_msg and (total_results_on_yok > 0):
            error_msg = (error_msg + "; " if error_msg else "") + "Thesis data extraction failed despite YÖK indicating results."
        elif all_compact_details:
            start_index = (request.page - 1) * request.limit_per_page
            end_index = start_index + request.limit_per_page
            paginated_results = all_compact_details[start_index:end_index]
            if not paginated_results and request.page > 1 and available_for_pagination > 0 :
                error_msg = (error_msg + "; " if error_msg else "") + f"Page {request.page} is beyond data in current batch."
            if results_displayed_in_js is not None and total_results_on_yok > results_displayed_in_js:
                logger.warning(f"YÖK: {total_results_on_yok} total, but only {results_displayed_in_js} in JS. Full pagination not implemented by client.")
        
        final_total_pages_on_yok = math.ceil(total_results_on_yok / request.limit_per_page) if total_results_on_yok > 0 else 0

        return YokTezSearchResult(
            theses=paginated_results, total_results_found=total_results_on_yok,
            current_page=request.page, total_pages=final_total_pages_on_yok, 
            query_used_parameters=request_params_dict, error_message=error_msg.strip("; ") if error_msg else None
        )

    async def get_thesis_pdf_as_markdown(self, request: YokTezDocumentRequest) -> YokTezDocumentMarkdown:
        """
        Retrieves a specific YÖK thesis, fetches metadata, downloads PDF (if permissible & not cached),
        isolates the specified PDF page using pypdf, and converts that page to Markdown using MarkItDown.
        """
        detail_page_url_str = str(request.detail_page_url)
        original_pdf_bytes = self._pdf_bytes_cache.get(detail_page_url_str)
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
            if metadata.get("metadata_error_message"): error_msg = (error_msg + "; " if error_msg else "") + metadata["metadata_error_message"]
            if metadata.get("pdf_permission_error_message"): error_msg = (error_msg + "; " if error_msg else "") + metadata["pdf_permission_error_message"]
        except httpx.RequestError as e: error_msg = (error_msg + "; " if error_msg else "") + f"Failed to fetch detail page: {e}"
        except Exception as e: error_msg = (error_msg + "; " if error_msg else "") + f"Error parsing detail page: {e}"

        if is_pdf_permissible and actual_pdf_url_str and not original_pdf_bytes:
            try:
                async with self._http_client.stream("GET", actual_pdf_url_str, timeout=self._request_timeout * 2) as pdf_response:
                    pdf_response.raise_for_status()
                    original_pdf_bytes = await pdf_response.aread()
                if not original_pdf_bytes: error_msg = (error_msg + "; " if error_msg else "") + "PDF empty or download failed."
                else: self._pdf_bytes_cache[detail_page_url_str] = original_pdf_bytes
            except Exception as e: error_msg = (error_msg + "; " if error_msg else "") + f"PDF download error: {e}"
        elif is_pdf_permissible and original_pdf_bytes: logger.info(f"CACHE Hit for PDF: {detail_page_url_str}")
        elif not is_pdf_permissible and not error_msg: error_msg = (error_msg + "; " if error_msg else "") + metadata.get("pdf_permission_error_message", "PDF not permissible.")

        if original_pdf_bytes and is_pdf_permissible:
            try:
                reader = PdfReader(io.BytesIO(original_pdf_bytes))
                total_pdf_pages = len(reader.pages)
                if not (0 < request.page_number <= total_pdf_pages):
                    error_msg = (error_msg + "; " if error_msg else "") + f"Page {request.page_number} out of range (1-{total_pdf_pages})."
                else:
                    writer = PdfWriter(); writer.add_page(reader.pages[request.page_number - 1])
                    single_pg_io = io.BytesIO(); writer.write(single_pg_io)
                    single_pg_bytes = single_pg_io.getvalue()
                    if single_pg_bytes:
                        try:
                            conv_res = self._md_converter.convert(io.BytesIO(single_pg_bytes))
                            page_markdown_content = conv_res.text_content
                            if page_markdown_content is not None:
                                characters_on_page = len(page_markdown_content)
                                if not page_markdown_content.strip() and characters_on_page == 0: logger.warning(f"MarkItDown: Empty content page {request.page_number}.")
                            else:
                                characters_on_page = 0; page_markdown_content = None
                                error_msg = (error_msg + "; " if error_msg else "") + f"MarkItDown: No content for page {request.page_number}."
                        except Exception as e: error_msg = (error_msg + "; " if error_msg else "") + f"MarkItDown conversion error: {e}"
                    else: error_msg = (error_msg + "; " if error_msg else "") + "pypdf: Failed to isolate page."
            except Exception as e: error_msg = (error_msg + "; " if error_msg else "") + f"pypdf processing error: {e}"
        elif not error_msg and is_pdf_permissible and not original_pdf_bytes: error_msg = (error_msg + "; " if error_msg else "") + "PDF content unavailable."
        
        return YokTezDocumentMarkdown(
            page_markdown_content=page_markdown_content, source_detail_page_url=request.detail_page_url,
            retrieved_pdf_url=HttpUrl(actual_pdf_url_str) if actual_pdf_url_str else None,
            current_pdf_page=request.page_number, total_pdf_pages=total_pdf_pages,
            is_paginated=total_pdf_pages > 1, characters_on_page=characters_on_page,
            error_message=error_msg.strip("; ") if error_msg else None, 
            thesis_title=extracted_thesis_title, thesis_author=extracted_thesis_author
        )