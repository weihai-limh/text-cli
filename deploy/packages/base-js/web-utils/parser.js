// 协议级参数解析 (SPEC §1.2.1 括号深度追踪逗号拆分)
// 仅当 {} [] "" 深度为 0 时，才按逗号拆分顶层参数。
// 与 Python service 的 parser 算法一致，确保含逗号/括号的复杂参数跨运行时解析结果相同。

function splitParamsOutsideBrackets(s) {
  const params = [];
  let buf = '';
  let depth = 0;     // 追踪 { } [ ]
  let inStr = false;
  let strCh = '';

  for (let i = 0; i < s.length; i++) {
    const ch = s[i];

    if (inStr) {
      buf += ch;
      if (ch === '\\' && i + 1 < s.length) { buf += s[i + 1]; i++; continue; }
      if (ch === strCh) inStr = false;
      continue;
    }

    if (ch === '"' || ch === "'") { inStr = true; strCh = ch; buf += ch; continue; }
    if (ch === '{' || ch === '[') depth++;
    else if (ch === '}' || ch === ']') depth = Math.max(0, depth - 1);

    if (ch === ',' && depth === 0) { params.push(buf); buf = ''; continue; }
    buf += ch;
  }
  if (buf.length > 0) params.push(buf);
  return params.map(p => p.trim());
}

module.exports = { splitParamsOutsideBrackets };
