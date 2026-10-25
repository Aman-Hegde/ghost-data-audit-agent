# Ghost Data audit agent

Phases 1-4 provide validated participant-data ingestion, timestamp-aware identity
reconstruction, multimodal evidence extraction, conservative intent classification,
policy evaluation, temporal state assessment, a provenance-validated resource
relationship graph, deterministic remediation/verification planning, contract
validation, and isolated public/synthetic evaluation.

Requirements: Python 3.11 plus the pinned packages in `requirements.txt`.

From the repository root:

```powershell
python code\main.py
python code\main.py --requests sample_deletion_requests.csv
python code\generate.py --requests sample_deletion_requests.csv --output code\evaluation\sample_predictions.csv
python -m unittest discover -s code -t code -v
python code\evaluation\main.py <prediction.csv> dataset\sample_output.csv
python code\evaluation\sample_report.py <prediction.csv> dataset\sample_output.csv code\evaluation\evaluation_report.md
python code\evaluation\mismatch_analysis.py
python code\evaluation\synthetic_cases.py
python code\generate.py --requests deletion_requests.csv --output output.csv --final
python code\evaluation\validate_submission.py output.csv
```

`code/main.py` validates and indexes data and prints a JSON summary. `code/generate.py`
writes to an explicit path and contains a pre-submission safety gate that rejects the root
`output.csv`. Ambiguous intent is represented explicitly and may be sent
through the `IntentAdjudicator` interface; the included multilingual adjudicator
only accepts high-precision deletion phrases and otherwise returns `AMBIGUOUS`.

Canonical sample output is read only by `code/evaluation/main.py` when explicitly
provided as a CLI argument. Production modules do not import or read it.

The 11 participant PNGs use the versioned exact-content-hash cache at
`audit_agent/extraction_cache/image_extractions.json`. It is required for reproducible
results and records development provenance (`OpenAI`, `gpt-5.6-sol`). The submitted
runtime makes no model calls; changed or uncached images remain explicitly unresolved.
