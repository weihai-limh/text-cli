// ========== tc-quiet.js ==========
// 免打扰轮（do-not-disturb round）：免打扰桥接编排闭包
// 设计稿锚点：§3.3 / §12.3.7（无 AI: 产出出口）/ §12.3.9（CORS 识别）
// 闭环：LLM 文本 → parseDirectives → 人闸决策 → 执行回填 → 或"无指令"退出

// 免打扰轮最大空转轮数：超过即判定"本轮无工具意图"，退出并把文本当普通回复
const QUIET_MAX_IDLE = 2;

// 真正执行一条指令：POST 到 tc 端点，解析 SPEC 信封
// 设计稿锚点：§4（信封铁律）/ §12.3.7（执行失败也可破产退出）
async function runTool(directive, deps) {
    const ep = runtimeConfig.tc_endpoint;
    if (!ep) {
        // §12.3.8b：端点空 = 纯对话模式，不伪造协议码
        return { ok: false, code: 'ERR_EXECUTION', message: t('tcNotConfigured') };
    }
    // 组装 AI: 原语文本（§4：域;动作,参数）
    const aiText = `AI:${directive.domain};${directive.action},${(directive.params || []).join(',')}`;
    try {
        // §2 双令牌头；§4 铁律：只看信封 rst_err，绝不靠 HTTP 状态
        const res = await fetch(ep, {
            method: 'POST',
            headers: buildTcHeaders(),
            body: JSON.stringify({ prompt: aiText })
        });
        if (!res.ok) {
            // HTTP 层（非信封层）失败：是 fetch 层降级，不写协议码，说人话（§4 铁律 / §12.3.9）
            const described = deps && deps.describeBridgeError
                ? deps.describeBridgeError(new TypeError('HTTP ' + res.status)) : { message: 'HTTP ' + res.status };
            return { ok: false, code: 'ERR_EXECUTION', message: described.message, cors: described.kind === 'cors-or-network' };
        }
        const env = await res.json().catch(() => null);
        // 信封：{ rst_err, rst_data, rst_types }（§4）
        const err = (env && typeof env.rst_err === 'string') ? env.rst_err : (env && env.rst_err !== undefined ? String(env.rst_err) : '');
        const ok = (err === '');                       // §4 铁律：rst_err==='' 即成功
        const data = (env && env.rst_data != null) ? env.rst_data : null;
        const types = (env && Array.isArray(env.rst_types)) ? env.rst_types : null;
        const msg = (env && typeof env.rst_msg === 'string' && env.rst_msg) ? env.rst_msg : '';
        return {
            ok,
            code: err || 'OK',                          // 成功时 code='OK'
            message: ok ? (msg || t('executed')) : describeCode(err, msg),
            result: data,
            types,                                      // §4 多模态（rst_types）供前端渲染
            // —— §4 非终态/委托信号 ——
            degraded: (data && data.status === 'stop'), // 降级信号：非终态，换路
            delegated: (data && Array.isArray(data.delegated)) ? data.delegated : null,
            pending: (data && data.status === 'pending' && data.task_id) ? data.task_id : null
        };
    } catch (e) {
        // §12.3.9：网络/CORS 层错误，说人话，不污染 §4 闭集
        const described = deps && deps.describeBridgeError ? deps.describeBridgeError(e) : { message: String(e) };
        return { ok: false, code: 'ERR_EXECUTION', message: described.message, cors: described.kind === 'cors-or-network' };
    }
}

// tc-path 教学指令：本地特判返回（不 POST 端点、不过人闸）。
// 开关开启 → 返回完整 path 教学文本；关闭 → SERVICE_DENIED（信封闭集，不伪造成功）。
// 返回的信封与 runTool 同构，可直接交给 onToolResult 展示与入史。
function tcPathExampleResult() {
    if (!runtimeConfig.tc_path_enabled) {
        return { ok: false, code: 'SERVICE_DENIED', message: t('tcPathDisabled') };
    }
    const text = (typeof TC_PATH_EXAMPLE !== 'undefined') ? TC_PATH_EXAMPLE : '';
    return { ok: true, code: 'OK', message: t('executed'), result: text };
}

// text-cli;query 本地只读查询（不 POST 端点、不过人闸，与教学特判同类）：
// 参数 json/空 → 全量暴露（跳过 tc_scope 精选）；意图关键词 → 本地缓存过滤命中示例。
// 缓存未就绪 / 无匹配 → 闭集错误，不伪造成功。
function tcLocalQueryResult(params) {
    if (!runtimeConfig.tc_enabled) return { ok: false, code: 'SERVICE_DENIED', message: t('tcCapNotEnabled') };
    const cache = (typeof getTcCache === 'function') ? getTcCache() : null;
    if (!cache || !cache.ready || !cache.directives.length) {
        return { ok: false, code: 'ERR_NOT_FOUND', message: t('queryNoCache') };
    }
    const text = (params || []).join(',');
    const isFull = !text.trim() || text.trim() === 'json';
    if (isFull) {
        return { ok: true, code: 'OK', message: t('executed'), result: tcCacheSummary({ ignoreScope: true }) };
    }
    const hits = tcQuery(text);
    if (!hits.length) return { ok: false, code: 'ERR_NOT_FOUND', message: t('queryNoMatch') };
    const lines = hits.map((d) => `AI:${d.domain};${d.action},${d.params || ''}  # ${d.alias || d.desc || ''}`);
    return { ok: true, code: 'OK', message: t('executed'), result: lines.join('\n') };
}

// §4 六码字符串闭集（未知回退 ERR_EXECUTION）：把 rst_err 翻译成人话（不向 LLM 伪造成功）
// 闭集键集合保持恒定（回归 R7.2 断言依赖）；值由 t() 运行时查表（i18n err_* key），支持多语言。
const TC_ERR_KEYS = [
    'ERR_NOT_FOUND', 'ERR_EXECUTION', 'ERR_ROUTING',
    'INVALID_PARAMS', 'ACCESS_DENIED', 'SERVICE_DENIED'
];
function describeCode(code, rstMsg) {
    const key = 'err_' + code;                                   // i18n key：err_ERR_NOT_FOUND 等
    const base = TC_ERR_KEYS.includes(code) ? t(key) : t('err_unknown', { code });
    return rstMsg ? `${base}${t('errSeparator')}${rstMsg}` : base;
}

// 编排闭包：接收"发起 LLM 请求"的函数，返回处理一轮文本的桥函数
// deps: { parseDirectives, decideExecution, runTool, onPlain, onToolResult, onAsk, describeBridgeError }
function createQuietBridge(deps) {
    let idleCount = 0;

    // 处理 LLM 一轮完整文本（流式结束后调用）
    async function handleLLMRound(text) {
        // §12.3.10 由 parser 内部兜底；此处直接解析
        const directives = deps.parseDirectives(text);
        if (!directives.length) {
            idleCount++;
            if (idleCount >= QUIET_MAX_IDLE) {
                // §12.3.7 出口：无 AI: 产出，退出免打扰轮，文本当普通回复
                idleCount = 0;
                deps.onPlain(text);
                return { exited: true, reason: 'no-directive' };
            }
            // 仍可能在后续轮产生指令，暂不退出（等待）
            deps.onPlain(text);
            return { exited: false, reason: 'idle-' + idleCount };
        }
        idleCount = 0;
        // 有指令：逐条人闸决策 → 执行/询问
        for (const d of directives) {
            // 本地教学指令特判：text-cli;get-path-example 无副作用、不碰端点，
            // 与 tcDiscover 同类，豁免人闸——必须在 decideExecution 之前短路，
            // 否则 isSideEffect 对未入 cache 的指令保守 ask，教学会被卡住。
            if (d.domain === 'text-cli' && d.action === 'get-path-example') {
                deps.onToolResult(d, tcPathExampleResult());
                continue;
            }
            // 本地只读查询：text-cli;query 缓存过滤/全暴露（不 POST 端点、不过人闸）
            if (d.domain === 'text-cli' && d.action === 'query') {
                deps.onToolResult(d, tcLocalQueryResult(d.params || []));
                continue;
            }
            const decision = deps.decideExecution(d);
            if (decision.act === 'auto') {
                const res = await deps.runTool(d);     // 执行并回填到对话
                // §4 异步任务：pending + task_id → 轮询 AI:task;status
                if (res.pending) {
                    deps.onToolResult(d, { ...res, message: (res.message || t('asyncSubmitted')) + t('asyncPending', { task: res.pending }) });
                    if (deps.onAsyncTask) deps.onAsyncTask(res.pending);
                    continue;
                }
                // §4 降级信号：status==='stop' 非终态，提示换路（不伪造成功）
                if (res.degraded) {
                    deps.onToolResult(d, { ...res, message: (res.message || t('degraded')) + t('degradedHint') });
                    continue;
                }
                // §4 delegated：部分结果 + 委托清单（挂在回复里让 LLM 续写）
                if (res.delegated && res.delegated.length) {
                    const list = res.delegated.map((x) => `· ${x.domain};${x.action}${x.params ? ',' + x.params : ''}`).join('\n');
                    deps.onToolResult(d, { ...res, message: (res.message || t('partial')) + t('delegatedHint') + '\n' + list });
                    continue;
                }
                deps.onToolResult(d, res);
            } else {
                // 需人确认：挂审批卡片，等待用户操作（不自动执行）
                deps.onAsk(d, decision);
            }
        }
        return { exited: false, reason: 'directives-' + directives.length };
    }

    // §12.3.9 CORS / 网络层识别：把 fetch 错误翻译成人话提示，不污染 §4 闭集
    function describeBridgeError(e) {
        if (e instanceof TypeError) {
            return { kind: 'cors-or-network', message: t('tcEndpointLabel') + t('corsBlocked') };
        }
        return { kind: 'bridge', message: String(e && e.message || e) };
    }

    function reset() { idleCount = 0; }

    return { handleLLMRound, describeBridgeError, reset, QUIET_MAX_IDLE };
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { createQuietBridge, QUIET_MAX_IDLE, tcPathExampleResult, tcLocalQueryResult };
}
