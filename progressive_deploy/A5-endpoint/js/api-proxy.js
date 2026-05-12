/**
 * text-cli-api 透明转发代理
 * 部署于 api.text-cli.com，将请求按路径/子域路由到不同后端。
 *
 * 用法：
 *   wrangler deploy
 *   wrangler routes add api.text-cli.com/*
 */

// ─── 路由表 ───────────────────────────────────────────
// key:  匹配模式（前缀匹配）
// host: 转发目标 hostname
// 匹配不到走 defaultRoute
const ROUTES = [
  // 示例：特定子路径转发到独立服务
  // { pattern: '/direct/weather', host: 'weather.instantiated.space' },
  // { pattern: '/direct/translate', host: 'translate.example.com' },
];

const defaultHost = 'text-cli-api.realearth.world';

// ─── Worker ───────────────────────────────────────────

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const path = url.pathname;

    // 匹配路由表（前缀匹配）
    const match = ROUTES.find(r => path.startsWith(r.pattern));

    const target = match ? match.host : defaultHost;

    // 可选：路径重写（去掉路由前缀）
    // if (match) url.pathname = path.replace(match.pattern, '') || '/';

    url.hostname = target;

    return fetch(url, new Request(url, request));
  }
};
