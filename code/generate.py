"""Generate predictions to an explicitly selected non-root path before submission."""

from __future__ import annotations

import argparse
from pathlib import Path

from audit_agent.pipeline import run_pipeline
from audit_agent.serialization import write_output


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic deletion-audit predictions")
    parser.add_argument("--dataset", type=Path, default=Path(__file__).resolve().parents[1] / "dataset")
    parser.add_argument("--requests", default="sample_deletion_requests.csv")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--final", action="store_true",
                        help="authorize writing the repository-root output.csv")
    args = parser.parse_args()
    dataset = args.dataset.resolve(); output = args.output.resolve()
    root_output = Path(__file__).resolve().parents[1] / "output.csv"
    if output == root_output.resolve() and not args.final:
        parser.error("root output.csv requires the explicitly approved --final flag")
    result = run_pipeline(dataset, args.requests)
    write_output(output, list(result.predictions), [item.case_id for item in result.requests])
    print(f"wrote {len(result.predictions)} predictions to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
