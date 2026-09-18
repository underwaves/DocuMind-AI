// DocuMind AI Frontend Application Controller
document.addEventListener("DOMContentLoaded", () => {
    // Elements
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("file-input");
    const uploadStatus = document.getElementById("upload-status");
    const uploadStatusText = document.getElementById("upload-status-text");
    const docList = document.getElementById("document-list");
    const docCount = document.getElementById("doc-count");
    const refreshDocsBtn = document.getElementById("refresh-docs-btn");
    const chatContainer = document.getElementById("chat-container");
    const chatForm = document.getElementById("chat-form");
    const queryInput = document.getElementById("query-input");
    const sendBtn = document.getElementById("send-btn");
    const clearChatBtn = document.getElementById("clear-chat-btn");
    const welcomeCard = document.getElementById("welcome-card");
    const vectorStatus = document.getElementById("vector-status");

    const apiKeyModalBtn = document.getElementById("api-key-modal-btn");
    const apiKeyBtnText = document.getElementById("api-key-btn-text");
    const apiKeyModal = document.getElementById("api-key-modal");
    const closeModalBtn = document.getElementById("close-modal-btn");
    const cancelModalBtn = document.getElementById("cancel-modal-btn");
    const saveApiKeyBtn = document.getElementById("save-api-key-btn");
    const apiKeyInput = document.getElementById("api-key-input");
    const modalAlert = document.getElementById("modal-alert");
    const llmStatus = document.getElementById("llm-status");

    let isStreaming = false;
    let pollInterval = null;

    // 1. Initial Health & API Key Status Check
    async function checkSystemHealth() {
        try {
            const res = await fetch("/health");
            if (res.ok) {
                const data = await res.json();
                vectorStatus.textContent = data.pgvector_active ? "PostgreSQL (pgvector)" : "SQLite (Local Vector)";
                vectorStatus.className = data.pgvector_active ? "text-emerald-400 font-mono" : "text-amber-400 font-mono";
            }
        } catch (err) {
            vectorStatus.textContent = "Offline";
            vectorStatus.className = "text-rose-400 font-mono";
        }

        try {
            const res = await fetch("/api/v1/settings/status");
            if (res.ok) {
                const settings = await res.json();
                if (settings.has_api_key) {
                    apiKeyBtnText.textContent = "Gemini API เชื่อมต่อแล้ว ✓";
                    apiKeyModalBtn.className = "text-xs px-3 py-1.5 rounded-lg border border-emerald-700/80 bg-emerald-950/40 hover:bg-emerald-900/60 text-emerald-300 transition flex items-center gap-1.5";
                    if (llmStatus) {
                        llmStatus.textContent = "Gemini 3.8 Flash (Active)";
                        llmStatus.className = "font-mono text-emerald-400";
                    }
                } else {
                    apiKeyBtnText.textContent = "ใส่ Gemini API Key ⚠️";
                    apiKeyModalBtn.className = "text-xs px-3 py-1.5 rounded-lg border border-amber-600/80 bg-amber-950/40 hover:bg-amber-900/60 text-amber-300 transition flex items-center gap-1.5";
                    if (llmStatus) {
                        llmStatus.textContent = "Mock Mode (ใส่ Key เพื่อใช้จริง)";
                        llmStatus.className = "font-mono text-amber-400";
                    }
                }
            }
        } catch (e) {
            console.error("Could not fetch settings status:", e);
        }
    }

    // 2. Fetch and Render Documents
    async function loadDocuments() {
        try {
            const res = await fetch("/api/v1/documents");
            if (!res.ok) return;
            const docs = await res.json();

            docCount.textContent = docs.length;

            if (docs.length === 0) {
                docList.innerHTML = `
                    <div class="text-center py-10 text-slate-500 text-sm">
                        <i class="fa-solid fa-folder-open text-2xl mb-2 block opacity-40"></i>
                        ยังไม่มีเอกสารในระบบ
                    </div>
                `;
                return;
            }

            docList.innerHTML = "";
            let hasProcessing = false;

            docs.forEach(doc => {
                if (doc.status === "PROCESSING") hasProcessing = true;

                const card = document.createElement("div");
                card.className = "p-3 rounded-xl bg-slate-800/60 border border-slate-700/60 hover:border-slate-600 transition flex items-start justify-between group";

                const icon = doc.file_type === "pdf" ? "fa-file-pdf text-rose-400" : "fa-file-lines text-indigo-400";
                
                let badgeColor = "bg-amber-500/10 text-amber-400 border-amber-500/30";
                let badgeText = "กำลังประมวลผล...";
                let badgeIcon = '<i class="fa-solid fa-spinner fa-spin mr-1"></i>';

                if (doc.status === "READY") {
                    badgeColor = "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
                    badgeText = `${doc.chunk_count} ชิ้นส่วน (Chunks)`;
                    badgeIcon = '<i class="fa-solid fa-check mr-1"></i>';
                } else if (doc.status === "FAILED") {
                    badgeColor = "bg-rose-500/10 text-rose-400 border-rose-500/30";
                    badgeText = "เกิดข้อผิดพลาด";
                    badgeIcon = '<i class="fa-solid fa-triangle-exclamation mr-1"></i>';
                }

                const sizeKB = Math.round(doc.file_size / 1024);

                card.innerHTML = `
                    <div class="flex items-start space-x-3 overflow-hidden">
                        <div class="mt-0.5 text-lg">
                            <i class="fa-solid ${icon}"></i>
                        </div>
                        <div class="overflow-hidden">
                            <h4 class="text-xs font-semibold text-slate-200 truncate max-w-[170px]" title="${doc.filename}">${doc.filename}</h4>
                            <p class="text-[10px] text-slate-400">${sizeKB} KB</p>
                            <span class="inline-flex items-center text-[10px] px-2 py-0.5 rounded-md border ${badgeColor} mt-1">
                                ${badgeIcon} ${badgeText}
                            </span>
                        </div>
                    </div>
                    <button data-id="${doc.id}" class="delete-doc-btn text-slate-500 hover:text-rose-400 opacity-0 group-hover:opacity-100 p-1.5 transition" title="ลบเอกสาร">
                        <i class="fa-solid fa-trash-can text-xs"></i>
                    </button>
                `;

                docList.appendChild(card);
            });

            // Bind delete buttons
            document.querySelectorAll(".delete-doc-btn").forEach(btn => {
                btn.addEventListener("click", async (e) => {
                    const id = e.currentTarget.getAttribute("data-id");
                    if (confirm("คุณแน่ใจว่าต้องการลบเอกสารนี้?")) {
                        await deleteDocument(id);
                    }
                });
            });

            // Auto poll if processing
            if (hasProcessing && !pollInterval) {
                pollInterval = setInterval(loadDocuments, 2000);
            } else if (!hasProcessing && pollInterval) {
                clearInterval(pollInterval);
                pollInterval = null;
            }

        } catch (err) {
            console.error("Error loading documents:", err);
        }
    }

    // 3. Delete Document
    async function deleteDocument(docId) {
        try {
            const res = await fetch(`/api/v1/documents/${docId}`, { method: "DELETE" });
            if (res.ok) {
                loadDocuments();
            }
        } catch (err) {
            console.error("Failed to delete document:", err);
        }
    }

    // 4. File Upload Handlers
    dropzone.addEventListener("click", () => fileInput.click());
    
    dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.classList.add("border-indigo-500", "bg-indigo-500/10");
    });

    dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("border-indigo-500", "bg-indigo-500/10");
    });

    dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("border-indigo-500", "bg-indigo-500/10");
        if (e.dataTransfer.files.length > 0) {
            uploadFile(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            uploadFile(e.target.files[0]);
        }
    });

    async function uploadFile(file) {
        uploadStatus.classList.remove("hidden");
        uploadStatusText.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-indigo-400"></i> กำลังอัปโหลด "${file.name}"...`;

        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await fetch("/api/v1/documents/upload", {
                method: "POST",
                body: formData
            });

            if (res.ok) {
                uploadStatusText.innerHTML = `<i class="fa-solid fa-check text-emerald-400"></i> เริ่มประมวลผล "${file.name}" เรียบร้อย`;
                setTimeout(() => uploadStatus.classList.add("hidden"), 3000);
                fileInput.value = "";
                loadDocuments();
            } else {
                const errData = await res.json();
                uploadStatusText.innerHTML = `<i class="fa-solid fa-circle-xmark text-rose-400"></i> ผิดพลาด: ${errData.detail || "Upload failed"}`;
            }
        } catch (err) {
            uploadStatusText.innerHTML = `<i class="fa-solid fa-circle-xmark text-rose-400"></i> เชื่อมต่อล้มเหลว`;
        }
    }

    refreshDocsBtn.addEventListener("click", loadDocuments);

    // 5. Chat Interaction & SSE Streaming
    queryInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event("submit"));
        }
    });

    // Auto-expand textarea
    queryInput.addEventListener("input", function() {
        this.style.height = "auto";
        this.style.height = (this.scrollHeight) + "px";
    });

    // Click sample prompts
    document.querySelectorAll(".sample-prompt").forEach(card => {
        card.addEventListener("click", () => {
            const text = card.querySelector("p:last-child").textContent.replace(/"/g, "");
            queryInput.value = text;
            queryInput.dispatchEvent(new Event("input"));
            queryInput.focus();
        });
    });

    clearChatBtn.addEventListener("click", () => {
        chatContainer.innerHTML = "";
        if (welcomeCard) chatContainer.appendChild(welcomeCard);
    });

    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const query = queryInput.value.trim();
        if (!query || isStreaming) return;

        // Hide welcome banner if visible
        if (welcomeCard && welcomeCard.parentElement) {
            welcomeCard.remove();
        }

        // 1. Append User Message
        appendUserMessage(query);
        queryInput.value = "";
        queryInput.style.height = "auto";

        // 2. Prepare Assistant Message container
        const assistantElements = createAssistantMessageContainer();
        chatContainer.scrollTop = chatContainer.scrollHeight;

        // 3. Initiate SSE Streaming
        isStreaming = true;
        sendBtn.disabled = true;

        try {
            const response = await fetch("/api/v1/chat/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query: query, stream: true })
            });

            if (!response.ok) {
                assistantElements.textEl.textContent = `เกิดข้อผิดพลาด (${response.status}): ไม่สามารถดึงคำตอบได้`;
                assistantElements.textEl.classList.remove("streaming-cursor");
                return;
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let accumulatedText = "";
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n\n");
                buffer = lines.pop(); // keep last incomplete line

                for (const line of lines) {
                    if (!line.trim()) continue;

                    const eventMatch = line.match(/^event:\s*(\w+)/m);
                    const dataMatch = line.match(/^data:\s*(.*)/m);

                    const event = eventMatch ? eventMatch[1] : "delta";
                    const dataStr = dataMatch ? dataMatch[1] : "";

                    if (event === "citations") {
                        try {
                            const citations = JSON.parse(dataStr);
                            renderCitations(assistantElements.citationsEl, citations);
                        } catch (e) {
                            console.error("Error parsing citations:", e);
                        }
                    } else if (event === "delta") {
                        try {
                            const data = JSON.parse(dataStr);
                            if (data.text) {
                                accumulatedText += data.text;
                                assistantElements.textEl.innerHTML = marked.parse(accumulatedText);
                                chatContainer.scrollTop = chatContainer.scrollHeight;
                            }
                        } catch (e) {
                            accumulatedText += dataStr;
                            assistantElements.textEl.innerHTML = marked.parse(accumulatedText);
                        }
                    } else if (event === "done") {
                        assistantElements.textEl.classList.remove("streaming-cursor");
                    }
                }
            }

            assistantElements.textEl.classList.remove("streaming-cursor");

        } catch (err) {
            console.error("Streaming error:", err);
            assistantElements.textEl.textContent = `เกิดข้อผิดพลาดในการเชื่อมต่อ: ${err.message}`;
            assistantElements.textEl.classList.remove("streaming-cursor");
        } finally {
            isStreaming = false;
            sendBtn.disabled = false;
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    });

    function appendUserMessage(text) {
        const row = document.createElement("div");
        row.className = "flex justify-end";
        row.innerHTML = `
            <div class="max-w-xl md:max-w-2xl bg-gradient-to-r from-indigo-600 to-indigo-700 text-white rounded-2xl rounded-tr-none px-5 py-3 shadow-lg shadow-indigo-500/10">
                <p class="text-sm leading-relaxed whitespace-pre-wrap">${escapeHtml(text)}</p>
            </div>
        `;
        chatContainer.appendChild(row);
    }

    function createAssistantMessageContainer() {
        const row = document.createElement("div");
        row.className = "flex items-start space-x-3 max-w-3xl";

        const avatar = `
            <div class="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center text-white flex-shrink-0 text-xs shadow-md mt-1">
                <i class="fa-solid fa-brain"></i>
            </div>
        `;

        const contentBox = document.createElement("div");
        contentBox.className = "flex-1 bg-slate-900/90 border border-slate-800/90 rounded-2xl rounded-tl-none p-5 shadow-xl";

        const textEl = document.createElement("div");
        textEl.className = "prose-chat streaming-cursor text-slate-200 text-sm";
        textEl.textContent = "";

        const citationsEl = document.createElement("div");
        citationsEl.className = "mt-4 pt-3 border-t border-slate-800/80 hidden";

        contentBox.appendChild(textEl);
        contentBox.appendChild(citationsEl);

        row.innerHTML = avatar;
        row.appendChild(contentBox);

        chatContainer.appendChild(row);

        return { textEl, citationsEl };
    }

    function renderCitations(container, citations) {
        if (!citations || citations.length === 0) return;

        container.classList.remove("hidden");
        container.innerHTML = `
            <div class="flex items-center gap-1.5 text-xs font-semibold text-slate-400 mb-2">
                <i class="fa-solid fa-bookmark text-indigo-400"></i> แหล่งข้อมูลอ้างอิง (${citations.length})
            </div>
            <div class="flex flex-wrap gap-2">
                ${citations.map((c, i) => `
                    <div class="px-2.5 py-1 rounded-lg bg-slate-800 border border-slate-700 text-[11px] text-slate-300 flex items-center gap-2 hover:border-indigo-500 transition cursor-help" title="${escapeHtml(c.snippet)}">
                        <span class="font-medium text-indigo-300">${i + 1}. ${escapeHtml(c.filename)} (น. ${c.page_number})</span>
                        <span class="text-[10px] px-1.5 py-0.2 rounded bg-indigo-950/60 text-indigo-400 border border-indigo-800 font-mono">
                            ${Math.round(c.similarity_score * 100)}% Match
                        </span>
                    </div>
                `).join("")}
            </div>
        `;
    }

    function escapeHtml(string) {
        const entityMap = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        };
        return String(string).replace(/[&<>"']/g, (s) => entityMap[s]);
    }

    // 6. API Key Modal Controls
    if (apiKeyModalBtn) {
        apiKeyModalBtn.addEventListener("click", () => {
            modalAlert.classList.add("hidden");
            apiKeyModal.classList.remove("hidden");
            apiKeyInput.focus();
        });
    }

    if (closeModalBtn) {
        closeModalBtn.addEventListener("click", () => apiKeyModal.classList.add("hidden"));
    }
    if (cancelModalBtn) {
        cancelModalBtn.addEventListener("click", () => apiKeyModal.classList.add("hidden"));
    }

    if (saveApiKeyBtn) {
        saveApiKeyBtn.addEventListener("click", async () => {
            const key = apiKeyInput.value.trim();
            if (!key) {
                modalAlert.textContent = "กรุณากรอก API Key ก่อนบันทึก";
                modalAlert.className = "text-xs p-2.5 rounded-lg bg-rose-500/20 text-rose-300 border border-rose-500/40 block";
                return;
            }

            saveApiKeyBtn.disabled = true;
            saveApiKeyBtn.textContent = "กำลังบันทึก...";

            try {
                const res = await fetch("/api/v1/settings/api-key", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ api_key: key })
                });

                if (res.ok) {
                    modalAlert.textContent = "บันทึกสำเร็จ! เชื่อมต่อ Gemini เรียบร้อยแล้ว";
                    modalAlert.className = "text-xs p-2.5 rounded-lg bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 block";
                    setTimeout(() => {
                        apiKeyModal.classList.add("hidden");
                        apiKeyInput.value = "";
                        saveApiKeyBtn.disabled = false;
                        saveApiKeyBtn.textContent = "บันทึก & ใช้งาน";
                        checkSystemHealth();
                    }, 1200);
                } else {
                    const err = await res.json();
                    modalAlert.textContent = "ผิดพลาด: " + (err.detail || "ไม่สามารถบันทึกได้");
                    modalAlert.className = "text-xs p-2.5 rounded-lg bg-rose-500/20 text-rose-300 border border-rose-500/40 block";
                    saveApiKeyBtn.disabled = false;
                    saveApiKeyBtn.textContent = "บันทึก & ใช้งาน";
                }
            } catch (e) {
                modalAlert.textContent = "เชื่อมต่อ API ล้มเหลว: " + e.message;
                modalAlert.className = "text-xs p-2.5 rounded-lg bg-rose-500/20 text-rose-300 border border-rose-500/40 block";
                saveApiKeyBtn.disabled = false;
                saveApiKeyBtn.textContent = "บันทึก & ใช้งาน";
            }
        });
    }

    // Initialize
    checkSystemHealth();
    loadDocuments();
});
