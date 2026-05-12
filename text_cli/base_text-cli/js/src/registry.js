const _registry = new Map();

export function registerHandler(domain, action, handler) {
  const key = `${domain};${action}`;
  _registry.set(key, handler);
}

export function dispatch(domain, action, params) {
  const key = `${domain};${action}`;
  const handler = _registry.get(key);
  if (!handler) {
    return `未找到匹配的指令: ${domain};${action}`;
  }
  return handler(params);
}

export function getRegisteredDirectives() {
  const result = {};
  for (const [key] of _registry) {
    const sepIdx = key.indexOf(';');
    const domain = key.slice(0, sepIdx);
    const action = key.slice(sepIdx + 1);
    if (!result[domain]) result[domain] = [];
    result[domain].push(action);
  }
  return result;
}

export function getRegistrySize() {
  return _registry.size;
}

export function clearRegistry() {
  _registry.clear();
}
