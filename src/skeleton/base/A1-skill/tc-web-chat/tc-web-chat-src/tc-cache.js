// ========== tc-cache.js ==========
// 本地能力缓存 + 运行时发现 + 查询过滤
// 设计稿锚点：§3.1 / §3.2 / §12.3.8（拉取失败可降级）

// ---------- 缓存结构 ----------
// tcCache: { endpoint, fetchedAt, directives: [ {domain, action, params, alias, desc} ] }
let tcCache = {
    endpoint: null,
    fetchedAt: 0,
    directives: [],     // 已发现的能力原语元数据
    ready: false        // §12.3.11 可观测：缓存是否就绪
};

function tcCacheReset() {
    tcCache = { endpoint: null, fetchedAt: 0, directives: [], ready: false };
}

// 端点/令牌变更或 Clean 时失效（§12.3.11）
function tcCacheInvalidate() {
    tcCacheReset();
}

// ---------- 运行时发现（§3.1 / §3.2） ----------
// 按设计稿 §3.2：POST {tc_endpoint} + {"prompt":"AI:text-cli;query,json"}，
// 拉回能力清单 directives[]，存本地缓存。
// 失败按 §12.3.8 三选一降级，§12.3.9 识别 CORS/网络层，绝不抛死，也不伪造 §4 协议码。
async function tcDiscover() {
    const ep = runtimeConfig.tc_endpoint;
    if (!ep) {
        // 端点空 = 纯对话模式（§12.3.8b 显式提示，主链仍可聊）
        tcCacheInvalidate();
        return { ok: false, reason: 'no-endpoint', mode: 'chat-only' };
    }
    try {
        // §2 双令牌头；§4 铁律：成功与否只看信封 rst_err，不看 HTTP 状态
        const res = await fetch(ep, { method: 'POST', headers: buildTcHeaders(),
            body: JSON.stringify({ prompt: 'AI:text-cli;query,json' }) });
        if (!res.ok) {
            // HTTP 层（非信封层）失败：视为 fetch 层降级，不写协议码（§4 铁律）
            if (tcCache.ready) return { ok: true, stale: true, directives: tcCache.directives }; // §12.3.8a
            return { ok: false, reason: 'discover-http-' + res.status, mode: 'chat-only' };
        }
        const data = await res.json();
        // 信封：{rst_err, rst_data}（§4）；rst_err==='' 才成功
        const env = data || {};
        if (env.rst_err !== undefined && env.rst_err !== '') {
            if (tcCache.ready) return { ok: true, stale: true, directives: tcCache.directives }; // §12.3.8a
            return { ok: false, reason: 'discover-rst-' + env.rst_err, mode: 'chat-only' };
        }
        // §3.2 返回的 directives 列表：设计稿约定直接是数组，
        // 但 zh 实证运行时包了一层 {directives:[...]}（schema 形态），兼容两种。
        const arr = (env.rst_data && Array.isArray(env.rst_data.directives))
            ? env.rst_data.directives
            : (Array.isArray(env.rst_data) ? env.rst_data : []);
        const directives = arr;
        tcCache = { endpoint: ep, fetchedAt: Date.now(), directives, ready: true };
        return { ok: true, directives };
    } catch (e) {
        // §12.3.9 本机 CORS / 网络层：识别 TypeError，说人话，不污染 §4 错误码闭集
        const isCors = (e instanceof TypeError);
        if (tcCache.ready) return { ok: true, stale: true, directives: tcCache.directives }; // §12.3.8a 降级
        return {
            ok: false,
            reason: isCors ? 'cors-blocked' : 'network-error',
            hint: isCors
                ? t('tcEndpointLabel') + t('corsBlocked')
                : t('endpointUnreachable'),
            mode: 'chat-only'
        };
    }
}

// ---------- 查询过滤（§3.2） ----------
// 用户/LLM 描述意图 → 从缓存返回匹配指令示例（域;动作;参数形状;别名）
function tcQuery(text) {
    if (!tcCache.ready || !tcCache.directives.length) return [];
    const q = (text || '').toLowerCase();
    return tcCache.directives.filter((d) => {
        const hay = [d.domain, d.action, d.alias, d.desc].filter(Boolean).join(' ').toLowerCase();
        return q.split(/\s+/).some((tok) => tok && hay.includes(tok));
    });
}

// 同步暴露给 LLM 提示词的"已缓存能力摘要"
// opts.ignoreScope：全暴露（text-cli;query,json）跳过 tc_scope 精选，返回端点全部能力
function tcCacheSummary(opts) {
    if (!runtimeConfig.tc_enabled) return t('tcCapNotEnabled');
    if (!tcCache.ready) return t('tcCapNotReady');
    // R4：tc_scope 非空时，对 directives 做客户端 best-effort 关键词精选（复用 tcQuery 思路）
    let directives = tcCache.directives;
    const scope = (runtimeConfig.tc_scope || '').trim().toLowerCase();
    if (scope && !(opts && opts.ignoreScope)) {
        const toks = scope.split(/[\s,;]+/).filter(Boolean);
        directives = directives.filter((d) => {
            const hay = [d.domain, d.action, d.alias, d.desc].filter(Boolean).join(' ').toLowerCase();
            return toks.some((tok) => hay.includes(tok));
        });
    }
    if (!directives.length) return t('tcCapNotReady');
    const lines = directives.map((d) => `AI:${d.domain};${d.action},${d.params || ''}  # ${d.alias || d.desc || ''}`);
    // tc-path 编排教学入口：开关开启时追加到发现面（在 scope 过滤之后，独立于端点能力清单）
    if (runtimeConfig.tc_path_enabled) {
        lines.push(TC_PATH_SUMMARY);
    }
    if (!lines.length) return t('tcCapNotReady');
    return lines.join('\n');
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        getTcCache: () => tcCache,
        tcCacheReset, tcCacheInvalidate, tcDiscover, tcQuery, tcCacheSummary,
        setTcCacheReady: (v) => { tcCache.ready = v; }
    };
}
