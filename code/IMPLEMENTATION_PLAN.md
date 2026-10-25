# Ghost Data Still Exists — Investigation and Implementation Plan

## 1. Scope and non-goals for this phase

This plan is based only on participant-facing repository files: the root instructions and documentation, every CSV under `dataset/`, and every file listed by `dataset/evidence_files.csv`. No organizer-only files were inspected or used.

This phase intentionally does **not** implement the audit engine and does **not** create the submission `output.csv`. The eventual implementation must be generic: it must derive answers from identity, policy, activity, timestamps, and evidence content rather than sample labels, case IDs, resource-name shortcuts, or repeated dataset-generation patterns.

## 2. Repository contract discovered

The submission engine must:

1. Read participant data relative to the repository root.
2. audit exactly the 518 cases in `dataset/deletion_requests.csv`;
3. decide whether the text authorizes deletion before doing destructive-policy reasoning;
4. resolve current and historical identifiers;
5. reconstruct evidence state at each case's `audit_at` cutoff;
6. treat workflow/activity results as claims, not state proof;
7. apply `deletion_rules.csv` without deleting required retained records;
8. emit exactly `case_id,deletion_status,steps_json`, with valid operations/states and deterministic sequence order; and
9. write the final file at repository-root `output.csv` only when the implementation phase is approved.

The required status values are `COMPLETE`, `INCOMPLETE`, and `NOT_APPLICABLE`. A non-deletion request must produce `NOT_APPLICABLE` and `[]`. A complete deletion has evidence-backed verification steps only. An incomplete deletion has evidence-backed findings, then future remediation and future verification steps with empty evidence IDs.

## 3. Dataset structure and scale

### 3.1 Participant CSVs

| File | Rows | Size | Schema / important observations |
|---|---:|---:|---|
| `deletion_requests.csv` | 518 | 164,183 B | `case_id,email,requested_at,reported_status,reported_at,audit_at,request_text`; IDs cover `case_33` through `case_550`; 517 unique emails; request times span 2026-01-05 to 2026-09-24; audit cutoffs span 2026-01-29 to 2026-10-01. |
| `sample_deletion_requests.csv` | 32 | 9,043 B | Same schema; 32 unique subjects and texts; requests include English, Spanish, French, and Japanese examples, historical-email requests, backups, sync, shared support context, and tombstones. |
| `sample_output.csv` | 32 | 38,681 B | `case_id,deletion_status,steps_json`; 10 `COMPLETE`, 22 `INCOMPLETE`, no public `NOT_APPLICABLE`; 193 total canonical steps. |
| `user_identities.csv` | 850 | 127,262 B | `user_id,name,email,phone,email_hash,updated_at`; all stable IDs/emails/phones/hashes unique; three duplicated names; snapshots span 2023-06-22 to 2026-08-30. |
| `user_audit_log.csv` | 306 | 37,016 B | `audit_id,user_id,event_time,field_name,old_value,new_value`; 107 email, 107 email-hash, and 92 phone changes across 196 users; 91 users have one event, 102 have two, and three have three or four. |
| `system_activity.csv` | 4,011 | 661,372 B | Global events with 17 event types, 11 source systems, 19 target systems, and results `SUCCESS`/`FAILED`/`PARTIAL`; resource IDs are not always unique across time. |
| `deletion_rules.csv` | 15 | 1,055 B | One rule per data category; 7 `DELETE`, 3 `REDACT`, 2 `ANONYMIZE`, and 3 `RETAIN`. |
| `evidence_files.csv` | 94 | 11,184 B | `file_id,file_path,origin,captured_at`; all paths exist and all evidence files are manifested. Capture times span 2026-01-29 through 2026-10-01. |
| `output.csv` | 0 | 36 B | Blank header-only template; it must remain untouched during this phase. |

Reported workflow status is weakly correlated with truth in the public set: 11 of 17 sample rows reported `COMPLETE` are actually `INCOMPLETE`; three `NOT_STARTED` cases are actually complete. The engine must never promote `reported_status` or an activity `reported_result` into proof.

Identity resolution is deliberately important:

- all 32 sample request emails resolve, but three resolve only through historical email audit entries;
- all 518 evaluation requests resolve, with 418 current-email and 100 historical-email matches;
- the evaluation set represents 517 unique users because one email appears in two separate cases;
- current identity snapshots are at or before all relevant audit cutoffs, but reconstruction should still be time-aware for hidden variants.

### 3.2 Evidence corpus

There are exactly 94 evidence files totaling 2,948,268 bytes. There are no unmanifested files and no missing manifest targets.

| Type | Count | Total bytes | Size range | Capture range | Parsing requirement |
|---|---:|---:|---:|---|---|
| JSON | 28 | 331,815 | 848–25,927 B | 2026-01-29 to 2026-10-01 | Standard JSON plus nested snapshot bundles and per-service exports. |
| Logs | 26 | 516,200 | 548–94,823 B | 2026-02-03 to 2026-09-30 | Multiple text log grammars: key/value, pipe-separated, bracketed application logs, RFC5424-like syslog, cloud-runtime wrappers, and timestamp followed by embedded JSON. |
| SQL | 24 | 334,058 | 838–36,128 B | 2026-02-08 to 2026-09-21 | Execute safely in in-memory SQLite; inspect primary, read, reporting, regional, and failover replicas; parse nested `record_json`. |
| PNG | 11 | 1,499,214 | 121,101–155,587 B | 2026-02-13 to 2026-09-26 | Screenshot/OCR or vision extraction with spatial context, selected rows, side panels, query/filter text, and UI capture time. |
| PDF | 4 | 262,447 | 64,847–66,039 B | 2026-05-29 to 2026-09-12 | Text extraction is available for these PDFs; retain page/location provenance and support an OCR/vision fallback for hidden scanned PDFs. |
| TXT | 1 | 4,534 | 4,534 B | 2026-10-01 | Line-oriented handover report with timestamp, system, resource, category, lookup result, and subject identifier. |

Evidence families and notable structures:

- Twelve records-assurance snapshot bundles contain named collections such as customer profiles, search documents, analytics reports, support conversations/attachments, connectors, backups, exports, security events, retained orders, and deleted-customer references.
- Eleven service-resource exports contain point-in-time service readbacks. Their nested shapes differ by service (`profile_lookups`, `profiles`, `restore_entries`, `exports`, `connectors`, `index_queries`, audit records, and support records). They directly express states such as 404/not found, null identifiers, enabled flags, restore permissions, and search hits.
- SQL snapshots fall into two designs:
  - normalized inventory tables for profiles, search documents, analytics, support, exports, connectors, backups, security records, and `snapshot_scope`;
  - generic primary/replica tables with `resource_id`, `origin_system`, `collection_name`, JSON payload, and `updated_at`.
- Replica evidence includes read replicas, two regional replicas, reporting replicas, a failover replica, and a dedicated account failover comparison. Logical system identity must be separated from physical replica/table identity.
- Central logs are semantically similar but syntactically heterogeneous. Point-readback logs use two-line request/result patterns and must be joined using trace/resource fields rather than line adjacency alone.
- PDFs cover an account/order statement, a legal-retention register, a security-retention extract, and a support attachment. A document can prove either prohibited PII, a required retained record, or only contextual linkage; document type alone is not a verdict.
- Screenshots cover account, analytics, backup, connector, export, tombstone/reference, marketing, object storage, search, security, and support systems. UI state must be extracted, not inferred from filenames.

The manifest `captured_at` is the outer temporal gate. Internal `observed_at`, `updated_at`, event timestamps, document dates, and snapshot-scope times should also be preserved. A file captured after `audit_at` must be excluded even if it describes an older event; a file captured before the cutoff may contain older claims that have been superseded by later eligible state observations.

## 4. Canonical sample-output analysis

### 4.1 Format and evidence behavior

Every step has exactly:

`step_no`, `phase`, `system_id`, `resource_id`, `operation`, `state`, `evidence_id`.

Object key order and JSON whitespace do not matter; array order does. Step numbers are consecutive from one. The public canonical set contains:

- 41 findings, 41 remediation steps, and 111 verification steps;
- findings and complete-case verifications with non-empty participant-visible `file_id` evidence;
- all remediation and incomplete-case future verification steps with `evidence_id=""`;
- no finding/remediation steps for complete cases;
- verification for both changed resources and required final-state dependencies (for example, account absence and retained security records even when those were not the violation).

Allowed operation ordering observed in samples matches the problem statement, not alphabetical sorting:

1. findings: remaining record, exposed PII, active data flow, restore risk;
2. remediation: disable flow, block restore, delete, redact, anonymize;
3. verification: absent, present, redacted, anonymized, flow disabled, restore blocked.

Within the same phase and operation, order by `system_id` and then `resource_id`. The serializer should use explicit rank tables, never enum/alphabetical order.

### 4.2 Sample case families

The 32 public cases exercise these behaviors:

- clean account absence despite `COMPLETE`, `PARTIALLY_COMPLETE`, or `NOT_STARTED` claims;
- a profile still present after reported completion;
- residual search, export, support attachment, support conversation, and analytics records;
- historical-email linkage to records that no longer display the current email;
- active connectors capable of repopulating downstream stores;
- restorable backup archives that are retained but must be blocked from restoring the subject;
- security audit records that policy requires to remain;
- analytics records that must be anonymized rather than deleted;
- shared support conversations that must be redacted, while subject-only attachments are deleted;
- stale read/replica state disagreeing with a primary source;
- a compliant tombstone that retains only `user_id`, versus a tombstone exposing direct identifiers;
- multilingual and indirect but still deletion-authorizing request language;
- decoy/similar emails that must not be conflated with the subject;
- temporal wording requiring the state at the specified audit cutoff rather than the newest available evidence.

The sample demonstrates that verification scope is policy-driven, not just finding-driven. For example, incomplete rows commonly verify the account is absent and a security record remains even when the only finding is a search, backup, support, or connector problem.

## 5. Policy interpretation

The rules should compile into executable predicates and actions rather than be scattered through case code.

| Category | Condition | Required action | Violation and output mapping |
|---|---|---|---|
| `USER_PROFILE` | Always | `DELETE` | Present → `REPORT_REMAINING_RECORD`, `DELETE_RECORD`, then `VERIFY_RECORD_ABSENT`; absent → verify absent. |
| `SECONDARY_IDENTIFIER` | Always | `DELETE` | Same mapping; covers identity copies distinct from the main profile. |
| `SEARCH_INDEX_ENTRY` | Always | `DELETE` | Any matched document is a remaining record, including historical identifier hits and stale replicas. |
| `CACHE_ENTRY` | Always | `DELETE` | Present cache entry must be deleted; absence must be verified where scoped evidence exists. |
| `SUPPORT_MESSAGE` | Shared customer/agent/order context must remain | `REDACT` | Direct identifiers exposed → `REPORT_EXPOSED_PII`, redact, verify redacted; retain non-identifying shared context. |
| `SUPPORT_ATTACHMENT` | Belongs only to subject | `DELETE` | Attachment must be removed in full; do not confuse the containing shared conversation with the attachment. |
| `ANALYTICS_PROFILE` | Still attributable | `ANONYMIZE` | Link through user ID, email/hash/phone, or other reversible identity → exposed PII, anonymize, verify anonymous. |
| `PRODUCT_TELEMETRY` | Still attributable | `ANONYMIZE` | Same semantic test as analytics, including indirect stable links. |
| `USER_EXPORT` | Always | `DELETE` | Delete both metadata/resource and downloadable object when represented as distinct resources. |
| `MARKETING_PROFILE` | Always | `DELETE` | Marketing opt-out alone is not account deletion, but an authorized deletion requires profile removal. |
| `EMAIL_DELIVERY_LOG` | Contains user email | `REDACT` | Preserve permitted log structure while removing email and other fields required by policy. |
| `SECURITY_AUDIT_LOG` | Within supplied retention period | `RETAIN` | Required existing record → `VERIFY_RECORD_PRESENT`; do not delete merely because it links by stable user ID. |
| `LEGAL_HOLD_RECORD` | Supplied hold active | `RETAIN` | Preserve and verify present while active. |
| `BACKUP_ARCHIVE` | Restore access can be blocked | `RETAIN` | Preserve archive, but allowed restore is `REPORT_RESTORE_RISK`; block restore and verify blocked. Public samples do not add a separate present verification for the archive. |
| `ACCOUNT_TOMBSTONE` | Deleted account needs stable `user_id` reference | `REDACT` | Stable internal subject reference and deleted status may remain; name, email, phone, email hash, and other direct identifiers must be null/removed. |

Two required process types are specified by the challenge but are not standalone rows in `deletion_rules.csv`:

- an enabled sync/import/connector is an active data flow: report, disable before dependent record changes, and verify disabled;
- a restore-capable backup is a restore risk: report and block before dependent record changes, then verify blocked.

`RETAIN` does not mean “ignore.” A complete deletion requires retained records to remain available, and those records need positive verification. Conversely, retention does not authorize retaining direct identifiers beyond the category's permitted content.

## 6. Hard edge cases and accuracy risks

1. **Historical identity chains.** Email, email hash, and phone changes can occur together or separately. Matching only the request email misses old copies; matching substrings can join a decoy. Build a stable-user identity graph with exact normalized values and provenance.
2. **Ambiguous intent.** Evaluation requests include clear non-deletion actions such as correction, access/export, login help, marketing-only opt-out, invoice copies, and email changes. Words like “remove” are not enough. Explicit scope and negation must win.
3. **Multilingual intent and encoding.** Inputs include multilingual text, and terminal displays reveal mojibake when decoded/displayed incorrectly. Read CSV as UTF-8 with BOM support and keep Unicode intact.
4. **Reported status/result leakage.** `COMPLETE` and `SUCCESS` are claims. Only state-bearing observations establish present/absent/redacted/anonymized/disabled/blocked state.
5. **Stale replicas.** A primary can be empty while a regional/read/reporting/failover copy still contains the record. Every physical copy is relevant, but output `system_id` generally uses the logical owning system.
6. **Contradictory observations over time.** Later eligible state evidence supersedes earlier observations for the same physical resource only when the evidence scope is comparable. A deletion event does not supersede a later “found” readback.
7. **Evidence after `audit_at`.** Later captures cannot change the historical answer. Both manifest time and internal observation time need validation.
8. **Absence proof.** A resource not mentioned in a partial export is not automatically absent. Absence requires a scoped 404/not-found/readback, a complete snapshot scope, or another explicit negative observation.
9. **Tombstones.** A stable `user_id` is permitted and sometimes required; direct identifiers are not. Treating any stable reference as PII exposure would incorrectly delete compliant tombstones and break retained-record references.
10. **Retention.** Security and legal records can be correctly present. An engine biased toward deletion will score badly and violate policy.
11. **Backups and restores.** The archive remains by policy, but restore permission must be blocked. A later restore can repopulate a downstream record, so state reconstruction must include restore events plus subsequent evidence.
12. **Active synchronization.** Delete downstream copies only after disabling the process that can recreate them. Public outputs require flow remediation before record deletion.
13. **Shared versus subject-only support data.** A shared conversation is redacted; a subject-owned attachment is deleted. Resource type and contextual condition both matter.
14. **Nested/unstructured PII.** Identifiers can appear in JSON strings, SQL `record_json`, PDF text, log fields, screenshots, message bodies, or object metadata.
15. **Hash matching.** Use supplied current/historical hashes and a documented normalized-email SHA-256 fallback only when validated; never assume every opaque hash uses the same normalization.
16. **Duplicate cases for one subject.** The same subject can have multiple cases with different cutoffs. Cache parsing, not final decisions; evaluate state independently at each `audit_at`.
17. **Resource/event reuse.** Some activity resource IDs have multiple events. Do not collapse activity by resource without timestamp and event semantics.
18. **Ordering exactness.** A semantically correct set in the wrong sequence loses sequence credit. Centralize canonical ordering and renumber only after final sort.
19. **Over-broad evidence citation.** Cite the exact `file_id`, `activity_id`, or `audit_id` that establishes the finding. Do not cite a manifest row, filename, or unrelated workflow event.
20. **AI extraction uncertainty.** OCR/vision or language-model output must not silently become fact. Validate identifiers, resource IDs, states, and timestamps against deterministic schemas and retain confidence/review metadata.

## 7. Proposed architecture

Use deterministic Python for ingestion, identity resolution, temporal reasoning, policy, planning, validation, serialization, and metrics. Use AI only for evidence that deterministic parsers cannot reliably structure, principally screenshots, scanned documents, and genuinely ambiguous request intent.

### 7.1 Pipeline

1. **Load and validate inputs.** Validate headers, unique IDs, timestamp syntax, allowed status/event values, manifest path containment, and evidence-file existence.
2. **Compile rules.** Convert each policy row into a category predicate, required terminal state, finding/remediation/verification mapping, and retention condition.
3. **Build identity graphs.** For each `user_id`, build current plus historical exact values for names, emails, email hashes, and phones. Record source (`identity snapshot` or `audit_id`) and effective time.
4. **Classify intent.** Apply deterministic high-precision multilingual patterns and negation/scope rules. Send only unresolved texts to a schema-constrained AI classifier. Cache by normalized-text hash.
5. **Parse evidence once.** Dispatch by MIME/extension, create normalized observations, and preserve source `file_id`, capture time, internal time, physical store/replica, logical system, resource, category, state, matched identifiers, and raw-location pointer.
6. **Index global activity.** Keep activity as claims/process edges. Use it for resource discovery and event chronology, but require state evidence for record-state conclusions.
7. **Link evidence to subjects.** Match exact user ID, exact current/historical identifiers, hashes, explicit data-catalog links, and resource relationships. Require a grounded path from observation to subject; score but do not accept fuzzy email/name matches.
8. **Apply each case cutoff.** Exclude evidence whose manifest capture is after `audit_at`; exclude internal observations after cutoff; derive the latest comparable state per physical resource without erasing contradictory replica state.
9. **Build a resource/process graph.** Nodes are logical records, physical copies, flows, backups, and retained records. Edges capture sync source/destination, backup restore target, attachment/container, export/object, replica-of, and stable-reference relationships.
10. **Evaluate policy.** Determine compliant, violating, unknown, or out-of-scope status per relevant node. Unknown must not be asserted as complete.
11. **Determine deletion status.** `NOT_APPLICABLE` for non-deletion intent; otherwise `INCOMPLETE` if any policy violation, active recreation path, restore risk, or missing required proof exists; `COMPLETE` only when all scoped requirements have positive evidence.
12. **Plan steps.** Generate findings from violations, remediation from rule mappings and dependencies, and verification from required terminal states. Topologically enforce process controls before record mutations and downstream copies before source records where dependency requires it.
13. **Canonicalize and validate.** Sort by explicit phase/operation ranks then system/resource, assign consecutive step numbers, enforce exact fields and operation/state pairs, validate evidence cutoffs and IDs, and serialize deterministically.

### 7.2 Normalized internal models

Use typed dataclasses or frozen models, for example:

- `Case`: request fields and parsed UTC timestamps;
- `IdentityValue`: user, kind, normalized/raw value, valid interval, provenance;
- `EvidenceArtifact`: manifest metadata, digest, parser version;
- `Observation`: logical/physical system, resource, category, state, attributes, observed/captured time, evidence ID, raw locator, parser confidence;
- `ActivityClaim`: activity row plus semantic type and dependency edges;
- `PolicyRule`: condition predicate and target terminal state;
- `ResourceAssessment`: applicable rule, evidence trail, state at cutoff, compliance result;
- `Step`: exact seven-field output contract;
- `UsageEvent`: provider/model, request hash, tokens, cost, cache status, latency, and purpose.

Do not discard provenance during normalization. The final step should be traceable back to one evidence observation and its source location.

### 7.3 Parser strategy

- CSV: standard-library `csv`, strict headers, UTF-8-SIG.
- timestamps: timezone-aware `datetime`; reject naive timestamps.
- JSON: family-specific adapters plus a safe generic walker for exact identifiers.
- SQL: execute a copy of the text in an in-memory `sqlite3` connection; enumerate schema; parse JSON columns; never write to dataset files.
- logs/TXT: grammar registry with named regex/token parsers; parse embedded JSON after its timestamp prefix; join multi-line request/results by trace/resource.
- PDFs: `pypdf` text extraction with page numbers; AI/vision fallback only when extracted text is empty or structurally inadequate.
- PNG: schema-constrained multimodal extraction for visible resource IDs, identifiers, state, capture/query context, and table/side-panel relationships. Validate extracted tokens against deterministic identity/resource indexes.

### 7.4 Targeted AI assistance

Runtime LLM calls are not needed per request. Preferred usage:

- zero calls for CSV, JSON, SQL, and parsable logs;
- at most one cached extraction call per unique screenshot or non-text PDF;
- batch only unique ambiguous intent texts, not 518 case rows;
- optional adjudication only when deterministic evidence linking remains ambiguous, never to invent evidence or decide from reported status.

Every AI call must use a strict JSON schema, temperature zero where supported, a versioned prompt, and explicit instructions to return only visible facts. Reject output containing unknown evidence IDs/resources or times beyond the artifact. The deterministic engine remains the final authority.

## 8. Proposed Python project layout

```text
code/
  README.md
  requirements.txt
  main.py
  audit_agent/
    __init__.py
    config.py
    models.py
    loaders.py
    identity.py
    intent.py
    policy.py
    temporal.py
    linking.py
    reasoning.py
    planning.py
    ordering.py
    validation.py
    serialization.py
    usage.py
    cache.py
    parsers/
      __init__.py
      json_parser.py
      sql_parser.py
      log_parser.py
      text_parser.py
      pdf_parser.py
      image_parser.py
    ai/
      __init__.py
      client.py
      schemas.py
      prompts.py
  evaluation/
    main.py
    metrics.py
    custom_cases.py
    evaluation_report.md
    usage_report.md
  tests/
    test_identity.py
    test_intent.py
    test_temporal.py
    test_policy.py
    test_parsers.py
    test_linking.py
    test_planning.py
    test_ordering.py
    test_validation.py
    test_samples.py
```

Keep dependencies small and Windows/Python 3.11 compatible:

- required: `pypdf` for cross-platform PDF text extraction;
- optional AI path: the selected provider's official SDK (for example `openai`) and `Pillow` for image validation/metadata;
- development: `pytest`, optionally `pytest-cov`;
- avoid pandas, an ORM, a vector database, or a workflow framework unless profiling shows a concrete need.

The standard library covers CSV, JSON, SQLite, hashing, regex, dataclasses, paths, logging, and timestamps.

## 9. Caching and reproducibility

Use a repository-local runtime cache outside submission outputs, configurable through an environment variable and safe to delete. Never cache final case labels.

Cache keys must include:

- SHA-256 of exact evidence bytes or normalized request text;
- parser/prompt schema version;
- model provider and exact model name for AI artifacts;
- extraction settings.

Cache values should contain normalized observations, provenance, validation status, and usage metadata. Writes should be atomic (`temporary file` then replace) and guarded against partial/corrupt entries. Sort all input traversals and output collections explicitly. Pin dependency versions for the final run and record Python/platform versions and input manifest digests in evaluation reports.

## 10. Sample evaluation workflow

1. Run the same production pipeline against `sample_deletion_requests.csv`; do not add sample-only logic.
2. Parse canonical and predicted `steps_json`; validate schema independently before scoring.
3. Report at least these metrics:
   - **status accuracy:** exact `deletion_status` matches / 32;
   - **exact-row accuracy:** status and entire ordered normalized step array match / 32;
   - **step precision/recall/F1:** exact step signatures over `(phase, system_id, resource_id, operation, state, evidence_id)`, with duplicate-safe multiset matching; report both macro and micro values;
   - **field-level accuracy:** correct fields over the union of matched, missing, and extra step slots; score all seven fields and report per-field results, treating missing/extra steps as incorrect fields rather than silently dropping them;
   - **sequence accuracy:** fraction of cases whose exact step signature sequence matches after JSON normalization; also report LCS-based sequence similarity as a diagnostic, not a replacement for exact sequence accuracy;
   - **contract checks:** valid JSON, exact fields, legal phase/operation/state pairs, consecutive numbering, evidence existence/cutoff, empty future evidence IDs, and canonical sorting.
4. Produce a per-case diff showing status mismatch, missing/extra steps, first sequence divergence, and field mismatches.
5. Stratify results by case family: current/historical identity, structured/unstructured evidence, replica drift, flows, backups, retained records, support redaction, analytics anonymization, tombstones, and multilingual intent.
6. Add at least three synthetic unit-level cases that do not copy sample labels: an explicit non-deletion request, a later evidence item excluded by cutoff, and a compliant tombstone plus retained record. Additional high-value cases are contradictory replicas and an enabled flow recreating a deleted search record.
7. Use failures to improve generic parsers/rules only. Never branch on sample case IDs, expected statuses, or resource IDs.

The public baseline targets should be 32/32 status accuracy, exact canonical step content, 100% legal schema, and 100% exact sequence before the 518-case run.

## 11. Testing strategy

- Unit-test Unicode normalization, email case-folding, phone normalization, hash linkage, audit-chain reconstruction, and valid intervals.
- Table-test deletion versus access/correction/export/marketing-only intent, including negation and multilingual phrases.
- Fixture-test every observed JSON family, SQL table family, and log grammar with small synthetic data, not copied answer labels.
- Test temporal boundaries at strictly before, equal to, and strictly after `audit_at`.
- Test that a successful delete event alone cannot prove absence.
- Test primary/replica disagreement and prevent one physical observation from erasing another.
- Table-test all 15 policy rows and the two process controls.
- Test tombstones with only stable user ID, with each prohibited PII field, and with no stable reference.
- Property-test ordering/idempotence: shuffled inputs must produce byte-identical `steps_json`.
- Validate that findings cite real eligible evidence and future steps have empty evidence.
- End-to-end test all 32 samples without exposing canonical answers to production modules.
- Smoke-test a clean run from a path containing spaces on Windows and Python 3.11.

## 12. Token usage and cost accounting

Wrap every model call in one provider-neutral client that records:

- UTC timestamp, purpose (`intent`, `image`, `document`, or `adjudication`);
- exact provider and model identifier;
- prompt/schema version and non-sensitive request digest;
- input, cached-input (if supplied), output, reasoning, and total tokens when the API exposes them;
- cache hit/miss, latency, and retry count;
- unit prices used and estimated cost.

Pricing must be configuration with a recorded effective date, not hardcoded as timeless truth. Aggregate per model and overall: call counts, input/output tokens, total/average tokens per audited request, total/per-request cost, and cache savings. The final `code/evaluation/usage_report.md` must describe the full run that actually generated `output.csv`; dry runs and failed calls should be separated but disclosed.

## 13. Implementation milestones and acceptance gates

1. **Foundation and contracts** — loaders, typed models, timestamp handling, schema validation, deterministic configuration. Gate: all participant CSVs load and validate on Windows/Python 3.11.
2. **Identity and intent** — historical identity graph and deterministic/AI-fallback intent classifier. Gate: 32 sample subjects resolve and explicit non-deletion fixtures return `NOT_APPLICABLE`.
3. **Structured evidence ingestion** — JSON, SQL, logs, and TXT adapters with normalized provenance. Gate: all 79 structured/text artifacts parse without unhandled errors and every observation points to a manifest ID.
4. **Document and image extraction** — PDF extraction and cached vision path. Gate: all 15 PDF/PNG artifacts yield validated structured facts or an explicit review/error state; no hallucinated IDs.
5. **Temporal linking and state engine** — cutoff filtering, physical-copy tracking, evidence precedence, and resource graph. Gate: boundary and stale-replica tests pass.
6. **Policy and planner** — compile rules, assess compliance, generate dependency-safe steps, canonical ordering. Gate: all operation/state combinations and policy fixtures pass.
7. **Public evaluation loop** — run 32 samples, generate reproducible metric/diff report, fix only generic defects. Gate: target exact status and sequence accuracy with zero contract violations.
8. **Full run readiness** — caching, usage accounting, CLI, error handling, README, and clean-run test. Gate: dry-run validates 518 unique case rows without writing final output until explicitly approved.
9. **Approved final generation and packaging** — only after user approval, generate root `output.csv`, populate reports, inspect package contents, and exclude dataset/caches/secrets.

## 14. Ambiguities to resolve or encode explicitly before implementation

1. **Case sort semantics:** `case_33`–`case_550` are not zero-padded. “Sort by `case_id`” could mean lexical order or natural numeric suffix order; the source file uses numeric order. Proposed default is natural numeric order, documented and tested, unless organizer clarification says lexical.
2. **Missing retained record:** required actions contain no create/restore operation. If an in-retention security/legal record is absent, the allowed output vocabulary cannot remediate it. The dataset may guarantee this cannot occur; otherwise an official interpretation is needed.
3. **Backup verification:** public canonical cases verify `VERIFY_RESTORE_BLOCKED` but not separate `VERIFY_RECORD_PRESENT` for retained backup archives. Treat this as a category-specific rule unless clarified otherwise.
4. **Evidence captured after cutoff:** the written contract says never cite an evidence item captured after `audit_at`; therefore a later file containing an older observation should be excluded wholesale. This should be confirmed because an event-time-only interpretation would differ.
5. **Conflicting equal-time evidence:** no explicit precedence is defined among direct service readback, complete snapshot, UI screenshot, and replicas at the same timestamp. Proposed behavior is to preserve physical copies separately and prefer direct state evidence only within the same physical scope.
6. **Completeness of snapshot scope:** absence from a snapshot should count only when the artifact explicitly establishes that its collection/system scope is complete. The exact completeness markers differ across evidence families and need documented parser rules.
7. **Historical identifier time range:** the request says search current and historical identifiers, while the audit cutoff says use only then-available information. Proposed behavior is to use identity values whose association existed at or before `audit_at`, never a future identity change.
8. **Evaluation report location wording:** `AGENTS.md` describes `evaluation/...`, while the repository README and starter layout require `code/evaluation/...` for packaging. Proposed implementation follows `code/evaluation/` and can mirror/copy only if later packaging validation requires it.
9. **Unknown versus complete:** the contract requires proof for complete cases but does not define an `UNKNOWN` status. Proposed conservative mapping is `INCOMPLETE` when a required final state lacks proof, with findings only when a concrete violation is evidenced; canonical expectations for proof gaps should be checked against samples and any official clarification.

None of these ambiguities requires sample hardcoding. They should be settled as explicit, testable global policies before the full engine is written.

## 15. Phase 1 implementation status (completed 2026-10-24)

Completed in the approved Phase 1 scope:

- typed immutable models for requests, identity snapshots/events/associations, activity, policy, evidence manifests, resources, observations, provenance, intent decisions, temporal histories, and evaluation metrics;
- strict UTF-8-SIG CSV loading with exact schemas, timezone-aware UTC timestamps, uniqueness checks, manifest path containment, and natural identifier ordering;
- collision-safe historical identity reconstruction with effective intervals and exact normalized email/phone/hash/name/user-ID indexes;
- conservative English intent rules, an explicit adjudicator protocol, a high-precision multilingual rules implementation, and an `AMBIGUOUS` result that is never promoted to deletion without support;
- JSON snapshot/service-export adapters, safe in-memory SQL parsing with replica identity preserved, and multi-grammar log/TXT parsing;
- recursive identifier extraction that retains nested field paths and evidence provenance;
- a deterministic evidence store indexed by user ID, email, resource ID, and logical system;
- temporal eligibility that rejects later point-in-time captures and allows retrospective event/history facts only through an explicit opt-in;
- resource-history reconstruction that retains contradictory physical-store observations;
- an isolated sample evaluation harness for status, exact row, exact step, field, and sequence metrics;
- 17 automated tests, including synthetic historical-email, identity-collision, contradictory-replica, later-capture, nested-identifier, parser, loader, and metric fixtures;
- full ingestion validation of 518 requests, 850 identities, 306 identity events, 4,011 activity events, 15 rules, and 79 structured/text evidence files producing 3,677 normalized observations.

Still pending and explicitly outside Phase 1:

- PDF extraction and screenshot/vision ingestion for the remaining 15 unstructured artifacts;
- policy compliance decisions and proof-sufficiency rules;
- resource dependency graph completion, deletion status prediction, remediation planning, and output serialization;
- model-call caching/usage reports for any later AI-assisted extraction;
- sample predictions, full-dataset predictions, and root `output.csv` generation.

Known Phase 1 limitations:

- log parsing preserves individual events but does not yet correlate multi-line request/result traces into compound observations;
- retrospective log/history facts are discoverable but deliberately cannot prove point-in-time record state;
- names are indexed for provenance but are not used alone to merge or resolve users;
- intent vocabulary is deliberately conservative; texts outside documented high-precision rules remain `AMBIGUOUS` for later adjudication;
- SQL is executed only in an in-memory database and rejects known unsafe statements, but the input is still assumed to be participant-provided challenge evidence rather than hostile arbitrary SQL.

## 16. Phase 2 implementation status (completed 2026-10-24)

Completed in the approved Phase 2 scope:

- embedded-text extraction for all four PDFs, retaining file ID, page locator, identifiers, mentioned timestamps, and source/capture metadata; PDF claims are historical facts with `DOCUMENTED` state rather than authoritative live-database observations;
- content-hash-cached structured extraction for all 11 PNG screenshots, PNG integrity checking, exact manifest provenance, identity-graph validation, and explicit unresolved behavior for cache misses or cross-user identifier conflicts;
- correlation-aware log parsing that joins stable request context to related responses, preserves physical continuation lines, retains trace IDs, and separates state readbacks from attempted/successful/failed/pending/partial operations;
- a `system_activity.csv` adapter that preserves original activity IDs and represents reported workflow results only as non-authoritative operation events;
- a temporal assessment engine that separates state, operation, and historical evidence, tracks each physical store independently, detects peer-replica and equal-time contradictions, recognizes post-deletion recreation patterns, and does not backdate later current-state captures;
- exact-observation deduplication without collapsing distinct states, physical copies, resource IDs, timestamps, or provenance;
- provenance validation against manifest file IDs, activity IDs, and identity audit IDs, including source-path, resource-support, state-support, and cutoff checks;
- full ingestion accounting for all 94 evidence artifacts: 94 parsed, zero unresolved, zero parser errors, and 3,872 usable evidence-derived observations;
- 27 passing automated tests, including all six required Phase 2 synthetic scenarios, multimodal corpus integration, log correlation, activity semantics, cache conflict handling, deduplication, and hallucinated citation rejection;
- a reproducible coverage-report generator and checked coverage report under `code/evaluation/`.

Phase 2 dependencies are pinned to `pypdf==6.13.3` and `Pillow==12.2.0`. No runtime model calls were made. Screenshot interpretations are stored as exact-SHA-256 cache entries with development provenance (`OpenAI`, `gpt-5.6-sol`); token metering was unavailable and is reported as unavailable rather than estimated or invented.

Still pending and explicitly outside Phase 2:

- compilation and evaluation of deletion policies;
- proof-sufficiency decisions that map reconstructed states to final case status;
- remediation dependency planning and canonical output ordering;
- public-sample predictions, full-dataset predictions, and root `output.csv` generation.

Known Phase 2 limitations and open decisions:

- the screenshot extractor intentionally has no automatic runtime vision fallback; a new or modified PNG becomes unresolved until reviewed and cached;
- two visible screenshot emails do not occur in the identity graph and therefore remain unlinked warnings, not user associations;
- PDF timestamps are retained as mentioned facts, but prose is not semantically promoted into live resource state;
- later-captured historical documents may support an earlier event only under explicit retrospective reconstruction; the output citation validator remains strict and rejects evidence captured after `audit_at`, matching the official cutoff rule;
- operation success is never absence proof; a separate eligible state readback is required in the future policy layer;
- no completeness inference is made from an omitted snapshot row, because the current evidence formats do not expose a universally reliable completeness marker.

## 17. Phase 3 implementation status (completed 2026-10-24)

Completed in the approved Phase 3 scope:

- a policy compiler driven exclusively by all 15 rows of `deletion_rules.csv`, with explicit action, terminal state, rule ID, condition, and prohibited-identifier metadata;
- canonical resource category/system normalization for structured snapshots, readback logs, replicas, handover records, PDFs, screenshots, flows, backups, and tombstones;
- semantic compliance checks for deletion, support/email redaction, analytics anonymization, retention, blocked restore access, disabled flows, and tombstones that retain only a stable subject reference;
- identity-grounded resource discovery across user ID, current/historical email, hashes, and phone, with names deliberately excluded as sole join keys;
- conservative complete-SQL-scope absence inference only for explicitly labeled point-in-time snapshots; partial snapshot omission remains non-evidence;
- request lifecycle filtering that prevents stale unrelated resource operations from being attached to a deletion request;
- deterministic findings, remediation, and verification planning using only contract operations/states, with data-flow and restore controls ordered before record changes;
- one centralized ordering/numbering implementation and one compact UTF-8 CSV serializer;
- output contract validation for row count, unique IDs, legal statuses, legal operation/state pairs, evidence requirements, cutoff-valid citations, canonical ordering, and consecutive numbering;
- an explicit Phase 3 safety gate that prevents `code/generate.py` from writing root `output.csv` before approval;
- isolated public-sample evaluation with a detailed per-case missing/extra/evidence/order report;
- 34 passing automated tests after adding policy, tombstone, handover, zero-row readback, ordering, and serialization regressions;
- an in-memory full-input readiness run producing 518 unique validated rows without writing a full output file.

Public sample results after generic fixes:

- status accuracy: 32/32 (100%);
- step precision: 100%;
- step recall: 85.49%;
- step F1: 92.18%;
- field accuracy: 74.91%;
- exact sequence and exact row accuracy: 15/32 (46.88%);
- no extra exact-signature steps, evidence-ID-only mismatches, or ordering-only mismatches remain.

The remaining sample gap is conservative under-linking. Most missing steps concern compliant account/analytics records from which identifiers have already been removed, or future verification resources whose IDs do not appear in participant-visible identity-linked evidence. The implementation does not infer those links from sample labels, list position, or case-number conventions. A future phase may add a formally justified workflow-correlation model if an organizer clarification or reliable participant-visible correlation key becomes available.

Full-input readiness validation produced 518 rows with 518 unique IDs in natural case order: 148 `COMPLETE`, 361 `INCOMPLETE`, and 9 `NOT_APPLICABLE`; eight cases retain explicit unresolved reasons. These are readiness diagnostics only, not a generated submission.

Still pending and explicitly outside Phase 3:

- user review/approval of sample evaluation tradeoffs;
- any stronger correlation strategy for identifier-free compliant resources;
- final root `output.csv`, final-run usage accounting, and `code.zip` packaging.

## 18. Phase 4 implementation status (completed 2026-10-25)

Completed in the approved Phase 4 scope:

- added typed `ResourceRelationship` edges with source/target nodes, relationship type, participant-visible supporting provenance, validity interval, capture cutoff, confidence, validity class, and rationale;
- built a deterministic relationship graph covering stable user IDs, historical identity audit references, explicit identity references, foreign keys, parent/child links, source/target flow references, backup/resource references, operation/readback correlations, and logical-to-physical replica lineage;
- limited prediction traversal to `VALIDATED` and `CORROBORATED` edges that existed by `audit_at`; operation-only edges are `REJECTED`, correlation-only edges are `AMBIGUOUS`, and resources referring to multiple users are collision-downgraded;
- integrated safe graph traversal into resource discovery while retaining the original exact-identifier path and state-evidence requirement;
- made verification scope explicit: every discovered policy-governed resource is rechecked after remediation, including absent records, redacted/anonymized records, required retained records, disabled flows, and blocked restore paths; no resource is manufactured solely because a policy category normally exists;
- extended provenance validation to every graph edge and verified that every supporting ID exists in the evidence manifest, system activity, or identity audit log and supports at least one endpoint;
- classified all 28 missing public canonical steps in `code/evaluation/mismatch_analysis.md`: 20 are missing subject/resource associations and eight are genuinely unresolvable from participant-visible pre-cutoff evidence; no policy, evidence-ID-only, or ordering-only errors remain;
- added eight relationship/identity/temporal safety scenarios plus one provenance validation scenario, covering all six requested regressions and explicit historical/foreign-key propagation;
- added three independent, exact-output synthetic evaluation cases (complete, incomplete, and non-deletion), with ground truth isolated under `code/evaluation/fixtures/` and never imported by production code;
- ran 44 automated tests successfully, compiled all Python modules, regenerated the public sample report, and completed a 518-request in-memory readiness run without creating root `output.csv`.

Phase 4 relationship corpus results:

- 10,061 total graph edges;
- 5,799 `VALIDATED`, 261 `AMBIGUOUS`, and 4,001 `REJECTED` edges;
- 923 stable-user, 248 historical-identity, 1,193 explicit-identity, 1 parent/child, 3 source/target-flow, 4,036 operation/readback, and 3,657 physical-replica edges;
- zero graph provenance validation errors;
- all 94 evidence files remain parsed, with 3,931 usable observations, zero unresolved evidence files, and zero parser errors.

Public sample results after Phase 4:

- status accuracy: 32/32 (100%); unchanged from Phase 3;
- step precision: 100%; unchanged;
- step recall: 85.49%; unchanged;
- step F1: 92.18%; unchanged;
- field accuracy: 74.91%; unchanged;
- exact sequence and exact row accuracy: 15/32 (46.88%); unchanged;
- 28 missing steps, zero extra steps, zero evidence-ID-only mismatches, and zero ordering-only mismatches.

The unchanged public score is an intentional safety outcome, not an unexamined failure. None of the remaining canonical resources has a prediction-safe participant-visible relationship at the relevant cutoff. The tempting associations rely on workflow timing, list position, a later capture, or a resource ID visible only in the canonical output. Promoting those signals would violate the hidden-test generalization and identity-collision requirements and caused measurable false positives during a rejected development experiment.

Still pending and explicitly outside Phase 4:

- user approval of the remaining precision/recall tradeoff;
- generation of the final root `output.csv`;
- final-run token/usage accounting tied to that generated submission;
- packaging and inspection of `code.zip`.

## 19. Final submission build status (completed 2026-10-25)

- reran all 44 automated tests and the three independent synthetic evaluations successfully;
- regenerated the 32 public sample predictions with unchanged, explicitly sample-only metrics;
- ran `python code/main.py` successfully from the repository root;
- added an explicit `--final` write gate and generated root `output.csv` from all 518 evaluation requests;
- independently reopened and validated all 518 unique naturally sorted rows, 2,639 ordered steps, 997 evidence-backed steps, legal operation/state pairs, evidence requirements, resource support, and audit cutoffs;
- finalized the evaluation and usage reports with zero runtime model calls/tokens/cost and separately disclosed the 11-entry development-time screenshot cache whose token metering is unavailable;
- documented the required exact-hash screenshot cache, deterministic runtime, and final generation/validation commands;
- validated the append-only root transcript structure and scanned it for common credential patterns without changing or fabricating historical entries;
- created and reopened `code.zip` with the required source, documentation, dependencies, interpretation instructions, reports, tests, and screenshot cache, excluding datasets, virtual environments, Python caches, generated sample predictions, nested archives, and secrets.

Final output status distribution is 148 `COMPLETE`, 361 `INCOMPLETE`, and 9 `NOT_APPLICABLE`. The public sample remains 32/32 for status, 100% step precision, 85.49% recall, 92.18% F1, 74.91% field accuracy, and 15/32 exact sequences. These public metrics are not claims about hidden-test performance.
