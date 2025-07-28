# PDF Outline Extractor: Connecting the Dots Through Docs (Round 1A)

This project offers a robust, Python-based solution for automatically extracting the title and a structured, hierarchical outline (H1, H2, H3 headings) from PDF documents. The extracted information is neatly organized and saved into a JSON file, serving as a foundational step for advanced document intelligence applications.

## Challenge Mission

The primary goal is to process a given PDF file (up to 50 pages) and generate a structured JSON output containing:
* The **main document title**.
* A list of **headings** (H1, H2, H3 levels) along with their text and corresponding page numbers.

This structured outline is crucial for enabling smarter document experiences like semantic search, recommendation systems, and insight generation, as machines don't inherently understand the visual and logical structure of PDFs.

## How It Works: Our Approach

Our solution is built upon a series of intelligent heuristics and text analysis techniques using established PDF processing libraries. The process can be broken down into the following key stages:

1.  ### Cover Page Detection (`is_cover_page`)
    This function accurately determines if the very first page of the PDF is a cover page, allowing the outline extraction to start from the actual content. It analyzes several characteristics of the target page (defaulting to page 0):
    * **Table of Contents (TOC) Check**: If the PDF has an embedded TOC that starts on page 2 or later, it's a strong indicator that page 1 is a cover.
    * **Text Density**: Cover pages typically have significantly less body text compared to content pages. We count lines that resemble body text (average font size, reasonable length).
    * **Font Prominence**: Cover pages often feature one or more very large, prominent text elements (the title, author, date). We identify if a "main title" text element exists, is significantly larger than the average font size, and is relatively centered and high up on the page.
    * **Image Presence**: Cover pages frequently contain significant images or graphics. We calculate the proportion of the page area covered by images.
    * **Sparsity**: Extremely sparse pages with minimal text but perhaps a large image are also considered.
    A combination of these heuristics determines the likelihood of a page being a cover.

2.  ### Document Title Finding (`TitleFinder`)
    This class identifies the most prominent title of the document. It focuses on the first *content* page (after accounting for a potential cover page). It iterates through text elements and identifies the text with the largest font size, then gathers adjacent text of similar dominant font size to form the complete title. Basic cleaning (e.g., deduplicating repeated characters) is applied.

3.  ### Core Outline Extraction (`PDFOutlineExtractor`)
    This is where the main logic for extracting and structuring the PDF outline resides.
    * **Font Style Analysis**: In the initial pages (first 20 pages or fewer, excluding the cover), the extractor analyzes all text spans to build a statistical understanding of font sizes and bolding. This helps in determining the "body text size" and identifying distinct "heading styles" (sizes/boldness that stand out from body text).
    * **Text Block Processing**: It iterates through each page, extracts text blocks, and cleans them by merging logically connected lines (e.g., multi-line headings) and filtering out potential headers/footers based on vertical position.
    * **Heading Candidate Identification**: Each clean text block is then evaluated against a set of rules to determine if it's a heading candidate. This involves checks for length, exclusion patterns (e.g., bullet points, captions, page numbers, form field labels, widely spaced text), and font characteristics compared to the body text size.
    * **Heading Level Determination**: For each valid heading candidate, its level (H1, H2, H3) is assigned based on:
        * **Numerical Prefixes**: Headings like "1. Introduction" or "1.1. Background" directly inform the level.
        * **Font Size Hierarchy**: The relative font size compared to the determined "heading styles" helps establish the hierarchy.
        * **Indentation**: Text that is significantly indented compared to previous headings often indicates a deeper hierarchical level.
        * **Vertical Spacing**: Large vertical gaps above a strongly left-aligned, larger-font text might suggest a new top-level section.
    * **Outline Refinement**: The final list of headings is refined to remove consecutive duplicates and ensure a logical flow in the hierarchy (e.g., preventing a jump from H1 directly to H3 without an H2 in between).

---

## Libraries Used

The solution relies on the following open-source Python libraries:

* **`PyMuPDF` (fitz)**: A powerful and lightweight PDF library used for opening documents, extracting detailed text information (spans, blocks, font sizes, bounding boxes), accessing embedded Tables of Contents, and retrieving page dimensions.
* **`pdfplumber`**: Built on `pdfminer.six`, `pdfplumber` is used for easier extraction of structured text data, including words with attributes like font size and font name. This is primarily used in `TitleFinder`.
* **Standard Python Libraries**: `os`, `json`, `re`, `collections`, `typing`.

**No external machine learning models are used**, ensuring the solution remains lightweight and operates entirely offline.

---

## Docker Requirements

The Docker setup is designed for **`AMD64` architecture**, ensuring compatibility with the evaluation environment.

* **CPU Architecture**: `amd64` (x86_64)
* **GPU Dependencies**: None (solution runs purely on CPU)
* **Model Size**: N/A (no external models used, thus ≤ 200MB constraint is inherently met)
* **Network**: No internet access required; the solution works completely offline.

---

## How to Build and Run Your Solution

Please ensure your project structure is as follows: `main.py`, `TitleFinder.py`, `PDFOutlineExtractor.py`, and `cover_page.py` should be in the root directory, with `input` and `output` directories at the same level as the Dockerfile.

### Project Structure Example:
