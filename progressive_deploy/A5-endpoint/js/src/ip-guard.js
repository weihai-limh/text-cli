function ipToInt(ip) {
  const parts = ip.split('.');
  return ((parseInt(parts[0], 10) << 24) |
    (parseInt(parts[1], 10) << 16) |
    (parseInt(parts[2], 10) << 8) |
    parseInt(parts[3], 10)) >>> 0;
}

function ipInCIDR(ip, cidr) {
  const [net, bitsStr] = cidr.split('/');
  const bits = parseInt(bitsStr, 10);
  const mask = ~((1 << (32 - bits)) - 1);
  return (ipToInt(ip) & mask) === (ipToInt(net) & mask);
}

let _blacklist = null;

function loadBlacklist(env) {
  const raw = env.IP_BLACKLIST || '';
  if (!raw) return [];
  return raw.split(',').map((s) => s.trim()).filter(Boolean);
}

export function isIPBlocked(ip, env) {
  if (!ip) return false;
  if (_blacklist === null) {
    _blacklist = loadBlacklist(env);
  }
  for (const entry of _blacklist) {
    if (entry.includes('/')) {
      if (ipInCIDR(ip, entry)) return true;
    } else if (ip === entry) {
      return true;
    }
  }
  return false;
}
