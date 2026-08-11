// tc-math JS — Safe math expression evaluator
// Zero external dependencies. Uses a simple AST-based evaluator
// with a whitelist of allowed Math functions.

"use strict";

// ─── Safe function whitelist ─────────────────────────

const _SAFE_FUNCS = {
  sqrt: Math.sqrt,
  sin: Math.sin,
  cos: Math.cos,
  tan: Math.tan,
  log: Math.log,
  log10: Math.log10,
  abs: Math.abs,
  ceil: Math.ceil,
  floor: Math.floor,
  round: Math.round,
};

const _SAFE_CONSTANTS = {
  pi: Math.PI,
  e: Math.E,
};

// ─── Tokenizer ───────────────────────────────────────

function tokenize(expr) {
  const tokens = [];
  let i = 0;
  while (i < expr.length) {
    const ch = expr[i];
    if (/\s/.test(ch)) { i++; continue; }
    if (/[0-9.]/.test(ch)) {
      let num = "";
      while (i < expr.length && /[0-9.]/.test(expr[i])) { num += expr[i]; i++; }
      tokens.push({ type: "num", value: parseFloat(num) });
      continue;
    }
    if (/[a-zA-Z_]/.test(ch)) {
      let ident = "";
      while (i < expr.length && /[a-zA-Z0-9_]/.test(expr[i])) { ident += expr[i]; i++; }
      tokens.push({ type: "ident", value: ident });
      continue;
    }
    if ("+-*/^()**".includes(ch)) {
      if (ch === "*" && expr[i + 1] === "*") { tokens.push({ type: "op", value: "**" }); i += 2; continue; }
      tokens.push({ type: "op", value: ch }); i++;
      continue;
    }
    throw new Error(`unexpected character: '${ch}'`);
  }
  return tokens;
}

// ─── Parser (recursive descent with index tracking) ──

function parseExpr(tokens, idxRef, minPrec) {
  minPrec = minPrec || 0;
  let left = parseAtom(tokens, idxRef);

  while (idxRef.i < tokens.length) {
    const op = tokens[idxRef.i];
    if (op.type !== "op") break;
    // skip non-binary operators: parens, commas
    if (op.value === ")" || op.value === "(" || op.value === ",") break;
    const prec = precedence(op.value);
    if (prec < minPrec) break;
    idxRef.i++; // consume op

    if (op.value === "**") {
      const right = parseExpr(tokens, idxRef, prec);
      left = Math.pow(left, right);
    } else {
      const right = parseExpr(tokens, idxRef, prec + 1);
      left = applyOp(op.value, left, right);
    }
  }
  return left;
}

function parseAtom(tokens, idxRef) {
  if (idxRef.i >= tokens.length) throw new Error("unexpected end of expression");
  const t = tokens[idxRef.i];
  idxRef.i++;

  if (t.type === "num") return t.value;

  if (t.type === "ident") {
    // function call
    if (idxRef.i < tokens.length && tokens[idxRef.i].type === "op" && tokens[idxRef.i].value === "(") {
      idxRef.i++; // consume "("
      const args = [];
      if (idxRef.i < tokens.length && !(tokens[idxRef.i].type === "op" && tokens[idxRef.i].value === ")")) {
        args.push(parseExpr(tokens, idxRef, 0));
        while (idxRef.i < tokens.length && tokens[idxRef.i].type === "op" && tokens[idxRef.i].value === ",") {
          idxRef.i++; // consume ","
          args.push(parseExpr(tokens, idxRef, 0));
        }
      }
      if (idxRef.i >= tokens.length || tokens[idxRef.i].type !== "op" || tokens[idxRef.i].value !== ")") {
        throw new Error("expected ')'");
      }
      idxRef.i++; // consume ")"
      const fn = _SAFE_FUNCS[t.value];
      if (!fn) throw new Error(`unknown function: ${t.value}`);
      return fn(...args);
    }
    // constant
    const c = _SAFE_CONSTANTS[t.value];
    if (c !== undefined) return c;
    throw new Error(`unknown identifier: ${t.value}`);
  }

  // unary minus
  if (t.type === "op" && t.value === "-") {
    return -parseAtom(tokens, idxRef);
  }

  // parenthesized expression
  if (t.type === "op" && t.value === "(") {
    const val = parseExpr(tokens, idxRef, 0);
    if (idxRef.i >= tokens.length || tokens[idxRef.i].type !== "op" || tokens[idxRef.i].value !== ")") {
      throw new Error("expected ')'");
    }
    idxRef.i++; // consume ")"
    return val;
  }

  throw new Error(`unexpected token: ${JSON.stringify(t)}`);
}

function precedence(op) {
  if (op === "+" || op === "-") return 1;
  if (op === "*" || op === "/") return 2;
  if (op === "**" || op === "^") return 3;
  return 0;
}

function applyOp(op, a, b) {
  switch (op) {
    case "+": return a + b;
    case "-": return a - b;
    case "*": return a * b;
    case "/": return a / b;
    case "^": return Math.pow(a, b);
    default: throw new Error(`unknown operator: ${op}`);
  }
}

// ─── Safe entry point ────────────────────────────────

function safeEval(expr) {
  const tokens = tokenize(expr);
  const idxRef = { i: 0 };
  const result = parseExpr(tokens, idxRef, 0);
  if (idxRef.i < tokens.length) throw new Error("unexpected tokens after expression");
  return result;
}

// ─── Directive handler ───────────────────────────────

function handler(params) {
  try {
    const result = safeEval(params[0]);
    return { status: "ok", result };
  } catch (e) {
    return { status: "error", reason: e.message };
  }
}

module.exports = {
  domainAlias: "\u8ba1\u7b97",
  directives: {
    eval: {
      handler,
      actionAliases: ["\u6c42\u503c"],
    },
  },
};
