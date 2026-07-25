# tc-math 计算工具

AST 校验的安全算术求值器。零依赖，仅用 Python math 标准库。

## Install

```
AI:text-cli;install,tc-math
```

## 支持

**函数：** sqrt, sin, cos, tan, log, log10, abs, ceil, floor, round

**常量：** pi, e

**运算符：** + - * / ** ( )

## Examples

```
tc-math;eval,sqrt(3**2 + 4**2)        → 5.0
tc-math;eval,sin(pi/2)                 → 1.0
tc-math;eval,round(log(e**10), 2)      → 10.0
tc-math;eval,ceil(abs(-3.7))           → 4.0
```

## Architecture

```
tc-math/handler.py  — ast.parse → walk AST → eval in math namespace
```
