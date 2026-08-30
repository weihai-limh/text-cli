// ========== tc-parser.js ==========
// 解析 LLM 文本中的 tc 指令原语：AI:域;动作,参数
// 设计稿锚点：§4（实证正则）/ §12.3.10（流结束兜底）
// §4 实证正则：支持「指令:」中文别名、JSON 括号深度、引号内逗号、限长 2048、限参 50

const TC_MAX_LEN = 2048;
const TC_MAX_PARAMS = 50;

// 设计稿 §4 实证正则（g）：AI:域;动作,参数（支持「指令:」别名、括号、引号内逗号）
const TC_DIRECTIVE_RE = /^\s*(?:AI|指令)[：:]([^;]+);([^,]+)(?:,(.+))?\s*$/;

function parseDirectiveLine(line) {
    const m = TC_DIRECTIVE_RE.exec(line);
    if (!m) return null;
    const domain = m[1].trim();
    const action = m[2].trim();
    const rawParams = m[3];
    let params = [];
    if (rawParams !== undefined) {
        // 引号内逗号不拆、括号深度不拆（§4 实证容错）
        const parts = [];
        let buf = '', depth = 0, inQ = false, q = '';
        for (const ch of rawParams) {
            if (inQ) {
                buf += ch;
                if (ch === q) inQ = false;
            } else if (ch === '"' || ch === "'") {
                inQ = true; q = ch; buf += ch;
            } else if (ch === '[' || ch === '{' || ch === '(') {
                depth++; buf += ch;
            } else if (ch === ']' || ch === '}' || ch === ')') {
                depth--; buf += ch;
            } else if (ch === ',' && depth === 0) {
                parts.push(buf); buf = '';
            } else {
                buf += ch;
            }
        }
        if (buf.trim()) parts.push(buf);
        params = parts.map((s) => s.trim()).filter((s) => s.length);
    }
    if (!domain || !action) return null;
    return { domain, action, params, raw: line.trim() };
}

function parseDirectives(text) {
    const out = [];
    if (!text) return out;
    const lines = text.slice(0, TC_MAX_LEN).split('\n');
    for (const line of lines) {
        const d = parseDirectiveLine(line);
        if (d) {
            if (d.params.length > TC_MAX_PARAMS) {
                // §4 护栏：参数超 50 截断，避免炸弹（安全网）
                d.params = d.params.slice(0, TC_MAX_PARAMS);
            }
            out.push(d);
        }
    }
    // 跨行兜底：正文内整段出现「AI:...」而非独立行时也尝试（§12.3.10 放宽）
    if (out.length === 0) {
        const inline = text.match(/(?:AI|指令)[：:][^\n;]+;[^\n]+/g);
        if (inline) {
            for (const seg of inline) {
                const d = parseDirectiveLine(seg.trim());
                if (d) out.push(d);
            }
        }
    }
    return out;
}

// 是否文本包含 tc 指令（用于 submit 判断是否进入免打扰轮）
function hasDirectives(text) {
    return parseDirectives(text).length > 0;
}

// 从文本中抽取"非指令"的普通回复部分（去掉 AI: 行）
function stripDirectives(text) {
    if (!text) return text;
    return text.replace(/(?:AI|指令)[：:][^\n]*/g, '').replace(/\n{2,}/g, '\n').trim();
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { parseDirectives, hasDirectives, stripDirectives, TC_DIRECTIVE_RE, TC_MAX_LEN, TC_MAX_PARAMS };
}

