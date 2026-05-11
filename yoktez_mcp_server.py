# yoktez_mcp_server.py
import asyncio
import atexit
import logging
import os
from pydantic import HttpUrl, Field
from typing import Optional

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from fastmcp import FastMCP  # noqa: E402

# Corrected imports: client and models are in the same directory
from client import YokTezApiClient  # noqa: E402
from models import (  # noqa: E402
    YokTezSearchRequest, YokTezSearchResult,
    YokTezDocumentRequest, YokTezDocumentMarkdown,
    YokTezThesisDetailsRequest, YokTezThesisDetails,
    YokTezRecentListRequest, YokTezRecentListMode,
    YokTezThesisTypeEnum, YokTezPermissionStatusEnum, YokTezStatusEnum,
    YokTezLanguageEnum, YokTezSearchFieldEnum, YokTezMatchTypeEnum,
    YokTezOperatorEnum,
)

app = FastMCP(
    name="YokTezMCP",
    instructions="MCP server for YÖK National Thesis Center. Allows detailed searching of theses and retrieving their PDF content as paginated Markdown (page by PDF page)."
)

# Disk cache only if explicitly enabled via env var (disabled by default for read-only containers)
enable_disk_cache = os.environ.get('YOKTEZ_ENABLE_DISK_CACHE', '').lower() == 'true'
yoktez_client_instance = YokTezApiClient(enable_disk_cache=enable_disk_cache)

@app.tool()
async def search_yok_tez_detailed(
    keyword: Optional[str] = Field(
        None,
        description=(
            "Primary search term — what to look for in YÖK theses. "
            "E.g. 'yapay zeka', 'machine learning', 'AHMET YILMAZ'. "
            "Either this or one of the legacy field-specific parameters (thesis_title, "
            "author_name, advisor_name, subject_headings, index_terms, abstract_text) "
            "must be provided."
        ),
    ),
    keyword_2: Optional[str] = Field(
        None,
        description="Second search term (optional). Combined with 'keyword' via 'operator_1'.",
    ),
    keyword_3: Optional[str] = Field(
        None,
        description="Third search term (optional). Combined with 'keyword_2' via 'operator_2'.",
    ),
    operator_1: YokTezOperatorEnum = Field(
        default=YokTezOperatorEnum.AND,
        description="Boolean operator between 'keyword' and 'keyword_2'.",
    ),
    operator_2: YokTezOperatorEnum = Field(
        default=YokTezOperatorEnum.AND,
        description="Boolean operator between 'keyword_2' and 'keyword_3'.",
    ),
    search_field: YokTezSearchFieldEnum = Field(
        default=YokTezSearchFieldEnum.TUMU,
        description=(
            "Which field to search the keyword(s) in. TUMU = all fields (default), "
            "TEZ_ADI = title, YAZAR = author, DANISMAN = advisor, KONU = subject, "
            "ANAHTAR_KELIME = index/keyword terms, OZET = abstract."
        ),
    ),
    match_type: YokTezMatchTypeEnum = Field(
        default=YokTezMatchTypeEnum.ICERSIN,
        description="ICERSIN = keyword appears anywhere (default). TAM_IFADE = exact phrase match.",
    ),
    thesis_title: Optional[str] = Field(
        None,
        description="DEPRECATED legacy alias. If provided, search_field is set to TEZ_ADI and 'keyword' is filled from this.",
    ),
    author_name: Optional[str] = Field(
        None,
        description="DEPRECATED legacy alias. If provided, search_field is set to YAZAR.",
    ),
    advisor_name: Optional[str] = Field(
        None,
        description="DEPRECATED legacy alias. If provided, search_field is set to DANISMAN.",
    ),
    subject_headings: Optional[str] = Field(
        None,
        description="DEPRECATED legacy alias. If provided, search_field is set to KONU.",
    ),
    index_terms: Optional[str] = Field(
        None,
        description="DEPRECATED legacy alias. If provided, search_field is set to ANAHTAR_KELIME.",
    ),
    abstract_text: Optional[str] = Field(
        None,
        description="DEPRECATED legacy alias. If provided, search_field is set to OZET.",
    ),
    thesis_type: YokTezThesisTypeEnum = Field(
        default=YokTezThesisTypeEnum.SECINIZ, description="Filter by thesis type."
    ),
    permission_status: YokTezPermissionStatusEnum = Field(
        default=YokTezPermissionStatusEnum.SECINIZ,
        description="Filter by PDF access permission (İzinli / İzinsiz).",
    ),
    thesis_status: YokTezStatusEnum = Field(
        default=YokTezStatusEnum.ONAYLANDI,
        description="Filter by approval status. Defaults to 'Onaylandı' (approved).",
    ),
    language: YokTezLanguageEnum = Field(
        default=YokTezLanguageEnum.SECINIZ, description="Filter by thesis language."
    ),
    year_start: str = Field(
        default="0",
        description="Start year for the search range (e.g. '2020'). '0' = no lower bound.",
    ),
    year_end: str = Field(
        default="0",
        description="End year for the search range (e.g. '2025'). '0' = no upper bound.",
    ),
    page: int = Field(default=1, ge=1, description="Page number of the search results."),
    results_per_page: int = Field(
        default=10, ge=1, le=50, description="Number of results to display per page."
    ),
) -> YokTezSearchResult:
    """Search the YÖK National Thesis Center.

    YÖK's API was redesigned in 2026: searches are now keyword-based against ONE
    field type at a time (with optional additional keyword slots joined by AND/OR),
    plus a small set of filter dropdowns (type, language, permission, status, years).

    University/institute/department text filters are no longer respected by YÖK and
    have been removed from this tool. The 'thesis_number' parameter has also been
    removed since YÖK no longer supports direct lookup by thesis number through this
    endpoint.

    Provide either:
      - 'keyword' (preferred — combine with 'search_field' if you need to restrict
        the search to a specific field like title or author), or
      - one of the legacy aliases (thesis_title, author_name, advisor_name,
        subject_headings, index_terms, abstract_text) which auto-set 'search_field'.
    """
    search_req = YokTezSearchRequest(
        aranacak_kelime=keyword,
        aranacak_kelime_2=keyword_2,
        aranacak_kelime_3=keyword_3,
        operator_1=operator_1,
        operator_2=operator_2,
        arama_alani=search_field,
        arama_tipi=match_type,
        tez_ad=thesis_title,
        yazar_ad_soyad=author_name,
        danisman_ad_soyad=advisor_name,
        konu_basliklari=subject_headings,
        dizin_terimleri=index_terms,
        ozet_metni=abstract_text,
        tez_turu=thesis_type,
        izin_durumu=permission_status,
        tez_durumu=thesis_status,
        dil=language,
        yil_baslangic=year_start,
        yil_bitis=year_end,
        page=page,
        limit_per_page=results_per_page,
    )
    log_params = search_req.model_dump(exclude_defaults=True, mode="json")
    logger.info(f"Tool 'search_yok_tez_detailed' called with parameters: {log_params}")
    try:
        result = await yoktez_client_instance.search_theses(search_req)
        if not result.theses and not result.error_message:
            result.error_message = "No theses found matching the specified criteria."
        if result.query_used_parameters is None:
            result.query_used_parameters = log_params
        return result
    except Exception as e:
        logger.exception("Error in tool 'search_yok_tez_detailed'.")
        return YokTezSearchResult(
            theses=[],
            current_page=page,
            query_used_parameters=log_params,
            error_message=f"An error occurred while executing the search tool: {e}",
        )

@app.tool()
async def list_recent_yok_tez(
    mode: YokTezRecentListMode = Field(
        default=YokTezRecentListMode.SON_15_GUN,
        description=(
            "Which curated list to fetch. SON_15_GUN: ~2-3K theses uploaded to YÖK in the last 15 days "
            "(useful for monitoring new additions; thesis publication year can vary). "
            "BU_YIL: all theses with the current publication year (e.g. ~100K+ for 2026, "
            "but YÖK caps the visible batch at ~2000)."
        ),
    ),
    page: int = Field(default=1, ge=1, description="Page number of the results."),
    results_per_page: int = Field(
        default=10, ge=1, le=50, description="Maximum number of results per page."
    ),
) -> YokTezSearchResult:
    """List recent YÖK theses without a search keyword.

    Calls YÖK's TezIslemleri endpoint (islem=7 or islem=8) and returns the same
    result shape as search_yok_tez_detailed. This is the ONLY way to enumerate
    recent theses since the regular search endpoint requires a keyword.

    Useful for:
      - Monitoring new theses added to YÖK each week (SON_15_GUN)
      - Browsing the current year's full corpus (BU_YIL)
    """
    req = YokTezRecentListRequest(mode=mode, page=page, limit_per_page=results_per_page)
    log_params = req.model_dump(mode="json")
    logger.info(f"Tool 'list_recent_yok_tez' called with parameters: {log_params}")
    try:
        result = await yoktez_client_instance.list_recent_theses(req)
        if result.query_used_parameters is None:
            result.query_used_parameters = log_params
        return result
    except Exception as exc:
        logger.exception("Error in tool 'list_recent_yok_tez'.")
        return YokTezSearchResult(
            theses=[],
            current_page=page,
            query_used_parameters=log_params,
            error_message=f"Unexpected error: {exc}",
        )


@app.tool()
async def get_yok_tez_thesis_details(
    detail_page_url: Optional[HttpUrl] = Field(
        None,
        description=(
            "Detail page URL from a prior search result (preferred). "
            "The thesis_key and encrypted_no are extracted from its query string."
        ),
    ),
    thesis_key: Optional[str] = Field(
        None,
        description="YÖK kayitNo. Required if 'detail_page_url' is not provided.",
    ),
    encrypted_no: Optional[str] = Field(
        None,
        description="YÖK tezNo. Required if 'detail_page_url' is not provided.",
    ),
) -> YokTezThesisDetails:
    """Fetch rich thesis metadata WITHOUT downloading the PDF.

    Returns:
      - Advisor name
      - Full hierarchical location (University / Institute / Department / Discipline)
      - Turkish abstract (full text)
      - English abstract (full text)
      - Turkish keywords (parsed bilingual pairs)
      - English keywords (parsed bilingual pairs)
      - Citations in APA, IEEE, MLA, Chicago, and Harvard formats

    Much cheaper than get_yok_tez_document_markdown — calls a single JSON endpoint
    instead of downloading the full PDF. Ideal for surveying or citing theses
    without needing their body text.
    """
    try:
        req = YokTezThesisDetailsRequest(
            detail_page_url=detail_page_url,
            thesis_key=thesis_key,
            encrypted_no=encrypted_no,
        )
    except Exception as exc:
        return YokTezThesisDetails(
            source_detail_page_url=detail_page_url,
            error_message=f"Invalid request: {exc}",
        )

    logger.info(
        f"Tool 'get_yok_tez_thesis_details' called for url={detail_page_url} "
        f"thesis_key={thesis_key} encrypted_no={encrypted_no}"
    )
    try:
        return await yoktez_client_instance.get_thesis_details(req)
    except Exception as exc:
        logger.exception("Error in tool 'get_yok_tez_thesis_details'.")
        return YokTezThesisDetails(
            source_detail_page_url=detail_page_url,
            error_message=f"Unexpected error: {exc}",
        )


@app.tool()
async def get_yok_tez_document_markdown(
    detail_page_url: HttpUrl = Field(..., description="The detail page URL of the thesis on YÖK Tez Merkezi. This URL is usually obtained from the 'search_yok_tez_detailed' tool results."),
    page_number: int = Field(default=1, ge=1, description="The PDF page number (1-based) for which to retrieve Markdown content. Default is 1.")
) -> YokTezDocumentMarkdown:
    """
    Retrieves a specific YÖK thesis PDF using its detail page URL.
    It fetches metadata from the detail page, downloads the PDF (if permissible and not cached),
    isolates the specified PDF page, converts that page to Markdown, and returns the content.
    """
    doc_req = YokTezDocumentRequest(
        detail_page_url=detail_page_url,
        page_number=page_number
    )
    logger.info(f"Tool 'get_yok_tez_document_markdown' called for URL: {detail_page_url}, PDF page_number: {page_number}")
    try:
        result = await yoktez_client_instance.get_thesis_pdf_as_markdown(doc_req)
        if result.page_markdown_content is None and result.error_message is None: # Further error refinement
            if not result.total_pdf_pages > 0 and result.is_paginated is False: # No PDF processed
                 result.error_message = "PDF could not be processed or has no pages."
            elif page_number > result.total_pdf_pages:
                 result.error_message = f"Requested page ({page_number}) is greater than total PDF pages ({result.total_pdf_pages})."
            else:
                 result.error_message = f"Could not generate Markdown content for PDF page {page_number} (e.g., page is blank or image-based)."
        return result
    except Exception as e:
        logger.exception("Error in tool 'get_yok_tez_document_markdown'.")
        return YokTezDocumentMarkdown(
            source_detail_page_url=detail_page_url,
            current_pdf_page=page_number,
            total_pdf_pages=0,
            is_paginated=False,
            error_message=f"An error occurred while executing the document retrieval tool: {str(e)}"
        )

# Application Shutdown Handling
def perform_cleanup():
    logger.info("YokTez MCP Server performing cleanup...")
    try:
        # Try to get existing loop or create new one for cleanup
        try:
            loop = asyncio.get_event_loop_policy().get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError: # No current event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def close_yoktez_client_async():
            if yoktez_client_instance and hasattr(yoktez_client_instance, 'close_client_session'):
                logger.info("Scheduling close for YokTezApiClient session...")
                await yoktez_client_instance.close_client_session()
        
        if loop.is_running():
            asyncio.ensure_future(close_yoktez_client_async(), loop=loop)
        else:
            loop.run_until_complete(close_yoktez_client_async())
            
    except Exception as e:
        logger.error(f"Error during atexit cleanup execution for YokTez: {e}", exc_info=True)
    finally:
        logger.info("YokTez MCP Server atexit cleanup process finished.")

atexit.register(perform_cleanup)

def main():
    logger.info(f"Starting {app.name} server...")
    try:
        app.run() # FastMCP's run method
    except KeyboardInterrupt:
        logger.info(f"{app.name} server shut down by user (KeyboardInterrupt).")
    except Exception:  # noqa: BLE001
        logger.exception(f"{app.name} server failed to start or crashed.")
    # perform_cleanup() will be called by atexit, no need to call explicitly here in finally.
    # finally:
    # logger.info(f"{app.name} server has shut down.")


if __name__ == "__main__":
    main()