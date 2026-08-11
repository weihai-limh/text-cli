const { ok, err } = require('./envelope');

exports.handler = async (params, event) => {
  // params: [] (无参数)
  // event: CloudBase event 对象（含 sourceIp 等信息）

  const publicIp = extractPublicIp(event);

  if (publicIp === 'unknown') {
    return err('CANNOT_GET_IP', 'Unable to determine public IP');
  }

  // 仅返回 IP 字符串，不返回归属地
  return ok({ status: 'ok', result: publicIp });
};

function extractPublicIp(event) {
  // 优先从 router 传过来的原始 event 里拿 IP
  const routerEvent = event._routerEvent;
  if (routerEvent) {
    if (routerEvent.sourceIp) return routerEvent.sourceIp;
    const routerHeaders = routerEvent.headers || {};
    if (routerHeaders['x-forwarded-for']) return routerHeaders['x-forwarded-for'].split(',')[0].trim();
    if (routerHeaders['x-real-ip']) return routerHeaders['x-real-ip'];
  }
  // 备选：直接用当前 event（HTTP 直连调用时）
  if (event.sourceIp) return event.sourceIp;
  const headers = event.headers || {};
  if (headers['x-forwarded-for']) return headers['x-forwarded-for'].split(',')[0].trim();
  if (headers['x-real-ip']) return headers['x-real-ip'];
  return 'unknown';
}
