# call.ps1 — text-cli 调用封装（PowerShell 版）
# 通过参数或 stdin 传递指令文本，从 conf.json 读取端点配置。
#
# 用法:
#   .\call.ps1 "AI:tc-datetime;now"
#   .\call.ps1 -d "AI:tc-datetime;now" -e http://其它端点/text-cli/cli
#   "AI:tc-datetime;now" | .\call.ps1
#
# 配置（优先级: 环境变量 > conf.json > 内置默认）:
#   conf.json  — 与本脚本同目录，包含 endpoint / service_token / access_token
#   环境变量   — TEXT_CLI_ENDPOINT / TEXT_CLI_SERVICE_TOKEN / TEXT_CLI_ACCESS_TOKEN
#
# Token 在请求头中的位置:
#   access_token  → Authorization: Bearer <value>
#   service_token → Service-token: <value>

param(
    [string]$d,           # 指令文本（直接参数）
    [string]$directive,   # 指令文本（长参数名）
    [string]$e,           # 端点地址（覆盖）
    [string]$endpoint,    # 端点地址（长参数名）
    [switch]$h,           # 帮助
    [switch]$help         # 帮助（长参数名）
)

$ErrorActionPreference = "Stop"

# ── 帮助 ─────────────────────────────────────────────

if ($h -or $help) {
    Write-Host "用法: .\call.ps1 `"AI:域;动作,参数`""
    Write-Host "  -d, -directive <文本>  指令文本"
    Write-Host "  -e, -endpoint <URL>    指定端点地址（可选）"
    Write-Host "  -h, -help              显示帮助"
    Write-Host ""
    Write-Host "示例:"
    Write-Host "  .\call.ps1 `"AI:tc-datetime;now`""
    Write-Host "  .\call.ps1 -d `"AI:tc-math;eval,2+3`""
    Write-Host "  `"AI:tc-datetime;now`" | .\call.ps1"
    exit 0
}

# ── 读取配置 ──────────────────────────────────────────

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfFile = Join-Path $ScriptDir "conf.json"

$Endpoint = ""
$ServiceToken = ""
$AccessToken = ""

if (Test-Path $ConfFile) {
    $Conf = Get-Content $ConfFile -Raw | ConvertFrom-Json
    $Endpoint = $Conf.endpoint
    $ServiceToken = $Conf.service_token
    $AccessToken = $Conf.access_token
}

# 环境变量覆盖
if ($env:TEXT_CLI_ENDPOINT) { $Endpoint = $env:TEXT_CLI_ENDPOINT }
if ($env:TEXT_CLI_SERVICE_TOKEN) { $ServiceToken = $env:TEXT_CLI_SERVICE_TOKEN }
if ($env:TEXT_CLI_ACCESS_TOKEN) { $AccessToken = $env:TEXT_CLI_ACCESS_TOKEN }

# 参数覆盖
if ($e) { $Endpoint = $e }
if ($endpoint) { $Endpoint = $endpoint }

# 默认值
if (-not $Endpoint) { $Endpoint = "http://127.0.0.1/text-cli/cli" }

# ── 获取指令文本 ──────────────────────────────────────

$DirectiveText = ""

if ($d) {
    $DirectiveText = $d
} elseif ($directive) {
    $DirectiveText = $directive
} elseif ($input) {
    # 从 stdin 读取
    $DirectiveText = ($input | Out-String).Trim()
}

if (-not $DirectiveText) {
    Write-Host "用法: .\call.ps1 `"AI:域;动作,参数`"" -ForegroundColor Red
    Write-Host "  -d, -directive <文本>  指令文本" -ForegroundColor Yellow
    Write-Host "  -e, -endpoint <URL>    指定端点地址（可选）" -ForegroundColor Yellow
    Write-Host "  -h, -help              显示帮助" -ForegroundColor Yellow
    exit 1
}

# ── 构建请求头 ─────────────────────────────────────────

$Headers = @{
    "Content-Type" = "application/json"
}

if ($AccessToken) {
    $Headers["Authorization"] = "Bearer $AccessToken"
}

if ($ServiceToken) {
    $Headers["Service-token"] = $ServiceToken
}

# ── 构建请求体 ─────────────────────────────────────────

$Body = @{
    prompt = $DirectiveText
} | ConvertTo-Json -Compress

# ── 发送请求 ───────────────────────────────────────────

try {
    $Response = Invoke-WebRequest -Uri $Endpoint -Method Post -Headers $Headers -Body $Body -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
    
    if ($Response.StatusCode -eq 200) {
        $Result = $Response.Content | ConvertFrom-Json
        
        if ($Result.rst_types -eq "text") {
            Write-Output $Result.rst_data.text
        } else {
            # 非文本类型，返回原始 JSON
            Write-Output $Response.Content
        }
    } else {
        Write-Host "[ERR] 调用失败 (HTTP $($Response.StatusCode))" -ForegroundColor Red
        Write-Output $Response.Content
        exit 1
    }
} catch {
    Write-Host "[ERR] 调用失败: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
