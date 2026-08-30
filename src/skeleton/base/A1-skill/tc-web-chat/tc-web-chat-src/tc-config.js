// ========== tc-config.js ==========
// 配置状态管理 + 多语言（i18n）+ SYSTEM_PROMPTS 占位
// 源模块：由 build.js 拼入 tc-web-chat.html 的 <script>
// 设计稿锚点：§3.2.1（SYSTEM_PROMPTS）、§3.5（LANGS/languagePrompt）、§11.2

// ---------- 配置持久化 ----------
const CONFIG_KEY = 'tc-web-chat-config';
const DEFAULT_CONFIG = {
    baseUrl: '/v1/chat/completions',
    model: 'default-model',
    headers: { 'Content-Type': 'application/json' },
    cdnUrl: '',
    maxTokens: 1000,
    temperature: 0.7,
    // —— tc 桥接新增（§2 配置项 6 项）——
    tc_enabled: false,      // 是否启用 tc 指令消费；false = 退化为纯聊天（§2 向后兼容）
    tc_endpoint: 'http://127.0.0.1:28050/text-cli/cli', // §2 默认对齐 A0 call.js DEFAULT_ENDPOINT
    service_token: '',      // 可选；对应 Service-token 头（§2）
    access_token: '',       // 可选；对应 Authorization: Bearer 头（§2 双令牌）
    tc_scope: '',           // 可选；对 query 结果做客户端精选以省 token（§2）
    auto_execute: 'readonly', // 人闸默认 readonly（§3.5 / §5）
    tc_path_enabled: false    // 是否启用 tc path 编排教学（§2 扩展：发现面可见 get-path-example，前端特判返回教学）
};

function loadConfig() {
    try {
        const raw = localStorage.getItem(CONFIG_KEY);
        if (raw) {
            const obj = JSON.parse(raw);
            return {
                ...DEFAULT_CONFIG,
                ...obj,
                headers: { 'Content-Type': 'application/json', ...(obj.headers || {}) }
            };
        }
    } catch (e) { /* 解析失败回退默认 */ }
    return { ...DEFAULT_CONFIG };
}

function saveConfig(config) {
    try { localStorage.setItem(CONFIG_KEY, JSON.stringify(config)); } catch (e) { /* storage 满则静默失败 */ }
}

let runtimeConfig = loadConfig();

// ---------- 语言注册表（§3.5：语言是数据不是分支，加语言 = 改 i18n.json 一行） ----------
// LANGS / I18N 不再硬编码于此，改由 build.js 构建时从 i18n.json 读取并按 --lang 注入到脚本段
// （见 build.js：读 i18n.json → 拼 `const LANGS=...; const I18N=...;` 注入）。
// 运行时此处仅消费全局 LANGS / I18N（同 <script> 共享作用域）。
function langList() { return Object.keys(LANGS).map((k) => ({ code: k, ...LANGS[k] })); }

// 默认语言：由注入词典推导——单语包只有一个键，默认即为该语言；双包回退 en
let currentLang = (typeof I18N !== 'undefined' && I18N && Object.keys(I18N).length === 1)
    ? Object.keys(I18N)[0] : 'en';

function t(key, params) {
    let s = I18N[currentLang] && I18N[currentLang][key];
    if (s === undefined) {
        // 双包才有 en 回退；单语包无 en 键，直接回退 key 本身（避免读 undefined['key'] 抛 TypeError）
        s = (I18N.en && I18N.en[key] !== undefined) ? I18N.en[key] : key;
    }
    if (typeof s === 'function') return s(params);
    if (params && typeof params === 'object') {
        for (const k in params) s = s.replace(new RegExp('\\{' + k + '\\}', 'g'), params[k]);
    }
    return s;
}

// 语言 prompt 随下拉变（§3.5 / §3.2.1 第二条）；LANGS 已是注册表对象
function currentLanguagePrompt() {
    const lang = LANGS[currentLang] || LANGS.zh;
    return lang ? lang.prompt : '';
}

// 遍历 LANGS 注册表生成 <option>（§3.5：语言是数据不是分支）
function buildLangOptions() {
    return langList().map((l) =>
        `<option value="${l.code}">${l.label} · ${l.name}</option>`).join('');
}

// §2 双令牌：组装 tc 请求头（Service-token + 可选 Authorization: Bearer）
// 注意：绝不靠 HTTP 状态码判断成功，信封 rst_err 才是协议真相（§4 铁律）
function buildTcHeaders() {
    const h = { 'Content-Type': 'application/json' };
    if (runtimeConfig.service_token) h['Service-token'] = runtimeConfig.service_token;
    if (runtimeConfig.access_token) h['Authorization'] = 'Bearer ' + runtimeConfig.access_token;
    return h;
}

// ---------- SYSTEM_PROMPTS（§3.2.1） ----------
// 第一条：固定中性、不本地化（如何使用 tc）
// 第二条：可变的语种指令，随下拉走 currentLanguagePrompt()
// 第三条（动态）：已缓存能力摘要（§3.2.1 / §3.3——让 LLM 照例生成 AI:）；
//   依赖 tc-cache.js 的 tcCacheSummary（同作用域）；缓存未就绪则降级为纯对话提示。
const SYSTEM_PROMPTS_STATIC = [
    '你可用 tc 工具。不确定用什么指令时，先发 "AI:text-cli;query,{意图关键词}"，' +
    '我会从本地缓存返回匹配指令示例（域;动作;参数形状;别名），你据此照例生成 "AI:域;动作,参数"。' +
    '关键词查不到、或需要俯瞰全部可用能力时，发 "AI:text-cli;query,json" 获取完整工具清单。'
];

// ---------- tc-path 编排教学（§2 扩展） ----------
// 配置资产：开关开启时 tc-cache.js 把摘要行追加进发现面；tc-quiet.js 特判 get-path-example
// 本地返回教学文本（不进端点、不过人闸，与 tcDiscover 同类）。内容对齐 text-cli;path 协议
// （steps/instruction/output_as/if/{input.x}/{step_id.field}，mode 默认 toolchain）。
// LLM 语言不敏感：教学文本固定中文（单语常量），不做多语言分支。
const TC_PATH_SUMMARY = 'AI:text-cli;get-path-example  # 多工具编排 — 一条请求编排多步工具的教学';

const TC_PATH_EXAMPLE = 'PATH 编排（临时编排权）：\n' +
    '用一条调用运行多步工具链。端点按顺序执行各步骤，前一步输出通过 {step_id.field} 注入后续\n' +
    '步骤（支持深路径）。{input.key} 引用你的尾随输入。\n' +
    '\n' +
    '语法：\n' +
    '  AI:text-cli;path,{内联 JSON}[,输入 JSON]\n' +
    '  AI:text-cli;path,<已注册 id>[,输入 JSON]\n' +
    '  AI:text-cli;path,<文件>,--register[,输入 JSON]   # 注册一次，之后按 id 复用\n' +
    '\n' +
    'Path JSON：\n' +
    '  { "id": "...", "type": "pipeline", "steps": [\n' +
    '      { "id": "s1", "instruction": "域;动作,参数,{input.x}", "output_as": "r1" },\n' +
    '      { "id": "s2", "instruction": "域2;动作2,{r1.字段}", "output_as": "r2",\n' +
    '        "if": { "step": "s1", "field": "status", "equals": "ok" } }   # 可选：条件不满足则跳过\n' +
    '  ]}\n' +
    '\n' +
    '最小可运行示例：\n' +
    '  AI:text-cli;path,{"id":"calc2","type":"pipeline","steps":[\n' +
    '    {"id":"sq","instruction":"tc-math;eval,{input.a}**2+{input.b}**2","output_as":"sq"},\n' +
    '    {"id":"rt","instruction":"tc-math;eval,sqrt({sq.result})","output_as":"rt"}\n' +
    '  ]},{"a":3,"b":4}\n' +
    '\n' +
    '说明：mode 默认为 "toolchain"（串行）。若端点不支持 path 会如实返回协议错误——不要盲目重试。';

function buildSystemPrompts() {
    const prompts = [];
    if (runtimeConfig.tc_enabled) {
        prompts.push(...SYSTEM_PROMPTS_STATIC);   // "你可用 tc 工具…"说明段
        if (typeof tcCacheSummary === 'function') prompts.push(tcCacheSummary());
    }
    prompts.push(currentLanguagePrompt());        // 语种指令始终注入（与 tc 无关）
    return prompts;
}

// ---------- 语言应用（§3.5：语言是数据不是分支，查表回退） ----------
// 单语版（注入词典仅一个键）：隐藏语言下拉框（头部 + 面板），避免出现无效切换器
function isSingleLang() {
    return !!(I18N && Object.keys(I18N).length === 1);
}

function applyLang(lang) {
    currentLang = lang || (isSingleLang() ? Object.keys(I18N)[0] : 'en');
    document.documentElement.lang = (currentLang === 'zh') ? 'zh-CN' : 'en';
    document.querySelectorAll('[data-i18n],[data-i18n-ph],[data-i18n-title]').forEach((el) => {
        if (el.hasAttribute('data-i18n')) el.textContent = t(el.getAttribute('data-i18n'));
        if (el.hasAttribute('data-i18n-ph')) el.placeholder = t(el.getAttribute('data-i18n-ph'));
        if (el.hasAttribute('data-i18n-title')) el.title = t(el.getAttribute('data-i18n-title'));
    });
    // 单语版不显示语言配置（下拉 + 所在行）；双包才同步 options 并置选中项
    const single = isSingleLang();
    ['langSelect', 'langSelectCfg'].forEach((id) => {
        const sel = document.getElementById(id);
        if (!sel) return;
        sel.style.display = single ? 'none' : '';
        if (!single) {
            if (!sel.options.length) sel.innerHTML = buildLangOptions();
            sel.value = currentLang;
        }
    });
    if (single) {
        const langRow = document.getElementById('configLangRow');
        if (langRow) langRow.style.display = 'none';
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        DEFAULT_CONFIG, loadConfig, saveConfig,
        LANGS, I18N, t, currentLanguagePrompt,
        SYSTEM_PROMPTS_STATIC, buildSystemPrompts,
        TC_PATH_SUMMARY, TC_PATH_EXAMPLE,
        applyLang, bindLangButtons,
        getRuntimeConfig: () => runtimeConfig,
        setRuntimeConfig: (c) => { runtimeConfig = c; }
    };
}
