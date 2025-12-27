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
    YokTezThesisTypeEnum, YokTezPermissionStatusEnum, YokTezStatusEnum,
    YokTezLanguageEnum, YokTezInstituteGroupEnum
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
    thesis_title: Optional[str] = Field(None, description="Thesis title to search for. E.g., 'artificial intelligence', 'climate change impacts'."),
    author_name: Optional[str] = Field(None, description="Author's name and surname. YÖK system might be case-sensitive; typically uppercase. E.g., 'AYŞE YILMAZ'."),
    advisor_name: Optional[str] = Field(None, description="Advisor's name and surname. Typically uppercase. E.g., 'MEHMET ÖZTÜRK'."),
    university_name: Optional[str] = Field(None, description="University name to filter by. E.g., 'İstanbul Üniversitesi'."),
    institute_name: Optional[str] = Field(None, description="Institute name to filter by. E.g., 'Sosyal Bilimler Enstitüsü'."),
    department_name: Optional[str] = Field(None, description="Main discipline/department name. E.g., 'İşletme'."),
    discipline_name: Optional[str] = Field(None, description="Specific discipline name. E.g., 'Pazarlama'."),
    thesis_number: Optional[str] = Field(None, description="Specific thesis number."),
    subject_headings: Optional[str] = Field(None, description="Subject headings or keywords."),
    index_terms: Optional[str] = Field(None, description="Index terms."),
    abstract_text: Optional[str] = Field(None, description="Text to search within the thesis abstract."),
    thesis_type: Optional[YokTezThesisTypeEnum] = Field(default=YokTezThesisTypeEnum.SECINIZ, description="Type of thesis."),
    permission_status: Optional[YokTezPermissionStatusEnum] = Field(default=YokTezPermissionStatusEnum.SECINIZ, description="PDF access permission status."),
    thesis_status: Optional[YokTezStatusEnum] = Field(default=YokTezStatusEnum.ONAYLANDI, description="Approval status of the thesis."),
    language: Optional[YokTezLanguageEnum] = Field(default=YokTezLanguageEnum.SECINIZ, description="Language of the thesis."),
    institute_group: Optional[YokTezInstituteGroupEnum] = Field(default=YokTezInstituteGroupEnum.SECINIZ, description="Group of the institute."),
    year_start: Optional[str] = Field(default="0", description="Start year for the search range (e.g., '2010'). '0' means not selected."),
    year_end: Optional[str] = Field(default="0", description="End year for the search range (e.g., '2023'). '0' means not selected."),
    page: int = Field(default=1, ge=1, description="Page number of the search results."),
    results_per_page: int = Field(default=10, ge=1, le=20, description="Number of results to display per page.")
) -> YokTezSearchResult:
    """
    Performs a detailed search on YÖK National Thesis Center using various criteria.
    Returns a paginated list of thesis summaries.
    Note on University/Institute/Discipline fields: The YÖK website uses popups to select IDs for these.
    This tool accepts text for these fields. YÖK's backend might perform a text-based search or use defaults if exact matches for IDs aren't found via text.
    """
    search_req = YokTezSearchRequest(
        tez_ad=thesis_title, yazar_ad_soyad=author_name, danisman_ad_soyad=advisor_name,
        universite_ad=university_name, enstitu_ad=institute_name, anabilim_dal_ad=department_name, bilim_dal_ad=discipline_name,
        tez_no=thesis_number, konu_basliklari=subject_headings, dizin_terimleri=index_terms, ozet_metni=abstract_text,
        tez_turu=thesis_type, izin_durumu=permission_status, tez_durumu=thesis_status, dil=language, enstitu_grubu=institute_group,
        yil_baslangic=year_start, yil_bitis=year_end,
        page=page, limit_per_page=results_per_page
    )
    log_params = search_req.model_dump(exclude_defaults=True)
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
            error_message=f"An error occurred while executing the detailed search tool: {str(e)}"
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