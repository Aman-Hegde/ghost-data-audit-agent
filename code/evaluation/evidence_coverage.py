"""Generate the reproducible Phase 2 evidence coverage report."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from audit_agent.identity import IdentityGraph
from audit_agent.ingestion import ingest_evidence
from audit_agent.loaders import load_evidence_manifest, load_identities, load_identity_events


def build_report(dataset: Path) -> str:
    manifest = load_evidence_manifest(dataset / "evidence_files.csv", dataset)
    graph = IdentityGraph(load_identities(dataset / "user_identities.csv"),
                          load_identity_events(dataset / "user_audit_log.csv"))
    result = ingest_evidence(manifest, identity_graph=graph)
    coverage = result.coverage
    types = Counter(item.file_path.suffix.casefold() for item in manifest)
    warnings = [item for item in coverage.issues if item.severity != "ERROR"]
    usage = coverage.model_usage[0]
    lines = [
        "# Phase 2 evidence coverage", "",
        "Generated deterministically from `dataset/evidence_files.csv`; no predictions or policy decisions are produced.", "",
        "## Coverage", "",
        f"- Manifest files: {coverage.manifest_files}",
        f"- Parsed files: {coverage.parsed_files}",
        f"- Unresolved files: {coverage.unresolved_files}",
        f"- Parser errors: {coverage.parser_errors}",
        f"- Observations before deduplication: {coverage.observations_before_deduplication}",
        f"- Usable observations: {coverage.usable_observations}",
        f"- Exact duplicate observations removed: {coverage.duplicate_observations}", "",
        "## Artifact types", "",
    ]
    lines.extend(f"- `{suffix}`: {count}" for suffix, count in sorted(types.items()))
    lines += ["", "## Unresolved and warnings", "",
              f"Unresolved evidence IDs: {', '.join(coverage.unresolved_evidence_ids) or 'none'}."]
    if warnings:
        lines += [""] + [f"- `{item.evidence_id}` `{item.code}`: {item.message}" for item in warnings]
    lines += ["", "## Dependencies and model usage", "",
              "- PDF: `pypdf==6.13.3` (embedded text; page-level provenance).",
              "- PNG validation: `Pillow==12.2.0`.",
              f"- Screenshot extraction cache provenance: provider `{usage.provider}`, model `{usage.model}`.",
              f"- Runtime model calls: {usage.calls}; input tokens: {usage.input_tokens}; output tokens: {usage.output_tokens}; estimated cost: ${usage.estimated_cost_usd:.2f}.",
              "- The development harness did not expose token metering, so no token count is invented; cached facts are keyed by exact SHA-256.", "",
              "## Interpretation limits", "",
              "- Two screenshot identifiers are visible but absent from the identity graph; they remain warnings and are not linked to a user.",
              "- Embedded PDF narrative is typed as historical/document evidence and cannot automatically prove a database's current state.",
              "- Cache misses or identity conflicts are explicit unresolved artifacts; runtime vision fallback is not configured.",
              "- Absence from a partial snapshot is never synthesized as an ABSENT observation.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path(__file__).resolve().parents[2] / "dataset")
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().with_name("evidence_coverage_report.md"))
    args = parser.parse_args()
    report = build_report(args.dataset.resolve())
    args.output.write_text(report, encoding="utf-8", newline="\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
