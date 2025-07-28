import fitz  # PyMuPDF
import re
from collections import defaultdict, Counter
from typing import List, Dict, Optional
import os
import json

class PDFOutlineExtractor:
    def __init__(self, document_title: str = "", is_first_page_cover: bool = False):
        self.document_title = document_title
        self.is_first_page_cover = is_first_page_cover
        self.font_stats = defaultdict(lambda: {'char_count': 0, 'bold_count': 0})
        self.page_dimensions = (0, 0)

        self.header_footer_threshold = 0.1
        self.min_heading_ratio = 1.3
        self.min_heading_length = 4
        self.max_heading_length = 100
        self.form_field_threshold = 0.15
        self.spaced_text_threshold = 0.5
        self.line_merge_tolerance_y = 7
        self.line_merge_tolerance_x = 20
        self.indentation_threshold = 25

        self.non_heading_patterns = [
            re.compile(r'^(figure|table|appendix|note:)\b', re.IGNORECASE),
            re.compile(r'^[•\-*·]\s'),
            re.compile(r'^\d+[/-]\d+$'),
            re.compile(r'^[A-Za-z]\d+$'),
            re.compile(r'^\s*\d+\s*$'),
            re.compile(r'^[A-Z][A-Za-z]*:$'),
            re.compile(r'^\w+/\w+:$'),
            re.compile(r'^\d+\.\s*\w+:$'),
            re.compile(r'^(s\.?no\.?|sr\.?no\.?)$', re.IGNORECASE),
            re.compile(r'^(name|date|address|phone|email|id|sex|gender|age|signature|city|state|zip|country|total|amount|item|quantity|description|relation|relationship|value|unit|price|type|status|comments|notes|remarks|subtotal|tax|grand total)$', re.IGNORECASE),
            re.compile(r'^\s*©\s*\d{4}\s*'),
            re.compile(r'^\s*all rights reserved\s*$', re.IGNORECASE),
            re.compile(r'^\s*confidential\s*$', re.IGNORECASE),
            re.compile(r'^\s*document\s+id:\s*', re.IGNORECASE),
            re.compile(r'^\s*page\s+\d+\s+of\s+\d+\s*$', re.IGNORECASE),
            re.compile(r'^\s*disclaimer\s*$', re.IGNORECASE),
            re.compile(r'^\s*copyright\s*$', re.IGNORECASE),
            re.compile(r'^\s*prepared\s+by:', re.IGNORECASE),
            re.compile(r'^\s*for\s+internal\s+use\s+only\s*$', re.IGNORECASE),
            re.compile(r'^\s*version\s+\d+(\.\d+)*(\s+\w+)?$', re.IGNORECASE),
            re.compile(r'^\s*revision\s+history\s*$', re.IGNORECASE),
        ]

        self.spaced_text_pattern = re.compile(r'\w\s{3,}\w')

    def extract_outline(self, pdf_path: str) -> Dict:
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                return {"title": self.document_title if self.document_title else os.path.splitext(os.path.basename(pdf_path))[0], "outline": []}

            self.page_dimensions = (doc[0].rect.width, doc[0].rect.height)

            self._analyze_document_styles(doc)

            if not self.document_title:
                extracted_title = self._extract_document_title(doc)
                self.document_title = extracted_title if extracted_title else os.path.splitext(os.path.basename(pdf_path))[0]

            outline_candidates = self._extract_headings_from_content(doc)

            refined_outline = self._refine_hierarchy(outline_candidates)

            return refined_outline

        except Exception as e:
            return {"title": self.document_title if self.document_title else os.path.splitext(os.path.basename(pdf_path))[0], "outline": []}
        finally:
            if 'doc' in locals():
                doc.close()

    def _analyze_document_styles(self, doc: fitz.Document) -> None:
        start_page_idx = 1 if self.is_first_page_cover else 0
        analyze_pages_count = min(20, len(doc) - start_page_idx)

        for i in range(analyze_pages_count):
            page_num = start_page_idx + i
            if page_num >= len(doc):
                break
            page = doc[page_num]

            if self._is_form_page(page):
                continue

            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if block["type"] != 0:
                    continue

                for line in block["lines"]:
                    if not line["spans"]:
                        continue

                    if self._is_header_footer(line["bbox"]):
                        continue

                    for span in line["spans"]:
                        font_size = round(span["size"], 1)
                        is_bold = self._is_bold_font(span["font"])
                        text = span["text"].strip()

                        if not text:
                            continue

                        self.font_stats[font_size]['char_count'] += len(text)
                        if is_bold:
                            self.font_stats[font_size]['bold_count'] += len(text)

    def _extract_headings_from_content(self, doc: fitz.Document) -> List[Dict]:
        if not self.font_stats:
            return []

        body_size = self._determine_body_text_size()
        heading_styles = self._identify_heading_styles(body_size)

        if not heading_styles:
            return []

        outline_candidates = []
        prev_heading_context = None

        start_page_idx = 1 if self.is_first_page_cover else 0

        for page_num_0_indexed in range(start_page_idx, len(doc)):
            page = doc[page_num_0_indexed]

            if self._is_form_page(page):
                continue

            text_blocks_on_page = self._get_clean_text_blocks(page)

            for block in text_blocks_on_page:
                if self._is_heading_candidate(block, body_size):
                    level = self._determine_heading_level(block, heading_styles, prev_heading_context)

                    entry = {
                        "level": level,
                        "text": block["text"],
                        "page": page_num_0_indexed
                    }

                    outline_candidates.append(entry)
                    prev_heading_context = {
                        "level": level,
                        "size": block["size"],
                        "origin_x": block["origin_x"],
                        "origin_y": block["origin_y"],
                        "bbox": block["bbox"]
                    }

        return outline_candidates

    def _is_form_page(self, page: fitz.Page) -> bool:
        widgets = list(page.widgets())
        if widgets:
            form_area = sum(w.rect.width * w.rect.height for w in widgets)
            page_area = self.page_dimensions[0] * self.page_dimensions[1]
            if (form_area / page_area) > self.form_field_threshold:
                return True

        text = page.get_text()
        form_indications = 0

        form_indications += text.count(":_____")
        form_indications += text.count(": ___")
        form_indications += text.count(":\n")

        form_labels = ["name:", "date:", "signature:", "address:", "phone:", "email:", "id number:", "ssn:", "account:"]
        form_indications += sum(text.lower().count(label) for label in form_labels)

        if "|   |" in text or "|___|" in text or "___ " * 3 in text:
            form_indications += 3

        return form_indications >= 3

    def _is_header_footer(self, line_bbox: List[float]) -> bool:
        y_pos_ratio = line_bbox[1] / self.page_dimensions[1]

        if (y_pos_ratio < self.header_footer_threshold or
                y_pos_ratio > 1 - self.header_footer_threshold):
            return True

        x_center = self.page_dimensions[0] / 2
        line_center = (line_bbox[0] + line_bbox[2]) / 2
        if abs(line_center - x_center) < 20:
            return True

        return False

    def _is_spaced_text(self, text: str) -> bool:
        if self.spaced_text_pattern.search(text):
            space_count = text.count(' ')
            total_chars = len(text)
            non_space_chars = total_chars - space_count
            if non_space_chars > 0:
                space_ratio = space_count / non_space_chars
                return space_ratio > self.spaced_text_threshold
        return False

    def _is_heading_candidate(self, block: Dict, body_size: float) -> bool:
        text = block["text"].strip()

        cleaned_text_for_comparison = re.sub(r'^[•\-\*\s]+|[•\-\*\s]+$', '', text).strip()
        cleaned_text_for_comparison = re.sub(r'[^a-zA-Z0-9\s]', '', cleaned_text_for_comparison).strip()

        if not text:
            return False

        if not cleaned_text_for_comparison:
            return False

        word_count = len(cleaned_text_for_comparison.split())

        if word_count == 1:
            if not re.match(r'^\d+(\.\d+)*$', cleaned_text_for_comparison):
                if len(cleaned_text_for_comparison) < self.min_heading_length:
                    return False
        elif word_count < 1:
            return False

        if len(text) > self.max_heading_length:
            return False

        for pattern in self.non_heading_patterns:
            if pattern.match(text):
                return False

        if text.endswith(":"):
            return False

        if "|" in text:
            return False

        if word_count <= 2 and text.isupper() and not re.match(r'^\d+(\.\d+)*\s*', text):
            return False

        if self._is_spaced_text(text):
            return False

        if body_size == 0:
            return False

        size_ratio = block["size"] / body_size
        is_bold_enough = block["is_bold"] and (block["size"] > body_size * 1.05)

        if not (size_ratio >= self.min_heading_ratio or is_bold_enough):
            return False

        looks_like_sentence = (text[0].isupper() and
                               word_count > 3 and
                               re.search(r'[\.\?\!]$', text))

        is_strong_heading_pattern = text.isupper() or re.match(r'^(?:\d+(\.\d+)*|[A-Z])\s*', text)

        if looks_like_sentence and not is_strong_heading_pattern:
            if not is_bold_enough and size_ratio < self.min_heading_ratio * 1.2:
                return False

        if re.match(r'^(?:\d+(\.\d+)*\s+|[A-Z]\.\s+)', text):
            return True

        if text.isupper() and word_count > 1:
            return True

        return True

    def _get_clean_text_blocks(self, page: fitz.Page) -> List[Dict]:
        blocks = []
        text_blocks = page.get_text("dict")["blocks"]

        current_merged_block = None

        for block in text_blocks:
            if block["type"] != 0:
                continue

            for line in block["lines"]:
                if not line["spans"]:
                    continue

                if self._is_header_footer(line["bbox"]):
                    continue

                line_text = ""
                size_counter = Counter()
                bold_counter = Counter()

                for span in line["spans"]:
                    span_text = span["text"]
                    if not span_text.strip():
                        continue

                    line_text += span_text
                    size = round(span["size"], 1)
                    size_counter[size] += len(span_text)
                    bold_counter[self._is_bold_font(span["font"])] += len(span_text)

                line_text = line_text.strip()
                if not line_text:
                    continue

                dominant_size = size_counter.most_common(1)[0][0] if size_counter else 0
                dominant_bold = bold_counter.most_common(1)[0][0] if bold_counter else False

                line_info = {
                    "text": line_text,
                    "size": dominant_size,
                    "is_bold": dominant_bold,
                    "bbox": list(line["bbox"]),
                    "origin_x": line["bbox"][0],
                    "origin_y": line["bbox"][1]
                }

                if current_merged_block:
                    if (abs(line_info["origin_y"] - current_merged_block["bbox"][3]) < self.line_merge_tolerance_y and
                            abs(line_info["size"] - current_merged_block["size"]) < 0.5 and
                            line_info["is_bold"] == current_merged_block["is_bold"] and
                            abs(line_info["origin_x"] - current_merged_block["origin_x"]) < self.line_merge_tolerance_x):

                        current_merged_block["text"] += " " + line_info["text"]
                        current_merged_block["bbox"][3] = line_info["bbox"][3]
                        current_merged_block["origin_y"] = line_info["origin_y"]
                    else:
                        blocks.append(current_merged_block)
                        current_merged_block = line_info
                else:
                    current_merged_block = line_info

        if current_merged_block:
            blocks.append(current_merged_block)

        return blocks

    def _determine_body_text_size(self) -> float:
        if not self.font_stats:
            return 11.0

        body_candidates = [size for size in self.font_stats
                           if 8 <= size <= 14]

        if not body_candidates:
            if self.font_stats:
                return max(self.font_stats, key=lambda s: (self.font_stats[s]['char_count'] - self.font_stats[s]['bold_count']))
            return 11.0

        return max(body_candidates,
                   key=lambda s: (self.font_stats[s]['char_count'] - self.font_stats[s]['bold_count']))

    def _identify_heading_styles(self, body_size: float) -> List[Dict]:
        heading_candidates = []

        for size, stats in self.font_stats.items():
            if size <= body_size * 0.95:
                continue

            size_ratio = size / body_size
            is_bold_likely = (stats['bold_count'] / max(1, stats['char_count'])) > 0.6

            if size_ratio >= self.min_heading_ratio or is_bold_likely:
                score = size_ratio * 50 + (40 if is_bold_likely else 0)
                heading_candidates.append({
                    "size": size,
                    "is_bold": is_bold_likely,
                    "score": score,
                    "char_count": stats['char_count']
                })

        sorted_candidates = sorted(heading_candidates,
                                   key=lambda x: (-x['score'], -x['size'], -x['char_count']))

        distinct_styles = []
        seen_sizes = set()

        for style in sorted_candidates:
            is_distinct = True
            for s_size in seen_sizes:
                if abs(style["size"] - s_size) < 0.5:
                    is_distinct = False
                    break

            if is_distinct:
                distinct_styles.append(style)
                seen_sizes.add(style["size"])
                if len(distinct_styles) >= 3:
                    break

        return distinct_styles

    def _determine_heading_level(self, block: Dict,
                                 heading_styles: List[Dict],
                                 prev_heading: Optional[Dict]) -> str:
        current_text = block["text"].strip()
        current_level_num = 3

        match_prefix = re.match(r'^(\d+(\.\d+)*|[A-Z])\s*', current_text)
        if match_prefix:
            prefix = match_prefix.group(1)
            dot_count = prefix.count('.')
            if dot_count == 0 and prefix.isdigit():
                current_level_num = 1
            elif dot_count == 1:
                current_level_num = 2
            elif dot_count == 2:
                current_level_num = 3

        if heading_styles:
            for i, style in enumerate(heading_styles):
                if (abs(block["size"] - style["size"]) < 0.5 and block["is_bold"] == style["is_bold"]):
                    if i + 1 < current_level_num:
                        current_level_num = i + 1
                    break

            h1_style_size = heading_styles[0]["size"]
            if h1_style_size > 0:
                size_ratio_to_h1 = block["size"] / h1_style_size
                if size_ratio_to_h1 > 0.9 and current_level_num > 1: current_level_num = 1
                elif size_ratio_to_h1 > 0.7 and current_level_num > 2: current_level_num = 2

        if prev_heading:
            prev_level_num = int(prev_heading["level"][1])

            if current_level_num > prev_level_num + 1:
                current_level_num = prev_level_num + 1

            if block["origin_x"] > prev_heading["origin_x"] + self.indentation_threshold:
                if current_level_num <= prev_level_num:
                    current_level_num = prev_level_num + 1

            typical_left_margin_x = self.page_dimensions[0] * 0.1

            is_strongly_left_aligned = abs(block["origin_x"] - typical_left_margin_x) < 30

            if prev_heading["size"] > 0 and \
               block["size"] > prev_heading["size"] * 1.5 and \
               is_strongly_left_aligned and \
               current_level_num > 1:
                current_level_num = 1

            if prev_heading.get("bbox") and prev_heading["bbox"][3] is not None:
                vertical_gap = block["origin_y"] - prev_heading["bbox"][3]
                if vertical_gap > (block["size"] * 2.5) and is_strongly_left_aligned and current_level_num > 1:
                    current_level_num = 1

            if block["size"] < prev_heading["size"] * 0.9 and current_level_num <= prev_level_num:
                current_level_num = prev_level_num + 1

        return f"H{min(current_level_num, 3)}"

    def _refine_hierarchy(self, outline_candidates: List[Dict]) -> List[Dict]:
        if not outline_candidates:
            return []

        refined_outline = []
        last_entry = None

        for entry in outline_candidates:
            if (last_entry and
                    entry["text"] == last_entry["text"] and
                    entry["level"] == last_entry["level"] and
                    entry["page"] == last_entry["page"]):
                continue

            refined_outline.append(entry)
            last_entry = entry

        final_cleaned_outline = []
        if refined_outline:
            final_cleaned_outline.append(refined_outline[0])

            for i in range(1, len(refined_outline)):
                current_entry = refined_outline[i]
                prev_entry = final_cleaned_outline[-1]

                curr_level_num = int(current_entry["level"][1])
                prev_level_num = int(prev_entry["level"][1])

                if curr_level_num > prev_level_num + 1:
                    current_entry["level"] = f"H{prev_level_num + 1}"

                common_short_words_to_exclude = {
                    "s.no", "name", "date", "id", "no", "description", "quantity", "total",
                    "relationship", "relation", "price", "unit", "value", "type", "status",
                    "comments", "notes", "remarks", "subtotal", "tax", "grand total", "item",
                    "code", "ref", "part", "model", "serial", "data", "key", "number"
                }

                cleaned_text_lower = re.sub(r'[^a-z0-9\s]', '', current_entry["text"].lower()).strip()

                if len(cleaned_text_lower.split()) == 1 and cleaned_text_lower in common_short_words_to_exclude:
                    if not re.match(r'^\d+(\.\d+)*\s*', current_entry["text"]):
                        continue

                final_cleaned_outline.append(current_entry)

        return final_cleaned_outline

    def _extract_document_title(self, doc: fitz.Document) -> str:
        if len(doc) == 0:
            return ""

        start_page_idx = 0 if not self.is_first_page_cover else 1
        if start_page_idx >= len(doc):
            return ""

        page = doc[start_page_idx]
        blocks_on_page = page.get_text("dict")["blocks"]

        title_candidates = []

        for block in blocks_on_page:
            if block["type"] != 0:
                continue

            for line in block["lines"]:
                if not line["spans"]:
                    continue

                if self._is_header_footer(line["bbox"]):
                    continue

                line_text = "".join(span["text"] for span in line["spans"]).strip()
                if not line_text:
                    continue

                dominant_size = max(span["size"] for span in line["spans"]) if line["spans"] else 0
                dominant_bold = any(self._is_bold_font(span["font"]) for span in line["spans"])

                y_pos_ratio = line["bbox"][1] / self.page_dimensions[1]
                if y_pos_ratio < 0.4:
                    title_candidates.append({
                        "text": line_text,
                        "size": dominant_size,
                        "is_bold": dominant_bold,
                        "y_top": line["bbox"][1],
                        "y_bottom": line["bbox"][3],
                        "x_left": line["bbox"][0]
                    })

        if not title_candidates:
            return ""

        title_candidates.sort(key=lambda x: (x["size"], -x["y_top"], x["is_bold"]), reverse=True)

        final_title_parts = []
        if title_candidates:
            potential_main_title = None
            for cand in title_candidates:
                if cand["size"] >= title_candidates[0]["size"] * 0.85 and \
                   not re.match(r'^\d+(\.\d+)*$', cand["text"].strip()) and \
                   not re.match(r'^[A-Z]$', cand["text"].strip()) and \
                   len(cand["text"].split()) > 1:
                    potential_main_title = cand
                    break

            if not potential_main_title:
                potential_main_title = title_candidates[0]

            final_title_parts.append(potential_main_title["text"])
            last_part_info = {
                "y_bottom": potential_main_title["y_bottom"],
                "x_left": potential_main_title["x_left"],
                "size": potential_main_title["size"]
            }

            start_idx_for_merge = -1
            for idx, cand in enumerate(title_candidates):
                if id(cand) == id(potential_main_title):
                    start_idx_for_merge = idx
                    break

            for i in range(start_idx_for_merge + 1, len(title_candidates)):
                next_part = title_candidates[i]

                if (abs(next_part["y_top"] - last_part_info["y_bottom"]) < 1.5 * next_part["size"] and
                        abs(next_part["size"] - last_part_info["size"]) < 2 and
                        abs(next_part["x_left"] - last_part_info["x_left"]) < 20 and
                        (next_part["y_top"] / self.page_dimensions[1]) < 0.5):

                    if (next_part["text"][0].islower() and len(next_part["text"].split()) > 7) or \
                       (len(next_part["text"].split()) < 3 and not next_part["text"].isupper() and \
                        not re.match(r'^\d+(\.\d+)*\s*', next_part["text"])):
                        break

                    final_title_parts.append(next_part["text"])
                    last_part_info["y_bottom"] = next_part["y_bottom"]
                    last_part_info["x_left"] = next_part["x_left"]
                    last_part_info["size"] = next_part["size"]
                else:
                    break

        return " ".join(final_title_parts)

    @staticmethod
    def _is_bold_font(font_name: str) -> bool:
        if not font_name:
            return False

        font_lower = font_name.lower()
        return any(keyword in font_lower
                   for keyword in ["bold", "black", "heavy", "demi", "bld", "700", "800", "900"])