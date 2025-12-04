"""
Quick test script to debug the redaction endpoint
"""
import fitz
import io

# Create a simple test PDF
doc = fitz.open()
page = doc.new_page()
page.insert_text((100, 100), "This is a test document with test text.")
page.insert_text((100, 150), "Another test line here.")

# Save to bytes
pdf_bytes = doc.tobytes()
doc.close()

# Now try to redact it
doc = fitz.open(stream=pdf_bytes, filetype="pdf")

search_text = "test"
case_sensitive = False
total_redactions = 0

for page in doc:
    search_flags = 0 if not case_sensitive else fitz.TEXT_PRESERVE_WHITESPACE
    text_instances = page.search_for(search_text, flags=search_flags)
    
    print(f"Page {page.number}: Found {len(text_instances)} instances of '{search_text}'")
    
    for inst in text_instances:
        print(f"  Instance: {inst}")
        annot = page.add_redact_annot(inst, fill=(0, 0, 0))
        total_redactions += 1
    
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE)

print(f"\nTotal redactions: {total_redactions}")

# Save result
output = io.BytesIO()
output.write(doc.tobytes())
doc.close()
output.seek(0)

print(f"Output size: {len(output.getvalue())} bytes")
print("Test completed successfully!")
