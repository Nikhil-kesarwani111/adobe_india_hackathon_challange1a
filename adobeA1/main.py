# main.py

import os
import json
from TitleFinder import TitleFinder
from PDFOutlineExtractor import PDFOutlineExtractor
from cover_page import is_cover_page # Import the new function

def process_pdf(input_path: str, output_path: str):
    """
    Processes a single PDF file to extract its title and outline (headings),
    then saves the information to a JSON file.
    Also identifies if the first page is a cover page and informs the outline extractor.
    """
    # print(f"Processing PDF: {input_path}...")
    
    # Initialize the TitleFinder and extract the title
    title_finder = TitleFinder()
    title = ""
    try:
        title_info = title_finder.find_title(input_path)
        title = title_info.get("title", os.path.splitext(os.path.basename(input_path))[0])
    except Exception as e:
        print(f"Warning: Title extraction failed for {input_path}: {e}. Using filename as title.")
        title = os.path.splitext(os.path.basename(input_path))[0]

    # Check if the first page is a cover page
    is_first_page_cover = is_cover_page(input_path, page_number=0)
    # print(f"Is the first page of '{os.path.basename(input_path)}' a cover page? {is_first_page_cover}")

    # Initialize the PDFOutlineExtractor and pass the cover page info
    # The extractor will now internally decide the starting page based on this flag
    extractor = PDFOutlineExtractor(document_title=title, is_first_page_cover=is_first_page_cover)
    outline = extractor.extract_outline(input_path)

    # The outline_starts_from_page can be derived directly from the extractor's state if needed,
    # or you can just rely on the print statement from within PDFOutlineExtractor.
    # For consistency, we'll still add it to the result dictionary based on the flag.
    outline_start_page_num = 2 if is_first_page_cover else 1


    # Construct the final result dictionary
    result = {
        "title": title,
        "outline": outline
    }

    # Save the result to a JSON file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Successfully saved outline to {output_path}")
    except Exception as e:
        print(f"Error saving outline to {output_path}: {e}")


if __name__ == "__main__":
    input_dir = "input"
    output_dir = "output"
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Process all PDF files in the input directory
    pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith(".pdf")]

    if not pdf_files:
        print(f"No PDF files found in the '{input_dir}' directory. Please place your PDFs there.")
    else:
        for filename in pdf_files:
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}.json")
            
            try:
                process_pdf(input_path, output_path)
            except Exception as e:
                print(f"An unexpected error occurred while processing {filename}: {str(e)}")