from app.services.ingestion import clean_text, chunk_text, extract_text_from_file

def test_clean_text():
    dirty = "Hello \x00 world!  \r\n\r\n\r\n\r\nThis is a    test. "
    cleaned = clean_text(dirty)
    assert "\x00" not in cleaned
    assert "\r" not in cleaned
    assert "Hello world!" in cleaned
    assert "This is a test." in cleaned


def test_chunk_text_splitting():
    # Page with 1000 characters
    long_text = "Data point. " * 100
    pages = [(1, long_text)]
    chunks = chunk_text(pages, chunk_size=200, chunk_overlap=50)

    assert len(chunks) > 1
    assert chunks[0]["page_number"] == 1
    assert "content" in chunks[0]
    assert chunks[0]["chunk_index"] == 0
    assert chunks[1]["chunk_index"] == 1


def test_extract_markdown():
    sample_md = b"# Company Rules\n\n- Rule 1: Always write tests.\n- Rule 2: Clean architecture."
    pages = extract_text_from_file(sample_md, "rules.md")
    assert len(pages) == 1
    assert pages[0][0] == 1
    assert "Rule 1: Always write tests." in pages[0][1]
