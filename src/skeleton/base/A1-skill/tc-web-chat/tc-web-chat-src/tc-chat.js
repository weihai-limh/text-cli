// ========== tc-chat.js ==========
// 会话历史 / 资源渲染 / 文件上传 / 提交主链 / Clean / 初始化
// 设计稿锚点：§3（会话/渲染）、§3.2.1（SYSTEM_PROMPTS 注入占位）、§12.3.10/§12.3.11
// 依赖（同 <script> 共享作用域）：t / runtimeConfig / buildSystemPrompts /
//   parseDirectives / tcDiscover / tcCacheInvalidate / createQuietBridge /
//   decideExecution / getApprovalMode

// ---------- 会话状态 ----------
// §3.2.1 SYSTEM_PROMPTS 注入：作为 conversationHistory 起始的 system 消息（位置占位，最后一期定）
let conversationHistory = buildSystemPrompts().map((c) => ({ role: 'system', content: c }));
let pendingAttachments = [];

// §4 多模态：按 rst_types 把 result 渲染成可读文本（前端不强制结构化，仅展示）
function renderTcTypes(result, types) {
    if (result == null) return '';
    try { return typeof result === 'string' ? result : JSON.stringify(result); }
    catch (e) { return String(result); }
}

// DOM 句柄（由 tc-integrate.js 在 DOMContentLoaded 后绑定；此处延迟取）
let messagesContainer, chatForm, userInput, statusElement, errorElement, attachmentsTray, uploadBtn, fileInput, cleanBtn, tcStatusEl;

// ---------- 资源渲染（<resources> 协议） ----------
const SECURITY = { whitelistEnabled: false, allowedHosts: [] };

function parseResources(content) {
    if (typeof content !== 'string') return null;
    const m = content.match(/^\s*<resources>([\s\S]*?)<\/resources>\s*$/);
    if (!m) return null;
    try {
        const arr = JSON.parse(m[1].trim().replace(/'/g, '"'));
        return Array.isArray(arr) ? arr : [arr];
    } catch (e) { return null; }
}

function detectType(url) {
    const u = String(url).split('?')[0].toLowerCase();
    if (/\.(png|jpe?g|gif|webp|avif|svg|bmp)$/.test(u)) return 'image';
    if (/\.(mp4|webm|ogg|mov|m4v)$/.test(u)) return 'video';
    if (/\.(mp3|wav|m4a|aac)$/.test(u)) return 'audio';
    if (/\.pdf$/.test(u)) return 'pdf';
    return 'webpage';
}

function safeUrl(url) {
    try {
        const u = new URL(url, location.href);
        if (u.protocol !== 'http:' && u.protocol !== 'https:') return null;
        if (SECURITY.whitelistEnabled && !SECURITY.allowedHosts.includes(u.hostname)) return null;
        return u.href;
    } catch (e) { return null; }
}

function fileName(url) {
    try {
        const u = new URL(url, location.href);
        const parts = u.pathname.split('/');
        return decodeURIComponent(parts[parts.length - 1]) || 'resource';
    } catch (e) { return 'resource'; }
}

function invalidResource(url) {
    const ph = document.createElement('div');
    ph.className = 'media-invalid';
    ph.textContent = t('invalidResource', { url });
    return ph;
}

function brokenImage() {
    const ph = document.createElement('div');
    ph.className = 'media-broken';
    ph.textContent = t('brokenImage');
    return ph;
}

function openLink(url) {
    const a = document.createElement('a');
    a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer';
    a.className = 'media-open-link';
    a.textContent = t('openInNewTab');
    return a;
}

function renderResource(url) {
    const safe = safeUrl(url);
    if (!safe) return invalidResource(url);
    const type = detectType(safe);
    if (type === 'image') {
        const block = document.createElement('div');
        block.className = 'media-item media-image-wrap';
        const img = document.createElement('img');
        img.className = 'media-image'; img.loading = 'lazy'; img.alt = fileName(safe);
        img.addEventListener('error', () => img.replaceWith(brokenImage()));
        img.src = safe; block.appendChild(img); return block;
    }
    if (type === 'video') {
        const block = document.createElement('div'); block.className = 'media-item';
        const v = document.createElement('video'); v.className = 'media-video'; v.controls = true; v.preload = 'none'; v.src = safe;
        block.appendChild(v); return block;
    }
    if (type === 'audio') {
        const block = document.createElement('div'); block.className = 'media-item';
        const a = document.createElement('audio'); a.className = 'media-audio'; a.controls = true; a.preload = 'none'; a.src = safe;
        block.appendChild(a); return block;
    }
    const block = document.createElement('div'); block.className = 'media-item';
    const details = document.createElement('details'); details.className = 'media-embed';
    const summary = document.createElement('summary');
    summary.textContent = (type === 'pdf' ? t('mediaPdf') : t('mediaWeb')) + fileName(safe);
    const body = document.createElement('div'); body.className = 'media-embed-body';
    details.appendChild(summary); details.appendChild(body);
    details.addEventListener('toggle', () => {
        if (details.open && !body.dataset.built) {
            body.dataset.built = '1';
            const iframe = document.createElement('iframe');
            iframe.className = 'media-iframe'; iframe.sandbox = 'allow-scripts allow-same-origin';
            iframe.referrerPolicy = 'no-referrer'; iframe.src = safe;
            body.appendChild(iframe); body.appendChild(openLink(safe));
        }
    });
    block.appendChild(details); return block;
}

function renderGallery(list) {
    const gallery = document.createElement('div'); gallery.className = 'media-gallery';
    list.forEach((item) => {
        const url = typeof item === 'string' ? item : (item && item.url);
        if (!url) return; gallery.appendChild(renderResource(url));
    });
    return gallery;
}

function addMessage(role, content) {
    const list = parseResources(content);
    const messageDiv = document.createElement('div');
    messageDiv.className = list ? 'message resource-message' : `message ${role}-message`;
    if (list) messageDiv.appendChild(renderGallery(list));
    else messageDiv.textContent = content;
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function showError(message) {
    errorElement.textContent = message;
    errorElement.style.display = 'block';
}

// 导出会话为 jsonl：只读外化 conversationHistory（本地 Blob 下载，不碰端点、不上传）
function exportConversationJsonl() {
    if (!conversationHistory.length) {
        showError(t('exportHistoryEmpty'));
        return false;
    }
    const pad = (n) => String(n).padStart(2, '0');
    const d = new Date();
    const ts = `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
    const blob = new Blob([conversationHistory.map((m) => JSON.stringify(m)).join('\n')], { type: 'application/x-ndjson' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tc-history-${ts}.jsonl`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    showError(t('exportHistoryDone', { n: conversationHistory.length }));
    return true;
}

// ---------- LLM 请求（非流式 + 流式） ----------
async function sendToLLM(messages) {
    statusElement.textContent = t('thinking');
    const requestHeaders = { ...runtimeConfig.headers };
    const ac = new AbortController();
    const timer = setTimeout(() => ac.abort(), 30000);
    let response;
    try {
        response = await fetch(runtimeConfig.baseUrl, {
            method: 'POST', headers: requestHeaders,
            body: JSON.stringify({
                model: runtimeConfig.model, messages: messages,
                max_tokens: runtimeConfig.maxTokens, temperature: runtimeConfig.temperature, stream: true
            }),
            signal: ac.signal
        });
    } catch (e) { clearTimeout(timer); throw e; }
    clearTimeout(timer);
    if (!response.ok) {
        let msg = `HTTP ${response.status}`;
        try {
            const errData = await response.json();
            if (errData && errData.error && errData.error.message) msg = errData.error.message;
        } catch (e) { /* ignore */ }
        throw new Error(msg);
    }
    const ct = response.headers.get('content-type') || '';
    if (ct.includes('text/event-stream')) return await readStreaming(response);
    const data = await response.json();
    if (data.error) throw new Error(data.error.message || t('apiErrorFallback'));
    const message = (data.choices && data.choices[0] && data.choices[0].message) || {};
    const content = message.content || '';
    addMessage('assistant', content);
    return content;
}

// 流式读取 SSE；收尾时 <resources> 整体替换为画廊。
// §12.3.10 流结束兜底：对 fullText 在 done 后由 parseDirectives（含 EOL 兜底）统一收口。
async function readStreaming(response) {
    statusElement.textContent = t('streaming');
    const bubble = document.createElement('div');
    bubble.className = 'message assistant-message';
    bubble.setAttribute('aria-live', 'off');
    messagesContainer.appendChild(bubble);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = ''; let fullText = ''; let potentialResource = false;
    const flush = () => { messagesContainer.scrollTop = messagesContainer.scrollHeight; };
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
            const rawEvent = buffer.slice(0, idx); buffer = buffer.slice(idx + 2);
            const line = rawEvent.trim();
            if (!line.startsWith('data:')) continue;
            const dataStr = line.slice(5).trim();
            if (dataStr === '[DONE]') continue;
            let evt; try { evt = JSON.parse(dataStr); } catch (e) { continue; }
            const choice = (evt.choices && evt.choices[0]) || {};
            const delta = choice.delta || {};
            if (delta.content) {
                fullText += delta.content;
                const trimmed = fullText.trimStart();
                if (/^\s*<resources[\s>]/.test(trimmed)) {
                    potentialResource = true; bubble.textContent = '';
                } else if (!potentialResource) {
                    bubble.textContent = fullText;
                }
                flush();
            }
        }
    }
    if (potentialResource) {
        const list = parseResources(fullText);
        if (list) {
            const galleryMsg = document.createElement('div');
            galleryMsg.className = 'message resource-message';
            galleryMsg.appendChild(renderGallery(list));
            bubble.replaceWith(galleryMsg);
        } else { bubble.textContent = fullText; }
    }
    bubble.setAttribute('aria-live', 'polite');
    return fullText; // §12.3.10：调用方可对 fullText 跑 parseDirectives 收尾
}

// ---------- 文件上传 + 多模态附件 ----------
function resolveUploadUrl() {
    const cdn = (runtimeConfig.cdnUrl || '').trim().replace(/\/+$/, '');
    if (cdn) return cdn + '/upload';
    try {
        const b = new URL(runtimeConfig.baseUrl, location.href);
        return (b.origin || location.origin) + '/upload';
    } catch (e) { return location.origin + '/upload'; }
}

function mediaPartFor(type, url) {
    if (type === 'image') return { type: 'image_url', image_url: { url } };
    if (type === 'video') return { type: 'video_url', video_url: { url } };
    if (type === 'audio') return { type: 'audio_url', audio_url: { url } };
    return { type: 'file_url', file_url: { url } };
}

function makeChip(att, withRemove, index) {
    const chip = document.createElement('div'); chip.className = 'att-chip att-' + att.type;
    if (att.type === 'image') {
        const img = document.createElement('img'); img.src = att.url; img.alt = att.name; img.className = 'att-thumb';
        chip.appendChild(img);
    } else {
        const icon = document.createElement('span'); icon.className = 'att-icon';
        icon.textContent = att.type === 'video' ? '🎬' : att.type === 'audio' ? '🔊' : '📄';
        chip.appendChild(icon);
    }
    const name = document.createElement('span'); name.className = 'att-name'; name.textContent = att.name; name.title = att.name;
    chip.appendChild(name);
    if (withRemove) {
        const x = document.createElement('button'); x.type = 'button'; x.className = 'att-remove';
        x.setAttribute('aria-label', t('removeAtt', { name: att.name })); x.textContent = '×';
        x.addEventListener('click', () => removeAttachment(index));
        chip.appendChild(x);
    }
    return chip;
}

function renderAttachmentsTray() {
    attachmentsTray.innerHTML = '';
    if (pendingAttachments.length === 0) { attachmentsTray.style.display = 'none'; return; }
    attachmentsTray.style.display = 'flex';
    pendingAttachments.forEach((att, i) => attachmentsTray.appendChild(makeChip(att, true, i)));
}

function removeAttachment(i) { pendingAttachments.splice(i, 1); renderAttachmentsTray(); }

function addUserBubble(text, attachments) {
    const div = document.createElement('div'); div.className = 'message user-message';
    if (text) { const p = document.createElement('div'); p.textContent = text; div.appendChild(p); }
    if (attachments && attachments.length) {
        const tray = document.createElement('div'); tray.className = 'att-inline';
        attachments.forEach((att) => tray.appendChild(makeChip(att, false, -1)));
        div.appendChild(tray);
    }
    messagesContainer.appendChild(div);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

async function uploadFile(file) {
    const url = resolveUploadUrl();
    const fd = new FormData();
    fd.append('file', file, file.name);
    const headers = { ...runtimeConfig.headers };
    delete headers['Content-Type'];
    statusElement.textContent = t('uploading', { name: file.name });
    try {
        const res = await fetch(url, { method: 'POST', headers, body: fd });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.error || ('HTTP ' + res.status));
        }
        const data = await res.json();
        if (!data.url) throw new Error('upload response missing url');
        pendingAttachments.push({ url: data.url, name: data.name || file.name, type: detectType(file.name) });
        renderAttachmentsTray();
        statusElement.textContent = t('statusReady');
    } catch (e) {
        console.error('上传失败:', e);
        showError(t('uploadFailed', { msg: e.message }));
        statusElement.textContent = t('statusReady');
    }
}

// ---------- 桥接入点：免打扰轮编排实例 ----------
// §12.3.7 出口 / §12.3.9 CORS / §5 人闸决策
let quietBridge = null;
function initQuietBridge() {
    quietBridge = createQuietBridge({
        parseDirectives,
        decideExecution,
        // 真接通：交给 tc-quiet.js 的 runTool（POST tc_endpoint + 6 码闭集解析）
        runTool: (d) => runTool(d, {
            describeBridgeError: (e) => quietBridge.describeBridgeError(e)
        }),
        onPlain: (text) => { if (text && text.trim()) addMessage('assistant', text); },
        onToolResult: (d, res) => {
            // §4 信封展示：成功显示结果，失败显示码文案（不伪造成功）
            const head = `↳ ${d.domain};${d.action}`;
            if (res.ok) {
                reportToolSuccess();                                 // §5 CircuitBreaker 清零
                const payload = (res.types && res.result != null)
                    ? renderTcTypes(res.result, res.types)           // §4 多模态 rst_types
                    : res.result;
                // R1：对象类结果美化呈现（去信封已具备：payload = res.result，信封不进 UI）
                const display = (typeof payload === 'object' && payload !== null)
                    ? JSON.stringify(payload, null, 2)
                    : payload;
                addMessage('assistant', `${head} ✓ ${display}`);
                // R1：工具结果入史，供后续多轮连贯（不做二次 LLM 合成回环）
                conversationHistory.push({ role: 'tool', content: String(display) });
            } else {
                const tripped = reportToolFailure();                 // §5 连续失败熔断
                const extra = tripped ? t('circuitBreaker') : '';
                addMessage('assistant', `${head} ✗ [${res.code}] ${res.message}${extra}`);
                // R1：失败也入史（如实记录，不伪造协议码）
                conversationHistory.push({ role: 'tool', content: `${head} ✗ [${res.code}] ${res.message}` });
            }
        },
        onAsk: (d, decision) => {
            // R2：渲染真实人审卡片（确认/拒绝/中止三态均可操作），不再只弹文字
            const card = approvalCard(d, decision);          // 纯数据：label 与发送原语逐字节一致
            const wrap = document.createElement('div');
            wrap.className = 'tc-approval-card';
            wrap.style.cssText = 'margin:6px 0;padding:8px 10px;border:1px solid #c9a227;border-radius:8px;background:#fff8e6;color:#333;';
            const head = document.createElement('div');
            head.textContent = `${t('approvalNeedConfirm', { reason: decision.reason })}: AI:${card.label}`;
            head.style.cssText = 'margin-bottom:6px;font-weight:600;';
            const mkBtn = (key, bg) => {
                const b = document.createElement('button');
                b.textContent = t(key);
                b.style.cssText = `margin-right:6px;padding:4px 10px;border:1px solid #bbb;border-radius:6px;cursor:pointer;background:${bg};`;
                return b;
            };
            const btnConfirm = mkBtn('approvalConfirmBtn', '#4caf50');
            const btnReject  = mkBtn('approvalRejectBtn', '#f0ad4e');
            const btnAbort   = mkBtn('approvalAbortBtn', '#d9534f');
            const lock = () => { btnConfirm.disabled = btnReject.disabled = btnAbort.disabled = true; };
            btnConfirm.onclick = async () => {
                lock();
                // 确认 → 真实执行（复用 runTool + onToolResult 闭幕逻辑，不伪造任何协议码）
                const res = await runTool(d, { describeBridgeError: (e) => quietBridge.describeBridgeError(e) });
                onToolResult(d, res);
                wrap.style.borderColor = '#4caf50';
            };
            btnReject.onclick = () => {
                lock();
                // 拒绝 → 本地 UI 决策，不产生 ACCESS_DENIED/SERVICE_DENIED（§5 铁律）
                addMessage('assistant', t('approvalRejected', { label: 'AI:' + card.label }));
                wrap.style.borderColor = '#d9534f';
            };
            btnAbort.onclick = () => {
                lock();
                // 中止 → 同拒绝语义，仅文案差异（§5 人审本地中止，无信封码）
                addMessage('assistant', t('approvalAborted', { label: 'AI:' + card.label }));
                wrap.style.borderColor = '#d9534f';
            };
            wrap.appendChild(head);
            wrap.appendChild(btnConfirm); wrap.appendChild(btnReject); wrap.appendChild(btnAbort);
            if (typeof messagesContainer !== 'undefined' && messagesContainer) messagesContainer.appendChild(wrap);
            else addMessage('assistant', `${t('approvalNeedConfirm', { reason: decision.reason })}: AI:${card.label}`); // 兜底
        },
        // §4 异步任务：pending 后用 AI:task;status 轮询回填
        onAsyncTask: async (taskId) => {
            addMessage('assistant', t('asyncPolling', { task: taskId }));
            for (let i = 0; i < 30; i++) {
                await new Promise((r) => setTimeout(r, 1000));
                const r = await runTool({ domain: 'task', action: 'status', params: [taskId] }, {
                    describeBridgeError: (e) => quietBridge.describeBridgeError(e)
                });
                if (r.ok && r.result && r.result.status !== 'pending') {
                    addMessage('assistant', `↳ task;status ✓ ${r.result.status}`);
                    return;
                }
            }
            addMessage('assistant', t('asyncTimeout'));
        }
    });
}

// 处理一轮 LLM 完整文本：若有 AI: 指令走免打扰轮，否则按普通回复
async function handleAssistantTurn(fullText) {
    // R3：tc 未启用时，即便文本含 AI: 原语也按纯文本呈现，不进免打扰轮、不解析、不执行
    if (runtimeConfig.tc_enabled && hasDirectives(fullText)) {
        // R1：补回 LLM 前导语（剥掉 AI: 行、保留自然语言）；handleLLMRound 在有指令时不会显示
        //     自然语言（见 tc-quiet.js:80-91 仅在无指令时 onPlain），故此处补显不会重复
        const preamble = stripDirectives(fullText);
        if (preamble && preamble.trim()) addMessage('assistant', preamble);
        await quietBridge.handleLLMRound(fullText);
    } else if (fullText && fullText.trim()) {
        addMessage('assistant', fullText);
    }
}

// ---------- 提交主链 ----------
function bindChatForm() {
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const userMessage = userInput.value.trim();
        if (!userMessage && pendingAttachments.length === 0) return;
        userInput.disabled = true;
        const submitBtn = chatForm.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        let content;
        if (pendingAttachments.length === 0) content = userMessage;
        else {
            content = [{ type: 'text', text: userMessage }];
            pendingAttachments.forEach((att) => content.push(mediaPartFor(att.type, att.url)));
        }
        try {
            addUserBubble(userMessage, pendingAttachments);
            conversationHistory.push({ role: 'user', content });
            userInput.value = ''; userInput.style.height = 'auto';
            pendingAttachments = []; renderAttachmentsTray();
            // §12.3.10 流结束兜底：sendToLLM 返回的 fullText 在此统一收口
            const assistantResponse = await sendToLLM(conversationHistory);
            await handleAssistantTurn(assistantResponse);
            conversationHistory.push({ role: 'assistant', content: assistantResponse });
            const MAX_HISTORY = 100;
            if (conversationHistory.length > MAX_HISTORY) {
                conversationHistory = conversationHistory.slice(-MAX_HISTORY);
            }
        } catch (error) {
            console.error('请求失败:', error);
            let detail;
            // §12.3.9：fetch 网络层失败（TypeError）→ 说人话，不污染协议层
            if (error instanceof TypeError || error.name === 'TypeError') {
                detail = t('networkConnectErr', { baseUrl: runtimeConfig.baseUrl });
            } else { detail = error.message; }
            showError(t('requestFailed', { msg: detail }));
        } finally {
            userInput.disabled = false; submitBtn.disabled = false;
            userInput.focus(); statusElement.textContent = t('statusReady');
        }
    });
}

// ---------- Clean：§12.3.11 缓存生命周期 ----------
function bindCleanBtn() {
    cleanBtn.addEventListener('click', () => {
        messagesContainer.innerHTML = '';
        pendingAttachments = []; renderAttachmentsTray();
        errorElement.style.display = 'none';
        // 先失效 tc 缓存（§12.3.11），再重建 system 段 → 摘要描述同步降级为"纯对话模式"
        tcCacheInvalidate();
        conversationHistory = buildSystemPrompts().map((c) => ({ role: 'system', content: c }));
        statusElement.textContent = t('statusReady');
        userInput.focus();
    });
}

// ---------- 初始化 ----------
function bindUpload() {
    uploadBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', async () => {
        const files = Array.from(fileInput.files || []);
        fileInput.value = '';
        for (const f of files) await uploadFile(f);
    });
}

function autoGrow() {
    userInput.style.height = 'auto';
    const max = Math.round(window.innerHeight * 0.4);
    userInput.style.height = Math.min(userInput.scrollHeight, max) + 'px';
}

function bindInput() {
    userInput.addEventListener('input', autoGrow);
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
            e.preventDefault(); chatForm.requestSubmit();
        }
    });
}

// 由 tc-integrate.js 在 DOM 就绪后调用：抓取 DOM 句柄 + 绑定事件 + 触发 tcDiscover
function initChatDom() {
    messagesContainer = document.getElementById('messages');
    chatForm = document.getElementById('chatForm');
    userInput = document.getElementById('userInput');
    statusElement = document.getElementById('status');
    errorElement = document.getElementById('error');
    attachmentsTray = document.getElementById('attachmentsTray');
    uploadBtn = document.getElementById('uploadBtn');
    fileInput = document.getElementById('fileInput');
    cleanBtn = document.getElementById('cleanBtn');
    tcStatusEl = document.getElementById('tcStatus');   // §12.3 可观测状态灯
    initQuietBridge();
    bindChatForm(); bindCleanBtn(); bindUpload(); bindInput();
}

// §12.3 可观测：把桥状态点亮成绿/黄/红（不增逻辑，只可视化可恢复分叉）
function setTcStatusLight(disc) {
    if (!tcStatusEl) return;
    let color, text;
    if (disc && disc.ok && !disc.stale) { color = '#2e7d32'; text = t('tcReady'); }
    else if (disc && disc.ok && disc.stale) { color = '#f9a825'; text = t('tcOffline') + t('staleCache'); }
    else { color = '#d32f2f'; text = t('tcOffline'); }
    if (disc && disc.hint) text += ' — ' + disc.hint;
    tcStatusEl.style.color = color;
    tcStatusEl.textContent = text;
}

async function onAppLoad() {
    applyLang(currentLang);
    if (typeof loadConfigToForm === 'function') loadConfigToForm();
    initChatDom();
    addMessage('assistant', t('greeting'));
    // R3：tc 未启用时跳过去发现，状态保持"纯聊天"，不残留 tc 痕迹、不发起发现请求
    if (!runtimeConfig.tc_enabled) {
        statusElement.textContent = t('tcOffline');
        return;                       // 状态灯 #tcStatus 保持初始空态（=未启用）
    }
    // §12.3.8 拉取失败可降级：端点空/拉取失败均不阻断聊天主链
    const disc = await tcDiscover();
    statusElement.textContent = disc.ok ? t('tcReady') : t('tcOffline');
    setTcStatusLight(disc);
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        handleAssistantTurn, onAppLoad, initChatDom, exportConversationJsonl,
        getConversationHistory: () => conversationHistory,
        setConversationHistory: (h) => { conversationHistory = h; }
    };
}
