import io

def test_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "app" in data


def test_upload_and_query_flow(client):
    # 1. Upload a markdown policy document
    content = b"# Remote Work Policy\nEmployees can work from home 3 days a week. Core hours are 10:00 to 16:00."
    file_payload = {"file": ("policy.md", io.BytesIO(content), "text/markdown")}

    upload_res = client.post("/api/v1/documents/upload", files=file_payload)
    assert upload_res.status_code == 202
    doc_data = upload_res.json()
    doc_id = doc_data["id"]
    assert doc_data["filename"] == "policy.md"

    # 2. Verify document in document list
    list_res = client.get("/api/v1/documents")
    assert list_res.status_code == 200
    docs = list_res.json()
    assert any(d["id"] == doc_id for d in docs)

    # 3. Ask a question via RAG chat
    chat_res = client.post(
        "/api/v1/chat",
        json={"query": "Can employees work from home?", "stream": False}
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert "answer" in chat_data
    assert "citations" in chat_data
