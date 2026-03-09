document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const elements = {
        valLlmModel: document.getElementById('val-llm-model'),
        valEmbedModel: document.getElementById('val-embed-model'),
        valIndexStatus: document.getElementById('val-index-status'),
        fileTree: document.getElementById('file-tree'),
        btnReindex: document.getElementById('btn-rebuild-index'),
        chatInput: document.getElementById('chat-input'),
        btnSend: document.getElementById('btn-send'),
        btnClearChat: document.getElementById('btn-clear-chat'),
        chatHistory: document.getElementById('chat-history'),
        welcomeState: document.getElementById('welcome-state'),
        topFilesContainer: document.getElementById('dynamic-suggestions'), // Matches HTML ID
        btnLangToggle: document.getElementById('btn-lang-toggle'),
        btnNewChat: document.getElementById('btn-new-chat'),
        sessionList: document.getElementById('session-list'),
        btnSaveInsights: document.getElementById('btn-save-insights'), // New
        chatTitle: document.getElementById('current-chat-title'), // New
        
        // Custom Confirm Modal
        confirmOverlay: document.getElementById('confirm-overlay'),
        confirmTitle: document.getElementById('confirm-title'),
        confirmDesc: document.getElementById('confirm-desc'),
        confirmIcon: document.getElementById('confirm-icon'), // New
        confirmButtons: document.getElementById('confirm-buttons'), // New
        btnConfirmCancel: document.getElementById('btn-confirm-cancel'),
        btnConfirmOk: document.getElementById('btn-confirm-ok'),

        // Sidebar Resize
        sidebar: document.querySelector('.sidebar'),
        sidebarHandle: document.getElementById('sidebar-resize-handle'),
        appContainer: document.querySelector('.app-container'),

        // Toast / Progress
        toastOverlay: document.getElementById('toast-overlay'),
        spinner: document.querySelector('.spinner'),
        toastTitle: document.getElementById('toast-title'),
        toastDesc: document.getElementById('toast-desc'),
        toastProgressContainer: document.querySelector('.progress-bar-container'),
        toastProgressBar: document.getElementById('toast-progress-bar'),


        // Logs
        logDrawer: document.getElementById('log-drawer'),
        btnToggleLogs: document.getElementById('btn-toggle-logs'),
        btnCloseLogs: document.getElementById('btn-close-logs'),
        btnClearLogs: document.getElementById('btn-clear-logs'),
        logContainer: document.getElementById('log-container'),
        logResizeHandle: document.getElementById('log-resize-handle'), // New handle
        dropOverlay: document.getElementById('drop-overlay'), // New
        
        // File Preview Modal
        previewOverlay: document.getElementById('preview-overlay'),
        previewFilename: document.getElementById('preview-filename'),
        previewBody: document.getElementById('preview-body'),
        btnClosePreview: document.getElementById('btn-close-preview'),
    };

    // --- API 鉴权配置 ---
    const API_KEY = ""; // Optional override; by default auth is handled by HttpOnly cookie.
    function getHeaders(isJson = false) {
        const headers = {};
        if (API_KEY) {
            headers["Authorization"] = `Bearer ${API_KEY}`;
        }
        if (isJson) {
            headers["Content-Type"] = "application/json";
        }
        return headers;
    }

    // --- i18n 多语言支持 ---
    const TRANSLATIONS = {
        zh: {
            nav_title: "星澜知库",
            llm_model_label: "LLM 模型",
            embed_model_label: "向量模型",
            index_status_label: "索引状态",
            knowledge_base: "知识库文档",
            rebuild_index: "重新构建索引",
            system_online: "已连接本地引擎",
            welcome_title: "今天想了解关于文档的什么？",
            welcome_subtitle: "请在左侧\"重新构建索引\"后，点击下方建议或直接输入提问。",
            loading_directory: "加载目录结构中...",
            loading_suggestions: "加载热门文档...",
            progress_starting: "即将开始...",
            input_placeholder: "向知识库提问 (Shift + Enter 换行)...",
            chat_clear_confirm: "确定清空会话吗？",
            index_building: "正在构建索引",
            index_waiting: "请稍候，由于文档较多可能需要几分钟时间...",
            index_success: "索引构建成功！",
            index_error: "索引构建失败",
            lang_toggle_btn: "EN",
            new_chat: "开启新对话",
            save_insights: "保存本文档分析心得",
            save_insights_btn: "存为记忆",
            memory_success: "知识记忆已存入大脑",
            memory_error: "提炼失败：未发现具体文件引用",
            status_online: "在线",
            status_offline: "离线",
            status_ready: "就绪",
            status_not_ready: "未就绪",
            status_persisted: "已落盘",
            status_not_persisted: "未落盘",
            status_loaded: "已加载",
            status_not_loaded: "未加载",
            status_available: "可用",
            status_not_available: "不可用",
            status_normal: "正常",
            status_not_indexed: "未构建",
            status_load_failed: "加载失败",
            saving: "正在保存...",
            saved: "已保存！",
            drop_title: "释放开始上传",
            drop_subtitle: "支持文件及文件夹批量拖入",
            uploading_title: "正在上传文件",
            upload_success: "上传成功！",
        },
        en: {
            nav_title: "NebulaVault",
            llm_model_label: "LLM Model",
            embed_model_label: "Embed Model",
            index_status_label: "Index Status",
            knowledge_base: "Knowledge Base",
            rebuild_index: "Rebuild Index",
            system_online: "Local Engine Online",
            welcome_title: "What would you like to know today?",
            welcome_subtitle: "Please click a suggestion below or type your question directly.",
            loading_directory: "Loading directories...",
            loading_suggestions: "Loading popular docs...",
            progress_starting: "Starting...",
            input_placeholder: "Ask the knowledge base (Shift+Enter for newline)...",
            chat_clear_confirm: "Are you sure you want to clear the chat?",
            index_building: "Indexing...",
            index_waiting: "Please wait, this may take a few minutes for many documents...",
            index_success: "Indexing success!",
            index_error: "Indexing failed",
            lang_toggle_btn: "中",
            new_chat: "New Chat",
            save_insights: "Save Document Insights",
            save_insights_btn: "Save Memory",
            memory_success: "Insights saved to Memory",
            memory_error: "Fail: No specific file identified",
            status_online: "Online",
            status_offline: "Offline",
            status_ready: "Ready",
            status_not_ready: "Not Ready",
            status_persisted: "Saved",
            status_not_persisted: "Not Saved",
            status_loaded: "Loaded",
            status_not_loaded: "Not Loaded",
            status_available: "Available",
            status_not_available: "Not Available",
            status_normal: "Active",
            status_not_indexed: "Empty",
            status_load_failed: "Error",
            saving: "Saving...",
            saved: "Saved!",
            drop_title: "Drop to Upload",
            drop_subtitle: "Supports files and folders",
            uploading_title: "Uploading Files",
            upload_success: "Upload Success!",
        }
    };

    let currentLang = localStorage.getItem('rag_language') || 'zh';

    async function setLanguage(lang) {
        currentLang = lang;
        localStorage.setItem('rag_language', lang);
        
        const dict = TRANSLATIONS[lang];
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (dict[key]) {
                el.textContent = dict[key];
            }
        });

        document.querySelectorAll('[data-i18n-title]').forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            if (dict[key]) {
                el.title = dict[key];
            }
        });
        
        if (elements.chatInput) {
            elements.chatInput.placeholder = dict.input_placeholder;
        }
        
        if (elements.btnLangToggle) {
            elements.btnLangToggle.textContent = dict.lang_toggle_btn;
        }

        // --- 核心：同步切换 Embedding 模型 ---
        // 这一步是异步的，不阻塞 UI 翻译，但我们要通知后端
        try {
            const resp = await fetch('/api/config/switch_lang', {
                method: 'POST',
                headers: getHeaders(true),
                body: JSON.stringify({ lang: lang })
            });
            const result = await resp.json();
            if (result.ok && result.changed) {
                // 如果模型确实发生了变化，提示用户
                console.info("Model switch triggered:", result.model);
                showToast(
                    lang === 'zh' ? "正在优化中文向量引擎" : "Optimizing English Engine",
                    dict.index_waiting || result.message,
                    true
                );
                // 3秒后自动关闭提示（服务器此时应该已经 reload 完成）
                setTimeout(() => {
                    elements.toastOverlay.classList.remove('active');
                    loadStatus();
                }, 4000);
            }
        } catch (e) {
            console.error("Autonomous model switch failed:", e);
        }
    }

    function showToast(title, desc, showSpinner = true, iconHtml = null) {
        if (!elements.toastOverlay) return;
        elements.toastTitle.innerHTML = title;
        elements.toastDesc.textContent = desc;
        elements.spinner.style.display = showSpinner ? 'block' : 'none';
        elements.toastProgressContainer.style.display = 'none';
        
        const existingIcon = elements.toastOverlay.querySelector('.toast-custom-icon');
        if (existingIcon) existingIcon.remove();
        
        if (iconHtml) {
            elements.toastTitle.insertAdjacentHTML('beforebegin', `<div class="toast-custom-icon">${iconHtml}</div>`);
        }
        
        elements.toastOverlay.classList.add('active');
    }

    function hideToast() {
        if (elements.toastOverlay) {
            elements.toastOverlay.classList.remove('active');
        }
    }

    // Initial language setup - fire and forget
    setLanguage(currentLang).catch(console.error);

    let currentSessionId = null; // 始终从欢迎页启动 (Always start with welcome screen)
    let chatHistory = [];

    // --- 多会话函数 (Session Functions) ---
    async function loadSessions() {
        try {
            const resp = await fetch('/api/sessions', { headers: getHeaders() });
            const result = await resp.json();
            if (result.ok) {
                renderSessionList(result.sessions);
            }
        } catch (e) {
            console.error("Failed to load sessions:", e);
        }
    }

    function renderSessionList(sessions) {
        if (!elements.sessionList) return;
        elements.sessionList.innerHTML = '';
        
        if (sessions.length === 0) {
            // 不再自动创建，保持空状态 (Allow empty list)
            return;
        }

        sessions.forEach(s => {
            const item = document.createElement('div');
            item.className = `session-item ${currentSessionId === s.id ? 'active' : ''}`;
            item.onclick = (e) => {
                if (e.target.closest('.btn-delete-session')) return;
                switchSession(s.id);
            };

            const dt = new Date(s.updated_at * 1000);
            const timeStr = `${(dt.getMonth() + 1).toString().padStart(2, '0')}-${dt.getDate().toString().padStart(2, '0')} ${dt.getHours().toString().padStart(2, '0')}:${dt.getMinutes().toString().padStart(2, '0')}`;
            
            item.innerHTML = `
                <div class="session-info">
                    <div class="session-title">${s.title}</div>
                    <div class="session-time">${timeStr}</div>
                </div>
                <button class="btn-delete-session" title="Delete Chat">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            `;

            const btnDel = item.querySelector('.btn-delete-session');
            btnDel.onclick = (e) => {
                e.stopPropagation();
                deleteSession(s.id);
            };

            elements.sessionList.appendChild(item);
        });
    }

    async function createSession() {
        try {
            const now = new Date();
            const timeStr = now.getHours().toString().padStart(2, '0') + ":" + now.getMinutes().toString().padStart(2, '0');
            const sessionTitle = currentLang === 'zh' ? `新会话 (${timeStr})` : `New Chat (${timeStr})`;

            const resp = await fetch('/api/sessions', { 
                method: 'POST',
                headers: getHeaders(true),
                body: JSON.stringify({ title: sessionTitle })
            });
            const result = await resp.json();
            if (result.ok) {
                currentSessionId = result.session_id;
                localStorage.setItem('rag_session_id', currentSessionId);
                chatHistory = [];
                renderChatHistory();
                loadSessions();
                scrollToBottom(true); // Force scroll on new chat
            }
        } catch (e) {
            console.error("Failed to create session:", e);
        }
    }

    async function switchSession(id) {
        if (currentSessionId === id) return;
        currentSessionId = id;
        localStorage.setItem('rag_session_id', id);
        
        try {
            const resp = await fetch(`/api/sessions/${id}`, { headers: getHeaders() });
            const result = await resp.json();
            if (result.ok) {
                chatHistory = result.session.history || [];
                if (elements.chatTitle) elements.chatTitle.textContent = result.session.title;
                renderChatHistory();
                loadSessions();
                scrollToBottom(true); // Force scroll on switch
            }
        } catch (e) {
            console.error("Failed to switch session:", e);
        }
    }

    async function saveInsights() {
        if (!currentSessionId || chatHistory.length === 0) return;
        
        const btn = elements.btnSaveInsights;
        const originalHtml = btn.innerHTML;
        
        // UI Feedback: Loading state
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> ${TRANSLATIONS[currentLang].saving}`;
        btn.classList.add('processing');

        showToast(
            currentLang === 'zh' ? "正在提炼知识记忆..." : "Distilling Insights...",
            currentLang === 'zh' ? "AI 正在分析本次会话的精华数据" : "AI is analyzing session key data",
            true
        );

        try {
            const resp = await fetch(`/api/sessions/${currentSessionId}/summarize`, { 
                method: 'POST',
                headers: getHeaders()
            });
            const result = await resp.json();
            if (result.ok) {
                // UI Feedback: Success state on button
                btn.classList.remove('processing');
                btn.classList.add('success');
                btn.innerHTML = `<i class="fa-solid fa-check"></i> ${TRANSLATIONS[currentLang].saved}`;

                showToast(
                    currentLang === 'zh' ? "记忆已存入" : "Memory Saved",
                    `${TRANSLATIONS[currentLang].memory_success} (Files: ${result.files.join(', ')})`,
                    false,
                    '<i class="fa-solid fa-check-circle" style="font-size:3rem;color:var(--success);margin-bottom:10px;"></i>'
                );
                
                // 刷新文件树以显示标记
                loadFileTree();
                
                // 2秒后恢复按钮并关闭弹窗
                setTimeout(() => {
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;
                    btn.classList.remove('success');
                    elements.toastOverlay.classList.remove('active');
                }, 2000);
            } else {
                throw new Error(result.error);
            }
        } catch (e) {
            console.error("Failed to save insights:", e);
            btn.disabled = false;
            btn.innerHTML = originalHtml;
            btn.classList.remove('processing');
            showToast(
                "Error",
                e.message || TRANSLATIONS[currentLang].memory_error,
                false
            );
            setTimeout(() => elements.toastOverlay.classList.remove('active'), 3000);
        }
    }

    // --- 自定义确认弹窗 (Custom Confirm Promise) ---
    function showConfirm(titleText, descText, buttons = null, iconHtml = null) {
        return new Promise((resolve) => {
            if (!elements.confirmOverlay) {
                resolve(confirm(descText)); // Fallback
                return;
            }

            if (elements.confirmTitle) elements.confirmTitle.textContent = titleText;
            if (elements.confirmDesc) elements.confirmDesc.textContent = descText;
            
            if (elements.confirmIcon) {
                if (iconHtml) {
                    elements.confirmIcon.innerHTML = iconHtml;
                } else {
                    // Default question icon
                    elements.confirmIcon.innerHTML = `<i class="fa-solid fa-circle-question" style="color: var(--primary); font-size: 2.5rem; margin-bottom: 1rem;"></i>`;
                }
            }

            // Clear and render buttons
            const btnContainer = elements.confirmButtons || document.querySelector('.confirm-actions');
            if (btnContainer) {
                btnContainer.innerHTML = '';
                
                const defaultButtons = [
                    { text: currentLang === 'zh' ? '取消' : 'Cancel', class: 'btn-action-outline', value: false },
                    { text: currentLang === 'zh' ? '确定' : 'Confirm', class: 'btn-action-outline danger', value: true }
                ];
                
                const actionButtons = buttons || defaultButtons;
                
                actionButtons.forEach(btnCfg => {
                    const btn = document.createElement('button');
                    btn.textContent = btnCfg.text;
                    btn.className = btnCfg.class;
                    btn.onclick = () => {
                        elements.confirmOverlay.classList.remove('active');
                        resolve(btnCfg.value);
                    };
                    btnContainer.appendChild(btn);
                });
            }

            elements.confirmOverlay.classList.add('active');
        });
    }

    async function deleteSession(id) {
        const confirmMsg = TRANSLATIONS[currentLang].chat_clear_confirm;
        const confirmTitle = currentLang === 'zh' ? "确认删除会话" : "Confirm Deletion";
        const confirmed = await showConfirm(confirmTitle, confirmMsg);
        if (!confirmed) return;
        
        try {
            const resp = await fetch(`/api/sessions/${id}`, { 
                method: 'DELETE',
                headers: getHeaders()
            });
            const result = await resp.json();
            if (result.ok) {
                if (currentSessionId === id) {
                    currentSessionId = null;
                    localStorage.removeItem('rag_session_id');
                    chatHistory = [];
                    renderChatHistory(); // Show welcome screen
                    if (elements.chatTitle) elements.chatTitle.textContent = TRANSLATIONS[currentLang].nav_title;
                }
                loadSessions();
            }
        } catch (e) {
            console.error("Failed to delete session:", e);
        }
    }

    function renderChatHistory() {
        if (!elements.chatHistory) return;
        
        // 保留 welcome-state，清除其他消息容器
        const children = Array.from(elements.chatHistory.children);
        children.forEach(child => {
            if (child.id !== 'welcome-state' && !child.classList.contains('welcome-container')) {
                child.remove();
            }
        });

        if (chatHistory.length === 0) {
            if (elements.welcomeState) {
                elements.welcomeState.style.display = 'flex';
                elements.welcomeState.classList.remove('hidden');
                elements.welcomeState.style.animation = 'slideUp 0.5s ease';
            }
        } else {
            if (elements.welcomeState) {
                elements.welcomeState.style.display = 'none';
                elements.welcomeState.classList.add('hidden');
            }
            chatHistory.forEach(pair => {
                appendMessage('user', pair.user, false);
                appendMessage('assistant', pair.assistant, false, pair.sources);
            });
            scrollToBottom(true);
        }
    }

    function appendMessage(role, text, animate = true, sources = []) {
        if (!elements.chatHistory) return;
        
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}-message`;
        if (animate) msgDiv.style.animation = 'fadeIn 0.3s ease';

        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'avatar';
        if (role === 'user') {
            avatarDiv.innerHTML = `<img src="/static/images/user_avatar.png" class="avatar user-avatar-img" alt="User">`;
        } else {
            avatarDiv.innerHTML = `<i class="fa-solid fa-robot"></i>`;
        }

        const contentDiv = document.createElement('div');
        contentDiv.className = 'content';
        
        if (role === 'user') {
            contentDiv.innerHTML = `<p>${escapeHtml(text)}</p>`;
        } else {
            // AI 消息使用 marked 渲染并进行 DOMPurify 消毒防 XSS
            const rawHtml = marked.parse(text);
            contentDiv.innerHTML = typeof DOMPurify !== "undefined" ? DOMPurify.sanitize(rawHtml) : rawHtml;
            
            // 如果有来源，渲染来源框
            if (sources && sources.length > 0) {
                const sourceHtml = sources.map(s => `<span class="source-tag"><i class="fa-solid fa-link"></i> ${s}</span>`).join('');
                contentDiv.innerHTML += `
                    <div class="sources-box">
                        <div class="sources-title"><i class="fa-solid fa-book-open"></i> 参考来源：</div>
                        <div class="sources-list">${sourceHtml}</div>
                    </div>
                `;
            }
        }

        msgDiv.appendChild(avatarDiv);
        msgDiv.appendChild(contentDiv);
        elements.chatHistory.appendChild(msgDiv);
        
        if (animate) scrollToBottom();
        return contentDiv;
    }

    // --- 侧边栏调整大小 (Sidebar Resizing) ---
    function initSidebarResize() {
        const handle = elements.sidebarHandle;
        const sidebar = elements.sidebar;
        const container = elements.appContainer;
        if (!handle || !sidebar) return;

        let isResizing = false;
        
        // 从本地存储加载宽度 (Load width from localStorage)
        const savedWidth = localStorage.getItem('sidebar_width');
        if (savedWidth) {
            sidebar.style.width = savedWidth + 'px';
        }

        handle.addEventListener('mousedown', (e) => {
            isResizing = true;
            handle.classList.add('active');
            container.classList.add('resizing-sidebar');
        });

        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;
            
            // 使用相对坐标，避免受外部容器居中的影响 (Use relative coords)
            let newWidth = e.clientX - sidebar.getBoundingClientRect().left;
            // 限制最小和最大宽度 (Min/Max limits)
            if (newWidth < 200) newWidth = 200;
            if (newWidth > 600) newWidth = 600;
            
            sidebar.style.width = newWidth + 'px';
            localStorage.setItem('sidebar_width', newWidth);
        });

        document.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false;
                handle.classList.remove('active');
                container.classList.remove('resizing-sidebar');
            }
        });
    }

    // 初始化所有模块
    initSidebarResize();
    initLogResizer();
    initDragDrop();
    
    // 加载会话列表 (Load sessions)
    loadSessions();

    if (elements.btnNewChat) {
        elements.btnNewChat.onclick = createSession;
    }
    if (elements.btnSaveInsights) {
        elements.btnSaveInsights.onclick = saveInsights;
    }

    let isProcessing = false;
    const AUTO_SCROLL_THRESHOLD = 180;
    let autoScrollLockedByUser = false;
    let isProgrammaticScroll = false;

    function isNearBottom(threshold = AUTO_SCROLL_THRESHOLD) {
        const container = elements.chatHistory;
        if (!container) return true;
        const distance = container.scrollHeight - container.scrollTop - container.clientHeight;
        return distance <= threshold;
    }

    if (elements.chatHistory) {
        // 用户在流式输出时上滑查看历史，暂停自动跟随，避免和滚轮冲突。
        elements.chatHistory.addEventListener('wheel', (e) => {
            if (!isProcessing) return;
            if (e.deltaY < 0) {
                autoScrollLockedByUser = true;
            } else if (isNearBottom()) {
                autoScrollLockedByUser = false;
            }
        }, { passive: true });

        // 用户手动滚回底部后，自动恢复跟随输出。
        elements.chatHistory.addEventListener('scroll', () => {
            if (isProgrammaticScroll) return;
            if (!isProcessing) {
                autoScrollLockedByUser = false;
                return;
            }
            autoScrollLockedByUser = !isNearBottom();
        });
    }

    function processSseBuffer(buffer, onEvent) {
        let normalized = buffer.replace(/\r\n/g, '\n');
        let boundary = normalized.indexOf('\n\n');

        while (boundary !== -1) {
            const eventStr = normalized.slice(0, boundary);
            normalized = normalized.slice(boundary + 2);
            boundary = normalized.indexOf('\n\n');

            if (!eventStr.trim()) {
                continue;
            }

            const lines = eventStr.split('\n');
            let currentEvent = null;
            let currentData = '';

            for (const line of lines) {
                if (line.startsWith('event:')) {
                    currentEvent = line.replace('event:', '').trim();
                } else if (line.startsWith('data:')) {
                    currentData += line.slice(5).trimStart();
                }
            }

            onEvent(currentEvent, currentData);
        }

        return normalized;
    }

    // 配置 marked 使用 highlight.js 进行语法高亮
    marked.setOptions({
        highlight: function(code, lang) {
            if (lang && hljs.getLanguage(lang)) {
                return hljs.highlight(code, { language: lang }).value;
            }
            return hljs.highlightAuto(code).value;
        },
        breaks: true, // 允许回车换行
    });

    // 根据文件后缀返回对应的 FontAwesome 图标
    function getFileIcon(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        const map = {
            'pdf': 'fa-file-pdf',
            'docx': 'fa-file-word',
            'doc': 'fa-file-word',
            'txt': 'fa-file-lines',
            'md': 'fa-file-code',
            'yml': 'fa-file-code',
            'yaml': 'fa-file-code',
            'csv': 'fa-file-csv',
            'html': 'fa-file-code',
            'htm': 'fa-file-code',
        };
        return map[ext] || 'fa-file';
    }

    // Load Initial Status
    async function loadStatus() {
        try {
            const res = await fetch('/api/status', { headers: getHeaders() });
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
            const data = await res.json();
            const { status, doc_files } = data;

            elements.valLlmModel.textContent = status.llm_model;
            elements.valEmbedModel.textContent = status.embed_model;
            // valDocCount removed from HTML
            
            if (status.has_index) {
                elements.valIndexStatus.innerHTML = `<span style="color: var(--success);"><i class="fa-solid fa-circle-check"></i> ${TRANSLATIONS[currentLang].status_normal}</span>`;
            } else {
                elements.valIndexStatus.innerHTML = `<span style="color: var(--error);"><i class="fa-solid fa-circle-xmark"></i> ${TRANSLATIONS[currentLang].status_not_indexed}</span>`;
            }

            // Document list is now handled by loadFileTree()

        } catch (error) {
            console.error("加载状态失败:", error);
            elements.valIndexStatus.innerHTML = `<span style="color: var(--error);"><i class="fa-solid fa-triangle-exclamation"></i> ${TRANSLATIONS[currentLang].status_load_failed}</span>`;
            // docList removed – tree handles display
        }
    }


    async function loadFileTree() {
        if (!elements.fileTree) return;
        try {
            // 获取文件列表和是否有记忆的状态 (Get memories list)
            const [treeResp, statusResp] = await Promise.all([
                fetch('/api/files', { headers: getHeaders() }),
                fetch('/api/status', { headers: getHeaders() })
            ]);
            const treeData = await treeResp.json();
            const statusData = await statusResp.json();
            
            // 后端返回哪些文件有记忆
            const memories = (statusData.status && statusData.status.memories) ? statusData.status.memories : [];

            elements.fileTree.innerHTML = '';
            // Render root node expanded
            const rootNode = renderTreeNode(treeData, true, memories);
            elements.fileTree.appendChild(rootNode);
        } catch (error) {
            console.error("加载文件树失败:", error);
            elements.fileTree.innerHTML = '<div class="tree-loading" style="color: var(--error);"><i class="fa-solid fa-triangle-exclamation"></i> 目录树加载失败</div>';
        }
    }

    function renderTreeNode(node, isExpanded = false, memories = []) {
        const div = document.createElement('div');
        div.className = `tree-node ${isExpanded ? 'expanded' : ''}`;
        
        const item = document.createElement('div');
        item.className = `tree-item ${node.type === 'file' ? 'is-file' : 'is-dir'}`;
        
        const icon = document.createElement('i');
        if (node.type === 'directory') {
            const chevron = document.createElement('i');
            chevron.className = 'fa-solid fa-chevron-right chevron-icon';
            item.appendChild(chevron);
            
            const isSkillDir = node.name.toLowerCase() === 'skills';
            icon.className = `fa-solid ${isSkillDir ? 'fa-star' : 'fa-folder'} tree-icon`;
            if (isSkillDir) icon.style.color = '#eab308';
        } else {
            icon.className = 'fa-solid fa-file-lines tree-icon';
            // Enhance icon based on extension
            const lowerName = node.name.toLowerCase();
            if (lowerName.endsWith('.pdf')) icon.className = 'fa-solid fa-file-pdf tree-icon';
            else if (lowerName.endsWith('.docx') || lowerName.endsWith('.doc')) icon.className = 'fa-solid fa-file-word tree-icon';
            else if (lowerName.endsWith('.md')) icon.className = 'fa-brands fa-markdown tree-icon';
            else if (lowerName.endsWith('.png') || lowerName.endsWith('.jpg') || lowerName.endsWith('.jpeg') || lowerName.endsWith('.webp')) icon.className = 'fa-solid fa-image tree-icon';
        }
        item.appendChild(icon);
        
        const label = document.createElement('span');
        label.className = 'tree-label';
        label.textContent = node.name;
        label.title = node.name;
        item.appendChild(label);

        // 如果该文件有记忆，添加大脑标记 (Add brain badge if has memory)
        if (node.type === 'file' && node.path) {
            const normalizedPath = node.path.replace(/\\/g, "/").replace(/^\.?\//, "");
            const memoryKey = encodeURIComponent(normalizedPath);
            if (memories.includes(memoryKey)) {
                const badge = document.createElement('i');
                badge.className = 'fa-solid fa-brain memory-badge';
                badge.title = 'HAS MEMORY / 有历史见解';
                item.appendChild(badge);
            }
        }
        
        // 双击预览功能 (Double click to preview)
        if (node.type === 'file') {
            item.title = "Double click to preview / 双击预览文件";
            item.addEventListener('dblclick', (e) => {
                console.log("File dblclicked:", node.path || node.name);
                e.stopPropagation();
                openFilePreview(node.path || node.name);
            });
        }
        
        div.appendChild(item);
        
        if (node.type === 'directory' && node.children && node.children.length > 0) {
            const childrenWrapper = document.createElement('div');
            childrenWrapper.className = 'tree-children';
            node.children.forEach(child => {
                childrenWrapper.appendChild(renderTreeNode(child, false, memories));
            });
            div.appendChild(childrenWrapper);
            
            item.addEventListener('click', () => {
                div.classList.toggle('expanded');
            });
        }
        
        return div;
    }

    async function openFilePreview(path) {
        console.log("openFilePreview called with path:", path);
        if (!elements.previewOverlay) {
            console.error("previewOverlay element not found!");
            return;
        }
        
        try {
            // Delay toast slightly; if request is fast (<200ms), don't show it to avoid flickering
            const toastTimer = setTimeout(() => {
                showToast(
                    TRANSLATIONS[currentLang].nav_title, 
                    `正在加载 ${path}...`, 
                    true
                );
            }, 200);

            console.log("Fetching content for path:", path);
            const res = await fetch(`/api/files/content?path=${encodeURIComponent(path)}`, { headers: getHeaders() });
            const data = await res.json();
            console.log("Preview API response:", data);
            
            clearTimeout(toastTimer);
            hideToast();

            if (data.ok) {
                elements.previewFilename.textContent = data.filename || path;
                
                // 使用 marked 渲染并进行 DOMPurify 消毒防 XSS
                let contentHtml = '';
                const suffix = (data.filename || path).toLowerCase();
                
                if (data.is_image) {
                    contentHtml = `<div class="preview-image-container">
                        <img src="${data.content}" alt="${data.filename}" style="max-width: 100%; height: auto; display: block; margin: 0 auto; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);">
                    </div>`;
                } else if (data.is_pdf) {
                    // Fetch PDF as blob with auth headers, then create blob URL for iframe
                    const pdfUrl = data.raw_url;
                    console.log("Fetching PDF blob from:", pdfUrl);
                    try {
                        const pdfRes = await fetch(pdfUrl, { headers: getHeaders() });
                        if (pdfRes.ok) {
                            const pdfBlob = await pdfRes.blob();
                            const blobUrl = URL.createObjectURL(pdfBlob);
                            contentHtml = `<div class="preview-pdf-container" style="height: 70vh; width: 100%;">
                                <iframe src="${blobUrl}" style="width: 100%; height: 100%; border: none; border-radius: 4px;"></iframe>
                            </div>`;
                            // Clean up blob URL when preview is closed
                            const oldClose = elements.btnClosePreview.onclick;
                            elements.btnClosePreview.onclick = () => {
                                URL.revokeObjectURL(blobUrl);
                                if (oldClose) oldClose();
                                elements.previewOverlay.classList.remove('active');
                                elements.previewOverlay.style.display = 'none';
                                document.body.style.overflow = '';
                            };
                        } else {
                            contentHtml = `<p style="color:red;">PDF 加载失败: HTTP ${pdfRes.status}</p>`;
                        }
                    } catch (pdfErr) {
                        console.error("PDF blob fetch error:", pdfErr);
                        contentHtml = `<p style="color:red;">PDF 加载失败: ${pdfErr.message}</p>`;
                    }
                } else if (suffix.endsWith('.md')) {
                    const rawHtml = marked.parse(data.content);
                    contentHtml = typeof DOMPurify !== "undefined" ? DOMPurify.sanitize(rawHtml) : rawHtml;
                } else {
                    // 非 Markdown 文件显示为代码块
                    const lang = suffix.split('.').pop();
                    contentHtml = `<pre><code class="language-${lang}">${escapeHtml(data.content)}</code></pre>`;
                }
                
                elements.previewBody.innerHTML = contentHtml;
                
                // 语法高亮
                elements.previewBody.querySelectorAll('pre code').forEach((block) => {
                    hljs.highlightElement(block);
                });
                
                elements.previewOverlay.style.display = 'flex'; // Explicitly set for robustness
                elements.previewOverlay.classList.add('active');
                document.body.style.overflow = 'hidden'; // 禁止背景滚动
                
                // Diagnostic check for visibility
                setTimeout(() => {
                    const rect = elements.previewOverlay.getBoundingClientRect();
                    const style = window.getComputedStyle(elements.previewOverlay);
                    console.log("Overlay visibility check:", {
                        opacity: style.opacity,
                        display: style.display,
                        zIndex: style.zIndex,
                        pointerEvents: style.pointerEvents,
                        rect: rect
                    });
                }, 500);
            } else {
                alert(`无法预览: ${data.error}`);
            }
        } catch (error) {
            hideToast();
            console.error("Preview failed:", error);
            alert("文件预览失败，请检查网络或后端日志。");
        }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 关闭预览
    if (elements.btnClosePreview) {
        elements.btnClosePreview.onclick = () => {
            elements.previewOverlay.classList.remove('active');
            document.body.style.overflow = '';
        };
    }
    
    // 点击遮罩关闭
    if (elements.previewOverlay) {
        elements.previewOverlay.onclick = (e) => {
            if (e.target === elements.previewOverlay) {
                elements.previewOverlay.classList.remove('active');
                document.body.style.overflow = '';
            }
        };
    }

    async function loadTopFiles() {
        const container = document.getElementById('dynamic-suggestions');
        if (!container) return;
        
        try {
            const res = await fetch('/api/top_files', { headers: getHeaders() });
            if (res.ok) {
                const data = await res.json();
                container.innerHTML = '';
                if (data.files && data.files.length > 0) {
                    data.files.forEach(file => {
                        const btn = document.createElement('button');
                        btn.className = 'chip';
                        // Get basename
                        const parts = file.split('/');
                        const basename = parts[parts.length - 1];
                        
                        btn.innerHTML = `<i class="${getFileIcon(basename)}"></i> 分析 ${basename}`;
                        btn.onclick = () => {
                            if (isProcessing) return;
                            
                            // 利用现有的发送管线 (Use existing send pipeline)
                            elements.chatInput.value = `帮我分析一下 ${file} 文件`;
                            elements.chatInput.dispatchEvent(new Event('input')); // 触发高度自适应和按钮解锁 (Trigger resize and unlock)
                            
                            // 确保光标到末尾体验更好
                            elements.chatInput.focus();
                            
                            // 模拟点击发送 (Simulate click to send)
                            setTimeout(() => {
                                elements.btnSend.click();
                            }, 50);
                        };
                        container.appendChild(btn);
                    });
                } else {
                    container.innerHTML = '<div style="font-size: 0.9rem; color: var(--text-muted);">暂无最近使用文档，请在左侧构建索引！</div>';
                }
            }
        } catch (e) {
            console.error('Error loading top files:', e);
            container.innerHTML = '<div style="font-size: 0.9rem; color: var(--error);">加载热门文档失败</div>';
        }
    }

    loadStatus();
    loadFileTree();
    loadTopFiles();

    // Auto resize textarea
    elements.chatInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        
        if (this.value.trim().length > 0 && !isProcessing) {
            elements.btnSend.disabled = false;
        } else {
            elements.btnSend.disabled = true;
        }
    });

    // 清空会话 (Clear/Delete current session)
    elements.btnClearChat.addEventListener('click', () => {
        if (isProcessing) return;
        
        // 如果没有对话内容，直接跳过 (Skip if no history)
        if (chatHistory.length === 0) return;
        
        // 使用通用的 deleteSession 逻辑 (调用后端并弹出确认)
        if (currentSessionId) {
            deleteSession(currentSessionId);
        }
    });

    // --- 日志控制台逻辑 ---
    let logSse = null;

    function initDragDrop() {
        const overlay = elements.dropOverlay;
        if (!overlay) return;

        let dragCounter = 0;

        document.addEventListener('dragenter', (e) => {
            e.preventDefault();
            dragCounter++;
            overlay.classList.add('active');
        });

        document.addEventListener('dragleave', (e) => {
            dragCounter--;
            if (dragCounter === 0) {
                overlay.classList.remove('active');
            }
        });

        document.addEventListener('dragover', (e) => {
            e.preventDefault(); 
        });

        document.addEventListener('drop', async (e) => {
            e.preventDefault();
            dragCounter = 0;
            overlay.classList.remove('active');

            const items = e.dataTransfer.items;
            if (!items) return;

            const filesToUpload = [];
            
            // Collect entries
            const entries = [];
            for (let i = 0; i < items.length; i++) {
                const item = items[i];
                if (item.kind === 'file') {
                    const entry = item.webkitGetAsEntry();
                    if (entry) entries.push(entry);
                }
            }
            
            if (entries.length === 0) return;

            // Recursive scan
            async function scanEntry(entry, path = "") {
                if (entry.isFile) {
                    const file = await new Promise(resolve => entry.file(resolve));
                    filesToUpload.push({ file, path: path + file.name });
                } else if (entry.isDirectory) {
                    const reader = entry.createReader();
                    const subEntries = await new Promise(resolve => reader.readEntries(resolve));
                    for (const sub of subEntries) {
                        await scanEntry(sub, path + entry.name + "/");
                    }
                }
            }

            for (const entry of entries) {
                await scanEntry(entry);
            }

            if (filesToUpload.length === 0) return;

            // Prompt
            if (filesToUpload.length === 1 && entries[0].isFile) {
                const fileName = filesToUpload[0].file.name;
                const mode = await showConfirm(
                    currentLang === 'zh' ? "发现新文档" : "New Document",
                    currentLang === 'zh' ? `是否对 "${fileName}" 立即开始智能分析？` : `Analyze "${fileName}" immediately?`,
                    [
                        { text: currentLang === 'zh' ? '暂不分析' : 'Archive Only', class: 'btn-action-outline', value: 'archive' },
                        { text: currentLang === 'zh' ? '立即分析' : 'Analyze Now', class: 'btn-action-outline primary', value: 'analyze' }
                    ],
                    `<i class="fa-solid fa-file-pdf" style="color:var(--primary); font-size:3rem; margin-bottom:1rem;"></i>`
                );
                
                if (mode) {
                    handleUpload(filesToUpload, mode === 'analyze');
                }
            } else {
                const mode = await showConfirm(
                    currentLang === 'zh' ? "批量上传" : "Batch Upload",
                    currentLang === 'zh' ? `已选择 ${filesToUpload.length} 个项目。直接存入知识库还是开启深度分析？` : `Selected ${filesToUpload.length} items. Save or Analyze?`,
                    [
                        { text: currentLang === 'zh' ? '存入知识库' : 'Save all', class: 'btn-action-outline', value: 'archive' },
                        { text: currentLang === 'zh' ? '开启深度分析' : 'Analyze all', class: 'btn-action-outline primary', value: 'analyze' }
                    ],
                    `<i class="fa-solid fa-folder-open" style="color:var(--primary); font-size:3rem; margin-bottom:1rem;"></i>`
                );
                if (mode) {
                    handleUpload(filesToUpload, mode === 'analyze');
                }
            }
        });
    }

    async function handleUpload(filesWithPaths, analyze = false) {
        const formData = new FormData();
        filesWithPaths.forEach(item => {
            formData.append('files', item.file);
            formData.append('relative_paths', item.path);
        });
        formData.append('analyze', analyze);

        showToast(
            TRANSLATIONS[currentLang].uploading_title || "正在上传",
            currentLang === 'zh' ? "请稍候..." : "Please wait...",
            true
        );

        try {
            const resp = await fetch('/api/upload', {
                method: 'POST',
                headers: getHeaders(), // No Content-Type for FormData
                body: formData
            });
            const result = await resp.json();
            
            if (result.ok) {
                elements.toastOverlay.classList.remove('active');
                if (analyze) {
                    await triggerReindex(true); // Wait for indexing to complete
                    
                    if (filesWithPaths.length === 1) {
                        const fileName = filesWithPaths[0].file.name;
                        elements.chatInput.value = currentLang === 'zh' ? `帮我深度分析一下 ${fileName} 这个文件` : `Deeply analyze the file ${fileName}`;
                    } else {
                        elements.chatInput.value = currentLang === 'zh' ? "请帮我分析一下这些新上传的文件。" : "Please analyze these newly uploaded files.";
                    }
                    sendMessage();
                } else {
                    showToast(
                        TRANSLATIONS[currentLang].upload_success || "上传成功",
                        currentLang === 'zh' ? "已存入知识库。请记得点击“重新构建索引”使其生效。" : "Saved to Base. Remember to Rebuild Index.",
                        false,
                        `<i class="fa-solid fa-circle-check" style="color:var(--success); font-size:3rem;"></i>`
                    );
                    setTimeout(() => {
                        elements.toastOverlay.classList.remove('active');
                    }, 4000);
                }
                loadFileTree();
            } else {
                throw new Error(result.error || "Upload failed");
            }
        } catch (e) {
            console.error(e);
            showToast(
                currentLang === 'zh' ? "上传失败" : "Upload Error",
                e.message,
                false,
                `<i class="fa-solid fa-triangle-exclamation" style="color:var(--error); font-size:3rem;"></i>`
            );
        }
    }

    function initLogStream() {
        if (logSse) logSse.close();
        
        logSse = new EventSource('/api/logs/stream');
        logSse.onmessage = (e) => {
            const data = e.data;
            appendLogLine(data);
        };
        logSse.onerror = () => {
            console.error("Log stream disconnected. Retrying...");
            logSse.close();
            setTimeout(initLogStream, 5000);
        };
    }

    function appendLogLine(text) {
        if (!elements.logContainer) return;
        
        const line = document.createElement('div');
        line.className = 'log-line';
        
        // 解析日志颜色 (简单正则)
        let html = text.replace(/(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})/g, '<span class="log-time">$1</span>');
        html = html.replace(/\[INFO\]/g, '<span class="log-level-info">[INFO]</span>');
        html = html.replace(/\[WARNING|WARN\]/g, '<span class="log-level-warning">[WARNING]</span>');
        html = html.replace(/\[ERROR\]/g, '<span class="log-level-error">[ERROR]</span>');
        
        line.innerHTML = html;
        elements.logContainer.appendChild(line);
        
        // 自动滚动 (仅当抽屉打开且之前已在底部时，或者强制滚动)
        elements.logContainer.scrollTop = elements.logContainer.scrollHeight;

        // 限制日志行数，防止浏览器内存爆炸 (保留最后 500 行)
        if (elements.logContainer.children.length > 500) {
            elements.logContainer.removeChild(elements.logContainer.firstChild);
        }
    }

    elements.btnClearLogs.addEventListener('click', () => {
        elements.logContainer.innerHTML = '';
    });
    // --- 日志面板调整大小逻辑 (Log Drawer Resize Logic) ---
    function initLogResizer() {
        let isResizingLogs = false;
        let logStartHeight = 350;
        
        if (elements.logResizeHandle) {
            elements.logResizeHandle.addEventListener('mousedown', (e) => {
                isResizingLogs = true;
                elements.logDrawer.classList.add('resizing');
                document.body.style.cursor = 'ns-resize';
                e.preventDefault();
            });

            window.addEventListener('mousemove', (e) => {
                if (!isResizingLogs) return;
                
                // 计算新高度 (Calculate new height)
                const newHeight = window.innerHeight - e.clientY;
                
                // 限制最小/最大高度 (Min/Max height constraints)
                if (newHeight > 100 && newHeight < window.innerHeight * 0.8) {
                    elements.logDrawer.style.height = `${newHeight}px`;
                    
                    // 如果当前是隐藏状态 (未 active)，调整 bottom 为 -newHeight 以确保完全隐藏
                    if (!elements.logDrawer.classList.contains('active')) {
                        elements.logDrawer.style.bottom = `-${newHeight}px`;
                    }
                    logStartHeight = newHeight;
                }
            });

            window.addEventListener('mouseup', () => {
                if (isResizingLogs) {
                    isResizingLogs = false;
                    elements.logDrawer.classList.remove('resizing');
                    document.body.style.cursor = '';
                    
                    // 确保 active 状态下 bottom 为 0
                    if (elements.logDrawer.classList.contains('active')) {
                        elements.logDrawer.style.bottom = '0';
                    }
                }
            });
        }
    }

    // 更新 Toggle 逻辑，处理动态高度的隐藏位移
    elements.btnToggleLogs.addEventListener('click', () => {
        const isActive = elements.logDrawer.classList.toggle('active');
        if (isActive) {
            elements.logDrawer.style.bottom = '0';
            if (!logSse) initLogStream();
        } else {
            elements.logDrawer.style.bottom = `-${elements.logDrawer.offsetHeight}px`;
        }
    });

    elements.btnCloseLogs.addEventListener('click', () => {
        elements.logDrawer.classList.remove('active');
        elements.logDrawer.style.bottom = `-${elements.logDrawer.offsetHeight}px`;
    });

    elements.btnLangToggle.addEventListener('click', () => {
        const nextLang = currentLang === 'zh' ? 'en' : 'zh';
        setLanguage(nextLang);
    });

    // Enter to insert newline, not send
    elements.chatInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) { // Only send on Enter, not Shift+Enter
            e.preventDefault(); // Prevent default Enter behavior (newline)
            if (!elements.btnSend.disabled) sendMessage();
        } else if (e.key === 'Enter' && e.shiftKey) {
            // Wait for the browser to insert the newline, then trigger input event to resize
            setTimeout(() => {
                this.dispatchEvent(new Event('input'));
            }, 0);
        }
    });

    // Send Button Click
    elements.btnSend.addEventListener('click', () => {
        if (!elements.btnSend.disabled) sendMessage();
    });

    // Send Message Logic
    async function sendMessage() {
        const text = elements.chatInput.value.trim();
        if (!text || isProcessing) return;

        // 如果当前没有会话，先创建一个 (Create session if none exists)
        if (!currentSessionId) {
            await createSession();
            if (!currentSessionId) {
                console.error("Failed to create session automatically");
                return;
            }
        }

        isProcessing = true;
        autoScrollLockedByUser = false;
        elements.chatInput.value = '';
        elements.chatInput.style.height = 'auto';
        elements.btnSend.disabled = true;

        // Hide welcome
        if (elements.welcomeState) {
            elements.welcomeState.style.display = 'none';
        }

        // Add user message
        elements.chatHistory.insertAdjacentHTML('beforeend', `
            <div class="message user-message">
                <img src="/static/images/user_avatar.png" class="avatar user-avatar-img" alt="User">
                <div class="content"><p>${escapeHtml(text)}</p></div>
            </div>
        `);
        scrollToBottom(true);

        // Add thinking placeholder
        const thinkingId = 'msg-' + Date.now();
        elements.chatHistory.insertAdjacentHTML('beforeend', `
            <div class="message ai-message" id="${thinkingId}">
                <div class="avatar"><i class="fa-solid fa-robot"></i></div>
                <div class="content temp-content">
                    <div class="thinking-indicator">
                        <div class="thinking-spinner"></div>
                        <span class="thinking-text">深度思考中，正在检索知识库...</span>
                    </div>
                </div>
            </div>
        `);
        scrollToBottom(true);

        // Gather history
        const history = [];
        const msgNodes = elements.chatHistory.querySelectorAll('.message');
        // Exclude the currently added user node which is the last one in DOM
        for (let i = 0; i < msgNodes.length - 1; i++) {
            const node = msgNodes[i];
            const isUser = node.classList.contains('user-message');
            // Extract the text content, skip sources blocks from AI messages if any
            let contentStr = '';
            if (isUser) {
                contentStr = node.querySelector('.content').textContent;
            } else {
                // Clone node to remove sources-box and temp spinner
                const clone = node.querySelector('.content').cloneNode(true);
                const sourcesBox = clone.querySelector('.sources-box');
                if (sourcesBox) sourcesBox.remove();
                contentStr = clone.textContent;
            }
            if (contentStr.trim()) {
                history.push({
                    role: isUser ? "user" : "assistant",
                    content: contentStr.trim()
                });
            }
        }

        try {
            const res = await fetch('/api/query', {
                method: 'POST',
                headers: getHeaders(true),
                body: JSON.stringify({
                    query: text,
                    category: 'all',  // Using intent extraction instead of dropdown
                    history: history
                })
            });
            if (!res.ok || !res.body) {
                throw new Error(`HTTP ${res.status}`);
            }

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            const contentNode = document.getElementById(thinkingId).querySelector('.content');
            
            // 首次收到 token 时切换为正常内容区
            let rawText = '';
            let firstToken = true;
            let sources = [];
            let hasError = false;
            let hasToken = false;

            function renderMarkdown() {
                const rawHtml = marked.parse(rawText);
                contentNode.innerHTML = typeof DOMPurify !== "undefined" ? DOMPurify.sanitize(rawHtml) : rawHtml;
                scrollToBottom(); // 这里的 force 默认为 false，实现智能跟随 (Smart scroll during streaming)
            }

            // 使用 requestAnimationFrame 节流渲染
            let renderPending = false;
            function scheduleRender() {
                if (!renderPending) {
                    renderPending = true;
                    requestAnimationFrame(() => {
                        renderMarkdown();
                        renderPending = false;
                    });
                }
            }

            async function readStream() {
                let buffer = '';
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) {
                        if (buffer.trim()) {
                            processSseBuffer(`${buffer}\n\n`, (currentEvent, currentData) => {
                                if (currentEvent === 'token') {
                                    if (firstToken) {
                                        contentNode.classList.remove('temp-content');
                                        contentNode.innerHTML = '';
                                        firstToken = false;
                                    }
                                    try {
                                        const payload = JSON.parse(currentData);
                                        rawText += payload.text;
                                        hasToken = true;
                                        scheduleRender();
                                    } catch (e) {
                                        console.error("Error parsing token JSON:", e);
                                    }
                                } else if (currentEvent === 'status') {
                                    try {
                                        const payload = JSON.parse(currentData);
                                        const thinkingText = contentNode.querySelector('.thinking-text');
                                        if (thinkingText) thinkingText.textContent = payload.status || currentData;
                                    } catch(e) {}
                                } else if (currentEvent === 'sources') {
                                    try { sources = JSON.parse(currentData); } catch(e) {}
                                } else if (currentEvent === 'error') {
                                    hasError = true;
                                    try {
                                        const payload = JSON.parse(currentData);
                                        contentNode.classList.remove('temp-content');
                                        contentNode.innerHTML = `<p style="color:var(--error);">⚠️ ${escapeHtml(payload.error || currentData)}</p>`;
                                    } catch(e) {
                                        contentNode.classList.remove('temp-content');
                                        contentNode.innerHTML = `<p style="color:var(--error);">⚠️ ${escapeHtml(currentData)}</p>`;
                                    }
                                }
                            });
                        }
                        break;
                    }

                    buffer += decoder.decode(value, { stream: true });
                    buffer = processSseBuffer(buffer, (currentEvent, currentData) => {
                        if (currentEvent === 'token') {
                            if (firstToken) {
                                contentNode.classList.remove('temp-content');
                                contentNode.innerHTML = '';
                                firstToken = false;
                            }
                            try {
                                const payload = JSON.parse(currentData);
                                rawText += payload.text;
                                hasToken = true;
                                scheduleRender();
                            } catch (e) {
                                console.error("Error parsing token JSON:", e);
                            }
                        } else if (currentEvent === 'status') {
                            try {
                                const payload = JSON.parse(currentData);
                                const thinkingText = contentNode.querySelector('.thinking-text');
                                if (thinkingText) thinkingText.textContent = payload.status || currentData;
                            } catch(e) {}
                        } else if (currentEvent === 'sources') {
                            try { sources = JSON.parse(currentData); } catch(e) {}
                        } else if (currentEvent === 'error') {
                            hasError = true;
                            try {
                                const payload = JSON.parse(currentData);
                                contentNode.classList.remove('temp-content');
                                contentNode.innerHTML = `<p style="color:var(--error);">⚠️ ${escapeHtml(payload.error || currentData)}</p>`;
                            } catch(e) {
                                contentNode.classList.remove('temp-content');
                                contentNode.innerHTML = `<p style="color:var(--error);">⚠️ ${escapeHtml(currentData)}</p>`;
                            }
                        }
                    });
                }
            }

            await readStream();

            if (!hasError) {
                if (hasToken) {
                    // 最终完整渲染一次 Markdown
                    renderMarkdown();
                } else {
                    contentNode.classList.remove('temp-content');
                    contentNode.innerHTML = '<p>未收到模型返回内容，请稍后重试。</p>';
                }

                // 渲染参考来源
                if (sources && sources.length > 0) {
                    const sourceHtml = sources.map(s => `<span class="source-tag"><i class="fa-solid fa-link"></i> ${s}</span>`).join('');
                    contentNode.innerHTML += `
                        <div class="sources-box">
                            <div class="sources-title"><i class="fa-solid fa-book-open"></i> 参考来源：</div>
                            <div class="sources-list">${sourceHtml}</div>
                        </div>
                    `;
                }

                // --- 关键：保存到会话历史 (Persist to backend session) ---
                const messagePair = {
                    user: text,
                    assistant: rawText,
                    sources: sources || []
                };
                chatHistory.push(messagePair);
                
                if (currentSessionId) {
                    fetch(`/api/sessions/${currentSessionId}/message`, {
                        method: 'POST',
                        headers: getHeaders(true),
                        body: JSON.stringify({ message_pair: messagePair })
                    }).then(() => {
                        // 如果是第一条消息，刷新列表以更新标题
                        if (chatHistory.length === 1) loadSessions();
                    });
                }
            }
            scrollToBottom(); // 这里也遵循智能跟随 (Smart scroll after stream ends)

        } catch (error) {
            console.error(error);
            const contentContainer = document.getElementById(thinkingId)?.querySelector('.content');
            if (contentContainer) {
                contentContainer.innerHTML = `<p style="color:var(--error);">⚠️ 发生错误：无法连接到后端大模型服务。</p>`;
            }
        } finally {
            isProcessing = false;
            autoScrollLockedByUser = false;
            if (elements.chatInput.value.trim().length > 0) {
                elements.btnSend.disabled = false;
            }
        }
    }

    // Reindex Logic via SSE
    function triggerReindex(showToastUI = true) {
        return new Promise((resolve, reject) => {
            if (showToastUI) {
                const modal = elements.toastOverlay.querySelector('.glass-modal');
                const existingCheck = modal.querySelector('.reindex-success-icon');
                if (existingCheck) existingCheck.remove();
                const spinnerEl = elements.toastOverlay.querySelector('.spinner');
                spinnerEl.style.display = '';

                elements.toastTitle.textContent = currentLang === 'zh' ? "准备重新构建知识库..." : "Rebuilding Knowledge Base...";
                elements.toastDesc.textContent = currentLang === 'zh' ? "正在解析文档，请稍候" : "Parsing documents, please wait";
                elements.toastOverlay.classList.add('active');
            }

            if (elements.btnReindex) elements.btnReindex.disabled = true;

            fetch('/api/index', { method: 'POST', headers: getHeaders() }).then(response => {
                if (!response.ok || !response.body) {
                    throw new Error(`HTTP ${response.status}`);
                }
                const reader = response.body.getReader();
                const decoder = new TextDecoder();

                let buffer = '';
                let reindexFinished = false;

                function finalizeReindex(delayMs = 1200) {
                    if (reindexFinished) return;
                    reindexFinished = true;
                    try { reader.cancel(); } catch (e) {}
                    
                    if (showToastUI) {
                        setTimeout(() => {
                            elements.toastOverlay.classList.remove('active');
                            if (elements.btnReindex) elements.btnReindex.disabled = false;
                            loadStatus();
                            resolve(true);
                        }, delayMs);
                    } else {
                        if (elements.btnReindex) elements.btnReindex.disabled = false;
                        loadStatus();
                        resolve(true);
                    }
                }

                function processReindexStream(reader, decoder, buffer) {
                    reader.read().then(({done, value}) => {
                        if (reindexFinished) return;
                        if (done) {
                            if (buffer.trim() && showToastUI) {
                                processSseBuffer(`${buffer}\n\n`, handleReindexEvent);
                            }
                            finalizeReindex(800);
                            return;
                        }

                        buffer += decoder.decode(value, { stream: true });
                        if (showToastUI) {
                            buffer = processSseBuffer(buffer, handleReindexEvent);
                        } else {
                            // If no UI, just consume buffer
                            buffer = ''; 
                        }

                        if (!reindexFinished) {
                            processReindexStream(reader, decoder, buffer);
                        }
                    }).catch(err => {
                        console.error("SSE End error: ", err);
                        finalizeReindex(0);
                    });
                }

                function handleReindexEvent(currentEvent, currentData) {
                    if (!showToastUI) return;
                    elements.toastDesc.textContent = currentData;
                    
                    const progMatch = currentData.match(/\((\d+)\/(\d+)\)/);
                    if (progMatch) {
                        const current = parseInt(progMatch[1]);
                        const total = parseInt(progMatch[2]);
                        const percent = Math.min(100, Math.max(0, (current / total) * 100));
                        elements.toastProgressBar.style.width = percent + '%';
                    }

                    if (currentEvent === 'progress') {
                        elements.toastTitle.textContent = currentLang === 'zh' ? "正在处理文档..." : "Processing documents...";
                        elements.toastProgressContainer.style.display = 'block';
                    } else if (currentEvent === 'success') {
                        elements.toastTitle.innerHTML = `<span style="color:var(--success)">${currentLang === 'zh' ? '构建完成！' : 'Build Complete!'}</span>`;
                        elements.toastOverlay.querySelector('.spinner').style.display = 'none';
                        elements.toastProgressContainer.style.display = 'none';
                        elements.toastProgressBar.style.width = '0%';
                        const existingCheck = elements.toastOverlay.querySelector('.reindex-success-icon');
                        if (!existingCheck) {
                            elements.toastOverlay.querySelector('h3').insertAdjacentHTML('beforebegin', '<div class="reindex-success-icon" style="font-size:3rem;color:var(--success);margin-bottom:10px;"><i class="fa-solid fa-check-circle"></i></div>');
                        }
                        finalizeReindex(1000);
                    } else if (currentEvent === 'error') {
                        elements.toastTitle.innerHTML = `<span style="color:var(--error)">${currentLang === 'zh' ? '构建超时或失败' : 'Timeout or Error'}</span>`;
                        elements.toastOverlay.querySelector('.spinner').style.display = 'none';
                        elements.toastProgressContainer.style.display = 'none';
                        finalizeReindex(3000);
                    }
                }

                processReindexStream(reader, decoder, buffer);
            }).catch(err => {
                console.error("Reindex request failed:", err);
                if (showToastUI) {
                    elements.toastTitle.innerHTML = `<span style="color:var(--error)">${currentLang === 'zh' ? '构建失败' : 'Failed'}</span>`;
                    elements.toastDesc.textContent = currentLang === 'zh' ? '无法连接到后端服务。' : 'Cannot connect to backend.';
                    elements.btnReindex.disabled = false;
                    setTimeout(() => {
                        elements.toastOverlay.classList.remove('active');
                        resolve(false);
                    }, 3000);
                } else {
                    if (elements.btnReindex) elements.btnReindex.disabled = false;
                    resolve(false);
                }
            });
        });
    }

    elements.btnReindex.addEventListener('click', () => triggerReindex(true));

    function scrollToBottom(force = false) {
        const container = elements.chatHistory;
        if (!container) return;

        if (!force && autoScrollLockedByUser) return;

        if (force || isNearBottom()) {
            // 使用 setTimeout 确保在布局更新后执行
            setTimeout(() => {
                isProgrammaticScroll = true;
                container.scrollTop = container.scrollHeight;
                requestAnimationFrame(() => {
                    isProgrammaticScroll = false;
                });
            }, 50);
        }
    }
});
