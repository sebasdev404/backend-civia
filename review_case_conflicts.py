import argparse
import json
from pathlib import Path
from app.core.database import SessionLocal
from app.services.case_conflict_review import run_conflict_review

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Comparar conflictos de origen sin fusionar ni borrar casos")
    parser.add_argument("--apply", action="store_true", help="Guardar únicamente el resultado de auditoría")
    parser.add_argument("--expect-count", type=int)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    with SessionLocal() as db:
        report = run_conflict_review(db, apply=args.apply, expected_count=args.expect_count)
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "items"}, ensure_ascii=True, indent=2))
