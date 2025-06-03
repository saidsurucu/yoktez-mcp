# models.py
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any
from enum import Enum

class YokTezThesisTypeEnum(str, Enum):
    """Enum for YÖK Thesis Types. Values correspond to form field options."""
    SECINIZ = "0" # Select / Not Specified
    YUKSEK_LISANS = "1" # Master's Thesis
    DOKTORA = "2" # Doctoral Dissertation
    TIPTA_UZMANLIK = "3" # Specialization in Medicine
    SANATTA_YETERLIK = "4" # Proficiency in Art
    DIS_HEKIMLIGI_UZMANLIK = "5" # Specialization in Dentistry
    TIPTA_YAN_DAL_UZMANLIK = "6" # Subspecialty in Medicine
    ECZACILIKTA_UZMANLIK = "7" # Specialization in Pharmacy

class YokTezPermissionStatusEnum(str, Enum):
    """Enum for PDF permission status on YÖK Tez."""
    SECINIZ = "0" # Select / Not Specified
    IZINLI = "1"  # Permitted (Full text accessible)
    IZINSIZ = "2" # Not Permitted (Full text inaccessible)

class YokTezStatusEnum(str, Enum):
    """Enum for the submission status of the thesis."""
    SECINIZ = "3" # Default "Select" on site, also implies "Approved" if not specified otherwise.
    ONAYLANDI = "3" # Approved
    HAZIRLANIYOR = "1" # In Preparation
    TUMU = "0" # All (includes both "Approved" and "In Preparation")

class YokTezLanguageEnum(str, Enum):
    """Enum for thesis language."""
    SECINIZ = "0" # Select / Not Specified
    TURKCE = "1"
    INGILIZCE = "2"
    ARAPCA = "3"
    ALMANCA = "4"
    FRANSIZCA = "5"
    ISPANYOLCA = "6"
    ITALYANCA = "7"
    RUSCA = "8"
    KURTCE = "11"
    AZERICE = "12"
    # Other languages can be added if needed, based on YÖK's form options.

class YokTezInstituteGroupEnum(str, Enum):
    """Enum for institute groups (e.g., Science, Social Sciences)."""
    SECINIZ = "" # Empty value for "Select" in the form
    FEN_BILIMLERI = "F" # Science
    SOSYAL_BILIMLERI = "S" # Social Sciences
    TIP_VE_SAGLIK_BILIMLERI = "T" # Medical and Health Sciences


class YokTezSearchRequest(BaseModel):
    """
    Request model for YÖK Thesis 'Detailed Search' (Detaylı Tarama).
    Corresponds to the fields in the 'GForm' on YÖK's tarama.jsp.
    """
    tez_ad: Optional[str] = Field(None, description="Thesis title to search for (Form field name: TezAd).")
    yazar_ad_soyad: Optional[str] = Field(None, description="Author's name and surname (Form field name: AdSoyad). YÖK's form may convert this to uppercase. For best results, consider providing in uppercase. E.g., 'AHMET YILMAZ'.")
    danisman_ad_soyad: Optional[str] = Field(None, description="Advisor's name and surname (Form field name: DanismanAdSoyad). YÖK's form may convert this to uppercase. For best results, consider providing in uppercase. E.g., 'MEHMET ÖZTÜRK'.")
    
    universite_ad: Optional[str] = Field(None, description="University name to filter by (Form field name: uniad). YÖK's system may require an exact or very close match (often ALL CAPS, as seen in YÖK's selection popups) for text-based searches if the corresponding ID is not used. E.g., 'ANKARA ÜNİVERSİTESİ'.")
    enstitu_ad: Optional[str] = Field(None, description="Institute name to filter by (Form field name: ensad). Similar to university name, an exact or very close match (often ALL CAPS) might be required by YÖK for text-based searches. E.g., 'SOSYAL BİLİMLER ENSTİTÜSÜ'.")
    anabilim_dal_ad: Optional[str] = Field(None, description="Main discipline name (Form field name: abdad). Text input; search precision depends on YÖK's backend text matching if its ID is not used.")
    bilim_dal_ad: Optional[str] = Field(None, description="Specific discipline name (Form field name: bilim). Text input; search precision depends on YÖK's backend text matching if its ID is not used.")
    
    tez_no: Optional[str] = Field(None, description="Specific thesis number (Form field name: TezNo).")
    konu_basliklari: Optional[str] = Field(None, description="Subject headings or keywords (Form field name: Konu).")
    dizin_terimleri: Optional[str] = Field(None, description="Index terms (Form field name: Dizin).")
    ozet_metni: Optional[str] = Field(None, description="Text to search within the thesis abstract (Form field name: Metin).")

    tez_turu: Optional[YokTezThesisTypeEnum] = Field(default=YokTezThesisTypeEnum.SECINIZ, description="Type of thesis (Form field name: Tur).")
    izin_durumu: Optional[YokTezPermissionStatusEnum] = Field(default=YokTezPermissionStatusEnum.SECINIZ, description="PDF access permission status (Form field name: izin).")
    tez_durumu: Optional[YokTezStatusEnum] = Field(default=YokTezStatusEnum.ONAYLANDI, description="Approval status of the thesis (Form field name: Durum). Defaults to 'Approved'.")
    dil: Optional[YokTezLanguageEnum] = Field(default=YokTezLanguageEnum.SECINIZ, description="Language of the thesis (Form field name: Dil).")
    enstitu_grubu: Optional[YokTezInstituteGroupEnum] = Field(default=YokTezInstituteGroupEnum.SECINIZ, description="Group of the institute (Form field name: EnstituGrubu).")
    
    yil_baslangic: Optional[str] = Field(default="0", description="Start year for the search range (Form field name: yil1). '0' means not selected.")
    yil_bitis: Optional[str] = Field(default="0", description="End year for the search range (Form field name: yil2). '0' means not selected.")

    page: int = Field(default=1, ge=1, description="Page number of the search results.")
    limit_per_page: int = Field(default=10, ge=1, le=20, description="Maximum number of results to display per page.")


class YokTezCompactThesisDetail(BaseModel):
    """Compact thesis details returned in search results, primarily parsed from JavaScript."""
    thesis_no: Optional[str] = Field(None, description="Thesis number.")
    title: Optional[str] = Field(None, description="Thesis title (can be bilingual, e.g., 'TR Title / EN Title').")
    author: Optional[str] = Field(None, description="Author of the thesis.")
    year: Optional[str] = Field(None, description="Year of the thesis.")
    university_info: Optional[str] = Field(None, description="University and institute information as a single string, parsed from JS.")
    thesis_type: Optional[str] = Field(None, description="Type of thesis (e.g., Master's, PhD), parsed from JS.")
    subject: Optional[str] = Field(None, description="Subject(s) of the thesis, often ;-separated, parsed from JS.")
    thesis_key: Optional[str] = Field(None, description="Internal YÖK key for the thesis, used to construct detail_page_url.")
    detail_page_url: Optional[HttpUrl] = Field(None, description="URL to the thesis detail page on YÖK Tez Merkezi.")

class YokTezSearchResult(BaseModel):
    """Model for YÖK Thesis search results."""
    theses: List[YokTezCompactThesisDetail] = Field(default_factory=list, description="List of found theses summaries.")
    total_results_found: Optional[int] = Field(None, description="Total number of results found as reported by YÖK or parsed from the page.")
    current_page: int = Field(description="The current page number of the search results.")
    total_pages: Optional[int] = Field(None, description="Total number of pages available for the query based on total_results_found and limit_per_page.")
    query_used_parameters: Optional[Dict[str, Any]] = Field(None, description="A dictionary of parameters used for this search.")
    error_message: Optional[str] = Field(None, description="Error message if the search failed or no results were found.")

class YokTezDocumentRequest(BaseModel):
    """Request model to retrieve the Markdown content of a specific YÖK Thesis document."""
    detail_page_url: HttpUrl = Field(..., description="The detail page URL of the thesis on YÖK Tez Merkezi. Usually obtained from 'search_yok_tez_detailed' tool results.")
    page_number: int = Field(default=1, ge=1, description="The PDF page number (1-based) for which to retrieve Markdown content. Default is 1.")

class YokTezDocumentMarkdown(BaseModel):
    """Model for the Markdown content extracted from a YÖK Thesis PDF page."""
    page_markdown_content: Optional[str] = Field(None, description="Markdown content of the requested PDF page. Null if the page is image-based or content extraction failed.")
    source_detail_page_url: HttpUrl = Field(description="The source YÖK Tez detail page URL from which the PDF was processed.")
    retrieved_pdf_url: Optional[HttpUrl] = Field(None, description="The actual URL from which the PDF was downloaded, if successful and permissible.")
    current_pdf_page: int = Field(description="The PDF page number for which the content was retrieved.")
    total_pdf_pages: int = Field(description="Total number of pages in the original PDF document.")
    is_paginated: bool = Field(description="True if the original PDF document has more than one page.")
    characters_on_page: Optional[int] = Field(None, description="Number of characters in the retrieved Markdown content for the current page.")
    error_message: Optional[str] = Field(None, description="Error message if document retrieval or processing failed (e.g., PDF not permissible, page out of range).")
    thesis_title: Optional[str] = Field(None, description="Title of the thesis, extracted from the detail page (usually Turkish part).")
    thesis_author: Optional[str] = Field(None, description="Author of the thesis, extracted from the detail page.")

class InternalThesisDetail(BaseModel):
    """Internal model for more comprehensive thesis details, used by the client when parsing detail pages."""
    thesis_no: Optional[str] = None
    pdf_url: Optional[str] = None # Direct PDF link if available from detail page
    title: Optional[str] = None # Turkish title from detail page
    title_en: Optional[str] = None # English title from detail page
    author: Optional[str] = None
    advisor: Optional[str] = None
    university_info: Optional[str] = None # Full location info from detail page
    subject: Optional[str] = None # Subject from detail page
    status: Optional[str] = None # Approval status from detail page
    thesis_type: Optional[str] = None # Thesis type from detail page
    language: Optional[str] = None # Language from detail page
    year: Optional[str] = None # Year from detail page
    pages: Optional[str] = None # Page count from detail page
    abstract_tr: Optional[str] = None # Turkish abstract from detail page
    abstract_en: Optional[str] = None # English abstract from detail page
    detail_page_url: Optional[HttpUrl] = None
    thesis_key: Optional[str] = None