"""
Directive registry with alias support.

Isomorphic with text-cli service core/registry.py @directive decorator.
Extracted to zero-dependency module for pip-installable textcli-loader.

Usage:
    from textcli_loader.registry import directive

    @directive("date-calc", "add-days", domain_alias="日期", action_aliases={"add-days": "加天"})
    def add_days(params):
        ...
"""

from collections.abc import Callable

_registry: dict[str, dict[str, Callable]] = {}
_domain_aliases: dict[str, str] = {}
_action_aliases: dict[str, dict[str, str]] = {}


def directive(
    domain: str,
    action: str,
    domain_alias: str | None = None,
    action_aliases: dict[str, str] | None = None,
):
    """Register a directive handler.

    Args:
        domain: Canonical (English) domain name
        action: Canonical (English) action name
        domain_alias: Optional Chinese domain alias (bidirectional)
        action_aliases: Optional {action: alias} mapping (bidirectional)
    """
    def decorator(func: Callable):
        domain_lower = domain.lower()
        if domain_lower not in _registry:
            _registry[domain_lower] = {}
        _registry[domain_lower][action.lower()] = func

        if domain_alias:
            alias_lower = domain_alias.lower()
            _domain_aliases[alias_lower] = domain_lower
            if domain_lower not in _domain_aliases:
                _domain_aliases[domain_lower] = alias_lower

        if action_aliases:
            if domain_lower not in _action_aliases:
                _action_aliases[domain_lower] = {}
            for ca, alias in action_aliases.items():
                _action_aliases[domain_lower][alias.lower()] = ca.lower()

        return func
    return decorator


def _resolve_domain(domain: str) -> str | None:
    d = domain.lower().strip()
    if d in _registry:
        return d
    if d in _domain_aliases:
        return _domain_aliases[d]
    return None


def _resolve_action(canonical_domain: str, action: str) -> str | None:
    a = action.lower().strip()
    actions = _registry.get(canonical_domain, {})
    if a in actions:
        return a
    domain_aliases = _action_aliases.get(canonical_domain, {})
    if a in domain_aliases:
        return domain_aliases[a]
    return None


def dispatch(domain: str, action: str, params: list[str]):
    """Dispatch a directive, resolving aliases before lookup.

    Returns handler result, or None if no matching directive found.
    Caller is responsible for wrapping in protocol envelope.
    """
    canonical_domain = _resolve_domain(domain)
    if canonical_domain is None:
        return None

    canonical_action = _resolve_action(canonical_domain, action)
    if canonical_action is None:
        return None

    handler = _registry[canonical_domain][canonical_action]
    return handler(params)


def get_registered() -> dict[str, list[str]]:
    """Return all registered directives."""
    return {
        domain: list(actions.keys())
        for domain, actions in _registry.items()
    }


def _clear():
    """Reset registry (internal, for testing)."""
    _registry.clear()
    _domain_aliases.clear()
    _action_aliases.clear()
