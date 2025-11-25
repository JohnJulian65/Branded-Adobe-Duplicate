"""
Agent PDF Utility - Flask Backend Server

This server provides four PDF manipulation endpoints:
1. /api/merge - Merge multiple PDF files into one
2. /api/split - Extract specific pages from a PDF
3. /api/convert - Convert PDF pages to PNG images in a ZIP file
4. /api/redact - Search and redact text with secure content removal

Libraries used:
- Flask: Web framework
- PyMuPDF (fitz): Advanced PDF manipulation and rendering
"""

from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import fitz  # PyMuPDF
import io
import zipfile
import re

app = Flask(__name__)
CORS(app)  # Enable CORS for local development

# Maximum file size: 50MB
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024


def validate_pdf(file_data):
    """
    Validate that the uploaded file is a valid PDF.
    
    Args:
        file_data: Binary file data
        
    Returns:
        bool: True if valid PDF, False otherwise
    """
    try:
        # Check PDF magic number (first 4 bytes should be %PDF)
        if not file_data.startswith(b'%PDF'):
            return False
        # Try to open it with PyMuPDF
        fitz.open(stream=file_data, filetype="pdf")
        return True
    except Exception:
        return False


def parse_page_ranges(range_string, max_pages):
    """
    Parse a page range string like "1-3, 5, 7-9" into a list of page numbers.
    
    Args:
        range_string: String containing page ranges (e.g., "1-3, 5, 7-9")
        max_pages: Maximum number of pages in the PDF
        
    Returns:
        list: Sorted list of page numbers (0-indexed)
        
    Raises:
        ValueError: If range is invalid
    """
    pages = set()
    
    # Remove whitespace
    range_string = range_string.replace(' ', '')
    
    # Split by comma
    parts = range_string.split(',')
    
    for part in parts:
        if '-' in part:
            # Range like "1-3"
            start, end = part.split('-')
            try:
                start = int(start)
                end = int(end)
            except ValueError:
                raise ValueError(f"Invalid range format: {part}")
            
            if start < 1 or end > max_pages or start > end:
                raise ValueError(f"Invalid range {start}-{end}. PDF has {max_pages} pages.")
            
            # Convert to 0-indexed and add to set
            pages.update(range(start - 1, end))
        else:
            # Single page like "5"
            try:
                page = int(part)
            except ValueError:
                raise ValueError(f"Invalid page number: {part}")
            
            if page < 1 or page > max_pages:
                raise ValueError(f"Page {page} is out of range. PDF has {max_pages} pages.")
            
            # Convert to 0-indexed
            pages.add(page - 1)
    
    return sorted(list(pages))


@app.route('/api/merge', methods=['POST'])
def merge_pdfs():
    """
    Merge multiple PDF files into a single PDF using PyMuPDF.
    
    Expected: Multiple files in the request with key 'files[]'
    Returns: Single merged PDF file
    """
    try:
        # Get uploaded files
        files = request.files.getlist('files[]')
        
        if len(files) < 2:
            return jsonify({'error': 'At least 2 PDF files are required for merging'}), 400
        
        # Create a new PDF document
        merged_doc = fitz.open()
        
        # Process each uploaded file
        for idx, file in enumerate(files):
            file_data = file.read()
            
            # Validate PDF
            if not validate_pdf(file_data):
                merged_doc.close()
                return jsonify({'error': f'File {idx + 1} is not a valid PDF'}), 400
            
            # Open PDF and insert all pages
            src_doc = fitz.open(stream=file_data, filetype="pdf")
            merged_doc.insert_pdf(src_doc)
            src_doc.close()
        
        # Save merged PDF to bytes
        output = io.BytesIO()
        output.write(merged_doc.tobytes())
        merged_doc.close()
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='merged.pdf'
        )
    
    except Exception as e:
        print(f"Error in merge_pdfs: {str(e)}")
        return jsonify({'error': f'Failed to merge PDFs: {str(e)}'}), 500


@app.route('/api/split', methods=['POST'])
def split_pdf():
    """
    Extract specific pages from a PDF based on page range using PyMuPDF.
    
    Expected: 
        - 'file': PDF file
        - 'pages': Page range string (e.g., "1-3, 5, 7-9")
    Returns: New PDF with only specified pages
    """
    try:
        # Get uploaded file
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        file_data = file.read()
        
        # Validate PDF
        if not validate_pdf(file_data):
            return jsonify({'error': 'Uploaded file is not a valid PDF'}), 400
        
        # Get page range
        page_range = request.form.get('pages', '')
        if not page_range:
            return jsonify({'error': 'Page range is required'}), 400
        
        # Open PDF
        src_doc = fitz.open(stream=file_data, filetype="pdf")
        total_pages = src_doc.page_count
        
        # Parse page ranges
        try:
            pages_to_extract = parse_page_ranges(page_range, total_pages)
        except ValueError as e:
            src_doc.close()
            return jsonify({'error': str(e)}), 400
        
        if not pages_to_extract:
            src_doc.close()
            return jsonify({'error': 'No valid pages specified'}), 400
        
        # Create new PDF with selected pages using select()
        src_doc.select(pages_to_extract)
        
        # Save to bytes
        output = io.BytesIO()
        output.write(src_doc.tobytes())
        src_doc.close()
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='split.pdf'
        )
    
    except Exception as e:
        print(f"Error in split_pdf: {str(e)}")
        return jsonify({'error': f'Failed to split PDF: {str(e)}'}), 500


@app.route('/api/convert', methods=['POST'])
def convert_to_images():
    """
    Convert each page of a PDF to a PNG image using PyMuPDF rendering.
    
    Expected: 'file': PDF file
    Returns: ZIP file containing PNG images of each page
    """
    try:
        # Get uploaded file
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        file_data = file.read()
        
        # Validate PDF
        if not validate_pdf(file_data):
            return jsonify({'error': 'Uploaded file is not a valid PDF'}), 400
        
        # Open PDF with PyMuPDF
        doc = fitz.open(stream=file_data, filetype="pdf")
        
        # Create ZIP file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Render each page to PNG
            for page_num in range(doc.page_count):
                page = doc[page_num]
                
                # Render page to pixmap (raster image) at 200 DPI
                # zoom = 200/72 = 2.78 (72 DPI is default)
                mat = fitz.Matrix(2.78, 2.78)
                pix = page.get_pixmap(matrix=mat)
                
                # Convert pixmap to PNG bytes
                img_bytes = pix.tobytes("png")
                
                # Add to ZIP with numbered filename
                zip_file.writestr(f'page_{page_num + 1}.png', img_bytes)
        
        doc.close()
        zip_buffer.seek(0)
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='pdf_images.zip'
        )
    
    except Exception as e:
        print(f"Error in convert_to_images: {str(e)}")
        return jsonify({'error': f'Failed to convert PDF: {str(e)}'}), 500


@app.route('/api/redact', methods=['POST'])
def redact_pdf():
    """
    Search for text in PDF and redact all instances with secure content removal.
    
    Expected:
        - 'file': PDF file
        - 'search_text': Text string to find and redact
        - 'case_sensitive': Boolean (optional, default: false)
    Returns: PDF with redacted content (black rectangles, content permanently removed)
    """
    try:
        # Get uploaded file
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        file_data = file.read()
        
        # Validate PDF
        if not validate_pdf(file_data):
            return jsonify({'error': 'Uploaded file is not a valid PDF'}), 400
        
        # Get search parameters
        search_text = request.form.get('search_text', '').strip()
        if not search_text:
            return jsonify({'error': 'Search text is required'}), 400
        
        case_sensitive = request.form.get('case_sensitive', 'false').lower() == 'true'
        
        # Open PDF
        doc = fitz.open(stream=file_data, filetype="pdf")
        
        total_redactions = 0
        
        # Iterate through all pages
        for page in doc:
            # Search for text instances
            # flags: 0 for case-insensitive, fitz.TEXT_PRESERVE_WHITESPACE for case-sensitive
            search_flags = 0 if not case_sensitive else fitz.TEXT_PRESERVE_WHITESPACE
            
            # Find all text instances (returns list of Quad objects)
            text_instances = page.search_for(search_text, flags=search_flags)
            
            # Add redaction annotation for each instance
            for inst in text_instances:
                # inst is a Rect object with the text location
                annot = page.add_redact_annot(inst, fill=(0, 0, 0))  # Black fill
                total_redactions += 1
            
            # Apply all redactions on this page
            # This permanently removes the content
            page.apply_redactions(
                images=fitz.PDF_REDACT_IMAGE_REMOVE,  # Remove redacted parts of images
                graphics=fitz.PDF_REDACT_LINE_ART_IF_TOUCHED  # Remove affected graphics
            )
        
        # Save redacted PDF to bytes
        output = io.BytesIO()
        output.write(doc.tobytes())
        doc.close()
        output.seek(0)
        
        # Create response with custom header indicating number of redactions
        response = send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='redacted.pdf'
        )
        response.headers['X-Redaction-Count'] = str(total_redactions)
        
        return response
    
    except Exception as e:
        print(f"Error in redact_pdf: {str(e)}")
        return jsonify({'error': f'Failed to redact PDF: {str(e)}'}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint to verify server is running."""
    return jsonify({
        'status': 'healthy', 
        'message': 'Agent PDF Utility server is running',
        'backend': 'PyMuPDF (fitz)',
        'features': ['merge', 'split', 'convert', 'redact']
    }), 200


if __name__ == '__main__':
    print("=" * 60)
    print("Agent PDF Utility Server (PyMuPDF Edition)")
    print("=" * 60)
    print("Server starting on http://localhost:5000")
    print("\nAvailable endpoints:")
    print("  POST /api/merge   - Merge multiple PDFs")
    print("  POST /api/split   - Extract pages from PDF")
    print("  POST /api/convert - Convert PDF to images")
    print("  POST /api/redact  - Redact text from PDF")
    print("  GET  /health      - Health check")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
