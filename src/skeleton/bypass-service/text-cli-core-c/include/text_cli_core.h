/* text_cli_core.h -- text-cli protocol core (C99, zero external dependency)
 *
 * Scope: direct projection of protocol clauses (SPEC S1.1 / S1.2.2 / S1.2.8).
 * Red lines: no IO / no network / no dynamic loading / no boundary validation /
 *            not a full 9-mechanism runtime.
 * Prefix: "AI:" only (legacy "directive:" NOT supported; see caps_json).
 *
 * Design:
 *  - zero-copy slices: parse results point into the caller's prompt buffer.
 *  - no global mutable state: all state lives in a caller-owned tc_registry.
 *  - table-driven state machine: no recursion, no backtracking.
 *  - registry: in-place model (caller holds it), fixed capacity, no malloc.
 */
#ifndef TEXT_CLI_CORE_H
#define TEXT_CLI_CORE_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ---- Constants (implementation constraints, not protocol; compile-time) ---- */
#ifndef TC_MAX_PARAMS
#define TC_MAX_PARAMS 16
#endif
#ifndef TC_MAX_PROMPT
#define TC_MAX_PROMPT 2048
#endif
#ifndef TC_MAX_DEPTH
#define TC_MAX_DEPTH 32
#endif
#ifndef TC_REG_CAP
#define TC_REG_CAP 64
#endif
#ifndef TC_REG_POOL
#define TC_REG_POOL 4096
#endif

/* ---- Closed set: error codes (SPEC S1.2.8) ---- */
typedef enum {
    TC_OK = 0,
    TC_ERR_NOT_FOUND,
    TC_ERR_EXECUTION,
    TC_ERR_ROUTING,
    TC_ERR_INVALID_PARAMS,
    TC_ERR_ACCESS_DENIED,
    TC_ERR_SERVICE_DENIED
} tc_err;

/* ---- Closed set: result types (SPEC S1.2.2) ---- */
typedef enum {
    TC_RST_TEXT = 0, TC_RST_PICTURE, TC_RST_VIDEO, TC_RST_AUDIO, TC_RST_FILE
} tc_rst_type;

/* ---- Parse result: zero-copy slices into caller prompt buffer ---- */
typedef struct {
    const char *domain;   size_t domain_len;
    const char *action;   size_t action_len;
    const char *params[TC_MAX_PARAMS];
    size_t      param_lens[TC_MAX_PARAMS];
    int         n_params;
    int         truncated;   /* 1 = exceeded TC_MAX_PARAMS */
} tc_directive;

/* ---- Envelope field: val is a pre-serialized JSON fragment ---- */
typedef struct {
    const char *key; size_t key_len;
    const char *val; size_t val_len;
} tc_field;

typedef struct {
    tc_rst_type  type;
    tc_field    *fields;      /* dispatch points it at a caller buffer */
    size_t       n_fields;
    size_t       fields_cap;
    tc_err       err;         /* TC_OK = success */
    /* Value arena: caller-provided buffer, valid until after
     * tc_envelope_serialize. dispatch resets used=0. Handlers build field
     * values here via the tc_json_* helpers (no malloc, no globals). */
    char        *scratch;
    size_t       scratch_cap;
    size_t       scratch_used;
} tc_response;

/* Handler: fill resp->fields[resp->n_fields++] (bounded by fields_cap),
 * using resp->scratch + tc_json_* helpers for field values.
 * Return TC_OK or a protocol error code. */
typedef tc_err (*tc_handler_fn)(const tc_directive *d, void *ud, tc_response *out);

/* ---- JSON value helpers (pure functions; no IO / no alloc / no globals) ----
 *
 * Handlers build `rst_data` field values as pre-serialized JSON fragments
 * into resp->scratch. These helpers do the quoting/escaping so a C handler
 * never hand-writes JSON escapes (mirrors json.dumps / JSON.stringify).
 *
 *   tc_json_raw  -- append a raw pre-serialized JSON fragment as-is
 *   tc_json_str  -- append a JSON string literal (escaped)
 *   tc_json_int  -- append a JSON number
 *   tc_json_bool -- append true/false
 *   tc_json_null -- append null
 *
 * Each returns a pointer into resp->scratch plus bytes written via *out_len,
 * or NULL when the scratch has no room (handler should then return
 * TC_ERR_EXECUTION).
 */
const char *tc_json_raw(tc_response *resp, const char *s, size_t len,
                        size_t *out_len);
const char *tc_json_str(tc_response *resp, const char *s, size_t len,
                        size_t *out_len);
const char *tc_json_int(tc_response *resp, long long v, size_t *out_len);
const char *tc_json_bool(tc_response *resp, int b, size_t *out_len);
const char *tc_json_null(tc_response *resp, size_t *out_len);

/* ---- Array builder (scratch-backed; handler owns the cursor struct) ----
 *
 * Handler usage:
 *     tc_json_array arr;
 *     if (tc_array_begin(&arr, resp) < 0) return TC_ERR_EXECUTION;
 *     tc_array_str(&arr, p1, l1);
 *     tc_array_str(&arr, p2, l2);
 *     if (tc_array_end(&arr) < 0) return TC_ERR_EXECUTION;
 *     const char *val; size_t val_len;
 *     tc_array_value(&arr, &val, &val_len);
 *     field.val = val; field.val_len = val_len;
 *
 * tc_array_begin writes '[' into scratch and records the offset. Element
 * appends write separators + values. tc_array_end writes ']'. The finished
 * fragment lives in resp->scratch (no extra allocation).
 */
typedef struct {
    tc_response *resp;
    size_t begin_off;   /* scratch offset just before '[' */
    int count;
    int failed;
} tc_json_array;

int  tc_array_begin(tc_json_array *a, tc_response *resp);
int  tc_array_raw(tc_json_array *a, const char *s, size_t len);
int  tc_array_str(tc_json_array *a, const char *s, size_t len);
int  tc_array_int(tc_json_array *a, long long v);
int  tc_array_end(tc_json_array *a);  /* 0 ok, <0 failed */
void tc_array_value(const tc_json_array *a, const char **out_s, size_t *out_len);

/* ---- Registry (in-place model, fixed capacity) ---- */
typedef struct {
    const char *key;      /* "domain\0action" (canon or alias), pool-owned */
    const char *canon;    /* alias -> canon "domain\0action"; NULL for handler */
    tc_handler_fn fn;     /* non-NULL for handler slot; NULL for alias slot */
    void *ud;
} tc_slot;

typedef struct {
    tc_slot  slots[TC_REG_CAP];
    size_t   n_slots;
    char     pool[TC_REG_POOL];
    size_t   pool_used;
} tc_registry;

/* ---- Functions ---- */
tc_err tc_parse(const char *prompt, size_t len, tc_directive *out);

tc_err tc_registry_init(tc_registry *r);
tc_err tc_register(tc_registry *r, const char *domain, const char *action,
                   tc_handler_fn fn, void *ud);
tc_err tc_alias_add(tc_registry *r,
                    const char *alias_domain, const char *alias_action,
                    const char *canon_domain, const char *canon_action);

/* Caller pre-sets resp (fields/fields_cap/type/err/n_fields=0) before calling. */
tc_err tc_dispatch(tc_registry *r, const char *prompt, size_t len,
                   tc_response *resp);

tc_err tc_envelope_serialize(const tc_response *resp,
                             char *buf, size_t cap, size_t *out_len);

const char *tc_caps_json(size_t *out_len);
const char *tc_err_str(tc_err e);
const char *tc_rst_str(tc_rst_type t);

#define TC_FIELDS_CAP 64

#ifdef __cplusplus
}
#endif

#endif /* TEXT_CLI_CORE_H */
