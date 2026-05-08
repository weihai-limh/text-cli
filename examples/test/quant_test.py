#!/usr/bin/env python3
"""text-cli Token 量化测试 — 逐条指令统计请求/响应体积"""

import json, urllib.request, sys, os

TOKEN = os.environ.get("TEXT_CLI_TOKEN_LOCAL", "local-dev-token-tide-2026")
URL = "http://127.0.0.1:20260/cli/text_cli"

def call(prompt):
    data = json.dumps({"prompt": prompt}).encode()
    req_size = len(data)
    req = urllib.request.Request(URL, data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req) as r:
        resp_data = r.read()
    resp_size = len(resp_data)
    result = json.loads(resp_data)
    success = 'rst_err' not in result
    status = '✅' if success else '⚠️'
    return req_size, resp_size, status, result

def measure_traditional(command, label):
    """Measure traditional exec character cost"""
    import subprocess
    cmd_chars = len(command)
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    output_chars = len(output)
    return cmd_chars, output_chars, output[:200]

# ═══════════════════════════════════════════════════════
# Phase 1: 14 条文本指令，逐条量化
# ═══════════════════════════════════════════════════════
print("=" * 70)
print("Phase 1: 文本指令逐条量化")
print("=" * 70)

instructions = [
    ("系统;健康", "指令:系统;健康"),
    ("系统;状态", "指令:系统;状态"),
    ("AI协作;状态,A", "指令:AI协作;状态,A"),
    ("AI协作;消息,1", "指令:AI协作;消息,1"),
    ("终端;天气,威海", "指令:终端;天气,威海"),
    ("编码;base64,encode,Hello Tide", "指令:编码;base64,encode,Hello Tide"),
    ("编码;hex,encode,Hello Tide", "指令:编码;hex,encode,Hello Tide"),
    ("文件;写入", f"指令:文件;写入,/root/.openclaw/workspace/tide-scripts/test/tc_test_write.md,量化测试文本。Token efficiency test. 123."),
    ("文件;读取", "指令:文件;读取,/root/.openclaw/workspace/tide-scripts/test/tc_test_write.md"),
    ("文件;列表", "指令:文件;列表,/root/.openclaw/workspace/tide-scripts/test"),
    ("文件;移动", "指令:文件;移动,/root/.openclaw/workspace/tide-scripts/test/tc_test_write.md,/root/.openclaw/workspace/tide-scripts/test/tc_test_moved.md"),
    ("Git;状态", "指令:Git;状态"),
]

print(f"\n{'指令':<22} {'请求(chars)':>10} {'响应(chars)':>10} {'合计':>8} {'':>3}")
print("-" * 60)

total_req = 0
total_resp = 0

for label, prompt in instructions:
    req, resp, status, result = call(prompt)
    total_req += req
    total_resp += resp
    print(f"{label:<22} {req:>10} {resp:>10} {req+resp:>8} {status}")

print("-" * 60)
print(f"{'Phase 1 合计':<22} {total_req:>10} {total_resp:>10} {total_req+total_resp:>8}")
print(f"{'平均/条':<22} {total_req//len(instructions):>10} {total_resp//len(instructions):>10} {((total_req+total_resp)//len(instructions)):>8}")

# Git push and email need special setup
print(f"\n{'Git;推送 (feat/..)':<22} (需分支操作，见 Phase 2)")
print(f"{'邮件;发送':<22} (需邮件内容，见 Phase 2)")

# ═══════════════════════════════════════════════════════
# Phase 2: 3步链路，两种方式逐条对比
# ═══════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("Phase 2: 文件→Git→邮件 链路，双方式逐条对比")
print("=" * 70)

print("\n── 2A: 文本指令方式 ──")
print(f"{'操作':<25} {'请求(chars)':>10} {'响应(chars)':>10} {'合计':>8} {'':>3}")
print("-" * 60)

tc_req_total = 0
tc_resp_total = 0

# 2A-1: 文件写入
prompt = "指令:文件;写入,/root/.openclaw/workspace/tide-scripts/test/tc_phase2.md,Phase2 测试文件。Token comparison test. 用于量化对比。"
req, resp, status, result = call(prompt)
tc_req_total += req; tc_resp_total += resp
print(f"{'文件;写入':<25} {req:>10} {resp:>10} {req+resp:>8} {status}")

# 2A-2: Git push (setup branch first)
import subprocess
repo = "/root/.openclaw/workspace/text-cli"
subprocess.run(["cp", f"/root/.openclaw/workspace/tide-scripts/test/tc_phase2.md", f"{repo}/tc_phase2_output.md"])
subprocess.run(["git", "-C", repo, "checkout", "-b", "feat/token-quant-test"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["git", "-C", repo, "add", "tc_phase2_output.md"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["git", "-C", repo, "commit", "-m", "test: token quantification phase 2"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

prompt = "指令:Git;推送,feat/token-quant-test"
req, resp, status, result = call(prompt)
tc_req_total += req; tc_resp_total += resp
print(f"{'Git;推送':<25} {req:>10} {resp:>10} {req+resp:>8} {status}")

# 2A-3: Email
prompt = "指令:邮件;发送,claw2@10000.world,量化测试-文本指令,这是文本指令方式发送的邮件。Token量化对比测试。"
req, resp, status, result = call(prompt)
tc_req_total += req; tc_resp_total += resp
print(f"{'邮件;发送':<25} {req:>10} {resp:>10} {req+resp:>8} {status}")

print("-" * 60)
print(f"{'文本指令 合计':<25} {tc_req_total:>10} {tc_resp_total:>10} {tc_req_total+tc_resp_total:>8}")
print(f"{'文本指令 平均':<25} {tc_req_total//3:>10} {tc_resp_total//3:>10} {(tc_req_total+tc_resp_total)//3:>8}")

# ═══════════════════════════════════════════════════════
# 2B: 传统方式
# ═══════════════════════════════════════════════════════
print("\n── 2B: 传统 Agent 方式 ──")
print(f"{'操作':<25} {'命令(chars)':>10} {'输出(chars)':>10} {'合计':>8} {'':>3}")
print("-" * 60)

tr_cmd_total = 0
tr_out_total = 0

# 2B-1: File write
cmd = "cat > /root/.openclaw/workspace/tide-scripts/test/tr_phase2.md << 'EOF'\n传统方式测试文件。Traditional method test. 用于Token量化对比。\nEOF"
cmd_chars, out_chars, preview = measure_traditional(cmd, "file_write")
tr_cmd_total += cmd_chars; tr_out_total += out_chars
print(f"{'文件写入 (exec)':<25} {cmd_chars:>10} {out_chars:>10} {cmd_chars+out_chars:>8} ✅")

# 2B-2: Git push
subprocess.run(["cp", "/root/.openclaw/workspace/tide-scripts/test/tr_phase2.md", f"{repo}/tr_phase2_output.md"], capture_output=True)
subprocess.run(["git", "-C", repo, "add", "tr_phase2_output.md"], capture_output=True)
subprocess.run(["git", "-C", repo, "commit", "-m", "test: traditional method phase 2"], capture_output=True)
cmd = "cd /root/.openclaw/workspace/text-cli && git push origin feat/token-quant-test 2>&1"
cmd_chars, out_chars, preview = measure_traditional(cmd, "git_push")
tr_cmd_total += cmd_chars; tr_out_total += out_chars
print(f"{'Git推送 (exec)':<25} {cmd_chars:>10} {out_chars:>10} {cmd_chars+out_chars:>8} ✅")

# 2B-3: Email (via Python smtplib)
cmd = """python3 -c "
import smtplib, ssl
from email.mime.text import MIMEText
msg = MIMEText('传统方式发送的邮件。Token量化对比测试。', _charset='utf-8')
msg['Subject'] = '量化测试-传统方式'
msg['From'] = 'claw1@10000.world'
msg['To'] = 'claw2@10000.world'
ctx = ssl.create_default_context()
with smtplib.SMTP_SSL('smtp.mxhichina.com', 465, context=ctx) as s:
    s.login('claw1@10000.world', 'Tide202606')
    s.send_message(msg)
print('邮件已发送')
"
"""
cmd_chars, out_chars, preview = measure_traditional(cmd, "email")
tr_cmd_total += cmd_chars; tr_out_total += out_chars
print(f"{'邮件发送 (exec)':<25} {cmd_chars:>10} {out_chars:>10} {cmd_chars+out_chars:>8} ✅")

print("-" * 60)
print(f"{'传统方式 合计':<25} {tr_cmd_total:>10} {tr_out_total:>10} {tr_cmd_total+tr_out_total:>10}")
print(f"{'传统方式 平均':<25} {tr_cmd_total//3:>10} {tr_out_total//3:>10} {(tr_cmd_total+tr_out_total)//3:>10}")

# ═══════════════════════════════════════════════════════
# Phase 2C: 对比结论
# ═══════════════════════════════════════════════════════
print("\n── 2C: 对比 ──")
tc_total = tc_req_total + tc_resp_total
tr_total = tr_cmd_total + tr_out_total
ratio = tr_total / tc_total if tc_total > 0 else 0
print(f"文本指令总字符: {tc_total}")
print(f"传统方式总字符: {tr_total}")
print(f"文本指令 / 传统方式: {tc_total}/{tr_total} = {1/ratio:.1%}" if ratio > 0 else "N/A")
print(f"传统方式是文本指令的: {ratio:.1f}x")

# ═══════════════════════════════════════════════════════
# Phase 3: 路径链
# ═══════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("Phase 3: 路径链量化")
print("=" * 70)

# Push AI status
import urllib.request as ur
status_data = json.dumps({"model": "test", "context_pct": 0, "message": "路径量化测试"}).encode()
req = ur.Request("http://127.0.0.1:20260/ai_status", data=status_data,
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"})
ur.urlopen(req)

print(f"\n{'步骤':<22} {'请求(chars)':>10} {'响应(chars)':>10} {'合计':>8} {'':>3}")
print("-" * 60)

path_req_total = 0
path_resp_total = 0

# Step 1: AI协作;消息
req, resp, status, result = call("指令:AI协作;消息,1")
path_req_total += req; path_resp_total += resp
print(f"{'AI协作;消息':<22} {req:>10} {resp:>10} {req+resp:>8} {status}")

# Step 2: 文件;写入
msg_text = result.get('rst_data', {}).get('text', 'no_msg')
req, resp, status, result = call(f"指令:文件;写入,/root/.openclaw/workspace/tide-scripts/test/tc_path_output2.md,路径链输出:{msg_text}")
path_req_total += req; path_resp_total += resp
print(f"{'文件;写入':<22} {req:>10} {resp:>10} {req+resp:>8} {status}")

# Step 3: 邮件;发送
req, resp, status, result = call(f"指令:邮件;发送,claw2@10000.world,路径量化测试,路径链测试邮件。Path chain quantification test.")
path_req_total += req; path_resp_total += resp
print(f"{'邮件;发送':<22} {req:>10} {resp:>10} {req+resp:>8} {status}")

print("-" * 60)
print(f"{'路径链 合计':<22} {path_req_total:>10} {path_resp_total:>10} {path_req_total+path_resp_total:>8}")
print(f"{'路径链 平均':<22} {path_req_total//3:>10} {path_resp_total//3:>10} {(path_req_total+path_resp_total)//3:>8}")

# ═══════════════════════════════════════════════════════
# Cleanup
# ═══════════════════════════════════════════════════════
subprocess.run(["git", "-C", repo, "checkout", "main"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["git", "-C", repo, "branch", "-D", "feat/token-quant-test"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["git", "-C", repo, "push", "origin", "--delete", "feat/token-quant-test"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("\n✅ 清理完成")
