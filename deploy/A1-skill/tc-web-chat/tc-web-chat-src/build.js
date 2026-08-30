// ========== build.js ==========
// 零依赖拼接：读 shell.html（外壳真源）→ 内联 tc-*.js 进 <script> 段 → 写制品
// 纪律：纯 node 内置 fs；不引入 webpack/rollup。
// 多语言：源为 i18n.json（不硬编码在 js）；构建时按 --lang 读取对应字段，拼 `const LANGS/I18N` 注入脚本段。
//   默认 both 产出 tc-web-chat.html（内嵌 zh+en）；--lang zh → tc-web-chat_zh.html；--lang en → tc-web-chat_en.html。
//   外壳 DOM 由 shell.html 维护，本脚本不做 DOM 注入。

const fs = require('fs');
const path = require('path');

const ROOT = __dirname;                       // tc-web-chat-src/ 所在目录
const WEB_ROOT = path.dirname(ROOT);          // other/web/
const SOURCE_HTML = path.join(ROOT, 'shell.html');        // 外壳真源
const I18N_JSON = path.join(ROOT, 'i18n.json');           // 多语言源（纯字符串）

// 拼接顺序即模块依赖顺序（单 <script> 共享作用域）
const MODULE_ORDER = [
    'tc-config.js',
    'tc-cache.js',
    'tc-parser.js',
    'tc-approval.js',
    'tc-quiet.js',
    'tc-chat.js',
    'tc-integrate.js'
];

// 解析 --lang 参数：both | zh | en（默认 both）
function parseLangArg() {
    const i = process.argv.indexOf('--lang');
    if (i === -1) return 'both';
    const v = process.argv[i + 1];
    if (v === 'zh' || v === 'en' || v === 'both') return v;
    console.warn('[build] 未知 --lang 值 "' + v + '"，回退到 both');
    return 'both';
}

// 从 i18n.json 拼出注入脚本段的字典声明（按 lang 选语言分支）
function buildI18nSnippet(lang) {
    const dict = JSON.parse(fs.readFileSync(I18N_JSON, 'utf8'));
    const langs = dict.langs;
    let i18nOnly;
    if (lang === 'both') {
        // 显式锁定中英双语，新增语言（如 ja）不会污染 both 包
        i18nOnly = { en: dict.en, zh: dict.zh };
    } else {
        const key = lang;                        // zh | en（键名已统一，无需映射）
        i18nOnly = { [key]: dict[key] };         // 单语只留对应分支
    }
    const langsText = JSON.stringify(langs, null, 4);
    const i18nText = JSON.stringify(i18nOnly, null, 4);
    return '// ---- i18n (from i18n.json, lang=' + lang + ') ----\n'
         + 'const LANGS = ' + langsText + ';\n'
         + 'const I18N = ' + i18nText + ';\n';
}

function main() {
    const lang = parseLangArg();

    // 1. 读外壳真源
    const html = fs.readFileSync(SOURCE_HTML, 'utf8');

    // 2. 切分 <script> 段：head（含开标签）→ 拼接模块 → tail（含闭标签与 </body></html>）
    const scriptOpen = html.indexOf('<script>');
    const scriptClose = html.lastIndexOf('</script>');
    if (scriptOpen === -1 || scriptClose === -1 || scriptClose < scriptOpen) {
        throw new Error('SOURCE_HTML 未找到 <script> 段');
    }
    const head = html.slice(0, scriptOpen + '<script>'.length);
    const tail = html.slice(scriptClose);

    // 3. 顺序读模块并内联
    const parts = MODULE_ORDER.map((name) => {
        const p = path.join(ROOT, name);
        if (!fs.existsSync(p)) throw new Error('缺少模块: ' + name);
        return '// ---- ' + name + ' ----\n' + fs.readFileSync(p, 'utf8');
    });

    // 4. i18n 注入片段（来自 i18n.json，非硬编码在 js）
    const i18nSnippet = buildI18nSnippet(lang);

    // 5. 启动入口：在末尾调 bootTcWebChat()
    const bootstrap = '\n// ---- bootstrap ----\nbootTcWebChat();\n';

    const newScript = head + '\n' + i18nSnippet + '\n' + parts.join('\n\n') + '\n' + bootstrap + '\n' + tail;

    // 6. 写制品（按 lang 决定文件名，下划线构型）
    const outName = (lang === 'both') ? 'tc-web-chat.html'
                  : (lang === 'zh')   ? 'tc-web-chat_zh.html'
                  :                     'tc-web-chat_en.html';
    const OUT_HTML = path.join(WEB_ROOT, outName);
    fs.writeFileSync(OUT_HTML, newScript, 'utf8');
    console.log('[build] 语言:', lang, '→ 生成制品:', OUT_HTML);
    console.log('[build] 内联模块:', MODULE_ORDER.length, '个');
    console.log('[build] 字节数:', Buffer.byteLength(newScript, 'utf8'));
}

main();
