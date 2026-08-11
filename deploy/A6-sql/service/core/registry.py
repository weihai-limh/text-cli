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
from contextvars import ContextVar

logger = logging.getLogger(__name__)

# ── Ancestor chain — cycle detection for directive re-entry ──
# Per-request call stack tracked as tuple of resolved target keys.
# Push on handler entry, pop on exit. Concurrent workers copy the chain.
_ANCESTOR_CHAIN: ContextVar = ContextVar("_ANCESTOR_CHAIN", default=())

# Directives whose true target key can only be determined after handler-level
# resolution (e.g. pro resolves short names to path/aggregate targets).
# These skip entry-level checking and defer to their handler.
_DEFERRED_KEYS = {("text-cli", "pro")}

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
    
    Returns a JSON string with {rst_types, rst_data, rst_err}. The handler
    MUST return a dict — it is placed directly into rst_data. If the handler
    includes pray_rst_types, the skeleton promotes it to rst_types and strips
    it from rst_data.

    Implements ancestor-chain cycle detection: push resolved target key on
    entry, pop on exit. Concurrent workers copy the chain via ctx.copy().
    """
    import json as _json
    from core.response import ok, error

    canonical_domain = _resolve_domain(domain)
    if canonical_domain is None:
        return _json.dumps(error(f"No matching directive: {domain};{action}", "ERR_NOT_FOUND"),
                           ensure_ascii=False)

    canonical_action = _resolve_action(canonical_domain, action)
    if canonical_action is None:
        return _json.dumps(error(f"No matching directive: {domain};{action}", "ERR_NOT_FOUND"),
                           ensure_ascii=False)

    # ── Ancestor chain: check for re-entry cycles ──
    is_deferred = (canonical_domain, canonical_action) in _DEFERRED_KEYS
    chain = _ANCESTOR_CHAIN.get()

    if not is_deferred:
        # Compute resolved target key as string
        key = _make_ancestor_key(canonical_domain, canonical_action, params)
        if key in chain:
            return _json.dumps(error(
                f"call cycle detected: {key} re-entered (chain: {' → '.join(chain)})",
                "ERR_EXECUTION",
            ), ensure_ascii=False)
        # Push key onto chain, call handler, pop on exit
        token = _ANCESTOR_CHAIN.set(chain + (key,))
    else:
        token = None

    try:
        handler = _registry[canonical_domain][canonical_action]
        result = handler(params)
    finally:
        if token is not None:
            _ANCESTOR_CHAIN.reset(token)

    if isinstance(result, dict):
        return _json.dumps(ok(result), ensure_ascii=False)

    if isinstance(result, str):
        return _json.dumps(error(
            f"Handler for {domain};{action} returned str — handlers must return dict. "
            f"See package-python-dev-guide_zh.md for the updated handler contract.",
            "ERR_EXECUTION",
        ), ensure_ascii=False)

    return _json.dumps(error(
        f"Handler for {domain};{action} returned unexpected type {type(result).__name__}",
        "ERR_EXECUTION",
    ), ensure_ascii=False)


def _make_ancestor_key(canonical_domain: str, canonical_action: str,
                       params: list[str]) -> str:
    """Build a resolved target key string for ancestor chain tracking.

    Key format:
        path:<id>        — for text-cli;path (params[0] = path id)
        agg:<name>       — for aggregate domain entries (matches pro's early check key)
        native:<domain>;<action> — for all other directives
    """
    if canonical_domain == "text-cli" and canonical_action == "path" and params:
        return f"path:{params[0]}"
    # Check if this domain is an aggregate entry (so pro's agg:<name> can match)
    if _is_aggregate_domain(canonical_domain):
        return f"agg:{canonical_domain}"
    return f"native:{canonical_domain};{canonical_action}"


# Aggregate domain names — populated by main.py's _load_aggregates() on startup.
# Used by _make_ancestor_key to emit agg:<domain> keys for pro early-check matching.
_known_aggregate_domains: set = set()


def register_aggregate_domain(domain: str) -> None:
    """Register a domain as an aggregate entry (called by main.py on startup)."""
    _known_aggregate_domains.add(domain)


def _is_aggregate_domain(domain: str) -> bool:
    return domain in _known_aggregate_domains


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
