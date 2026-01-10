"""
Test Script for PDF Processing

Processes a PDF file and prints analysis results to console.
Does NOT save to Supabase - for testing purposes only.
"""

import sys
import json
from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image
import io

from app.services.analyzer import analyze_pdf_page
from app.models.schemas import SlideAnalysis


def pil_image_to_bytes(image: Image.Image, format: str = "JPEG") -> bytes:
    """
    Convert PIL Image to bytes.
    
    Args:
        image: PIL Image object
        format: Output format (default: JPEG)
        
    Returns:
        Image bytes
    """
    img_bytes = io.BytesIO()
    image.save(img_bytes, format=format)
    return img_bytes.getvalue()


def process_pdf_test(pdf_path: str) -> None:
    """
    Process a PDF file and print analysis results to console.
    
    Args:
        pdf_path: Path to the PDF file
    """
    pdf_file = Path(pdf_path)
    
    if not pdf_file.exists():
        print(f"Error: PDF file not found: {pdf_path}")
        return
    
    print("=" * 80)
    print(f"Processing PDF: {pdf_file.name}")
    print("=" * 80)
    print()
    
    try:
        # Convert PDF to images
        print("Converting PDF to images...")
        images = convert_from_path(
            str(pdf_file),
            dpi=300,
            fmt='jpeg'
        )
        
        page_count = len(images)
        print(f"✓ Converted {page_count} pages to images")
        print()
        
        # Process each page
        for page_num, image in enumerate(images, start=1):
            print("-" * 80)
            print(f"PAGE {page_num} / {page_count}")
            print("-" * 80)
            
            try:
                # Convert PIL Image to bytes
                image_bytes = pil_image_to_bytes(image)
                
                # Analyze page
                print(f"Analyzing page {page_num} with Gemini...")
                analysis = analyze_pdf_page(image_bytes)
                
                # Print results
                print()
                print("📄 SUMMARY:")
                print(f"   {analysis.summary}")
                print()
                
                print("🔑 KEY TERMS:")
                for term in analysis.key_terms:
                    print(f"   • {term}")
                print()
                
                print("❓ EXAM QUESTIONS:")
                for i, question in enumerate(analysis.exam_questions, 1):
                    print(f"   {i}. {question}")
                print()
                
                print("📊 DIAGRAM DESCRIPTION:")
                print(f"   {analysis.diagram_description}")
                print()
                
                # Print JSON representation
                print("📋 JSON OUTPUT:")
                print(json.dumps(analysis.model_dump(), indent=2, ensure_ascii=False))
                print()
                
            except Exception as e:
                print(f"❌ Error processing page {page_num}: {str(e)}")
                print()
                continue
        
        print("=" * 80)
        print("Processing completed!")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python test_pdf_processing.py <path_to_pdf>")
        print()
        print("Example:")
        print("  python test_pdf_processing.py test_lecture.pdf")
        print("  python test_pdf_processing.py ../lectures/marketing_101.pdf")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    process_pdf_test(pdf_path)


if __name__ == "__main__":
    main()
