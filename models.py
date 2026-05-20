# models.py
from pydantic import BaseModel, Field, HttpUrl, model_validator
from typing import List, Optional, Dict, Any
from enum import Enum


class YokTezThesisTypeEnum(str, Enum):
    """Enum for YÖK Thesis Types. Values correspond to form field options."""
    SECINIZ = "0"  # Select / Not Specified
    YUKSEK_LISANS = "1"  # Master's Thesis
    DOKTORA = "2"  # Doctoral Dissertation
    TIPTA_UZMANLIK = "3"  # Specialization in Medicine
    SANATTA_YETERLIK = "4"  # Proficiency in Art
    DIS_HEKIMLIGI_UZMANLIK = "5"  # Specialization in Dentistry
    TIPTA_YAN_DAL_UZMANLIK = "6"  # Subspecialty in Medicine
    ECZACILIKTA_UZMANLIK = "7"  # Specialization in Pharmacy


class YokTezPermissionStatusEnum(str, Enum):
    """Enum for PDF permission status on YÖK Tez."""
    SECINIZ = "0"  # Select / Not Specified
    IZINLI = "1"  # Permitted (Full text accessible)
    IZINSIZ = "2"  # Not Permitted (Full text inaccessible)


class YokTezStatusEnum(str, Enum):
    """Enum for the submission status of the thesis."""
    SECINIZ = "3"  # Default "Select" on site, also implies "Approved" if not specified otherwise.
    ONAYLANDI = "3"  # Approved
    HAZIRLANIYOR = "1"  # In Preparation
    TUMU = "0"  # All (includes both "Approved" and "In Preparation")


class YokTezLanguageEnum(str, Enum):
    """Enum for thesis language."""
    SECINIZ = "0"
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


class YokTezSearchFieldEnum(str, Enum):
    """Which field the keyword(s) should be searched in (form field: nevi)."""
    TUMU = "7"          # All fields (default)
    TEZ_ADI = "1"        # Thesis title
    YAZAR = "2"          # Author
    DANISMAN = "3"       # Advisor
    KONU = "4"           # Subject
    ANAHTAR_KELIME = "5"  # Keyword / index term
    OZET = "6"           # Abstract


class YokTezMatchTypeEnum(str, Enum):
    """How to match the keyword (form field: tip)."""
    TAM_IFADE = "1"     # Exact phrase
    ICERSIN = "2"        # Contains (default)


class YokTezOperatorEnum(str, Enum):
    """Boolean operator between keyword slots (form fields: ops_field, ops_field1)."""
    AND = "and"
    OR = "or"


class YokTezRecentListMode(str, Enum):
    """Which 'recent theses' list to fetch via TezIslemleri."""
    SON_15_GUN = "7"   # Theses added to YÖK in the last 15 days (~2-3K results)
    BU_YIL = "8"        # All theses with current-year date (~100K+ results, server-capped at 2000 visible)


class YokTezSearchRequest(BaseModel):
    """
    Request model for YÖK Thesis search.

    The YÖK Tez Merkezi search API was redesigned in 2026: it now accepts up to 3
    keyword terms (combined with AND/OR operators) restricted to one search field
    at a time, plus a few filter dropdowns.

    Old field-specific parameters (tez_ad, yazar_ad_soyad, danisman_ad_soyad,
    konu_basliklari, dizin_terimleri, ozet_metni) are still accepted for backwards
    compatibility. When supplied, they are automatically converted into the new
    keyword/field format. If multiple are provided, the first non-empty one in the
    priority order above is used and the rest are ignored.

    Parameters that YÖK no longer supports have been removed:
    universite_ad, enstitu_ad, anabilim_dal_ad, bilim_dal_ad, enstitu_grubu, tez_no.
    """

    # --- New keyword-based search (preferred) ---
    aranacak_kelime: Optional[str] = Field(
        None,
        description="Main search term. The most common way to search — e.g. 'yapay zeka', 'machine learning', 'AHMET YILMAZ'.",
    )
    aranacak_kelime_2: Optional[str] = Field(
        None,
        description="Second search term (optional). Combined with the first term via 'operator_1'.",
    )
    aranacak_kelime_3: Optional[str] = Field(
        None,
        description="Third search term (optional). Combined with the second term via 'operator_2'.",
    )
    operator_1: YokTezOperatorEnum = Field(
        default=YokTezOperatorEnum.AND,
        description="Boolean operator between 'aranacak_kelime' and 'aranacak_kelime_2' (and/or).",
    )
    operator_2: YokTezOperatorEnum = Field(
        default=YokTezOperatorEnum.AND,
        description="Boolean operator between 'aranacak_kelime_2' and 'aranacak_kelime_3' (and/or).",
    )
    arama_alani: YokTezSearchFieldEnum = Field(
        default=YokTezSearchFieldEnum.TUMU,
        description="Which field to search the keyword(s) in. Defaults to 'TUMU' (all fields).",
    )
    arama_tipi: YokTezMatchTypeEnum = Field(
        default=YokTezMatchTypeEnum.ICERSIN,
        description="Match type. 'ICERSIN' (default) = keyword appears anywhere; 'TAM_IFADE' = exact phrase match.",
    )

    # --- Backwards-compatible aliases (deprecated) ---
    tez_ad: Optional[str] = Field(
        None,
        description="DEPRECATED. Alias for searching the thesis title — sets arama_alani=TEZ_ADI.",
    )
    yazar_ad_soyad: Optional[str] = Field(
        None,
        description="DEPRECATED. Alias for searching by author name — sets arama_alani=YAZAR.",
    )
    danisman_ad_soyad: Optional[str] = Field(
        None,
        description="DEPRECATED. Alias for searching by advisor name — sets arama_alani=DANISMAN.",
    )
    konu_basliklari: Optional[str] = Field(
        None,
        description="DEPRECATED. Alias for searching by subject headings — sets arama_alani=KONU.",
    )
    dizin_terimleri: Optional[str] = Field(
        None,
        description="DEPRECATED. Alias for searching by index/keyword terms — sets arama_alani=ANAHTAR_KELIME.",
    )
    ozet_metni: Optional[str] = Field(
        None,
        description="DEPRECATED. Alias for searching within the abstract — sets arama_alani=OZET.",
    )

    # --- Filters that still work in the new API ---
    tez_turu: YokTezThesisTypeEnum = Field(
        default=YokTezThesisTypeEnum.SECINIZ,
        description="Filter by thesis type (Yüksek Lisans, Doktora, etc.).",
    )
    izin_durumu: YokTezPermissionStatusEnum = Field(
        default=YokTezPermissionStatusEnum.SECINIZ,
        description="Filter by PDF access permission (İzinli / İzinsiz).",
    )
    tez_durumu: YokTezStatusEnum = Field(
        default=YokTezStatusEnum.ONAYLANDI,
        description="Filter by approval status. Defaults to 'Onaylandı' (approved).",
    )
    dil: YokTezLanguageEnum = Field(
        default=YokTezLanguageEnum.SECINIZ,
        description="Filter by thesis language.",
    )
    yil_baslangic: str = Field(
        default="0",
        description="Start year for the search range (e.g. '2020'). '0' means no lower bound.",
    )
    yil_bitis: str = Field(
        default="0",
        description="End year for the search range (e.g. '2025'). '0' means no upper bound.",
    )

    # --- Pagination (client-side; YÖK returns up to ~2000 results per query) ---
    page: int = Field(default=1, ge=1, description="Page number of the search results.")
    limit_per_page: int = Field(
        default=10, ge=1, le=50, description="Maximum number of results to display per page."
    )

    @model_validator(mode="after")
    def _apply_deprecated_aliases(self) -> "YokTezSearchRequest":
        """If old field-specific parameters are used, map them onto the new keyword/field model.

        Priority order (highest first): tez_ad, yazar_ad_soyad, danisman_ad_soyad,
        konu_basliklari, dizin_terimleri, ozet_metni.
        Only applied when 'aranacak_kelime' is not already set, so callers using the
        new API are never overridden.
        """
        if self.aranacak_kelime:
            return self

        alias_map = [
            ("tez_ad", YokTezSearchFieldEnum.TEZ_ADI),
            ("yazar_ad_soyad", YokTezSearchFieldEnum.YAZAR),
            ("danisman_ad_soyad", YokTezSearchFieldEnum.DANISMAN),
            ("konu_basliklari", YokTezSearchFieldEnum.KONU),
            ("dizin_terimleri", YokTezSearchFieldEnum.ANAHTAR_KELIME),
            ("ozet_metni", YokTezSearchFieldEnum.OZET),
        ]
        for attr_name, field_enum in alias_map:
            value = getattr(self, attr_name, None)
            if value:
                self.aranacak_kelime = value
                self.arama_alani = field_enum
                break
        return self


class YokTezCompactThesisDetail(BaseModel):
    """Compact thesis details returned in search results."""
    thesis_no: Optional[str] = Field(None, description="Thesis number (e.g. '1003627').")
    title: Optional[str] = Field(None, description="Thesis title in original language.")
    title_translated: Optional[str] = Field(
        None, description="Translated thesis title (typically English when original is Turkish, or vice versa)."
    )
    author: Optional[str] = Field(None, description="Author of the thesis.")
    year: Optional[str] = Field(None, description="Year of the thesis.")
    university_info: Optional[str] = Field(
        None, description="University and institute information."
    )
    thesis_type: Optional[str] = Field(
        None, description="Type of thesis (e.g. 'Yüksek Lisans', 'Doktora')."
    )
    language: Optional[str] = Field(None, description="Thesis language (e.g. 'Türkçe').")
    subject: Optional[str] = Field(None, description="Subject area(s) of the thesis.")
    thesis_key: Optional[str] = Field(
        None, description="YÖK internal kayitNo, used as the 'id' parameter in detail/PDF URLs."
    )
    encrypted_no: Optional[str] = Field(
        None, description="YÖK internal tezNo, used as the 'no' parameter in detail/PDF URLs."
    )
    detail_page_url: Optional[HttpUrl] = Field(
        None, description="URL to the thesis detail page on YÖK Tez Merkezi."
    )


class YokTezSearchResult(BaseModel):
    """Model for YÖK Thesis search results."""
    theses: List[YokTezCompactThesisDetail] = Field(
        default_factory=list, description="List of found theses summaries."
    )
    total_results_found: Optional[int] = Field(
        None, description="Total number of results found as reported by YÖK."
    )
    results_in_batch: Optional[int] = Field(
        None,
        description=(
            "Number of results actually returned in the current HTML batch. "
            "YÖK caps this at ~2000 even when total_results_found is larger."
        ),
    )
    current_page: int = Field(description="The current page number of the search results.")
    total_pages: Optional[int] = Field(
        None,
        description="Total number of pages available based on results_in_batch and limit_per_page.",
    )
    query_used_parameters: Optional[Dict[str, Any]] = Field(
        None, description="The parameters used for this search."
    )
    error_message: Optional[str] = Field(
        None, description="Error message if the search failed or no results were found."
    )


class YokTezDocumentRequest(BaseModel):
    """Request model to retrieve the Markdown content of a specific YÖK Thesis document."""
    detail_page_url: HttpUrl = Field(
        ...,
        description="The detail page URL of the thesis on YÖK Tez Merkezi (from search results).",
    )
    page_number: int = Field(
        default=1, ge=1, description="The PDF page number (1-based) to retrieve. Default is 1."
    )


class YokTezDocumentMarkdown(BaseModel):
    """Model for the Markdown content extracted from a YÖK Thesis PDF page."""
    page_markdown_content: Optional[str] = Field(
        None,
        description="Markdown content of the requested PDF page. Null if extraction failed.",
    )
    source_detail_page_url: HttpUrl = Field(
        description="The source YÖK Tez detail page URL the PDF was processed from."
    )
    retrieved_pdf_url: Optional[HttpUrl] = Field(
        None, description="The actual URL the PDF was downloaded from."
    )
    current_pdf_page: int = Field(description="The PDF page number returned.")
    total_pdf_pages: int = Field(description="Total number of pages in the original PDF.")
    is_paginated: bool = Field(description="True if the PDF has more than one page.")
    characters_on_page: Optional[int] = Field(
        None, description="Number of characters in the page's Markdown content."
    )
    error_message: Optional[str] = Field(
        None, description="Error message if document retrieval or processing failed."
    )
    thesis_title: Optional[str] = Field(
        None, description="Title of the thesis (Turkish), extracted from the detail page."
    )
    thesis_author: Optional[str] = Field(
        None, description="Author of the thesis, extracted from the detail page."
    )


class YokTezRecentListRequest(BaseModel):
    """Request for the 'recently added theses' lists exposed by TezIslemleri."""
    mode: YokTezRecentListMode = Field(
        default=YokTezRecentListMode.SON_15_GUN,
        description=(
            "Which recent-list to fetch. SON_15_GUN: ~2-3K theses uploaded to YÖK in the last 15 days "
            "(thesis publication year may still be older). BU_YIL: all theses published this year "
            "(YÖK caps the visible batch at ~2000 even when the total is larger)."
        ),
    )
    page: int = Field(default=1, ge=1, description="Page number of the results.")
    limit_per_page: int = Field(
        default=10, ge=1, le=50, description="Maximum number of results per page."
    )


class YokTezAnabilimDali(BaseModel):
    """A single 'Anabilim Dalı' (academic department/discipline) option on YÖK.

    These come from YÖK's advanced-search department list. The 'code' is YÖK's
    internal numeric id used to filter searches; the 'name' is the full Turkish
    department title (e.g. 'KAMU HUKUKU ANABİLİM DALI').
    """
    code: str = Field(description="YÖK internal department code, used as the ABD filter value.")
    name: str = Field(description="Full department name (Turkish), e.g. 'KAMU HUKUKU ANABİLİM DALI'.")


class YokTezAnabilimDaliListResult(BaseModel):
    """Result of searching YÖK's department (anabilim dalı) list by keyword."""
    matches: List[YokTezAnabilimDali] = Field(
        default_factory=list,
        description="Departments whose name contains the keyword (name + code pairs).",
    )
    total_matches: int = Field(
        0, description="Total number of departments matching the keyword."
    )
    returned: int = Field(
        0, description="Number of matches actually returned (may be capped by max_results)."
    )
    keyword: Optional[str] = Field(
        None, description="The keyword that was matched against department names."
    )
    error_message: Optional[str] = Field(
        None, description="Error message if the list could not be fetched or no match was found."
    )


class YokTezAnabilimDaliSearchRequest(BaseModel):
    """Request for YÖK's advanced (islem=2) search filtered by one or more departments.

    Unlike the keyword search, this path filters by 'Anabilim Dalı' (department) and
    does NOT support a free full-text/abstract keyword. It DOES support filtering by
    thesis title, author, advisor and index terms, plus the usual dropdown filters.
    When multiple department codes are given, each is searched and the results merged
    (deduplicated by thesis).
    """
    anabilim_dali_kodlari: List[str] = Field(
        ...,
        min_length=1,
        description="One or more YÖK department codes (from list_yok_tez_anabilim_dali). Each is searched and results merged.",
    )
    tez_adi: Optional[str] = Field(None, description="Optional: filter by words in the thesis title.")
    yazar: Optional[str] = Field(None, description="Optional: filter by author name.")
    danisman: Optional[str] = Field(None, description="Optional: filter by advisor name.")
    dizin_terimleri: Optional[str] = Field(None, description="Optional: filter by index/keyword terms.")
    tez_turu: YokTezThesisTypeEnum = Field(
        default=YokTezThesisTypeEnum.SECINIZ, description="Filter by thesis type."
    )
    izin_durumu: YokTezPermissionStatusEnum = Field(
        default=YokTezPermissionStatusEnum.SECINIZ,
        description="Filter by PDF access permission (İzinli / İzinsiz).",
    )
    tez_durumu: YokTezStatusEnum = Field(
        default=YokTezStatusEnum.ONAYLANDI,
        description="Filter by approval status. Defaults to 'Onaylandı' (approved).",
    )
    dil: YokTezLanguageEnum = Field(
        default=YokTezLanguageEnum.SECINIZ, description="Filter by thesis language."
    )
    yil_baslangic: str = Field(
        default="0", description="Start year (e.g. '2020'). '0' = no lower bound."
    )
    yil_bitis: str = Field(
        default="0", description="End year (e.g. '2025'). '0' = no upper bound."
    )
    page: int = Field(default=1, ge=1, description="Page number of the merged results.")
    limit_per_page: int = Field(
        default=10, ge=1, le=50, description="Maximum number of results per page."
    )


class YokTezKeywordPair(BaseModel):
    """A bilingual keyword pair as returned by YÖK ('TR = EN' format)."""
    tr: Optional[str] = Field(None, description="Turkish keyword/term.")
    en: Optional[str] = Field(None, description="English translation of the keyword/term.")


class YokTezThesisDetailsRequest(BaseModel):
    """Request to fetch rich thesis metadata (advisor, abstracts, keywords, citations).

    Either supply the detail_page_url from a prior search result, or both
    'thesis_key' and 'encrypted_no' (the raw IDs from search results) directly.
    """
    detail_page_url: Optional[HttpUrl] = Field(
        None,
        description="Detail page URL from a search result (preferred). The IDs are extracted from it.",
    )
    thesis_key: Optional[str] = Field(
        None,
        description="YÖK kayitNo. Required if 'detail_page_url' is not provided.",
    )
    encrypted_no: Optional[str] = Field(
        None,
        description="YÖK tezNo. Required if 'detail_page_url' is not provided.",
    )

    @model_validator(mode="after")
    def _require_ids(self) -> "YokTezThesisDetailsRequest":
        if self.detail_page_url is None and not (self.thesis_key and self.encrypted_no):
            raise ValueError(
                "Either 'detail_page_url' or both 'thesis_key' and 'encrypted_no' are required."
            )
        return self


class YokTezThesisDetails(BaseModel):
    """Rich thesis metadata fetched directly from YÖK's tezBilgiDetay.jsp endpoint.

    Returned without downloading the PDF — ideal for inspecting a thesis cheaply.
    """
    advisor: Optional[str] = Field(
        None, description="Thesis advisor (e.g. 'PROF. DR. AYŞE YILMAZ')."
    )
    location_full: Optional[str] = Field(
        None,
        description="Full hierarchical location: University / Institute / Department / Discipline.",
    )
    abstract_tr: Optional[str] = Field(None, description="Turkish abstract (full text).")
    abstract_en: Optional[str] = Field(None, description="English abstract (full text).")
    keywords_tr: List[YokTezKeywordPair] = Field(
        default_factory=list,
        description="Turkish keywords with their English glosses, as parsed pairs.",
    )
    keywords_en: List[YokTezKeywordPair] = Field(
        default_factory=list,
        description="English keywords with their Turkish glosses, as parsed pairs.",
    )
    citation_apa: Optional[str] = Field(None, description="APA-style citation string (HTML).")
    citation_ieee: Optional[str] = Field(None, description="IEEE-style citation string.")
    citation_mla: Optional[str] = Field(None, description="MLA-style citation string (HTML).")
    citation_chicago: Optional[str] = Field(None, description="Chicago-style citation string.")
    citation_harvard: Optional[str] = Field(
        None, description="Harvard-style citation string (HTML)."
    )
    source_detail_page_url: Optional[HttpUrl] = Field(
        None, description="The detail page URL these details were fetched for."
    )
    error_message: Optional[str] = Field(
        None, description="Error message if fetching or parsing failed."
    )


class InternalThesisDetail(BaseModel):
    """Internal model for comprehensive thesis details parsed from the detail page."""
    thesis_no: Optional[str] = None
    pdf_url: Optional[str] = None
    title: Optional[str] = None
    title_en: Optional[str] = None
    author: Optional[str] = None
    advisor: Optional[str] = None
    university_info: Optional[str] = None
    subject: Optional[str] = None
    status: Optional[str] = None
    thesis_type: Optional[str] = None
    language: Optional[str] = None
    year: Optional[str] = None
    pages: Optional[str] = None
    abstract_tr: Optional[str] = None
    abstract_en: Optional[str] = None
    detail_page_url: Optional[HttpUrl] = None
    thesis_key: Optional[str] = None
