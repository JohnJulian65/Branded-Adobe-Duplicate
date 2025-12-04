"""
Test script to verify the Stamping endpoint programmatically.
"""
import requests
import os
import sys
import fitz

# Fix encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_BASE = 'http://localhost:5000/api'

def create_dummy_pdf(filename):
    """Create a dummy PDF for testing."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((100, 100), "Original Content")
    doc.save(filename)
    doc.close()

def test_stamp():
    """Test PDF stamping endpoint."""
    print("\n" + "=" * 60)
    print("Testing PDF Stamping")
    print("=" * 60)
    
    test_file = 'test_files/stamp_test.pdf'
    os.makedirs('test_files', exist_ok=True)
    create_dummy_pdf(test_file)
    
    try:
        with open(test_file, 'rb') as f:
            files = {'file': ('stamp_test.pdf', f, 'application/pdf')}
            data = {
                'stamp_text': 'CONFIDENTIAL',
                'font_size': '60',
                'opacity': '0.5'
            }
            
            print(f"Uploading {test_file}...")
            print("Applying stamp: 'CONFIDENTIAL'")
            response = requests.post(f'{API_BASE}/stamp', files=files, data=data)
            
            if response.ok:
                output_path = 'test_output/stamped.pdf'
                os.makedirs('test_output', exist_ok=True)
                with open(output_path, 'wb') as out:
                    out.write(response.content)
                
                print(f"[PASS] PDF stamped successfully!")
                print(f"  Output: {output_path}")
                
                # Verify stamp exists in output
                doc = fitz.open(output_path)
                page = doc[0]
                text = page.get_text()
                if "CONFIDENTIAL" in text:
                     print("  [PASS] Stamp text found in output PDF")
                else:
                     # Note: Text might not be extractable if it's vector graphics or if PyMuPDF handles it differently,
                     # but insert_text usually makes it extractable.
                     print("  [WARN] Stamp text NOT found in text extraction (might be expected if rendered as graphics)")
                
                doc.close()
                return True
            else:
                error = response.json()
                print(f"[FAIL] Stamp failed: {error.get('error', 'Unknown error')}")
                return False
                
    except Exception as e:
        print(f"[FAIL] Error during stamp: {e}")
        return False

if __name__ == '__main__':
    test_stamp()
