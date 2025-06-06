"""
sudo apt-get update
sudo apt-get install tesseract-ocr
sudo apt-get install poppler-utils
pip install pytesseract pdf2image Pillow
"""

import pytesseract
from pdf2image import convert_from_path
import os

# --- CONFIGURATION ---
# For Windows users, you might need to specify the path to the Tesseract executable
# if it's not in your system's PATH.
# Example: pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def convert_pdf_to_markdown(pdf_path, output_md_path):
    """
    Converts a PDF with scanned images to a Markdown file using OCR.

    Args:
        pdf_path (str): The file path to the input PDF.
        output_md_path (str): The file path for the output Markdown file.
    """
    if not os.path.exists(pdf_path):
        print(f"Error: The file '{pdf_path}' was not found.")
        return

    print(f"Starting conversion for '{pdf_path}'...")

    # 1. Convert PDF pages to a list of images
    try:
        # For Windows, you might need to specify the poppler path:
        # images = convert_from_path(pdf_path, poppler_path=r"C:\path\to\poppler-xx\bin")
        images = convert_from_path(pdf_path)
    except Exception as e:
        print(f"Error converting PDF to images: {e}")
        print("Please ensure Poppler is installed and in your system's PATH.")
        return

    full_markdown_text = ""
    total_pages = len(images)
    
    print(f"Found {total_pages} pages to process.")

    # 2. Iterate through each image (page) and perform OCR
    for i, page_image in enumerate(images):
        print(f"Processing page {i + 1}/{total_pages}...")
        
        try:
            # 3. Use Tesseract to extract text from the image
            # You can specify a language if needed, e.g., lang='eng+fra' for English and French
            text = pytesseract.image_to_string(page_image, lang='eng')
            
            # 4. Append the extracted text to our main string
            full_markdown_text += text
            
            # Add a separator between pages for clarity in the final markdown file.
            # A horizontal rule `---` is a good choice.
            if i < total_pages - 1:
                full_markdown_text += "\n\n---\n\n"
                
        except pytesseract.TesseractNotFoundError:
            print("Tesseract Error: The Tesseract executable was not found.")
            print("Please make sure Tesseract is installed and its path is configured correctly.")
            return
        except Exception as e:
            print(f"An error occurred during OCR on page {i+1}: {e}")


    # 5. Write the combined text to the output Markdown file
    try:
        with open(output_md_path, "w", encoding="utf-8") as md_file:
            md_file.write(full_markdown_text)
        print(f"\nSuccessfully converted PDF to '{output_md_path}'")
    except Exception as e:
        print(f"Error writing to the output file: {e}")


# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # The name of your scanned PDF file
    input_pdf_file = "1.pdf" 
    
    # The name for your output Markdown file
    output_markdown_file = "output_document.md"
    
    convert_pdf_to_markdown(input_pdf_file, output_markdown_file)
