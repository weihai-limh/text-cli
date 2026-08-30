// ========== tc-integrate.js ==========
// 唯一胶水层：知道 HTML 结构，绑定所有 DOM 事件，串起各源模块。
// 设计稿锚点：§11.2（唯一知道行号）/ §3.5（人闸下拉 + tc 端点字段）
// 依赖（同 <script> 共享作用域）：runtimeConfig / saveConfig / loadConfigToForm /
//   t / LANGS / applyLang / bindLangButtons / setApprovalMode / getApprovalMode /
//   onAppLoad / showError / exportConversationJsonl / getTcCache

// ---------- 配置面板（旧 html 547–642 迁此） ----------
function bindConfigPanel() {
    const toggleConfigBtn = document.getElementById('toggleConfig');
    const configPanel = document.getElementById('configPanel');
    const toggleHeadersBtn = document.getElementById('toggleHeaders');
    const headersEditor = document.getElementById('headersEditor');
    const toggleCdnBtn = document.getElementById('toggleCdn');
    const cdnEditor = document.getElementById('cdnEditor');
    const saveConfigBtn = document.getElementById('saveConfig');
    const cancelConfigBtn = document.getElementById('cancelConfig');
    const exportHistoryBtn = document.getElementById('exportHistory');
    const cfgBaseUrl = document.getElementById('cfgBaseUrl');
    const cfgModel = document.getElementById('cfgModel');
    const cfgHeaders = document.getElementById('cfgHeaders');
    const cfgCdn = document.getElementById('cfgCdn');
    const errorElement = document.getElementById('error');

    loadConfigToForm = function () {
        cfgBaseUrl.value = runtimeConfig.baseUrl;
        cfgModel.value = runtimeConfig.model;
        cfgHeaders.value = JSON.stringify(runtimeConfig.headers, null, 2);
        cfgCdn.value = JSON.stringify({ cdn_url: runtimeConfig.cdnUrl }, null, 2);
        // §2 六配置 + §3.5 人闸下拉（头部 approvalSelect / 面板 approvalSelectCfg 两处）
        const en = document.getElementById('cfgTcEnabled');
        const ep = document.getElementById('cfgTcEndpoint');
        const tk = document.getElementById('cfgTcToken');
        const at = document.getElementById('cfgTcAccessToken');
        const sc = document.getElementById('cfgTcScope');
        const pp = document.getElementById('cfgTcPathEnabled');
        if (en) en.checked = !!runtimeConfig.tc_enabled;
        if (pp) pp.checked = !!runtimeConfig.tc_path_enabled;
        if (ep) ep.value = runtimeConfig.tc_endpoint || '';
        if (tk) tk.value = runtimeConfig.service_token || '';
        if (at) at.value = runtimeConfig.access_token || '';
        if (sc) sc.value = runtimeConfig.tc_scope || '';
        // §3.5 人闸/语言下拉：头部与面板两份都要同步（id 列表遍历，兼容双实例）
        syncSelectValue(['approvalSelect', 'approvalSelectCfg'], runtimeConfig.auto_execute || 'readonly');
        syncLangSelect();
        applyLang(currentLang);
    };

    toggleConfigBtn.addEventListener('click', () => {
        if (!configPanel.classList.contains('show')) loadConfigToForm();
        configPanel.classList.toggle('show');
    });
    toggleHeadersBtn.addEventListener('click', () => headersEditor.classList.toggle('show'));
    toggleCdnBtn.addEventListener('click', () => cdnEditor.classList.toggle('show'));
    cancelConfigBtn.addEventListener('click', () => {
        configPanel.classList.remove('show'); headersEditor.classList.remove('show');
    });
    // 导出会话为 jsonl：本地 Blob 下载，只读外化 conversationHistory（含 system/工具回填/信封码）
    exportHistoryBtn.addEventListener('click', () => exportConversationJsonl());

    saveConfigBtn.addEventListener('click', () => {
        const baseUrl = cfgBaseUrl.value.trim();
        if (!baseUrl) { showError(t('baseUrlEmpty')); return; }
        try {
            const parsedHeaders = JSON.parse(cfgHeaders.value.trim());
            runtimeConfig.baseUrl = baseUrl;
            runtimeConfig.model = cfgModel.value.trim() || 'default-model';
            runtimeConfig.headers = parsedHeaders;
            try {
                const parsedCdn = JSON.parse(cfgCdn.value.trim());
                runtimeConfig.cdnUrl = (parsedCdn.cdn_url || '').trim();
            } catch (e) { runtimeConfig.cdnUrl = ''; }

            // §2 落库：六配置项
            const en = document.getElementById('cfgTcEnabled');
            const ep = document.getElementById('cfgTcEndpoint');
            const tk = document.getElementById('cfgTcToken');
            const at = document.getElementById('cfgTcAccessToken');
            const sc = document.getElementById('cfgTcScope');
            const pp = document.getElementById('cfgTcPathEnabled');
            if (en) runtimeConfig.tc_enabled = en.checked;
            if (pp) runtimeConfig.tc_path_enabled = pp.checked;
            if (ep) runtimeConfig.tc_endpoint = ep.value.trim();
            if (tk) runtimeConfig.service_token = tk.value.trim();
            if (at) runtimeConfig.access_token = at.value.trim();
            if (sc) runtimeConfig.tc_scope = sc.value.trim();
            // §3.5 人闸：取头部或面板任一处的值（两处绑定同一 state）
            const apHead = document.getElementById('approvalSelect');
            const apCfg = document.getElementById('approvalSelectCfg');
            const apVal = (apHead && apHead.value) || (apCfg && apCfg.value);
            if (apVal) setApprovalMode(apVal);

            errorElement.textContent = t('configSaved');
            errorElement.style.background = '#e8f5e9';
            errorElement.style.color = '#2e7d32';
            errorElement.style.display = 'block';
            setTimeout(() => {
                errorElement.style.display = 'none';
                errorElement.style.background = '#ffebee';
                errorElement.style.color = '#d32f2f';
            }, 2000);
            configPanel.classList.remove('show');
            headersEditor.classList.remove('show');
            saveConfig(runtimeConfig);
            // §12.3.11 端点/令牌变更：重建缓存并刷新状态灯（不阻断主链）
            if (typeof tcDiscover === 'function') {
                tcDiscover().then((disc) => {
                    if (typeof setTcStatusLight === 'function') setTcStatusLight(disc);
                });
            }
        } catch (e) {
            showError(t('headersJsonErr', { msg: e.message }));
        }
    });
}

// 同步多个同义下拉（头部 + 面板两份）的选中值
function syncSelectValue(ids, value) {
    ids.forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.value = value;
    });
}
// 填充并同步所有语言下拉（头部 langSelect + 面板 langSelectCfg）
function syncLangSelect() {
    ['langSelect', 'langSelectCfg'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) {
            if (!el.options.length) el.innerHTML = buildLangOptions();
            el.value = currentLang;
        }
    });
}

// ---------- 语言下拉 + 人闸下拉（头部 + 面板双实例都绑） ----------
function bindUiControls() {
    ['langSelect', 'langSelectCfg'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', () => applyLang(el.value));
    });
    ['approvalSelect', 'approvalSelectCfg'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', () => setApprovalMode(el.value));
    });
}

// ---------- 全部绑定 + 启动 ----------
function bootTcWebChat() {
    bindConfigPanel();
    bindUiControls();
    // 聊天 DOM + 事件由 tc-chat.js 的 initChatDom 负责（它也在 onAppLoad 调）
    window.addEventListener('DOMContentLoaded', () => {
        onAppLoad();
    });
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { bindConfigPanel, bindUiControls, bootTcWebChat };
}
