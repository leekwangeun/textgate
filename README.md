# textgate

Check what a language model wrote against word rules before anyone reads it, and measure how often real drafts pass.

```bash
textgate try rules.toml "커피가 따뜻해"              # which forbidden patterns a sentence hits
textgate sample myapp.spec:SPEC -n 30               # N real drafts: pass rate, failures, time, tokens
textgate recheck myapp.spec:SPEC data/sample-*.jsonl # the saved drafts against today's rules, no API calls
```
