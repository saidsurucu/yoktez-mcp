# yoktez_mcp_server.py
import asyncio
import atexit
import logging
import os
from pydantic import HttpUrl, Field
from typing import Optional, Dict, List, Any
import urllib.parse

# Logging Configuration
LOG_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
if not os.path.exists(LOG_DIRECTORY):
    os.makedirs(LOG_DIRECTORY)
LOG_FILE_PATH = os.path.join(LOG_DIRECTORY, "yoktez_mcp_server.log")
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(threadName)s - %(message)s')
file_handler = logging.FileHandler(LOG_FILE_PATH, mode='a', encoding='utf-8')
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)
root_logger.addHandler(console_handler)
logger = logging.getLogger(__name__)
# --- Logging Configuration End ---

from fastmcp import FastMCP # Assuming this library is available

# Corrected imports: client and models are in the same directory
from client import YokTezApiClient
from models import (
    YokTezSearchRequest, YokTezSearchResult,
    YokTezDocumentRequest, YokTezDocumentMarkdown,
    YokTezThesisTypeEnum, YokTezPermissionStatusEnum, YokTezStatusEnum,
    YokTezLanguageEnum, YokTezInstituteGroupEnum
)

app = FastMCP(
    name="YokTezMCP",
    instructions="MCP server for YÖK National Thesis Center. Allows detailed searching of theses and retrieving their PDF content as paginated Markdown (page by PDF page).",
    dependencies=["httpx", "beautifulsoup4", "playwright", "pypdf", "markitdown", "pydantic"]
)

yoktez_client_instance = YokTezApiClient(playwright_headless=True)

@app.tool()
async def search_yok_tez_detailed(
    tez_ad: Optional[str] = Field(None, description="Thesis title to search for. E.g., 'artificial intelligence', 'climate change impacts'."),
    yazar_ad_soyad: Optional[str] = Field(None, description="Author's name and surname. YÖK system might be case-sensitive; typically uppercase. E.g., 'AYŞE YILMAZ'."),
    danisman_ad_soyad: Optional[str] = Field(None, description="Advisor's name and surname. Typically uppercase. E.g., 'MEHMET ÖZTÜRK'."),
    universite_ad: Optional[str] = Field(None, description="University name to filter by. E.g., 'İstanbul Üniversitesi'."),
    enstitu_ad: Optional[str] = Field(None, description="Institute name to filter by. E.g., 'Sosyal Bilimler Enstitüsü'."),
    anabilim_dal_ad: Optional[str] = Field(None, description="Main discipline name. E.g., 'İşletme'."),
    bilim_dal_ad: Optional[str] = Field(None, description="Specific discipline name. E.g., 'Pazarlama'."),
    tez_no: Optional[str] = Field(None, description="Specific thesis number."),
    konu_basliklari: Optional[str] = Field(None, description="Subject headings or keywords."),
    dizin_terimleri: Optional[str] = Field(None, description="Index terms."),
    ozet_metni: Optional[str] = Field(None, description="Text to search within the thesis abstract."),
    tez_turu: Optional[YokTezThesisTypeEnum] = Field(default=YokTezThesisTypeEnum.SECINIZ, description="Type of thesis."),
    izin_durumu: Optional[YokTezPermissionStatusEnum] = Field(default=YokTezPermissionStatusEnum.SECINIZ, description="PDF access permission status."),
    tez_durumu: Optional[YokTezStatusEnum] = Field(default=YokTezStatusEnum.ONAYLANDI, description="Approval status of the thesis."),
    dil: Optional[YokTezLanguageEnum] = Field(default=YokTezLanguageEnum.SECINIZ, description="Language of the thesis."),
    enstitu_grubu: Optional[YokTezInstituteGroupEnum] = Field(default=YokTezInstituteGroupEnum.SECINIZ, description="Group of the institute."),
    yil_baslangic: Optional[str] = Field(default="0", description="Start year for the search range (e.g., '2010'). '0' means not selected."),
    yil_bitis: Optional[str] = Field(default="0", description="End year for the search range (e.g., '2023'). '0' means not selected."),
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
        tez_ad=tez_ad, yazar_ad_soyad=yazar_ad_soyad, danisman_ad_soyad=danisman_ad_soyad,
        universite_ad=universite_ad, enstitu_ad=enstitu_ad, anabilim_dal_ad=anabilim_dal_ad, bilim_dal_ad=bilim_dal_ad,
        tez_no=tez_no, konu_basliklari=konu_basliklari, dizin_terimleri=dizin_terimleri, ozet_metni=ozet_metni,
        tez_turu=tez_turu, izin_durumu=izin_durumu, tez_durumu=tez_durumu, dil=dil, enstitu_grubu=enstitu_grubu,
        yil_baslangic=yil_baslangic, yil_bitis=yil_bitis,
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
    logger.info(f"Starting {app.name} server via main() function...")
    logger.info(f"Logs will be written to: {LOG_FILE_PATH}")
    try:
        app.run() # FastMCP's run method
    except KeyboardInterrupt:
        logger.info(f"{app.name} server shut down by user (KeyboardInterrupt).")
    except Exception as e:
        logger.exception(f"{app.name} server failed to start or crashed.")
    # perform_cleanup() will be called by atexit, no need to call explicitly here in finally.
    # finally:
    # logger.info(f"{app.name} server has shut down.")


if __name__ == "__main__":
    main()