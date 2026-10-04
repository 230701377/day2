"""
Azure Document Intelligence Service.

Extracts text, layout structure, headings, page numbers, key-value pairs,
and tables from contracts using Azure Document Intelligence (Form Recognizer).
Includes clean local fallback for offline/demo operation.
"""
import io
import json
import logging
from typing import List, Tuple, Dict, Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class AzureDocumentIntelligenceService:
    """
    Integrates with Azure AI Document Intelligence API (Layout Model).
    Parse PDFs and DOCX files to extract structured paragraph text, page numbers,
    layout signals, tables, and clause heading candidates.
    """

    def __init__(self):
        self.endpoint = settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT.rstrip("/")
        self.api_key = settings.AZURE_DOCUMENT_INTELLIGENCE_KEY
        self.model_id = settings.AZURE_DOCUMENT_INTELLIGENCE_MODEL or "prebuilt-layout"
        self.enabled = settings.AZURE_AI_ENABLED and bool(self.endpoint) and bool(self.api_key)

    def is_available(self) -> bool:
        return self.enabled

    def analyze_document_bytes(self, content: bytes, mime_type: str = "application/pdf") -> Tuple[str, int, List[Tuple[int, str]], Dict[str, Any]]:
        """
        Analyze document bytes using Azure Document Intelligence.
        Returns:
            - full_text: string
            - page_count: int
            - page_text: List of (page_num, page_content)
            - metadata: Dict with layout metadata, tables, key_value_pairs
        """
        if not self.is_available():
            return self._fallback_local_parse(content, mime_type)

        try:
            # Azure Document Intelligence REST API v2023-07-31 / 2024-02-29-preview
            url = f"{self.endpoint}/documentintelligence/documentModels/{self.model_id}:analyze?api-version=2024-02-29-preview"
            headers = {
                "Ocp-Apim-Subscription-Key": self.api_key,
                "Content-Type": mime_type if mime_type != "application/octet-stream" else "application/pdf"
            }

            with httpx.Client(timeout=90.0) as client:
                response = client.post(url, headers=headers, content=content)
                if response.status_code != 202:
                    logger.warning(f"Azure Document Intelligence submit failed ({response.status_code}): {response.text}")
                    return self._fallback_local_parse(content, mime_type)

                operation_url = response.headers.get("Operation-Location")
                if not operation_url:
                    return self._fallback_local_parse(content, mime_type)

                # Poll operation status
                import time
                for _ in range(30):
                    poll_resp = client.get(operation_url, headers={"Ocp-Apim-Subscription-Key": self.api_key})
                    if poll_resp.status_code == 200:
                        data = poll_resp.json()
                        status = data.get("status")
                        if status == "succeeded":
                            return self._process_azure_result(data.get("analyzeResult", {}))
                        elif status == "failed":
                            logger.error("Azure Document Intelligence analysis operation failed.")
                            break
                    time.sleep(1.5)

        except Exception as e:
            logger.error(f"Error calling Azure Document Intelligence: {e}")

        return self._fallback_local_parse(content, mime_type)

    def _process_azure_result(self, result: Dict[str, Any]) -> Tuple[str, int, List[Tuple[int, str]], Dict[str, Any]]:
        pages_data = result.get("pages", [])
        paragraphs = result.get("paragraphs", [])
        tables = result.get("tables", [])
        key_value_pairs = result.get("keyValuePairs", [])

        page_count = len(pages_data)
        page_dict: Dict[int, List[str]] = {p.get("pageNumber", i + 1): [] for i, p in enumerate(pages_data)}

        for p in paragraphs:
            p_text = p.get("content", "").strip()
            if not p_text:
                continue
            regions = p.get("boundingRegions", [])
            p_num = regions[0].get("pageNumber", 1) if regions else 1
            if p_num not in page_dict:
                page_dict[p_num] = []
            page_dict[p_num].append(p_text)

        page_tuples: List[Tuple[int, str]] = []
        full_parts = []
        for p_num in sorted(page_dict.keys()):
            p_content = "\n\n".join(page_dict[p_num])
            page_tuples.append((p_num, p_content))
            full_parts.append(p_content)

        full_text = "\n\n".join(full_parts)
        metadata = {
            "source": "azure_document_intelligence",
            "model": self.model_id,
            "table_count": len(tables),
            "kv_pair_count": len(key_value_pairs),
            "tables": tables,
            "key_value_pairs": key_value_pairs
        }

        return full_text, page_count or len(page_tuples), page_tuples, metadata

    def _fallback_local_parse(self, content: bytes, mime_type: str) -> Tuple[str, int, List[Tuple[int, str]], Dict[str, Any]]:
        """Fallback to local PyMuPDF / pypdf parsing."""
        from app.services.parser import extract_pdf_pages, extract_docx, extract_text
        if "pdf" in mime_type or content.startswith(b"%PDF"):
            text, pages, page_text = extract_pdf_pages(content)
        elif "officedocument" in mime_type or mime_type.endswith("docx"):
            text, pages, page_text = extract_docx(content)
        else:
            text, pages, page_text = extract_text(content)

        metadata = {
            "source": "local_parser_fallback",
            "table_count": 0,
            "kv_pair_count": 0
        }
        return text, pages, page_text, metadata


azure_doc_intelligence_service = AzureDocumentIntelligenceService()
