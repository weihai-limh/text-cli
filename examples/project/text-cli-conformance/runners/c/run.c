/* run.c -- C core parser runner for the conformance drift mirror.
 *
 * Contract: read prompts line by line from stdin (blank line = empty prompt),
 * write one JSON line per prompt to stdout:
 *   {"domain":..,"action":..,"params":[..]}  on success
 *   {"error":"INVALID_PARAMS"}               on parse error
 * Stop at EOF.
 *
 * Build (from conformance/):
 *   gcc -std=c99 -I../include runners/c/run.c ../src/text_cli_core.c -o runners/c/run
 */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "text_cli_core.h"

#define LINE_CAP 4096

static void emit_str(const char *s, size_t n) {
    putchar('"');
    for (size_t i = 0; i < n; i++) {
        unsigned char c = (unsigned char)s[i];
        switch (c) {
        case '"':  fputs("\\\"", stdout); break;
        case '\\': fputs("\\\\", stdout); break;
        case '\n': fputs("\\n", stdout); break;
        case '\r': fputs("\\r", stdout); break;
        case '\t': fputs("\\t", stdout); break;
        default:
            if (c < 0x20) {
                printf("\\u%04x", c);
            } else {
                putchar((char)c);
            }
        }
    }
    putchar('"');
}

static void handle(const char *prompt, size_t len) {
    tc_directive d;
    tc_err e = tc_parse(prompt, len, &d);
    if (e != TC_OK) {
        fputs("{\"error\":\"INVALID_PARAMS\"}", stdout);
        putchar('\n');
        return;
    }
    fputs("{\"domain\":", stdout);
    emit_str(d.domain, d.domain_len);
    fputs(",\"action\":", stdout);
    emit_str(d.action, d.action_len);
    fputs(",\"params\":[", stdout);
    for (int i = 0; i < d.n_params; i++) {
        if (i > 0) putchar(',');
        emit_str(d.params[i], d.param_lens[i]);
    }
    fputs("]}", stdout);
    putchar('\n');
    fflush(stdout);
}

int main(void) {
    char *line = malloc(LINE_CAP);
    if (!line) return 1;
    while (fgets(line, LINE_CAP, stdin)) {
        size_t len = strlen(line);
        while (len > 0 && (line[len - 1] == '\n' || line[len - 1] == '\r')) {
            line[len - 1] = '\0';
            len--;
        }
        handle(line, len);
    }
    free(line);
    return 0;
}
