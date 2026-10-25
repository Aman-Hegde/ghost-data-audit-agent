# Final full-run model and token usage

This report describes the final 518-request run that generated root `output.csv` on 2026-10-25.

## Runtime inference

| Provider | Model | Calls | Input tokens | Output tokens | Total tokens | Estimated cost |
|---|---|---:|---:|---:|---:|---:|
| None | None — deterministic Python | 0 | 0 | 0 | 0 | $0.00 |

- Requests processed: 518
- Total runtime model calls: 0
- Total runtime input tokens: 0
- Total runtime output tokens: 0
- Total runtime tokens: 0
- Average runtime tokens per request: 0.00
- Estimated total runtime inference cost: $0.00
- Estimated runtime cost per request: $0.000000

Identity reconstruction, intent rules, evidence parsing, relationship extraction,
temporal reasoning, policy assessment, planning, validation, and serialization all ran
locally in deterministic Python. Structured evidence did not use a model.

## Development-time screenshot cache

The 11 supplied PNG screenshots use exact-SHA-256 entries in
`audit_agent/extraction_cache/image_extractions.json`. The cache records provider
`OpenAI` and model `gpt-5.6-sol`, with method `content_hash_cache:reviewed_vision`.
These interpretations were created during development and were reused by the final
run; the final runtime made no fresh model or vision calls.

Development-time token metering was not exposed by the harness, so input tokens,
output tokens, total tokens, and development cost are **unavailable**. They are not
reported as zero and no estimate is invented. The cache is packaged as a required,
versioned code asset. Hash mismatches, missing entries, or identity conflicts produce
explicit unresolved evidence rather than automatic model calls.
