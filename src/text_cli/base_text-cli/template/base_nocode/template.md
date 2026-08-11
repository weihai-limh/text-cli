# {TITLE}

<!--
  Field labels below are in English (en).
  The parser is language-agnostic: add your language to FIELD_LABELS in
  converter_template.py and use those labels here.
  Field values (the text after ":") and body content can be in any language.
-->

## Directive
- Domain: {DOMAIN}
- Action: {ACTION}
- Triggers: {TRIGGERS}
- Params: {PARAM_1}, {PARAM_2}
- Source: {SOURCE}                  # Optional — where this knowledge comes from
- Verified: {VERIFIED}              # Optional — who verified, YYYY-MM-DD
- Stale After: {STALE_AFTER}        # Optional — freshness deadline, YYYY-MM-DD
- Status: {STATUS}                  # Optional — draft | stable | deprecated

## Knowledge
<!--
  Content fields below are convention, not parsed. Use your own language.
-->

### {CATEGORY_1}
#### {SUB_1}
- Cause: ...
- Treatment: ...
- Prevention: ...
- Differential: ...                 # Optional — how to distinguish from similar issues
- Lessons: ...                      # Optional — hard-earned lessons

### {CATEGORY_2}
#### {SUB_2}
- Cause: ...
- Treatment: ...
- Prevention: ...
- Differential: ...
- Lessons: ...

---
> {FOOTER}
