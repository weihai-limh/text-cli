/* text_cli_core.c -- text-cli protocol core (C99, zero external dependency)
 *
 * M3 scope: tc_parse / in-place registry / tc_dispatch /
 *           tc_envelope_serialize / tc_json_* helpers / tc_caps_json.
 *
 * Semantic decisions (see docs/LIMITS_zh.md; match conformance observe items):
 *  - Double quote opens/closes a string; single quote does NOT
 *    (aligned with the Python textcli-loader).
 *  - Backslash escapes the next char (backslash itself is KEPT);
 *    aligned with Python (JS drops the backslash -- a known drift).
 *  - Empty params after trim are dropped.
 *  - pray_rst_types: non-"text" value promotes type and is stripped;
 *    "text" is also stripped (SPEC S1.2.2).
 *  - Prefix: "AI:" only.
 */
#include "text_cli_core.h"

#include <string.h>

/* ---- helpers ---- */

static int is_ws(unsigned char c) {
    return c == ' ' || c == '\t' || c == '\r' || c == '\n';
}

/* ---- tc_parse ---- */

tc_err tc_parse(const char *prompt, size_t len, tc_directive *out) {
    if (!prompt || !out) return TC_ERR_INVALID_PARAMS;
    memset(out, 0, sizeof(*out));
    if (len == 0 || len > TC_MAX_PROMPT) return TC_ERR_INVALID_PARAMS;

    /* Leading whitespace before the prefix (matches JS regex ^\s*AI:) */
    size_t lead = 0;
    while (lead < len && is_ws((unsigned char)prompt[lead])) lead++;
    len -= lead;
    prompt += lead;

    /* Prefix: "AI:" (3 bytes) */
    if (len < 3 || memcmp(prompt, "AI:", 3) != 0) return TC_ERR_INVALID_PARAMS;

    size_t i = 3;
    while (i < len && is_ws((unsigned char)prompt[i])) i++;

    /* domain: up to the first ';' */
    size_t dom_s = i;
    while (i < len && prompt[i] != ';') i++;
    if (i >= len) return TC_ERR_INVALID_PARAMS;   /* no ';' */
    size_t dom_e = i;
    i++;

    /* action: up to the first ',' or end */
    size_t act_s = i;
    while (i < len && prompt[i] != ',') i++;
    size_t act_e = i;

    /* trim domain/action */
    while (dom_s < dom_e && is_ws((unsigned char)prompt[dom_s])) dom_s++;
    while (dom_e > dom_s && is_ws((unsigned char)prompt[dom_e - 1])) dom_e--;
    while (act_s < act_e && is_ws((unsigned char)prompt[act_s])) act_s++;
    while (act_e > act_s && is_ws((unsigned char)prompt[act_e - 1])) act_e--;

    if (dom_e == dom_s) return TC_ERR_INVALID_PARAMS;  /* empty domain */
    if (act_e == act_s) return TC_ERR_INVALID_PARAMS;  /* empty action */

    out->domain = prompt + dom_s;
    out->domain_len = dom_e - dom_s;
    out->action = prompt + act_s;
    out->action_len = act_e - act_s;

    /* params: split after the first ',' if present */
    if (i < len) {
        i++;  /* skip ',' */
        size_t tail_s = i, tail_e = len;
        while (tail_e > tail_s && is_ws((unsigned char)prompt[tail_e - 1])) tail_e--;

        int depth = 0, in_str = 0, esc = 0;
        size_t seg_s = tail_s;
        int n = 0, truncated = 0;

        for (size_t j = tail_s; j <= tail_e; j++) {
            int at_end = (j == tail_e);
            unsigned char c = at_end ? 0 : (unsigned char)prompt[j];
            int flush = at_end;

            if (!at_end) {
                if (esc) { esc = 0; continue; }
                if (c == '\\') { esc = 1; continue; }
                if (c == '"' && depth == 0) { in_str = !in_str; continue; }
                if (in_str) continue;
                if (c == '{' || c == '[') {
                    if (depth >= TC_MAX_DEPTH) return TC_ERR_INVALID_PARAMS;
                    depth++;
                    continue;
                }
                if (c == '}' || c == ']') { if (depth > 0) depth--; continue; }
                if (c == ',' && depth == 0) flush = 1;
            }

            if (flush) {
                /* segment [seg_s, j) -- trim, drop if empty */
                size_t s2 = seg_s;
                size_t e2 = at_end ? tail_e : j;
                while (s2 < e2 && is_ws((unsigned char)prompt[s2])) s2++;
                while (e2 > s2 && is_ws((unsigned char)prompt[e2 - 1])) e2--;
                if (e2 > s2) {
                    if (n < TC_MAX_PARAMS) {
                        out->params[n] = prompt + s2;
                        out->param_lens[n] = e2 - s2;
                        n++;
                    } else {
                        truncated = 1;
                    }
                }
                if (!at_end) seg_s = j + 1;
            }
        }
        out->n_params = n;
        out->truncated = truncated;
    }
    return TC_OK;
}

/* ---- registry (in-place, fixed capacity) ---- */

tc_err tc_registry_init(tc_registry *r) {
    if (!r) return TC_ERR_INVALID_PARAMS;
    memset(r, 0, sizeof(*r));
    return TC_OK;
}

/* pool-copy "a\0b\0" */
static char *pool_dup(tc_registry *r, const char *a, size_t al,
                      const char *b, size_t bl) {
    size_t total = al + 1 + bl + 1;
    if (r->pool_used + total > sizeof(r->pool)) return NULL;
    char *buf = r->pool + r->pool_used;
    memcpy(buf, a, al);
    buf[al] = '\0';
    memcpy(buf + al + 1, b, bl);
    buf[al + 1 + bl] = '\0';
    r->pool_used += total;
    return buf;
}

tc_err tc_register(tc_registry *r, const char *domain, const char *action,
                   tc_handler_fn fn, void *ud) {
    if (!r || !domain || !action || !fn) return TC_ERR_INVALID_PARAMS;
    if (r->n_slots >= TC_REG_CAP) return TC_ERR_EXECUTION;
    size_t dl = strlen(domain), al = strlen(action);
    if (dl == 0 || al == 0) return TC_ERR_INVALID_PARAMS;
    char *key = pool_dup(r, domain, dl, action, al);
    if (!key) return TC_ERR_EXECUTION;
    tc_slot *s = &r->slots[r->n_slots++];
    s->key = key;
    s->canon = NULL;
    s->fn = fn;
    s->ud = ud;
    return TC_OK;
}

tc_err tc_alias_add(tc_registry *r,
                    const char *alias_domain, const char *alias_action,
                    const char *canon_domain, const char *canon_action) {
    if (!r || !alias_domain || !alias_action || !canon_domain || !canon_action)
        return TC_ERR_INVALID_PARAMS;
    if (r->n_slots >= TC_REG_CAP) return TC_ERR_EXECUTION;
    char *akey = pool_dup(r, alias_domain, strlen(alias_domain),
                          alias_action, strlen(alias_action));
    char *ckey = pool_dup(r, canon_domain, strlen(canon_domain),
                          canon_action, strlen(canon_action));
    if (!akey || !ckey) return TC_ERR_EXECUTION;
    tc_slot *s = &r->slots[r->n_slots++];
    s->key = akey;
    s->canon = ckey;
    s->fn = NULL;
    s->ud = NULL;
    return TC_OK;
}

/* resolve: first direct hit; if it is an alias, follow canon. */
static tc_handler_fn resolve(tc_registry *r, const char *d, size_t dl,
                             const char *a, size_t al, void **out_ud) {
    const tc_slot *found = NULL;
    for (size_t i = 0; i < r->n_slots; i++) {
        const tc_slot *s = &r->slots[i];
        size_t klen = strlen(s->key);
        if (klen != dl || memcmp(s->key, d, dl) != 0) continue;
        if (strlen(s->key + klen + 1) != al) continue;
        if (memcmp(s->key + klen + 1, a, al) != 0) continue;
        found = s;
        break;
    }
    if (!found) return NULL;
    if (found->fn) { *out_ud = found->ud; return found->fn; }
    if (!found->canon) return NULL;
    {
        size_t cdl = strlen(found->canon);
        const char *ca = found->canon + cdl + 1;
        for (size_t i = 0; i < r->n_slots; i++) {
            const tc_slot *s = &r->slots[i];
            if (!s->fn) continue;
            size_t klen = strlen(s->key);
            if (klen == cdl && memcmp(s->key, found->canon, cdl) == 0 &&
                strlen(s->key + klen + 1) == strlen(ca) &&
                memcmp(s->key + klen + 1, ca, strlen(ca)) == 0) {
                *out_ud = s->ud;
                return s->fn;
            }
        }
    }
    return NULL;
}

/* promote+strip pray_rst_types */
static void promote_pray(tc_response *resp) {
    for (size_t i = 0; i < resp->n_fields; i++) {
        if (resp->fields[i].key_len == 15 &&
            memcmp(resp->fields[i].key, "pray_rst_types", 15) == 0) {
            const char *v = resp->fields[i].val;
            size_t vl = resp->fields[i].val_len;
            if (vl >= 2 && v[0] == '"' && v[vl - 1] == '"') { v++; vl -= 2; }
            if (vl == 7 && memcmp(v, "picture", 7) == 0) resp->type = TC_RST_PICTURE;
            else if (vl == 5 && memcmp(v, "video", 5) == 0) resp->type = TC_RST_VIDEO;
            else if (vl == 5 && memcmp(v, "audio", 5) == 0) resp->type = TC_RST_AUDIO;
            else if (vl == 4 && memcmp(v, "file", 4) == 0) resp->type = TC_RST_FILE;
            /* "text"/unknown: type unchanged, but strip the key */
            for (size_t k = i; k + 1 < resp->n_fields; k++)
                resp->fields[k] = resp->fields[k + 1];
            resp->n_fields--;
            return;
        }
    }
}

tc_err tc_dispatch(tc_registry *r, const char *prompt, size_t len,
                   tc_response *resp) {
    if (!r || !prompt || !resp) return TC_ERR_INVALID_PARAMS;
    resp->type = TC_RST_TEXT;
    resp->err = TC_OK;
    resp->n_fields = 0;
    resp->scratch_used = 0;

    tc_directive d;
    tc_err pe = tc_parse(prompt, len, &d);
    if (pe != TC_OK) { resp->err = pe; return pe; }

    void *ud = NULL;
    tc_handler_fn fn = resolve(r, d.domain, d.domain_len,
                               d.action, d.action_len, &ud);
    if (!fn) { resp->err = TC_ERR_NOT_FOUND; return TC_ERR_NOT_FOUND; }

    tc_err he = fn(&d, ud, resp);
    if (he == TC_OK) promote_pray(resp);
    resp->err = he;
    return he;
}

/* ---- JSON value helpers (scratch-backed; pure, no IO/alloc) ---- */

/* reserve n bytes in scratch; returns start offset or (size_t)-1 */
static size_t scratch_reserve(tc_response *resp, size_t n) {
    if (!resp->scratch || resp->scratch_used + n > resp->scratch_cap)
        return (size_t)-1;
    size_t off = resp->scratch_used;
    resp->scratch_used += n;
    return off;
}

const char *tc_json_raw(tc_response *resp, const char *s, size_t len,
                        size_t *out_len) {
    if (!resp || !s) return NULL;
    size_t off = scratch_reserve(resp, len);
    if (off == (size_t)-1) return NULL;
    memcpy(resp->scratch + off, s, len);
    if (out_len) *out_len = len;
    return resp->scratch + off;
}

const char *tc_json_str(tc_response *resp, const char *s, size_t len,
                        size_t *out_len) {
    if (!resp || !s) return NULL;
    /* worst case: quotes (2) + per control byte up to 6 chars (\u00xx) */
    size_t cap = 2 + len * 6;
    if (!resp->scratch || resp->scratch_used + cap > resp->scratch_cap)
        return NULL;
    size_t off = resp->scratch_used;
    char *p = resp->scratch + off;
    size_t n = 0;
    p[n++] = '"';
    for (size_t i = 0; i < len; i++) {
        unsigned char c = (unsigned char)s[i];
        switch (c) {
        case '"':  p[n++] = '\\'; p[n++] = '"';  break;
        case '\\': p[n++] = '\\'; p[n++] = '\\'; break;
        case '\n': p[n++] = '\\'; p[n++] = 'n';  break;
        case '\r': p[n++] = '\\'; p[n++] = 'r';  break;
        case '\t': p[n++] = '\\'; p[n++] = 't';  break;
        case '\b': p[n++] = '\\'; p[n++] = 'b';  break;
        case '\f': p[n++] = '\\'; p[n++] = 'f';  break;
        default:
            if (c < 0x20) {
                static const char hex[] = "0123456789abcdef";
                p[n++] = '\\';
                p[n++] = 'u';
                p[n++] = '0';
                p[n++] = '0';
                p[n++] = hex[c >> 4];
                p[n++] = hex[c & 0x0f];
            } else {
                p[n++] = (char)c;
            }
        }
    }
    p[n++] = '"';
    resp->scratch_used += n;
    if (out_len) *out_len = n;
    return resp->scratch + off;
}

const char *tc_json_int(tc_response *resp, long long v, size_t *out_len) {
    if (!resp) return NULL;
    char tmp[24];
    int n = 0;
    if (v < 0) {
        unsigned long long u = (unsigned long long)(-(v + 1)) + 1ull;
        tmp[n++] = '-';
        char dig[24];
        int dn = 0;
        do { dig[dn++] = (char)('0' + (u % 10)); u /= 10; } while (u);
        while (dn > 0) tmp[n++] = dig[--dn];
    } else {
        unsigned long long u = (unsigned long long)v;
        char dig[24];
        int dn = 0;
        do { dig[dn++] = (char)('0' + (u % 10)); u /= 10; } while (u);
        while (dn > 0) tmp[n++] = dig[--dn];
    }
    return tc_json_raw(resp, tmp, (size_t)n, out_len);
}

const char *tc_json_bool(tc_response *resp, int b, size_t *out_len) {
    if (b) return tc_json_raw(resp, "true", 4, out_len);
    return tc_json_raw(resp, "false", 5, out_len);
}

const char *tc_json_null(tc_response *resp, size_t *out_len) {
    return tc_json_raw(resp, "null", 4, out_len);
}

/* ---- array builder ---- */

int tc_array_begin(tc_json_array *a, tc_response *resp) {
    if (!a || !resp) return -1;
    a->resp = resp;
    a->count = 0;
    a->failed = 0;
    a->begin_off = resp->scratch_used;
    if (scratch_reserve(resp, 1) == (size_t)-1) { a->failed = 1; return -1; }
    resp->scratch[a->begin_off] = '[';
    return 0;
}

/* append ',' before an element when not the first */
static int array_sep(tc_json_array *a) {
    if (!a || a->failed) return -1;
    if (a->count == 0) return 0;
    tc_response *resp = a->resp;
    if (scratch_reserve(resp, 1) == (size_t)-1) { a->failed = 1; return -1; }
    resp->scratch[resp->scratch_used - 1] = ',';
    return 0;
}

/* serialize one element in place; roll back separator on failure */
static int array_put_str(tc_json_array *a, const char *s, size_t len) {
    if (!a || a->failed) return -1;
    tc_response *resp = a->resp;
    size_t used_before = resp->scratch_used;
    if (array_sep(a) < 0) return -1;
    size_t flen = 0;
    if (!tc_json_str(resp, s, len, &flen)) {
        resp->scratch_used = used_before;
        a->failed = 1;
        return -1;
    }
    a->count++;
    return 0;
}

static int array_put_raw(tc_json_array *a, const char *s, size_t len) {
    if (!a || a->failed) return -1;
    tc_response *resp = a->resp;
    size_t used_before = resp->scratch_used;
    if (array_sep(a) < 0) return -1;
    size_t flen = 0;
    if (!tc_json_raw(resp, s, len, &flen)) {
        resp->scratch_used = used_before;
        a->failed = 1;
        return -1;
    }
    a->count++;
    return 0;
}

int tc_array_raw(tc_json_array *a, const char *s, size_t len) {
    return array_put_raw(a, s, len);
}

int tc_array_str(tc_json_array *a, const char *s, size_t len) {
    return array_put_str(a, s, len);
}

int tc_array_int(tc_json_array *a, long long v) {
    if (!a || a->failed) return -1;
    tc_response *resp = a->resp;
    size_t used_before = resp->scratch_used;
    if (array_sep(a) < 0) return -1;
    size_t flen = 0;
    if (!tc_json_int(resp, v, &flen)) {
        resp->scratch_used = used_before;
        a->failed = 1;
        return -1;
    }
    a->count++;
    return 0;
}

int tc_array_end(tc_json_array *a) {
    if (!a || a->failed) return -1;
    tc_response *resp = a->resp;
    if (scratch_reserve(resp, 1) == (size_t)-1) { a->failed = 1; return -1; }
    resp->scratch[resp->scratch_used - 1] = ']';
    return 0;
}

void tc_array_value(const tc_json_array *a, const char **out_s, size_t *out_len) {
    if (!a || !out_s || !out_len) return;
    *out_s = a->resp->scratch + a->begin_off;
    *out_len = a->resp->scratch_used - a->begin_off;
}

/* ---- serialize ---- */

tc_err tc_envelope_serialize(const tc_response *resp,
                             char *buf, size_t cap, size_t *out_len) {
    if (!resp || !buf) return TC_ERR_INVALID_PARAMS;
    const char *rt = tc_rst_str(resp->type);
    if (!rt) return TC_ERR_EXECUTION;
    size_t used = 0;
#define PUSH(s, n) do { if (used + (n) + 1 > cap) return TC_ERR_EXECUTION; \
                        memcpy(buf + used, (s), (n)); used += (n); } while (0)
#define PUSHS(s) PUSH((s), strlen(s))
#define PUSHC(c) do { if (used + 2 > cap) return TC_ERR_EXECUTION; buf[used++] = (c); } while (0)

    PUSHS("{\"rst_types\":\"");
    PUSHS(rt);
    PUSHS("\",\"rst_data\":{");

    for (size_t i = 0; i < resp->n_fields; i++) {
        if (i > 0) PUSHC(',');
        PUSHC('"');
        for (size_t k = 0; k < resp->fields[i].key_len; k++) {
            unsigned char c = (unsigned char)resp->fields[i].key[k];
            if (c == '"' || c == '\\') PUSHC('\\');
            PUSHC((char)c);
        }
        PUSHS("\":");
        PUSH(resp->fields[i].val, resp->fields[i].val_len);
    }

    PUSHS("},\"rst_err\":\"");
    if (resp->err != TC_OK) {
        const char *es = tc_err_str(resp->err);
        if (es) PUSHS(es);
    }
    PUSHS("\"}");

    buf[used] = '\0';
    if (out_len) *out_len = used;
    return TC_OK;
#undef PUSH
#undef PUSHS
#undef PUSHC
}

/* ---- string maps ---- */

const char *tc_err_str(tc_err e) {
    switch (e) {
    case TC_OK: return "";
    case TC_ERR_NOT_FOUND: return "ERR_NOT_FOUND";
    case TC_ERR_EXECUTION: return "ERR_EXECUTION";
    case TC_ERR_ROUTING: return "ERR_ROUTING";
    case TC_ERR_INVALID_PARAMS: return "INVALID_PARAMS";
    case TC_ERR_ACCESS_DENIED: return "ACCESS_DENIED";
    case TC_ERR_SERVICE_DENIED: return "SERVICE_DENIED";
    }
    return NULL;
}

const char *tc_rst_str(tc_rst_type t) {
    switch (t) {
    case TC_RST_TEXT: return "text";
    case TC_RST_PICTURE: return "picture";
    case TC_RST_VIDEO: return "video";
    case TC_RST_AUDIO: return "audio";
    case TC_RST_FILE: return "file";
    }
    return NULL;
}

const char *tc_caps_json(size_t *out_len) {
    static const char s[] =
        "{\"prefixes\":[\"AI:\"],"
        "\"mechanisms\":[\"directive_execution\",\"package_lifecycle\"],"
        "\"errors\":[\"ERR_NOT_FOUND\",\"ERR_EXECUTION\",\"ERR_ROUTING\","
        "\"INVALID_PARAMS\",\"ACCESS_DENIED\",\"SERVICE_DENIED\"],"
        "\"rst_types\":[\"text\",\"picture\",\"video\",\"audio\",\"file\"]}";
    if (out_len) *out_len = sizeof(s) - 1;
    return s;
}
