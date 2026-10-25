# Evidence interpretation and model-call policy

The submitted runtime uses deterministic Python and makes no language-model or
vision-model calls.

Structured JSON, SQL, logs, text files, and embedded PDF text are parsed by the
adapters under `audit_agent/parsers/`. Narrative document text is retained as
documented or historical evidence and is not automatically promoted to live database
state. Operation results remain claims until supported by state evidence.

The 11 participant screenshots use the versioned cache at
`audit_agent/extraction_cache/image_extractions.json`. Each entry is selected only by
the SHA-256 hash of the exact PNG bytes. Cached observations include the resource,
system, category, state, timestamp, visible identifiers, attributes, and UI locator.
Identifiers are checked against the identity graph; conflicting-user screenshots are
unresolved. A missing or changed image has no fallback inference path and is reported
as unresolved rather than guessed.

The cache metadata records development-time visual-review provenance as provider
`OpenAI`, model `gpt-5.6-sol`. Development token metering was unavailable. The final
518-request run reused the cache with zero runtime model calls, tokens, or cost.

Request intent uses conservative multilingual rules in `audit_agent/intent.py`.
There is an adjudicator interface for ambiguous language, but the submitted runtime
does not call an external model and never silently promotes ambiguity to deletion.
