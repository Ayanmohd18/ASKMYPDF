"""
Tests for the PDF ingestion module.
"""
import pytest
from pathlib import Path
from app.ingestion import extract_pages, semantic_chunk, ingest_pdf, ingest_multiple
from reportlab.pdfgen import canvas
import uuid

@pytest.fixture
def temp_pdf_dir(tmp_path: Path) -> Path:
    """Fixture providing a temporary directory for PDF generation."""
    return tmp_path

def create_synthetic_pdf(path: Path, pages: int, sentences_per_page: int) -> None:
    """
    Helper to generate a synthetic PDF with specific content.
    
    Args:
        path: Where to save the PDF.
        pages: Number of pages to generate.
        sentences_per_page: Number of sentences per page.
    """
    c = canvas.Canvas(str(path))
    for p in range(pages):
        y = 800
        for i in range(sentences_per_page):
            c.drawString(50, y, "This is a synthetic sentence for testing purposes. ")
            y -= 15
            if y < 50:
                break  # simple boundary check
        c.showPage()
    c.save()

def test_extract_pages(temp_pdf_dir: Path) -> None:
    """Test extracting pages from a 3-page PDF."""
    pdf_path = temp_pdf_dir / "test_extract.pdf"
    create_synthetic_pdf(pdf_path, 3, 5)
    
    pages = extract_pages(pdf_path)
    assert len(pages) == 3
    for i, page in enumerate(pages):
        assert "page_number" in page
        assert "text" in page
        assert "doc_name" in page
        assert page["page_number"] == i + 1
        assert page["doc_name"] == "test_extract"
        assert len(page["text"]) > 20

def test_semantic_chunk_fields(temp_pdf_dir: Path) -> None:
    """Test that all required fields are present in the chunk objects."""
    pdf_path = temp_pdf_dir / "test_fields.pdf"
    create_synthetic_pdf(pdf_path, 2, 20)
    
    chunks = ingest_pdf(pdf_path)
    assert len(chunks) > 0
    for chunk in chunks:
        assert isinstance(chunk.chunk_id, str)
        # Validate uuid
        uuid.UUID(chunk.chunk_id)
        assert isinstance(chunk.doc_name, str)
        assert chunk.doc_name == "test_fields"
        assert isinstance(chunk.page_number, int)
        assert chunk.page_number >= 1
        assert isinstance(chunk.text, str)
        assert len(chunk.text) > 0
        assert isinstance(chunk.token_count, int)
        assert chunk.token_count > 0

def test_chunk_token_limit(temp_pdf_dir: Path) -> None:
    """Test that chunks do not exceed the token limit."""
    pdf_path = temp_pdf_dir / "test_limit.pdf"
    create_synthetic_pdf(pdf_path, 1, 50)
    
    pages = extract_pages(pdf_path)
    # Using 100 max tokens to ensure we get a few chunks out of 50 sentences
    chunks = semantic_chunk(pages, max_tokens=100)
    
    for chunk in chunks:
        # Check against a small tolerance due to sentence boundary tokenization
        assert chunk.token_count <= 130

def test_ingest_multiple(temp_pdf_dir: Path) -> None:
    """Test ingesting multiple PDFs at once."""
    paths = []
    for i in range(3):
        p = temp_pdf_dir / f"test_multi_{i}.pdf"
        create_synthetic_pdf(p, 1, 5)
        paths.append(p)
        
    all_chunks = ingest_multiple(paths)
    assert len(all_chunks) > 0
    
    doc_names = set(chunk.doc_name for chunk in all_chunks)
    assert len(doc_names) == 3
    for i in range(3):
        assert f"test_multi_{i}" in doc_names
