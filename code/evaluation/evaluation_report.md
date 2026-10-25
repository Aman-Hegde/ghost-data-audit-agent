# Phase 4 public sample evaluation

Canonical output is read only by this evaluation module and is not imported by prediction code.

All accuracy figures below are public-sample results only. They are not presented as
hidden-test accuracy or as a guarantee of private evaluation performance.

## Metrics

- Cases: 32
- Status accuracy: 32/32 (100.00%)
- Step precision: 100.00%
- Step recall: 85.49%
- Step F1: 92.18%
- Field accuracy: 74.91%
- Exact sequence accuracy: 15/32 (46.88%)
- Exact row accuracy: 15/32 (46.88%)

### Phase 3 baseline comparison

| Metric | Phase 3 | Phase 4 | Change |
|---|---:|---:|---:|
| Status accuracy | 100.00% | 100.00% | 0.00% |
| Step precision | 100.00% | 100.00% | 0.00% |
| Step recall | 85.49% | 85.49% | 0.00% |
| Step F1 | 92.18% | 92.18% | 0.00% |
| Field accuracy | 74.91% | 74.91% | 0.00% |
| Exact sequence | 15/32 | 15/32 | +0 cases |

The public metrics are intentionally unchanged. The new graph recovered no additional public step that met the stricter provenance and cutoff gates; accepting temporal proximity alone would have reduced precision.

### Aggregate mismatches

- Missing steps: 28
- Extra steps: 0
- Evidence-ID-only mismatch cases: 0
- Ordering-only mismatch cases: 0

### Field accuracy

- `evidence_id`: 164/193 (84.97%)
- `operation`: 133/193 (68.91%)
- `phase`: 165/193 (85.49%)
- `resource_id`: 126/193 (65.28%)
- `state`: 133/193 (68.91%)
- `step_no`: 165/193 (85.49%)
- `system_id`: 126/193 (65.28%)

## Per-case differences

### case_03

- Status: predicted `COMPLETE`, canonical `COMPLETE`.
- First sequence divergence: 3.
- Ordering-only mismatch: no.
- Evidence-ID-only mismatch: no.
- Missing steps: 1.
  - `('VERIFICATION', 'analytics_platform', 'analytics_9406', 'VERIFY_RECORD_ANONYMIZED', 'ANONYMIZED', 'evidence_94')`
- Extra steps: 0.

### case_04

- Status: predicted `COMPLETE`, canonical `COMPLETE`.
- First sequence divergence: 1.
- Ordering-only mismatch: no.
- Evidence-ID-only mismatch: no.
- Missing steps: 1.
  - `('VERIFICATION', 'account_service', 'account_004', 'VERIFY_RECORD_ABSENT', 'ABSENT', 'evidence_54')`
- Extra steps: 0.

### case_09

- Status: predicted `INCOMPLETE`, canonical `INCOMPLETE`.
- First sequence divergence: 3.
- Ordering-only mismatch: no.
- Evidence-ID-only mismatch: no.
- Missing steps: 2.
  - `('VERIFICATION', 'account_service', 'account_3960', 'VERIFY_RECORD_ABSENT', 'ABSENT', '')`
  - `('VERIFICATION', 'security_service', 'audit_record_4902', 'VERIFY_RECORD_PRESENT', 'PRESENT', '')`
- Extra steps: 0.

### case_18

- Status: predicted `INCOMPLETE`, canonical `INCOMPLETE`.
- First sequence divergence: 9.
- Ordering-only mismatch: no.
- Evidence-ID-only mismatch: no.
- Missing steps: 2.
  - `('VERIFICATION', 'account_service', 'account_5521', 'VERIFY_RECORD_ABSENT', 'ABSENT', '')`
  - `('VERIFICATION', 'security_service', 'audit_record_6645', 'VERIFY_RECORD_PRESENT', 'PRESENT', '')`
- Extra steps: 0.

### case_20

- Status: predicted `INCOMPLETE`, canonical `INCOMPLETE`.
- First sequence divergence: 5.
- Ordering-only mismatch: no.
- Evidence-ID-only mismatch: no.
- Missing steps: 2.
  - `('VERIFICATION', 'account_service', 'account_5037', 'VERIFY_RECORD_ABSENT', 'ABSENT', '')`
  - `('VERIFICATION', 'security_service', 'audit_record_5569', 'VERIFY_RECORD_PRESENT', 'PRESENT', '')`
- Extra steps: 0.

### case_21

- Status: predicted `COMPLETE`, canonical `COMPLETE`.
- First sequence divergence: 1.
- Ordering-only mismatch: no.
- Evidence-ID-only mismatch: no.
- Missing steps: 2.
  - `('VERIFICATION', 'account_service', 'account_6440', 'VERIFY_RECORD_ABSENT', 'ABSENT', 'evidence_92')`
  - `('VERIFICATION', 'analytics_platform', 'analytics_5335', 'VERIFY_RECORD_ANONYMIZED', 'ANONYMIZED', 'evidence_92')`
- Extra steps: 0.

### case_22

- Status: predicted `INCOMPLETE`, canonical `INCOMPLETE`.
- First sequence divergence: 5.
- Ordering-only mismatch: no.
- Evidence-ID-only mismatch: no.
- Missing steps: 1.
  - `('VERIFICATION', 'account_service', 'account_4990', 'VERIFY_RECORD_ABSENT', 'ABSENT', '')`
- Extra steps: 0.

### case_23

- Status: predicted `INCOMPLETE`, canonical `INCOMPLETE`.
- First sequence divergence: 5.
- Ordering-only mismatch: no.
- Evidence-ID-only mismatch: no.
- Missing steps: 2.
  - `('VERIFICATION', 'account_service', 'account_410', 'VERIFY_RECORD_ABSENT', 'ABSENT', '')`
  - `('VERIFICATION', 'security_service', 'audit_record_4128', 'VERIFY_RECORD_PRESENT', 'PRESENT', '')`
- Extra steps: 0.

### case_24

- Status: predicted `INCOMPLETE`, canonical `INCOMPLETE`.
- First sequence divergence: 7.
- Ordering-only mismatch: no.
- Evidence-ID-only mismatch: no.
- Missing steps: 1.
  - `('VERIFICATION', 'security_service', 'audit_record_7095', 'VERIFY_RECORD_PRESENT', 'PRESENT', '')`
- Extra steps: 0.

### case_25

- Status: predicted `COMPLETE`, canonical `COMPLETE`.
- First sequence divergence: 1.
- Ordering-only mismatch: no.
- Evidence-ID-only mismatch: no.
- Missing steps: 2.
  - `('VERIFICATION', 'account_service', 'account_3136', 'VERIFY_RECORD_ABSENT', 'ABSENT', 'evidence_92')`
  - `('VERIFICATION', 'analytics_platform', 'analytics_1895', 'VERIFY_RECORD_ANONYMIZED', 'ANONYMIZED', 'evidence_92')`
- Extra steps: 0.

### case_26

- Status: predicted `COMPLETE`, canonical `COMPLETE`.
- First sequence divergence: 1.
- Ordering-only mismatch: no.
- Evidence-ID-only mismatch: no.
- Missing steps: 2.
  - `('VERIFICATION', 'account_service', 'account_5684', 'VERIFY_RECORD_ABSENT', 'ABSENT', 'evidence_92')`
  - `('VERIFICATION', 'analytics_platform', 'analytics_4566', 'VERIFY_RECORD_ANONYMIZED', 'ANONYMIZED', 'evidence_92')`
- Extra steps: 0.

### case_27

- Status: predicted `COMPLETE`, canonical `COMPLETE`.
- First sequence divergence: 1.
- Ordering-only mismatch: no.
- Evidence-ID-only mismatch: no.
- Missing steps: 2.
  - `('VERIFICATION', 'account_service', 'account_3866', 'VERIFY_RECORD_ABSENT', 'ABSENT', 'evidence_92')`
  - `('VERIFICATION', 'analytics_platform', 'analytics_4574', 'VERIFY_RECORD_ANONYMIZED', 'ANONYMIZED', 'evidence_92')`
- Extra steps: 0.

### case_28

- Status: predicted `COMPLETE`, canonical `COMPLETE`.
- First sequence divergence: 1.
- Ordering-only mismatch: no.
- Evidence-ID-only mismatch: no.
- Missing steps: 2.
  - `('VERIFICATION', 'account_service', 'account_5482', 'VERIFY_RECORD_ABSENT', 'ABSENT', 'evidence_92')`
  - `('VERIFICATION', 'analytics_platform', 'analytics_6077', 'VERIFY_RECORD_ANONYMIZED', 'ANONYMIZED', 'evidence_92')`
- Extra steps: 0.

### case_29

- Status: predicted `INCOMPLETE`, canonical `INCOMPLETE`.
- First sequence divergence: 9.
- Ordering-only mismatch: no.
- Evidence-ID-only mismatch: no.
- Missing steps: 2.
  - `('VERIFICATION', 'account_service', 'account_7012', 'VERIFY_RECORD_ABSENT', 'ABSENT', '')`
  - `('VERIFICATION', 'security_service', 'audit_record_3954', 'VERIFY_RECORD_PRESENT', 'PRESENT', '')`
- Extra steps: 0.

### case_30

- Status: predicted `INCOMPLETE`, canonical `INCOMPLETE`.
- First sequence divergence: 9.
- Ordering-only mismatch: no.
- Evidence-ID-only mismatch: no.
- Missing steps: 2.
  - `('VERIFICATION', 'account_service', 'account_4163', 'VERIFY_RECORD_ABSENT', 'ABSENT', '')`
  - `('VERIFICATION', 'security_service', 'audit_record_1707', 'VERIFY_RECORD_PRESENT', 'PRESENT', '')`
- Extra steps: 0.

### case_31

- Status: predicted `COMPLETE`, canonical `COMPLETE`.
- First sequence divergence: 1.
- Ordering-only mismatch: no.
- Evidence-ID-only mismatch: no.
- Missing steps: 1.
  - `('VERIFICATION', 'account_service', 'account_4857', 'VERIFY_RECORD_ABSENT', 'ABSENT', 'evidence_51')`
- Extra steps: 0.

### case_32

- Status: predicted `INCOMPLETE`, canonical `INCOMPLETE`.
- First sequence divergence: 3.
- Ordering-only mismatch: no.
- Evidence-ID-only mismatch: no.
- Missing steps: 1.
  - `('VERIFICATION', 'account_service', 'account_8858', 'VERIFY_RECORD_ABSENT', 'ABSENT', '')`
- Extra steps: 0.

## Exact cases

`case_01`, `case_02`, `case_05`, `case_06`, `case_07`, `case_08`, `case_10`, `case_11`, `case_12`, `case_13`, `case_14`, `case_15`, `case_16`, `case_17`, `case_19`

## Root-cause summary

- All 32 deletion statuses are correct.
- No extra exact-signature steps remain; remaining error is missing coverage, not invented findings.
- The separate `mismatch_analysis.md` classifies all 28 missing steps: 20 lack a validated subject/resource association and eight are genuinely unresolvable from pre-cutoff participant evidence.
- The engine intentionally does not infer those associations from sample labels, array position, operation timing, or canonical resource names.
- Phase 4 adds validated graph traversal for stable IDs, historical identities, explicit foreign keys, parent/child references, source/target flow references, operation/readback provenance, and physical replicas.

## Independent synthetic evaluation

Three ground-truth cases in `evaluation/fixtures/synthetic_expected.json` pass exactly: one complete deletion, one incomplete deletion with an active flow and retained security record, and one explicit non-deletion request. The fixture is loaded only by `evaluation/synthetic_cases.py` and is not imported by production code.

## Final full-dataset validation

- 518 predictions were generated from `dataset/deletion_requests.csv` and independently reopened.
- All 518 case IDs are unique, complete, and naturally sorted.
- The output contains 2,639 ordered steps, including 997 evidence-backed steps.
- Status distribution: 148 `COMPLETE`, 361 `INCOMPLETE`, and 9 `NOT_APPLICABLE`.
- All JSON arrays, step fields, operation/state pairs, step numbers, ordering, evidence requirements, evidence IDs, resource support, and audit cutoffs passed validation.
- The run parsed all 94 evidence files and indexed 3,931 observations with zero parser errors.

## Known limitations

- Twenty missing public steps concern resources visible before cutoff but lacking a validated subject relationship; eight concern resources with no usable pre-cutoff participant evidence.
- Correlation-only activity timing is retained for diagnostics but is not treated as ownership proof.
- Screenshot interpretation depends on an exact-content-hash development cache; the runtime has no fresh vision fallback.
- Ambiguous intent remains `INCOMPLETE` pending adjudication rather than being asserted as deletion authorization.
