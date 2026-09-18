import json
import logging
from typing import List, Dict, Any, AsyncGenerator
from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """คุณคือ DocuMind AI ผู้ช่วยวิเคราะห์และตอบคำถามจากเอกสารระดับองค์กร (Enterprise Document Assistant)
ภารกิจของคุณคือการตอบคำถามของผู้ใช้อย่างกระชับ ถูกต้อง ชัดเจน และตรงประเด็น โดยอิงจาก "ข้อมูลบริบทเอกสาร (Context)" ที่แนบมาด้านล่างนี้เท่านั้น

กฎเหล็กที่คุณต้องปฏิบัติตาม:
1. ตอบคำถามโดยใช้ข้อมูลจาก "ข้อมูลบริบทเอกสาร (Context)" ที่ให้มาเท่านั้น
2. ในคำตอบของคุณ ทุกครั้งที่ยกข้อมูลมาจากเอกสาร ให้ระบุการอ้างอิงท้ายประโยคหรือข้อความนั้นในรูปแบบ: [อ้างอิง: <ชื่อไฟล์>, หน้า <เลขหน้า>]
3. หากคำถามไม่สามารถตอบได้จากข้อมูลบริบทที่ให้มา ให้ตอบอย่างสุภาพว่า "ขออภัยครับ ไม่พบข้อมูลที่เกี่ยวข้องในเอกสารที่อัปโหลดไว้" ห้ามแต่งหรือคาดเดาข้อมูลขึ้นมาเองโดยเด็ดขาด (Anti-hallucination)
4. ตอบด้วยภาษาที่สุภาพ เป็นมืออาชีพ และจัดรูปแบบด้วย Markdown (เช่น หัวข้อ, Bullet point, ตัวหนา) ให้อ่านง่าย

ข้อมูลบริบทเอกสาร (Context):
{context_text}
"""


def build_rag_prompt(query: str, matched_chunks: List[Dict[str, Any]], history: List[Dict[str, str]] = None) -> str:
    """Builds augmented prompt with retrieved context."""
    if not matched_chunks:
        context_text = "(ไม่มีเอกสารที่เกี่ยวข้อง)"
    else:
        context_parts = []
        for i, chunk in enumerate(matched_chunks, 1):
            part = (
                f"--- เอกสารชิ้นที่ {i} ---\n"
                f"ชื่อไฟล์: {chunk['filename']}\n"
                f"หน้าที่: {chunk['page_number']}\n"
                f"ข้อความ:\n{chunk['content']}\n"
            )
            context_parts.append(part)
        context_text = "\n".join(context_parts)

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context_text=context_text)

    prompt = f"{system_prompt}\n\nคำถามของผู้ใช้: {query}\n\nคำตอบ:"
    return prompt


def generate_rag_response_sync(query: str, matched_chunks: List[Dict[str, Any]]) -> str:
    """Non-streaming generation."""
    prompt = build_rag_prompt(query, matched_chunks)

    if not settings.GEMINI_API_KEY:
        if not matched_chunks:
            return "ขออภัยครับ ยังไม่มีเอกสารในระบบ กรุณาอัปโหลดเอกสารก่อนทำการค้นหาครับ"
        top = matched_chunks[0]
        return (
            f"*(โหมดจำลองคำตอบ - ยังไม่ได้ระบุ GEMINI_API_KEY)*\n\n"
            f"ระบบค้นพบบริบทที่ตรงที่สุดจากเอกสาร **{top['filename']}** (หน้าที่ {top['page_number']}):\n\n"
            f"> \"{top['content'][:300]}...\"\n\n"
            f"[อ้างอิง: {top['filename']}, หน้า {top['page_number']}]\n\n"
            f"💡 *ในการใช้งานโมเดลจริง สามารถเพิ่ม `GEMINI_API_KEY` ในไฟล์ `.env` ได้เลยครับ*"
        )

    try:
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        models_to_try = [settings.CHAT_MODEL, "gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.1-flash-lite"]
        seen = set()
        unique_models = [m for m in models_to_try if not (m in seen or seen.add(m))]

        last_err = None
        for m in unique_models:
            try:
                response = client.models.generate_content(
                    model=m,
                    contents=prompt
                )
                if response and response.text:
                    return response.text
            except Exception as e:
                last_err = e
                logger.warning(f"Sync generation failed with model {m}: {e}")

        raise last_err or Exception("All Gemini models failed")
    except Exception as e:
        logger.error(f"Error calling Gemini generate_content: {e}")
        return f"เกิดข้อผิดพลาดในการติดต่อ Gemini API: {str(e)}"


async def stream_rag_response(
    query: str,
    matched_chunks: List[Dict[str, Any]]
) -> AsyncGenerator[str, None]:
    """
    Streams response tokens using Server-Sent Events (SSE) format.
    First yields metadata (citations), then yields text delta chunks.
    """
    # 1. Send Citations event first
    citations = [
        {
            "document_id": c["document_id"],
            "filename": c["filename"],
            "chunk_index": c["chunk_index"],
            "page_number": c["page_number"],
            "similarity_score": c["similarity_score"],
            "snippet": c["content"]
        }
        for c in matched_chunks
    ]
    yield f"event: citations\ndata: {json.dumps(citations, ensure_ascii=False)}\n\n"

    # 2. If no context found
    if not matched_chunks:
        no_doc_msg = "ขออภัยครับ ไม่พบข้อมูลที่เกี่ยวข้องในเอกสารที่อัปโหลดไว้ กรุณาลองตรวจสอบเอกสารหรือเปลี่ยนคำค้นหาครับ"
        yield f"event: delta\ndata: {json.dumps({'text': no_doc_msg}, ensure_ascii=False)}\n\n"
        yield "event: done\ndata: {}\n\n"
        return

    # 3. If no Gemini API key, stream mock typewriter
    if not settings.GEMINI_API_KEY:
        mock_answer = generate_rag_response_sync(query, matched_chunks)
        # Stream word by word
        import asyncio
        words = mock_answer.split(" ")
        for word in words:
            yield f"event: delta\ndata: {json.dumps({'text': word + ' '}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.03)
        yield "event: done\ndata: {}\n\n"
        return

    # 4. Stream from Google GenAI SDK with multi-model resiliency
    prompt = build_rag_prompt(query, matched_chunks)
    try:
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        # Prefer fast & reliable models first
        models_to_try = [settings.CHAT_MODEL, "gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.1-flash-lite"]
        seen = set()
        unique_models = [m for m in models_to_try if not (m in seen or seen.add(m))]
        last_err = None

        for m in unique_models:
            try:
                stream = client.models.generate_content_stream(
                    model=m,
                    contents=prompt
                )
                streamed_any = False
                for chunk in stream:
                    if chunk.text:
                        streamed_any = True
                        yield f"event: delta\ndata: {json.dumps({'text': chunk.text}, ensure_ascii=False)}\n\n"
                
                if streamed_any:
                    yield "event: done\ndata: {}\n\n"
                    return
            except Exception as e:
                last_err = e
                logger.warning(f"Model {m} failed during stream: {e}. Trying fallback model...")

        # If all models failed
        raise last_err or Exception("All Gemini models temporarily unavailable")

    except Exception as e:
        logger.error(f"Error in Gemini streaming: {e}")
        err_msg = f"\n\n[ขออภัย โมเดลกำลังมีผู้ใช้งานหนาแน่น กรุณาลองใหม่อีกครั้ง: {str(e)}]"
        yield f"event: delta\ndata: {json.dumps({'text': err_msg}, ensure_ascii=False)}\n\n"
        yield "event: done\ndata: {}\n\n"
