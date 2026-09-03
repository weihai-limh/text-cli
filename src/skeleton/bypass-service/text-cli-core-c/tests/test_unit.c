/* test_unit.c -- text-cli-core-c M3 unit tests (pure ASCII)
 *
 * Covers: tc_parse (baseline semantics), registry, alias, envelope,
 *         tc_json_* value helpers (scratch-backed array/string builders).
 * Mirrors the baseline rows of conformance/vectors/parse.jsonl +
 * envelope.jsonl. (The JSONL machine runner lands in the conformance phase.)
 */
#include <stdio.h>
#include <string.h>

#include "text_cli_core.h"

static int _fails = 0;

#define CHECK(cond, msg) do { \
    if (!(cond)) { \
        printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, msg); \
        _fails++; \
    } \
} while (0)

/* One parse assertion: expects domain/action/params ('|'-joined) or an error
 * when exp_domain is NULL. */
static void expect_parse(const char *prompt,
                         const char *exp_domain, const char *exp_action,
                         const char *exp_params) {
    tc_directive d;
    tc_err e = tc_parse(prompt, strlen(prompt), &d);

    if (exp_domain == NULL) {
        if (e == TC_OK) {
            printf("FAIL parse(%s): expected INVALID_PARAMS, got OK\n", prompt);
            _fails++;
        }
        return;
    }
    if (e != TC_OK) {
        printf("FAIL parse(%s): parse error %s\n", prompt, tc_err_str(e));
        _fails++;
        return;
    }
    if (d.domain_len != strlen(exp_domain) ||
        memcmp(d.domain, exp_domain, d.domain_len) != 0) {
        printf("FAIL parse(%s): domain=%.*s expected %s\n", prompt,
               (int)d.domain_len, d.domain, exp_domain);
        _fails++;
        return;
    }
    if (d.action_len != strlen(exp_action) ||
        memcmp(d.action, exp_action, d.action_len) != 0) {
        printf("FAIL parse(%s): action=%.*s expected %s\n", prompt,
               (int)d.action_len, d.action, exp_action);
        _fails++;
        return;
    }
    /* params: exp_params uses '|' as separator */
    int idx = 0;
    const char *cur = exp_params;
    while (cur && *cur) {
        const char *pipe = strchr(cur, '|');
        size_t plen = pipe ? (size_t)(pipe - cur) : strlen(cur);
        if (idx >= d.n_params) {
            printf("FAIL parse(%s): want more params (#%d '%.*s'), got %d\n",
                   prompt, idx, (int)plen, cur, d.n_params);
            _fails++;
            return;
        }
        if (d.param_lens[idx] != plen ||
            memcmp(d.params[idx], cur, plen) != 0) {
            printf("FAIL parse(%s): param[%d]=%.*s expected %.*s\n", prompt, idx,
                   (int)d.param_lens[idx], d.params[idx], (int)plen, cur);
            _fails++;
            return;
        }
        idx++;
        cur = pipe ? pipe + 1 : NULL;
    }
    if (idx != d.n_params) {
        printf("FAIL parse(%s): param count %d expected %d\n",
               prompt, d.n_params, idx);
        _fails++;
    }
}

/* scratch backing the response value arena */
static char g_scratch[4096];

static void resp_init(tc_response *resp, tc_field *fields, size_t cap) {
    memset(resp, 0, sizeof(*resp));
    resp->fields = fields;
    resp->fields_cap = cap;
    resp->scratch = g_scratch;
    resp->scratch_cap = sizeof(g_scratch);
}

/* A tiny helper for handlers to append a JSON field, keeping each value's
 * own length (a scratch pointer can be consumed by later helper calls, so
 * capture val_len right after each serialize). */
typedef struct {
    tc_field *fields;
    size_t n;
    size_t cap;
} tc_field_writer;

static int fw_put(tc_field_writer *w, const char *key, size_t key_len,
                  const char *val, size_t val_len) {
    if (w->n >= w->cap) return -1;
    w->fields[w->n].key = key;
    w->fields[w->n].key_len = key_len;
    w->fields[w->n].val = val;
    w->fields[w->n].val_len = val_len;
    w->n++;
    return 0;
}

/* test handlers */
static tc_err h_echo(const tc_directive *d, void *ud, tc_response *out) {
    (void)ud;
    tc_field_writer w = { out->fields, out->n_fields, out->fields_cap };
    size_t ok_len = 0, n_len = 0;
    const char *okv = tc_json_raw(out, "\"ok\"", 4, &ok_len);
    const char *nv = tc_json_int(out, (long long)d->n_params, &n_len);
    if (!okv || !nv) return TC_ERR_EXECUTION;
    if (fw_put(&w, "status", 6, okv, ok_len) < 0) return TC_ERR_EXECUTION;
    if (fw_put(&w, "n", 1, nv, n_len) < 0) return TC_ERR_EXECUTION;
    out->n_fields = w.n;
    return TC_OK;
}

/* tc-probe style echo handler: {"status":"ok","echo":params[0]} */
static tc_err h_probe_echo(const tc_directive *d, void *ud, tc_response *out) {
    (void)ud;
    tc_field_writer w = { out->fields, out->n_fields, out->fields_cap };
    size_t ok_len = 0, echo_len = 0;
    const char *echo = d->n_params > 0
        ? tc_json_str(out, d->params[0], d->param_lens[0], &echo_len)
        : tc_json_str(out, "", 0, &echo_len);
    const char *okv = tc_json_raw(out, "\"ok\"", 4, &ok_len);
    if (!echo || !okv) return TC_ERR_EXECUTION;
    if (fw_put(&w, "status", 6, okv, ok_len) < 0) return TC_ERR_EXECUTION;
    if (fw_put(&w, "echo", 4, echo, echo_len) < 0) return TC_ERR_EXECUTION;
    out->n_fields = w.n;
    return TC_OK;
}

/* tc-probe style params handler: echo the parsed internal shape with a JSON
 * array of params -- the exact case the JSON helpers exist for. */
static tc_err h_probe_params(const tc_directive *d, void *ud, tc_response *out) {
    (void)ud;
    tc_field_writer w = { out->fields, out->n_fields, out->fields_cap };

    tc_json_array arr;
    if (tc_array_begin(&arr, out) < 0) return TC_ERR_EXECUTION;
    for (int i = 0; i < d->n_params; i++) {
        if (tc_array_str(&arr, d->params[i], d->param_lens[i]) < 0)
            return TC_ERR_EXECUTION;
    }
    if (tc_array_end(&arr) < 0) return TC_ERR_EXECUTION;
    const char *arrv = NULL; size_t arrl = 0;
    tc_array_value(&arr, &arrv, &arrl);
    if (!arrv) return TC_ERR_EXECUTION;

    size_t ok_len = 0, dom_len = 0, act_len = 0, np_len = 0;
    const char *okv = tc_json_raw(out, "\"ok\"", 4, &ok_len);
    const char *dom = tc_json_str(out, "tc-probe", 8, &dom_len);
    const char *act = tc_json_str(out, "params", 6, &act_len);
    const char *np  = tc_json_int(out, (long long)d->n_params, &np_len);
    if (!okv || !dom || !act || !np) return TC_ERR_EXECUTION;

    if (fw_put(&w, "status", 6, okv, ok_len) < 0) return TC_ERR_EXECUTION;
    if (fw_put(&w, "domain", 6, dom, dom_len) < 0) return TC_ERR_EXECUTION;
    if (fw_put(&w, "action", 6, act, act_len) < 0) return TC_ERR_EXECUTION;
    if (fw_put(&w, "n_params", 8, np, np_len) < 0) return TC_ERR_EXECUTION;
    if (fw_put(&w, "params", 6, arrv, arrl) < 0) return TC_ERR_EXECUTION;
    out->n_fields = w.n;
    return TC_OK;
}

static tc_err h_pray(const tc_directive *d, void *ud, tc_response *out) {
    (void)d; (void)ud;
    if (out->n_fields + 2 > out->fields_cap) return TC_ERR_EXECUTION;
    out->fields[out->n_fields].key = "pray_rst_types";
    out->fields[out->n_fields].key_len = 15;
    out->fields[out->n_fields].val = "\"picture\"";
    out->fields[out->n_fields].val_len = 9;
    out->n_fields++;
    out->fields[out->n_fields].key = "url";
    out->fields[out->n_fields].key_len = 3;
    out->fields[out->n_fields].val = "\"http://x/a.jpg\"";
    out->fields[out->n_fields].val_len = 16;
    out->n_fields++;
    return TC_OK;
}

static tc_err h_pray_text(const tc_directive *d, void *ud, tc_response *out) {
    (void)d; (void)ud;
    if (out->n_fields + 2 > out->fields_cap) return TC_ERR_EXECUTION;
    out->fields[out->n_fields].key = "pray_rst_types";
    out->fields[out->n_fields].key_len = 15;
    out->fields[out->n_fields].val = "\"text\"";
    out->fields[out->n_fields].val_len = 6;
    out->n_fields++;
    out->fields[out->n_fields].key = "result";
    out->fields[out->n_fields].key_len = 6;
    out->fields[out->n_fields].val = "1";
    out->fields[out->n_fields].val_len = 1;
    out->n_fields++;
    return TC_OK;
}

static void test_parse(void) {
    /* ---- baseline (matches vectors/parse.jsonl baseline rows) ---- */
    expect_parse("AI:tc-math;eval,2+3*4", "tc-math", "eval", "2+3*4");
    expect_parse("AI:a;b,c,d", "a", "b", "c|d");
    expect_parse("AI:a;b", "a", "b", "");
    expect_parse("AI:weather;query,\xe5\x8c\x97\xe4\xba\xac,\xe6\x98\x8e\xe5\xa4\xa9",
                 "weather", "query",
                 "\xe5\x8c\x97\xe4\xba\xac|\xe6\x98\x8e\xe5\xa4\xa9");
    expect_parse("AI:a;b,c,,d", "a", "b", "c|d");     /* empty param dropped */
    expect_parse("AI:a;b,c,", "a", "b", "c");          /* trailing comma dropped */
    expect_parse("AI:a;b, c , d ", "a", "b", "c|d");   /* trim */
    expect_parse("AI:Weather;Query,\xe5\x8c\x97\xe4\xba\xac",
                 "Weather", "Query", "\xe5\x8c\x97\xe4\xba\xac");
    expect_parse("  AI:a;b,c  ", "a", "b", "c");       /* outer pad */

    /* brace/bracket depth */
    expect_parse("AI:a;b,c,{x:1,y:2}", "a", "b", "c|{x:1,y:2}");
    expect_parse("AI:a;b,{a:{b:1,c:[1,2]}},z", "a", "b", "{a:{b:1,c:[1,2]}}|z");
    expect_parse("AI:a;b,{x:1},y", "a", "b", "{x:1}|y");
    expect_parse("AI:a;b,{x:1,y:2", "a", "b", "{x:1,y:2");  /* unbalanced stays one */
    expect_parse("AI:a;b,{x:1,[2,3]},tail", "a", "b", "{x:1,[2,3]}|tail");
    expect_parse("AI:a;b,[1,2,3],z", "a", "b", "[1,2,3]|z");
    expect_parse("AI:a;b,[{a:1},{a:2}],z", "a", "b", "[{a:1},{a:2}]|z");

    /* double quote */
    expect_parse("AI:a;b,\"x,y\",z", "a", "b", "\"x,y\"|z");
    expect_parse("AI:a;b,{text: \"has, comma\"}", "a", "b", "{text: \"has, comma\"}");

    /* errors */
    expect_parse("AI:;b,c", NULL, NULL, NULL);
    expect_parse("AI:a;,c", NULL, NULL, NULL);
    expect_parse("AI:abc", NULL, NULL, NULL);
    expect_parse("", NULL, NULL, NULL);
    expect_parse("AI:", NULL, NULL, NULL);

    printf("test_parse done (%d fails so far)\n", _fails);
}

static void test_json_helpers(void) {
    tc_field fields[TC_FIELDS_CAP];
    tc_response resp;
    char buf[1024];
    size_t blen = 0;
    size_t vlen = 0;

    /* string escaping */
    resp_init(&resp, fields, TC_FIELDS_CAP);
    const char *s = tc_json_str(&resp, "he said \"hi\" \\ ok\n", 18, &vlen);
    CHECK(s != NULL, "tc_json_str basic");
    CHECK(vlen == 24, "tc_json_str escaped length");
    CHECK(memcmp(s, "\"he said \\\"hi\\\" \\\\ ok\\n\"", 24) == 0,
          "tc_json_str escaped content");

    /* control char -> \u00xx */
    resp_init(&resp, fields, TC_FIELDS_CAP);
    {
        const char ctl[1] = { 0x01 };
        s = tc_json_str(&resp, ctl, 1, &vlen);
        CHECK(s != NULL, "tc_json_str control");
        CHECK(vlen == 8, "tc_json_str control length");
        CHECK(memcmp(s, "\"\\u0001\"", 8) == 0, "tc_json_str control content");
    }

    /* int + bool + null */
    resp_init(&resp, fields, TC_FIELDS_CAP);
    s = tc_json_int(&resp, -42, &vlen);
    CHECK(vlen == 3 && memcmp(s, "-42", 3) == 0, "tc_json_int negative");
    s = tc_json_int(&resp, 0, &vlen);
    CHECK(vlen == 1 && memcmp(s, "0", 1) == 0, "tc_json_int zero");
    s = tc_json_bool(&resp, 1, &vlen);
    CHECK(vlen == 4 && memcmp(s, "true", 4) == 0, "tc_json_bool true");
    s = tc_json_null(&resp, &vlen);
    CHECK(vlen == 4 && memcmp(s, "null", 4) == 0, "tc_json_null");

    /* array builder with mixed elements, then envelope serialize */
    {
        tc_response r2;
        resp_init(&r2, fields, TC_FIELDS_CAP);
        tc_json_array arr;
        CHECK(tc_array_begin(&arr, &r2) == 0, "array begin");
        CHECK(tc_array_str(&arr, "a", 1) == 0, "array str a");
        CHECK(tc_array_str(&arr, "b\"c", 3) == 0, "array str b");
        CHECK(tc_array_int(&arr, 7) == 0, "array int");
        CHECK(tc_array_end(&arr) == 0, "array end");
        const char *av = NULL; size_t al = 0;
        tc_array_value(&arr, &av, &al);
        CHECK(av != NULL, "array value ptr");
        CHECK(al == 14, "array value len");
        CHECK(memcmp(av, "[\"a\",\"b\\\"c\",7]", 14) == 0, "array value content");

        /* wire into a response and serialize */
        r2.type = TC_RST_TEXT;
        r2.err = TC_OK;
        r2.n_fields = 0;
        if (r2.n_fields + 1 <= r2.fields_cap) {
            r2.fields[r2.n_fields].key = "items";
            r2.fields[r2.n_fields].key_len = 5;
            r2.fields[r2.n_fields].val = av;
            r2.fields[r2.n_fields].val_len = al;
            r2.n_fields++;
        }
        CHECK(tc_envelope_serialize(&r2, buf, sizeof(buf), &blen) == TC_OK,
              "array envelope serialize");
        CHECK(strcmp(buf,
            "{\"rst_types\":\"text\",\"rst_data\":{\"items\":[\"a\",\"b\\\"c\",7]},\"rst_err\":\"\"}") == 0,
            "array envelope content");
        printf("  array envelope: %s\n", buf);
    }

    printf("test_json_helpers done (%d fails so far)\n", _fails);
}

static void test_dispatch_envelope(void) {
    static tc_registry reg_storage;
    tc_registry *reg = &reg_storage;
    tc_err ie = tc_registry_init(reg);
    CHECK(ie == TC_OK, "registry init in place");

    CHECK(tc_register(reg, "echo", "run", h_echo, NULL) == TC_OK, "register echo");
    CHECK(tc_register(reg, "pray", "pic", h_pray, NULL) == TC_OK, "register pray/pic");
    CHECK(tc_register(reg, "pray", "txt", h_pray_text, NULL) == TC_OK, "register pray/txt");
    CHECK(tc_register(reg, "tc-probe", "echo", h_probe_echo, NULL) == TC_OK,
          "register tc-probe echo");
    CHECK(tc_register(reg, "tc-probe", "params", h_probe_params, NULL) == TC_OK,
          "register tc-probe params");
    CHECK(tc_alias_add(reg, "hui-xian", "zhi-xing", "echo", "run") == TC_OK, "alias add");

    tc_field fields[TC_FIELDS_CAP];
    tc_response resp;
    char buf[2048];
    size_t blen = 0;

    /* dispatch echo */
    resp_init(&resp, fields, TC_FIELDS_CAP);
    tc_err de = tc_dispatch(reg, "AI:echo;run,a,b", strlen("AI:echo;run,a,b"), &resp);
    CHECK(de == TC_OK, "dispatch echo ok");
    tc_err se = tc_envelope_serialize(&resp, buf, sizeof(buf), &blen);
    CHECK(se == TC_OK, "serialize echo ok");
    CHECK(strcmp(buf, "{\"rst_types\":\"text\",\"rst_data\":{\"status\":\"ok\",\"n\":2},\"rst_err\":\"\"}") == 0,
          "echo envelope text match");
    printf("  echo envelope: %s\n", buf);

    /* alias resolution */
    resp_init(&resp, fields, TC_FIELDS_CAP);
    de = tc_dispatch(reg, "AI:hui-xian;zhi-xing,x", strlen("AI:hui-xian;zhi-xing,x"), &resp);
    CHECK(de == TC_OK, "dispatch alias ok");

    /* tc-probe echo with unicode + comma-in-text */
    resp_init(&resp, fields, TC_FIELDS_CAP);
    de = tc_dispatch(reg, "AI:tc-probe;echo,hello", strlen("AI:tc-probe;echo,hello"), &resp);
    CHECK(de == TC_OK, "dispatch probe echo");
    se = tc_envelope_serialize(&resp, buf, sizeof(buf), &blen);
    CHECK(se == TC_OK, "serialize probe echo");
    CHECK(strstr(buf, "\"echo\":\"hello\"") != NULL, "probe echo content");
    printf("  probe echo: %s\n", buf);

    /* tc-probe params with nested object param -> array of strings */
    resp_init(&resp, fields, TC_FIELDS_CAP);
    de = tc_dispatch(reg, "AI:tc-probe;params,{\"a\":1,\"b\":2},tail",
                     strlen("AI:tc-probe;params,{\"a\":1,\"b\":2},tail"), &resp);
    CHECK(de == TC_OK, "dispatch probe params");
    se = tc_envelope_serialize(&resp, buf, sizeof(buf), &blen);
    CHECK(se == TC_OK, "serialize probe params");
    CHECK(strstr(buf, "\"n_params\":2") != NULL, "probe params n");
    CHECK(strstr(buf, "\"params\":[\"{\\\"a\\\":1,\\\"b\\\":2}\",\"tail\"]") != NULL,
          "probe params array content");
    printf("  probe params: %s\n", buf);

    /* pray promote picture */
    resp_init(&resp, fields, TC_FIELDS_CAP);
    de = tc_dispatch(reg, "AI:pray;pic", strlen("AI:pray;pic"), &resp);
    CHECK(de == TC_OK, "dispatch pray/pic ok");
    se = tc_envelope_serialize(&resp, buf, sizeof(buf), &blen);
    CHECK(se == TC_OK, "serialize pray/pic");
    CHECK(strstr(buf, "\"rst_types\":\"picture\"") != NULL,
          "pray promoted to picture");
    CHECK(strstr(buf, "\"pray_rst_types\"") == NULL,
          "pray stripped from rst_data");
    printf("  pray envelope: %s\n", buf);

    /* pray text: stripped, type stays text */
    resp_init(&resp, fields, TC_FIELDS_CAP);
    de = tc_dispatch(reg, "AI:pray;txt", strlen("AI:pray;txt"), &resp);
    CHECK(de == TC_OK, "dispatch pray/txt ok");
    se = tc_envelope_serialize(&resp, buf, sizeof(buf), &blen);
    CHECK(se == TC_OK, "serialize pray/txt");
    CHECK(strstr(buf, "\"rst_types\":\"text\"") != NULL,
          "pray text keeps type text");
    CHECK(strstr(buf, "\"pray_rst_types\"") == NULL,
          "pray text stripped too");
    printf("  pray-text envelope: %s\n", buf);

    /* unregistered -> NOT_FOUND */
    resp_init(&resp, fields, TC_FIELDS_CAP);
    de = tc_dispatch(reg, "AI:nope;x", strlen("AI:nope;x"), &resp);
    CHECK(de == TC_ERR_NOT_FOUND, "unregistered -> NOT_FOUND");
    se = tc_envelope_serialize(&resp, buf, sizeof(buf), &blen);
    CHECK(strstr(buf, "\"rst_err\":\"ERR_NOT_FOUND\"") != NULL,
          "NOT_FOUND envelope");
    printf("  notfound envelope: %s\n", buf);

    printf("test_dispatch_envelope done (%d fails so far)\n", _fails);
}

int main(void) {
    test_parse();
    test_json_helpers();
    test_dispatch_envelope();
    if (_fails == 0) {
        printf("ALL PASS\n");
        return 0;
    }
    printf("%d FAILURES\n", _fails);
    return 1;
}
