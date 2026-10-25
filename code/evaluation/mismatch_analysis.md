# Phase 4 public-sample mismatch analysis

This report is evaluation-only. Canonical steps are used to diagnose aggregate failure modes and are never imported by production prediction code.

## Aggregate

- Missing steps: 28
- Extra steps: 0
- Evidence-ID-only mismatches: 0
- Ordering-only mismatches: 0

- Missing resource associations: 20
- Identifier-free retained records: 0
- Missing historical identity relationships: 0
- Missing active-flow or restore dependencies: 0
- Temporal reconstruction errors: 0
- Policy interpretation errors: 0
- Verification coverage errors: 0
- Evidence-selection errors: 0
- Other genuinely unresolvable associations: 8

## Relationship graph coverage

- Relationships: 10061
- Provenance validation: passed (0 issues)
- Validity classes: `{'AMBIGUOUS': 261, 'REJECTED': 4001, 'VALIDATED': 5799}`
- Relationship types: `{'EXPLICIT_IDENTITY_REFERENCE': 1193, 'HISTORICAL_IDENTITY': 248, 'OPERATION_READBACK': 4036, 'PARENT_CHILD': 1, 'PHYSICAL_REPLICA': 3657, 'SOURCE_TARGET_FLOW': 3, 'STABLE_USER_ID': 923}`

`REJECTED` operation edges and `AMBIGUOUS` correlation/collision edges are retained for audit diagnostics but are not prediction-traversable.

## Per-step classification

### case_03 / step 3

- Root cause: Missing resource associations
- Step: `('VERIFICATION', 'analytics_platform', 'analytics_9406', 'VERIFY_RECORD_ANONYMIZED', 'ANONYMIZED', 'evidence_94')`
- Rationale: the resource is visible before audit_at but lacks a validated subject relationship; eligible_state=1, pre_cutoff_activity=1.

### case_04 / step 1

- Root cause: Other genuinely unresolvable associations
- Step: `('VERIFICATION', 'account_service', 'account_004', 'VERIFY_RECORD_ABSENT', 'ABSENT', 'evidence_54')`
- Rationale: no participant-visible pre-cutoff resource evidence exists; eligible_state=0, pre_cutoff_activity=0.

### case_09 / step 3

- Root cause: Missing resource associations
- Step: `('VERIFICATION', 'account_service', 'account_3960', 'VERIFY_RECORD_ABSENT', 'ABSENT', '')`
- Rationale: the resource is visible before audit_at but lacks a validated subject relationship; eligible_state=0, pre_cutoff_activity=1.

### case_09 / step 4

- Root cause: Other genuinely unresolvable associations
- Step: `('VERIFICATION', 'security_service', 'audit_record_4902', 'VERIFY_RECORD_PRESENT', 'PRESENT', '')`
- Rationale: the resource appears only in later-captured evidence; eligible_state=0, pre_cutoff_activity=0.

### case_18 / step 9

- Root cause: Missing resource associations
- Step: `('VERIFICATION', 'account_service', 'account_5521', 'VERIFY_RECORD_ABSENT', 'ABSENT', '')`
- Rationale: the resource is visible before audit_at but lacks a validated subject relationship; eligible_state=0, pre_cutoff_activity=1.

### case_18 / step 11

- Root cause: Other genuinely unresolvable associations
- Step: `('VERIFICATION', 'security_service', 'audit_record_6645', 'VERIFY_RECORD_PRESENT', 'PRESENT', '')`
- Rationale: no participant-visible pre-cutoff resource evidence exists; eligible_state=0, pre_cutoff_activity=0.

### case_20 / step 5

- Root cause: Missing resource associations
- Step: `('VERIFICATION', 'account_service', 'account_5037', 'VERIFY_RECORD_ABSENT', 'ABSENT', '')`
- Rationale: the resource is visible before audit_at but lacks a validated subject relationship; eligible_state=0, pre_cutoff_activity=1.

### case_20 / step 7

- Root cause: Other genuinely unresolvable associations
- Step: `('VERIFICATION', 'security_service', 'audit_record_5569', 'VERIFY_RECORD_PRESENT', 'PRESENT', '')`
- Rationale: no participant-visible pre-cutoff resource evidence exists; eligible_state=0, pre_cutoff_activity=0.

### case_21 / step 1

- Root cause: Missing resource associations
- Step: `('VERIFICATION', 'account_service', 'account_6440', 'VERIFY_RECORD_ABSENT', 'ABSENT', 'evidence_92')`
- Rationale: the resource is visible before audit_at but lacks a validated subject relationship; eligible_state=1, pre_cutoff_activity=1.

### case_21 / step 3

- Root cause: Missing resource associations
- Step: `('VERIFICATION', 'analytics_platform', 'analytics_5335', 'VERIFY_RECORD_ANONYMIZED', 'ANONYMIZED', 'evidence_92')`
- Rationale: the resource is visible before audit_at but lacks a validated subject relationship; eligible_state=1, pre_cutoff_activity=1.

### case_22 / step 5

- Root cause: Missing resource associations
- Step: `('VERIFICATION', 'account_service', 'account_4990', 'VERIFY_RECORD_ABSENT', 'ABSENT', '')`
- Rationale: the resource is visible before audit_at but lacks a validated subject relationship; eligible_state=0, pre_cutoff_activity=1.

### case_23 / step 5

- Root cause: Missing resource associations
- Step: `('VERIFICATION', 'account_service', 'account_410', 'VERIFY_RECORD_ABSENT', 'ABSENT', '')`
- Rationale: the resource is visible before audit_at but lacks a validated subject relationship; eligible_state=0, pre_cutoff_activity=1.

### case_23 / step 8

- Root cause: Other genuinely unresolvable associations
- Step: `('VERIFICATION', 'security_service', 'audit_record_4128', 'VERIFY_RECORD_PRESENT', 'PRESENT', '')`
- Rationale: the resource appears only in later-captured evidence; eligible_state=0, pre_cutoff_activity=0.

### case_24 / step 7

- Root cause: Other genuinely unresolvable associations
- Step: `('VERIFICATION', 'security_service', 'audit_record_7095', 'VERIFY_RECORD_PRESENT', 'PRESENT', '')`
- Rationale: the resource appears only in later-captured evidence; eligible_state=0, pre_cutoff_activity=0.

### case_25 / step 1

- Root cause: Missing resource associations
- Step: `('VERIFICATION', 'account_service', 'account_3136', 'VERIFY_RECORD_ABSENT', 'ABSENT', 'evidence_92')`
- Rationale: the resource is visible before audit_at but lacks a validated subject relationship; eligible_state=1, pre_cutoff_activity=1.

### case_25 / step 3

- Root cause: Missing resource associations
- Step: `('VERIFICATION', 'analytics_platform', 'analytics_1895', 'VERIFY_RECORD_ANONYMIZED', 'ANONYMIZED', 'evidence_92')`
- Rationale: the resource is visible before audit_at but lacks a validated subject relationship; eligible_state=1, pre_cutoff_activity=1.

### case_26 / step 1

- Root cause: Missing resource associations
- Step: `('VERIFICATION', 'account_service', 'account_5684', 'VERIFY_RECORD_ABSENT', 'ABSENT', 'evidence_92')`
- Rationale: the resource is visible before audit_at but lacks a validated subject relationship; eligible_state=1, pre_cutoff_activity=1.

### case_26 / step 4

- Root cause: Missing resource associations
- Step: `('VERIFICATION', 'analytics_platform', 'analytics_4566', 'VERIFY_RECORD_ANONYMIZED', 'ANONYMIZED', 'evidence_92')`
- Rationale: the resource is visible before audit_at but lacks a validated subject relationship; eligible_state=1, pre_cutoff_activity=1.

### case_27 / step 1

- Root cause: Missing resource associations
- Step: `('VERIFICATION', 'account_service', 'account_3866', 'VERIFY_RECORD_ABSENT', 'ABSENT', 'evidence_92')`
- Rationale: the resource is visible before audit_at but lacks a validated subject relationship; eligible_state=1, pre_cutoff_activity=1.

### case_27 / step 4

- Root cause: Missing resource associations
- Step: `('VERIFICATION', 'analytics_platform', 'analytics_4574', 'VERIFY_RECORD_ANONYMIZED', 'ANONYMIZED', 'evidence_92')`
- Rationale: the resource is visible before audit_at but lacks a validated subject relationship; eligible_state=1, pre_cutoff_activity=1.

### case_28 / step 1

- Root cause: Missing resource associations
- Step: `('VERIFICATION', 'account_service', 'account_5482', 'VERIFY_RECORD_ABSENT', 'ABSENT', 'evidence_92')`
- Rationale: the resource is visible before audit_at but lacks a validated subject relationship; eligible_state=1, pre_cutoff_activity=1.

### case_28 / step 4

- Root cause: Missing resource associations
- Step: `('VERIFICATION', 'analytics_platform', 'analytics_6077', 'VERIFY_RECORD_ANONYMIZED', 'ANONYMIZED', 'evidence_92')`
- Rationale: the resource is visible before audit_at but lacks a validated subject relationship; eligible_state=1, pre_cutoff_activity=1.

### case_29 / step 9

- Root cause: Missing resource associations
- Step: `('VERIFICATION', 'account_service', 'account_7012', 'VERIFY_RECORD_ABSENT', 'ABSENT', '')`
- Rationale: the resource is visible before audit_at but lacks a validated subject relationship; eligible_state=0, pre_cutoff_activity=1.

### case_29 / step 11

- Root cause: Other genuinely unresolvable associations
- Step: `('VERIFICATION', 'security_service', 'audit_record_3954', 'VERIFY_RECORD_PRESENT', 'PRESENT', '')`
- Rationale: the resource appears only in later-captured evidence; eligible_state=0, pre_cutoff_activity=0.

### case_30 / step 9

- Root cause: Missing resource associations
- Step: `('VERIFICATION', 'account_service', 'account_4163', 'VERIFY_RECORD_ABSENT', 'ABSENT', '')`
- Rationale: the resource is visible before audit_at but lacks a validated subject relationship; eligible_state=0, pre_cutoff_activity=1.

### case_30 / step 11

- Root cause: Other genuinely unresolvable associations
- Step: `('VERIFICATION', 'security_service', 'audit_record_1707', 'VERIFY_RECORD_PRESENT', 'PRESENT', '')`
- Rationale: the resource appears only in later-captured evidence; eligible_state=0, pre_cutoff_activity=0.

### case_31 / step 1

- Root cause: Missing resource associations
- Step: `('VERIFICATION', 'account_service', 'account_4857', 'VERIFY_RECORD_ABSENT', 'ABSENT', 'evidence_51')`
- Rationale: the resource is visible before audit_at but lacks a validated subject relationship; eligible_state=0, pre_cutoff_activity=1.

### case_32 / step 3

- Root cause: Missing resource associations
- Step: `('VERIFICATION', 'account_service', 'account_8858', 'VERIFY_RECORD_ABSENT', 'ABSENT', '')`
- Rationale: the resource is visible before audit_at but lacks a validated subject relationship; eligible_state=0, pre_cutoff_activity=1.

## Safety conclusion

No missing step is recoverable from a case number, list position, neighboring activity timestamp, or canonical resource label. Such correlations remain diagnostic-only. Identifier-free records become prediction-eligible only through an explicit participant-visible foreign key, parent/child edge, stable identity reference, source/target reference, or similarly validated relationship.
