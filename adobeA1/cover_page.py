import fitz # PyMuPDF

def _analyze_page_for_cover_characteristics(page, document, max_body_text_lines=8, min_image_area_ratio=0.02, min_prominent_font_ratio=1.2, min_prominent_elements=1, max_prominent_elements=15, title_centering_threshold=0.30, title_vertical_pos_threshold=0.5):
    """
    Internal helper function to analyze a single page for cover page characteristics.
    This version refines heuristics to better distinguish cover pages from content pages.

    Args:
        page (fitz.Page): The page object to analyze.
        document (fitz.Document): The parent document object (needed for TOC).
        max_body_text_lines (int): Max number of lines considered body text for a cover page.
        min_image_area_ratio (float): Minimum proportion of page area covered by images.
        min_prominent_font_ratio (float): A font size must be this many times larger than the average
                                          to be considered "prominent".
        min_prominent_elements (int): Minimum number of prominent text elements expected on a cover page.
        max_prominent_elements (int): Max count of distinct very large text elements.
        title_centering_threshold (float): Max deviation from center for main title.
        title_vertical_pos_threshold (float): Max vertical position (from top, as ratio of page height) for main title.
                                              e.g., 0.5 means title must be in upper half.
    """
    page_name = f"Page {page.number + 1} of {document.name if hasattr(document, 'name') else 'unknown_document'}"
    print(f"\n--- Analyzing {page_name} ---")

    try:
        # --- TOC Check (Strongest Indicator) ---
        toc = document.get_toc()
        if toc:
            first_toc_page = toc[0][2] if toc and len(toc[0]) > 2 else -1 
            if first_toc_page == page.number + 1 and page.number == 0:
                # TOC starts on page 1, and this is page 1. Likely a content page, let other heuristics decide.
                print(f"  TOC starts on page 1. Likely content page. Continuing heuristics.")
            elif first_toc_page > 1 and page.number == 0: # TOC starts on page 2 or later, and this is page 1
                print(f"  Result for {page_name}: True (Reason: TOC starts on page {first_toc_page}, so page 1 is likely cover)")
                return True


        # --- Extract all text spans and blocks ---
        text_blocks = page.get_text("dict")["blocks"]
        spans = []
        full_page_text = ""
        for b in text_blocks:
            if b["type"] == 0: # Only process text blocks
                for line in b["lines"]:
                    line_text = " ".join(s["text"] for s in line["spans"]).strip()
                    spans.extend(line["spans"])
                    full_page_text += line_text + "\n" # Collect text for keyword search

        # --- Heuristic: Copyright/Legal Keywords (Optional, can be added if needed) ---
        # found_copyright_keyword = False
        # copyright_patterns = [
        #     r"copyright", r"all rights reserved", r"version \d+(\.\d+)*",
        #     r"confidential", r"proprietary", r"document no\.", r"rev\.", r"issue date"
        # ]
        # for pattern in copyright_patterns:
        #     if re.search(pattern, full_page_text, re.IGNORECASE):
        #         found_copyright_keyword = True
        #         break
        # print(f"  found_copyright_keyword: {found_copyright_keyword}")


        # --- Heuristic 2: Image Presence ---
        images_info = page.get_image_info() 
        page_area = page.rect.width * page.rect.height
        total_image_area = 0

        for img_info in images_info:
            if 'bbox' in img_info and 'width' in img_info and 'height' in img_info:
                if img_info['width'] > 0 and img_info['height'] > 0:
                    total_image_area += img_info['width'] * img_info['height']
        
        has_significant_image = (total_image_area / page_area if page_area > 0 else 0) > min_image_area_ratio
        print(f"  has_significant_image: {has_significant_image} (Total area: {total_image_area:.2f}, Page area: {page_area:.2f}, Threshold: {min_image_area_ratio})")


        if not spans:
            print(f"  No text spans found. Is significant image? {has_significant_image}")
            if has_significant_image:
                print(f"  Result for {page_name}: True (No text, significant image)")
            else:
                print(f"  Result for {page_name}: False (No text, no significant image)")
            return has_significant_image 

        all_font_sizes = [s["size"] for s in spans]
        if not all_font_sizes: 
            print("  No font sizes found in spans. Returning False.")
            print(f"  Result for {page_name}: False (No font sizes)")
            return False 
        
        avg_font_size = sum(all_font_sizes) / len(all_font_sizes)
        max_font_size = max(all_font_sizes)

        has_a_large_font = max_font_size > avg_font_size * min_prominent_font_ratio
        print(f"  has_a_large_font: {has_a_large_font} (Max: {max_font_size:.2f}, Avg: {avg_font_size:.2f}, Ratio Threshold: {min_prominent_font_ratio})")

        # --- Heuristic 1: Body Text Density ---
        body_text_lines_count = 0
        unique_lines = {} 
        for b in text_blocks:
            if b["type"] == 0:
                for line in b["lines"]:
                    line_text = " ".join(s["text"] for s in line["spans"]).strip()
                    if line_text:
                        max_line_font_size = max(s["size"] for s in line["spans"])
                        normalized_line_text = ' '.join(line_text.split())
                        unique_lines[normalized_line_text] = max(unique_lines.get(normalized_line_text, 0), max_line_font_size)

        for line_text, line_font_size in unique_lines.items():
            if line_font_size <= avg_font_size * 1.2 and len(line_text.split()) > 4 and line_font_size < max_font_size * 0.8:
                body_text_lines_count += 1
        
        print(f"  body_text_lines_count: {body_text_lines_count} (Threshold: {max_body_text_lines})")
        if body_text_lines_count > max_body_text_lines:
            print(f"  Result for {page_name}: False (Reason: Too many body text lines)")
            return False


        # --- Heuristic 3: Number of Prominent Text Elements ---
        prominent_text_elements_count = 0
        processed_prominent_lines = set()
        
        for span in sorted(spans, key=lambda s: s["size"], reverse=True):
            text = span["text"].strip()
            normalized_text = ' '.join(text.split())
            if not normalized_text:
                continue

            if span["size"] > avg_font_size * min_prominent_font_ratio and normalized_text not in processed_prominent_lines:
                prominent_text_elements_count += 1
                processed_prominent_lines.add(normalized_text)
        
        print(f"  prominent_text_elements_count: {prominent_text_elements_count} (Min: {min_prominent_elements}, Max: {max_prominent_elements})")
        if not (min_prominent_elements <= prominent_text_elements_count <= max_prominent_elements):
            print(f"  Result for {page_name}: False (Reason: Prominent elements count outside expected range)")
            return False
        
        # --- Heuristic 4: Main Title Centering and Vertical Position ---
        is_main_title_centered = False
        is_main_title_high_enough = False
        main_title_span = None
        if spans:
            main_title_span = max(spans, key=lambda s: s["size"]) 
        
        if main_title_span:
            main_title_bbox = main_title_span["bbox"]
            page_width = page.rect.width
            page_height = page.rect.height
            center_x_title = (main_title_bbox[0] + main_title_bbox[2]) / 2
            center_x_page = page_width / 2
            is_main_title_centered = abs(center_x_title - center_x_page) / page_width < title_centering_threshold
            print(f"  is_main_title_centered: {is_main_title_centered} (Deviation: {abs(center_x_title - center_x_page) / page_width:.2f}, Threshold: {title_centering_threshold})")

            # Check vertical position: is the top of the title within the top X% of the page?
            # Smaller ratio means higher up the page (e.g., 0.5 means top half)
            vertical_pos_ratio = main_title_bbox[1] / page_height
            is_main_title_high_enough = vertical_pos_ratio < title_vertical_pos_threshold
            print(f"  is_main_title_high_enough: {is_main_title_high_enough} (Top Y ratio: {vertical_pos_ratio:.2f}, Threshold: {title_vertical_pos_threshold})")

        # --- Final Decision Logic ---
        is_very_sparse_overall = len(spans) < 10 and body_text_lines_count == 0

        is_likely_cover = (body_text_lines_count <= max_body_text_lines and 
                           has_a_large_font and 
                           is_main_title_centered and
                           is_main_title_high_enough and # New heuristic
                           prominent_text_elements_count >= min_prominent_elements and # Ensure at least min prominent elements
                           prominent_text_elements_count <= max_prominent_elements) # Ensure not too many

        # Fallback for image-heavy or extremely sparse covers or those with copyright keywords
        is_fallback_cover = is_very_sparse_overall and has_significant_image # Removed keyword check from here, can be added as separate param if needed

        print(f"  is_likely_cover (primary criteria): {is_likely_cover}")
        print(f"  is_fallback_cover (sparse/image): {is_fallback_cover}")

        final_result = is_likely_cover or is_fallback_cover
        print(f"  Result for {page_name}: {final_result}")
        return final_result

    except Exception as e:
        print(f"Error analyzing page for cover characteristics in _analyze_page_for_cover_characteristics: {e}")
        return False

def is_cover_page(pdf_path, page_number=0, **kwargs):
    """
    Determines if a specific page of a PDF is a cover page.

    Args:
        pdf_path (str): The path to the PDF file.
        page_number (int): The 0-indexed page number to check. Defaults to 0 (first page).
        **kwargs: Optional parameters to fine-tune heuristics:
                  max_body_text_lines (int, default=8): Max number of lines considered body text for a cover page.
                  min_image_area_ratio (float, default=0.02): Minimum proportion of page area covered by images.
                  min_prominent_font_ratio (float, default=1.2): A font size must be this many times larger than the average
                                                                  to be considered "prominent".
                  min_prominent_elements (int, default=1): Minimum number of prominent text elements expected on a cover page.
                  max_prominent_elements (int, default=15): Max count of distinct very large text elements.
                  title_centering_threshold (float, default=0.30): Max deviation from center for main title.
                  title_vertical_pos_threshold (float, default=0.5): Max vertical position (from top, as ratio of page height) for main title.

    Returns:
        bool: True if the specified page is likely a cover page, False otherwise.
    """
    try:
        document = fitz.open(pdf_path)
        if document.page_count <= page_number:
            print(f"Error: Page {page_number} does not exist in {pdf_path}. Document has {document.page_count} pages.")
            return False

        page = document.load_page(page_number)
        result = _analyze_page_for_cover_characteristics(page, document, **kwargs) # Pass document object
        document.close()
        return result

    except Exception as e:
        print(f"Error opening or processing PDF '{pdf_path}' in is_cover_page: {e}")
        return False

