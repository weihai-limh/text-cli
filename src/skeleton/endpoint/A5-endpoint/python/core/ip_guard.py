import os
import ipaddress
import logging

logger = logging.getLogger(__name__)

_blacklist = None


def _load_blacklist():
    raw = os.getenv("IP_BLACKLIST", "")
    if not raw:
        return []

    networks = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            logger.warning("Invalid IP blacklist entry: %s", item)

    return networks


def _get_blacklist():
    global _blacklist
    if _blacklist is None:
        _blacklist = _load_blacklist()
    return _blacklist


def is_ip_blocked(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        logger.warning("Cannot parse client IP: %s", ip_str)
        return False

    for net in _get_blacklist():
        if ip in net:
            logger.warning("Blocked IP: %s (matched %s)", ip_str, net)
            return True

    return False
