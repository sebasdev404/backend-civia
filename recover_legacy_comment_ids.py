"""Preview by default. Explicit --apply persists only strict matches and audit outcomes."""
import argparse
import json
from pathlib import Path
from app.core.database import SessionLocal
from app.services.provenance_recovery import run_recovery

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expect-recoverable", type=int)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    with SessionLocal() as db:
        report = run_recovery(db, apply=args.apply, expected_recoverable=args.expect_recoverable)
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "items"}, ensure_ascii=True, indent=2))
