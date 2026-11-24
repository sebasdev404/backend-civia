"""Read-only local provenance audit. Prints counts, never contact data or credentials."""
import ast
import json
import re
from collections import Counter
from pathlib import Path
from app.core.database import SessionLocal
from app.models.case import Case
from app.models.case_comment import CaseComment
from app.models.meta_post import MetaPost
from app.services.triage import captured_comments


def audit(db):
    fixtures = []
    for node in ast.parse(Path(__file__).with_name("app").joinpath("api/v1/seed.py").read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign):
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError, SyntaxError):
                continue
            if isinstance(value, list):
                fixtures.extend(item for item in value if isinstance(item, dict) and "title" in item and "content" in item)
    posts = {post.id: captured_comments(post) for post in db.query(MetaPost)}
    links = {}
    for link in db.query(CaseComment):
        links.setdefault(link.case_id, []).append((link.post_id, link.comment_id))
    counts = Counter()
    for case in db.query(Case):
        if any(case.title == fixture["title"] and case.content == fixture["content"] for fixture in fixtures):
            counts["exact_demo_fixture_match"] += 1
            continue
        post = re.search(r"\[Post ID\]:\s*([^\s]+)", case.internal_notes or "")
        comment = re.search(r"\[Comment ID\]:\s*([^\s]+)", case.internal_notes or "")
        references = links.get(case.id) or ([(post[1], comment[1])] if post and comment else [])
        if not references:
            counts["individual_comment_reference_missing"] += 1
        elif all(cid in posts.get(pid, {}) for pid, cid in references):
            if len(references) == 1:
                original = posts[references[0][0]][references[0][1]]
                counts["exact_comment_text_in_capture" if case.content == (original.get("content") or original.get("message")) else "capture_exists_text_requires_review"] += 1
            else:
                counts["multiple_comments_found_in_capture"] += 1
        elif any(pid in posts for pid, cid in references):
            counts["post_exists_comment_not_in_capture"] += 1
        else:
            counts["source_post_not_in_capture"] += 1
    return {"cases_audited": sum(counts.values()), "counts": dict(counts), "seed_fixtures_compared": len(fixtures),
            "limitation": "Missing evidence does not prove fabrication. A stored capture is not a fresh verification with Meta. This audit does not delete or reclassify records."}


if __name__ == "__main__":
    with SessionLocal() as session:
        print(json.dumps(audit(session), ensure_ascii=True, indent=2))
