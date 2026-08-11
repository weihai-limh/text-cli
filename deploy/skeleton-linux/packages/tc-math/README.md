# tc-math

Safe arithmetic expression evaluator for path pipelines. AST-validated — it rejects any node that is not a constant, an operator, or a whitelisted math function, so there is no arbitrary code execution. Zero dependencies, Python stdlib `math` only.

## Install

```
AI:text-cli;install,tc-math
```

## Functions & Constants

**Functions:** `sqrt`, `sin`, `cos`, `tan`, `log`, `log10`, `abs`, `ceil`, `floor`, `round`

**Constants:** `pi`, `e`

**Operators:** `+ - * / ** % ( )`

## Directives

| Directive | Description |
|-----------|-------------|
| `tc-math;eval,<expression>` | Safely evaluate an arithmetic expression |

## Example

```
AI:tc-math;eval,sqrt(3**2 + 4**2)
→ {"status":"ok","result":5.0}

AI:tc-math;eval,sin(pi/2)
→ {"status":"ok","result":1.0}

AI:tc-math;eval,round(log(e**10), 2)
→ {"status":"ok","result":10.0}

AI:tc-math;eval,ceil(abs(-3.7))
→ {"status":"ok","result":4.0}
```

## Architecture

```
tc-math/
└── handler.py   — ast.parse → walk AST → eval in math namespace
```

Only `ast.Constant`, `ast.BinOp`, `ast.UnaryOp`, `ast.Call` (to whitelisted functions), and `ast.Name` (to constants) are evaluated. Anything else raises an error.
