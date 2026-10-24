# Ghost Data audit agent

Phase 1 provides validated participant-data ingestion, timestamp-aware identity
reconstruction, conservative intent classification, structured evidence parsing,
an indexed evidence store, temporal reconstruction primitives, and sample metric
infrastructure. It does not implement policy decisions, remediation planning, or
submission prediction generation.

Requirements: Python 3.11. Phase 1 uses only the Python standard library.

From the repository root:

```powershell
python code\main.py
python code\main.py --requests sample_deletion_requests.csv
python -m unittest discover -s code -t code -v
python code\evaluation\main.py <prediction.csv> dataset\sample_output.csv
```

`code/main.py` validates and indexes data and prints a JSON summary. It never
writes `output.csv`. Ambiguous intent is represented explicitly and may be sent
through the `IntentAdjudicator` interface; the included multilingual adjudicator
only accepts high-precision deletion phrases and otherwise returns `AMBIGUOUS`.

Canonical sample output is read only by `code/evaluation/main.py` when explicitly
provided as a CLI argument. Production modules do not import or read it.
