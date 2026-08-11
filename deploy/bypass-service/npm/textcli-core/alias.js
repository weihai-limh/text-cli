// textcli-core alias — Alias mapping for directive domain/action
// Zero-dependency, isomorphic with Python textcli-loader registry alias logic.
//
// Aliases are bidirectional for lookup purposes (Chinese <-> English),
// but resolve() always returns the canonical form.
// Aliases are only access entries — they do not change the routing primary key.

"use strict";

/** @type {Map<string, string>} anyKey -> canonicalDomain */
const _domainMap = new Map();

/** @type {Map<string, Map<string, string>>} canonicalDomain -> (anyKey -> canonicalAction) */
const _actionMap = new Map();

/**
 * Register an alias mapping.
 * Creates lookup entries so that both alias->canonical and canonical->alias
 * (when used as input) resolve to the canonical form.
 *
 * @param {string} domainAlias - alias for the domain (e.g. "天气")
 * @param {string} actionAlias - alias for the action (e.g. "查询")
 * @param {string} canonicalDomain - canonical domain name (e.g. "weather")
 * @param {string} canonicalAction - canonical action name (e.g. "query")
 */
function addAlias(domainAlias, actionAlias, canonicalDomain, canonicalAction) {
  const da = domainAlias.toLowerCase();
  const cd = canonicalDomain.toLowerCase();
  const aa = actionAlias.toLowerCase();
  const ca = canonicalAction.toLowerCase();

  // domain: both alias and canonical map to canonical
  _domainMap.set(da, canonicalDomain);
  _domainMap.set(cd, canonicalDomain);

  // action: under canonicalDomain, both alias and canonical map to canonicalAction
  if (!_actionMap.has(cd)) _actionMap.set(cd, new Map());
  _actionMap.get(cd).set(aa, canonicalAction);
  _actionMap.get(cd).set(ca, canonicalAction);
}

/**
 * Resolve domain and action to canonical names.
 * Both inputs may be aliases or canonical — the result is always canonical.
 *
 * @param {string} domain - possibly aliased domain
 * @param {string} action - possibly aliased action
 * @returns {{domain:string, action:string}|null} canonical pair, or null if not found
 */
function resolve(domain, action) {
  const d = domain.toLowerCase();
  const a = action.toLowerCase();

  const canonicalDomain = _domainMap.get(d);
  if (!canonicalDomain) return null;

  const actions = _actionMap.get(canonicalDomain.toLowerCase());
  if (!actions) return null;

  const canonicalAction = actions.get(a);
  if (!canonicalAction) return null;

  return { domain: canonicalDomain, action: canonicalAction };
}

module.exports = { addAlias, resolve };
