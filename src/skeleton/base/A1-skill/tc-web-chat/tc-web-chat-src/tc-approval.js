// ========== tc-approval.js ==========
// 人闸（approval gate）：none / readonly / all 三态状态机
// 设计稿锚点：§3.5（下拉 N 态）/ §5（人审本地中止，无信封码）
// 语义：人闸是前端本地 UI 决策，不产生 ACCESS_DENIED/SERVICE_DENIED 等业务码（见 §4 铁律）

// 三态定义
const APPROVAL_MODES = {
    none:     { key: 'none',     labelKey: 'approvalNone',     auto: false, readonly: false },
    readonly: { key: 'readonly', labelKey: 'approvalReadonly', auto: true,  readonly: true  },
    all:      { key: 'all',      labelKey: 'approvalAll',      auto: true,  readonly: false }
};

// 当前人闸态（默认 readonly，§5 最安全默认）
let approvalMode = (runtimeConfig && runtimeConfig.auto_execute) || 'readonly';

function getApprovalMode() { return approvalMode; }

function setApprovalMode(mode) {
    if (!APPROVAL_MODES[mode]) return false;
    approvalMode = mode;
    if (runtimeConfig) runtimeConfig.auto_execute = mode;
    return true;
}

// §5 副作用判定：依据 query 表单的 usage/description 元数据关键词，而非动作名硬编码
// 元数据来自 tcCache.directives（§3.2 发现结果）；找不到则保守视为可能副作用 → 询问
const SIDE_EFFECT_KEYWORDS = ['写', '改', '删', '创建', '发送', '提交', '更新', 'write', 'create', 'delete', 'send', 'submit', 'update', 'mutate', '危险', 'danger'];
function isSideEffect(directive) {
    const cache = (typeof getTcCache === 'function') ? getTcCache() : null;
    const matched = cache && Array.isArray(cache.directives)
        ? cache.directives.find((d) => d.domain === directive.domain && d.action === directive.action)
        : null;
    if (!matched) return true; // 未知指令保守询问（安全网）
    const usage = String(matched.usage || matched.description || '');
    if (!usage) return true;    // 无描述保守询问
    return SIDE_EFFECT_KEYWORDS.some((k) => usage.toLowerCase().includes(k.toLowerCase()));
}

// ---------- CircuitBreaker（§5 连续 3 次失败转 none） ----------
let failureStreak = 0;
const FAILURE_THRESHOLD = 3;
const CIRCUIT_RECOVER_MS = 5 * 60 * 1000; // 5 分钟 refractory 后允许恢复
let circuitTrippedAt = 0;

function reportToolFailure() {
    failureStreak++;
    if (failureStreak >= FAILURE_THRESHOLD && approvalMode !== 'none') {
        circuitTrippedAt = Date.now();
        setApprovalMode('none'); // §5：熔断，转人工兜底
        return true;             // 本次触发了熔断
    }
    return false;
}
function reportToolSuccess() { failureStreak = 0; }
// refractory 后调用可在用户切回时恢复（不自动恢复，需用户操作，但清零计数以便重算）
function resetCircuitIfRecovered() {
    if (circuitTrippedAt && Date.now() - circuitTrippedAt > CIRCUIT_RECOVER_MS) {
        failureStreak = 0; circuitTrippedAt = 0;
    }
}

// 决策：给定一条待执行指令，返回 { act: 'auto' | 'ask' | 'deny', reason }
// - all：一切自动（act=auto）
// - readonly：只读类（usage 无副作用关键词）自动，写/危险类需询问（act=ask）
// - none：一切先问（act=ask）
function decideExecution(directive) {
    resetCircuitIfRecovered();
    const mode = APPROVAL_MODES[approvalMode];
    if (!mode) return { act: 'ask', reason: 'unknown-mode' };
    if (mode.key === 'all') return { act: 'auto', reason: 'gate-all' };
    // readonly：按元数据判定副作用（§5），而非动作名前缀
    const safe = !isSideEffect(directive);
    if (mode.key === 'readonly') {
        return safe ? { act: 'auto', reason: 'readonly-safe' } : { act: 'ask', reason: 'readonly-needs-confirm' };
    }
    // none：全询问
    return { act: 'ask', reason: 'gate-none' };
}

// 渲染人闸卡片（占位 UI；胶水在 tc-chat.js 调 addMessage 时挂）
function approvalCard(directive, decision) {
    const params = directive.params || [];
    // 与 runTool 发送的 AI: 原语逐字节一致（§4 字节同一性）：domain;action,param1,param2
    const label = `${directive.domain};${directive.action},${params.join(',')}`;
    return {
        type: 'approval',
        label,
        decision,            // { act, reason }
        confirmed: false,
        denied: false
    };
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        APPROVAL_MODES, getApprovalMode, setApprovalMode, decideExecution, approvalCard,
        isSideEffect, reportToolFailure, reportToolSuccess, resetCircuitIfRecovered
    };
}
