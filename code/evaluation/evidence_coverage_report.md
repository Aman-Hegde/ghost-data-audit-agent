# Phase 2 evidence coverage

Generated deterministically from `dataset/evidence_files.csv`; no predictions or policy decisions are produced.

## Coverage

- Manifest files: 94
- Parsed files: 94
- Unresolved files: 0
- Parser errors: 0
- Observations before deduplication: 3931
- Usable observations: 3931
- Exact duplicate observations removed: 0

## Artifact types

- `.json`: 28
- `.log`: 26
- `.pdf`: 4
- `.png`: 11
- `.sql`: 24
- `.txt`: 1

## Unresolved and warnings

Unresolved evidence IDs: none.

- `evidence_09` `IDENTIFIER_NOT_IN_IDENTITY_GRAPH`: unmatched visible identifiers for search_1874: ['g.silva76.jr@gmail.com']
- `evidence_60` `IDENTIFIER_NOT_IN_IDENTITY_GRAPH`: unmatched visible identifiers for marketing_001: ['sj.park@naver.com']

## Dependencies and model usage

- PDF: `pypdf==6.13.3` (embedded text; page-level provenance).
- PNG validation: `Pillow==12.2.0`.
- Screenshot extraction cache provenance: provider `OpenAI`, model `gpt-5.6-sol`.
- Runtime model calls: 0; input tokens: 0; output tokens: 0; estimated cost: $0.00.
- The development harness did not expose token metering, so no token count is invented; cached facts are keyed by exact SHA-256.

## Interpretation limits

- Two screenshot identifiers are visible but absent from the identity graph; they remain warnings and are not linked to a user.
- Embedded PDF narrative is typed as historical/document evidence and cannot automatically prove a database's current state.
- Cache misses or identity conflicts are explicit unresolved artifacts; runtime vision fallback is not configured.
- Absence from a partial snapshot is never synthesized as an ABSENT observation.
