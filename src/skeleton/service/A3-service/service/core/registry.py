"""
Directive registry with alias support.

English is canonical: domain and action names are registered in English.
Chinese names are registered as bidirectional aliases via domain_alias / action_aliases.

Usage:
    @directive("key", "register", domain_alias="密钥", action_aliases={"register": "注册"})
    def key_register(params): ...

During transition, ALL combinations work:
    AI:key;register   → canonical
    AI:密钥;注册      → aliased (both domain and action)
    AI:key;注册       → mixed (canonical domain, aliased action)
    指令:密钥;register → mixed (aliased domain, canonical action)
"""

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

_registry: dict[str, dict[str, Callable]] = {}

# Alias maps: lowercase alias → canonical name
_domain_aliases: dict[str, str] = {}
_action_aliases: dict[str, dict[str, str]] = {}  # canonical_domain → {action_alias: canonical_action}


def directive(
    domain: str,
    action: str,
    domain_alias: str | None = None,
    action_aliases: dict[str, str] | None = None,
):
    """
    Register a directive handler.

    Args:
        domain: Canonical (English) domain name
        action: Canonical (English) action name
        domain_alias: Optional Chinese domain alias (bidirectional)
        action_aliases: Optional {canonical_action: chinese_alias} mapping (bidirectional)
    """
    def decorator(func: Callable):
        domain_lower = domain.lower()
        action_lower = action.lower()

        if domain_lower in _registry and action_lower in _registry[domain_lower]:
            logger.warning("Directive re-registered: %s;%s (overwriting %s → %s)",
                           domain, action,
                           _registry[domain_lower][action_lower].__name__, func.__name__)

        if domain_lower not in _registry:
            _registry[domain_lower] = {}
        _registry[domain_lower][action.lower()] = func

        # Register domain alias (bidirectional)
        if domain_alias:
            alias_lower = domain_alias.lower()
            _domain_aliases[alias_lower] = domain_lower
            # Also map canonical → alias for reverse lookup
            if domain_lower not in _domain_aliases:
                _domain_aliases[domain_lower] = alias_lower

        # Register action aliases (bidirectional)
        if action_aliases:
            if domain_lower not in _action_aliases:
                _action_aliases[domain_lower] = {}
            for canonical_action, chinese_alias in action_aliases.items():
                _action_aliases[domain_lower][chinese_alias.lower()] = canonical_action.lower()

        logger.info("Directive registered: %s;%s → %s (alias: %s)",
                     domain, action, func.__name__, domain_alias or "-")
        return func
    return decorator


def _resolve_domain(domain: str) -> str | None:
    """Resolve a (possibly aliased) domain to its canonical form (lowercase)."""
    d = domain.lower().strip()
    if d in _registry:
        return d
    if d in _domain_aliases:
        return _domain_aliases[d]
    return None


def _resolve_action(canonical_domain: str, action: str) -> str | None:
    """Resolve a (possibly aliased) action within a canonical domain (lowercase)."""
    a = action.lower().strip()
    actions = _registry.get(canonical_domain, {})
    if a in actions:
        return a
    # Check action aliases for this domain
    domain_action_aliases = _action_aliases.get(canonical_domain, {})
    if a in domain_action_aliases:
        return domain_action_aliases[a]
    return None


def dispatch(domain: str, action: str, params: list[str]) -> str:
    """Dispatch a directive, resolving aliases before lookup.
    
    Returns a JSON string with {rst_types, rst_data, rst_err}. If the directive
    is not found, rst_err is set to 'ERR_NOT_FOUND'. Plain-text handler returns
    are wrapped in the standard format.
    """
    import json as _json
    canonical_domain = _resolve_domain(domain)
    if canonical_domain is None:
        return _json.dumps({"rst_types": "text", "rst_data": {"text": f"No matching directive: {domain};{action}"},
                            "rst_err": "ERR_NOT_FOUND"}, ensure_ascii=False)

    canonical_action = _resolve_action(canonical_domain, action)
    if canonical_action is None:
        return _json.dumps({"rst_types": "text", "rst_data": {"text": f"No matching directive: {domain};{action}"},
                            "rst_err": "ERR_NOT_FOUND"}, ensure_ascii=False)

    handler = _registry[canonical_domain][canonical_action]
    result = handler(params)
    if isinstance(result, str):
        try:
            parsed = _json.loads(result)
            if isinstance(parsed, dict) and "rst_types" in parsed:
                return result
        except (_json.JSONDecodeError, TypeError):
            pass
    return _json.dumps({"rst_types": "text", "rst_data": {"text": result},
                        "rst_err": ""}, ensure_ascii=False)


def get_registered_directives() -> dict[str, list[str]]:
    """Return registered directives with canonical names."""
    return {
        domain: list(actions.keys())
        for domain, actions in _registry.items()
    }


def unregister(domain: str, action: str) -> bool:
    """Remove a directive from the in-memory registry.
    
    Called during package uninstallation to prevent stale handler references.
    Returns True if an entry was removed, False if not found.
    """
    domain_lower = domain.lower().strip()
    action_lower = action.lower().strip()
    if domain_lower in _registry and action_lower in _registry[domain_lower]:
        del _registry[domain_lower][action_lower]
        if not _registry[domain_lower]:
            del _registry[domain_lower]
        logger.info("Directive unregistered: %s;%s", domain, action)
        return True
    return False
