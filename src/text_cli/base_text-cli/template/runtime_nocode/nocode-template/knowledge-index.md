# Knowledge Index

Format: each line maps a knowledge file to its key symptoms.
AI uses this for semantic matching to find the right document.

```
{file-name-1}.md  ← {symptom-keywords-1}
{file-name-2}.md  ← {symptom-keywords-2}
NOMATCH           ← none of the above matches
```

## Example (from nocode-example-zh)

```
aphids.md    ← tiny bugs on tender shoots, leaves curling, sticky honeydew
root-rot.md  ← leaves yellow from bottom up, stem turns black, soil smells rotten
NOMATCH      ← none of the above matches
```
