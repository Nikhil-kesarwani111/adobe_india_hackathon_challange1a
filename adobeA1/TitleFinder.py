import os
import pdfplumber
from collections import defaultdict

class TitleFinder:
    def __init__(self):
        self.title = ""
        self.title_page = 1
        self.title_font_size = 0
        self.title_font_name = ""

    def find_title(self, pdf_path):
        with pdfplumber.open(pdf_path) as pdf:
            first_content_page, page_num = self._find_first_content_page(pdf)
            self.title_page = page_num

            if first_content_page:
                words = self._safe_extract_words(first_content_page)

                current_title_words = []
                current_font_size = 0
                current_font_name = ""

                for word in words:
                    font_size = word.get("size", 0)
                    font_name = word.get("fontname", "unknown")
                    text = word.get("text", "")

                    # Basic filter: ignore super-short or numeric strings
                    if len(text.strip()) <= 2 or text.isdigit():
                        continue

                    # Set new dominant font if larger size
                    if font_size > current_font_size:
                        current_title_words = [text]
                        current_font_size = font_size
                        current_font_name = font_name

                    elif font_size == current_font_size and font_name == current_font_name:
                        current_title_words.append(text)

                # Join and clean title
                raw_title = " ".join(current_title_words).strip()
                self.title = self._deduplicate_title(raw_title)
                self.title_font_size = current_font_size
                self.title_font_name = current_font_name

        return {
            "title": self.title if self.title else os.path.splitext(os.path.basename(pdf_path))[0],
            "page": self.title_page
        }

    def _find_first_content_page(self, pdf):
        for page_num, page in enumerate(pdf.pages, start=1):
            try:
                if page.extract_text() and page.extract_text().strip():
                    return page, page_num
            except:
                continue
        return None, 1

    def _safe_extract_words(self, page):
        try:
            words = page.extract_words(extra_attrs=["size", "fontname"])
            return [{"text": w["text"],
                     "size": w.get("size", 0),
                     "fontname": w.get("fontname", "unknown")}
                    for w in words]
        except:
            return []

    def _deduplicate_title(self, text):
        # Remove repeated characters like "RRRR" → "R", "PPPrrrrooooppppooooss..." → "Proposal"
        import re
        # Remove 3 or more repeated characters in a row
        return re.sub(r'(.)\1{2,}', r'\1', text)
