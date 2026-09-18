import io
import re
import hashlib
import logging
from typing import List, Dict, Any, Tuple
import numpy as np
from pypdf import PdfReader
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize GenAI Client if API key is provided
genai_client = None
if settings.GEMINI_API_KEY:
    try:
        from google import genai
        genai_client = genai.Client(api_key=settings.GEMINI_API_KEY)
    except Exception as e:
        logger.warning(f"Could not initialize GenAI Client: {e}")


def extract_text_from_file(file_bytes: bytes, filename: str) -> List[Tuple[int, str]]:
    """
    Extracts text from uploaded file bytes.
    Returns a list of tuples: (page_number, text_content).
    """
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    pages_text = []

    if ext == "pdf":
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            for idx, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                clean = clean_text(text)
                if clean:
                    pages_text.append((idx + 1, clean))
        except Exception as e:
            logger.error(f"Error reading PDF {filename}: {e}")
            raise ValueError(f"Failed to parse PDF: {str(e)}")
    else:
        # Markdown or Plain Text
        try:
            text = file_bytes.decode("utf-8", errors="ignore")
            clean = clean_text(text)
            if clean:
                pages_text.append((1, clean))
        except Exception as e:
            logger.error(f"Error reading text file {filename}: {e}")
            raise ValueError(f"Failed to parse text file: {str(e)}")

    return pages_text


def clean_text(text: str) -> str:
    """Removes irregular whitespaces, null bytes and excess empty lines."""
    text = text.replace("\x00", "")
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def chunk_text(
    pages_text: List[Tuple[int, str]],
    chunk_size: int = settings.CHUNK_SIZE,
    chunk_overlap: int = settings.CHUNK_OVERLAP
) -> List[Dict[str, Any]]:
    """
    Recursive character text chunker with overlap and page tracking.
    """
    chunks = []
    chunk_idx = 0

    for page_num, text in pages_text:
        if len(text) <= chunk_size:
            chunks.append({
                "chunk_index": chunk_idx,
                "page_number": page_num,
                "content": text,
                "char_count": len(text)
            })
            chunk_idx += 1
            continue

        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            
            # If not at the end of the text, try to find a natural break point
            if end < len(text):
                break_point = max(
                    text.rfind("\n\n", start, end),
                    text.rfind("\n", start, end),
                    text.rfind(". ", start, end),
                    text.rfind(" ", start, end)
                )
                if break_point > start + (chunk_size // 2):
                    end = break_point + 1

            chunk_content = text[start:end].strip()
            if chunk_content:
                chunks.append({
                    "chunk_index": chunk_idx,
                    "page_number": page_num,
                    "content": chunk_content,
                    "char_count": len(chunk_content)
                })
                chunk_idx += 1

            # Advance start pointer with overlap
            if end >= len(text):
                break
            start = max(start + 1, end - chunk_overlap)

    return chunks


def get_mock_embedding(text: str, dim: int = 768) -> List[float]:
    """Generates a deterministic normalized pseudo-embedding for testing or zero-key mode."""
    # Hash the text to seed a pseudo-random generator
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generates vector embeddings for a list of text strings using Gemini Embeddings API.
    Falls back to deterministic normalized embeddings if API key is not configured or in offline mode.
    """
    global genai_client
    # Refresh client if API key was updated at runtime
    if not genai_client and settings.GEMINI_API_KEY:
        try:
            from google import genai
            genai_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        except Exception:
            pass

    if not genai_client or not settings.GEMINI_API_KEY:
        logger.info("Using deterministic local embeddings (GEMINI_API_KEY not set).")
        return [get_mock_embedding(t) for t in texts]

    import time
    try:
        from google.genai import types
        all_embeddings = []
        batch_size = 20

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = genai_client.models.embed_content(
                model=settings.EMBEDDING_MODEL,
                contents=batch,
                config=types.EmbedContentConfig(output_dimensionality=768)
            )
            if hasattr(response, "embeddings") and response.embeddings:
                for emb in response.embeddings:
                    all_embeddings.append(emb.values)
            elif hasattr(response, "embedding") and response.embedding:
                all_embeddings.append(response.embedding.values)
            
            if len(texts) > batch_size:
                time.sleep(0.3)

        # Pad with mock embeddings if any discrepancy
        if len(all_embeddings) < len(texts):
            for i in range(len(all_embeddings), len(texts)):
                all_embeddings.append(get_mock_embedding(texts[i]))

        return all_embeddings

    except Exception as e:
        logger.error(f"Gemini embedding API call failed: {e}. Falling back to mock embeddings.")
        return [get_mock_embedding(t) for t in texts]
