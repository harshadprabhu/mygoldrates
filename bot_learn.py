#!/usr/bin/env python3
"""Sona's learned answers: copy the answers the owner approved into git.

Visitors' questions stay in the private database (bot_questions). The owner
reads the ones Sona could not answer on the private analytics page and
approves an answer (bot_approve). This job, run daily, writes every active
approved answer to data/assistant_answers.json - question, answer, optional
link, date - which the site build folds into Sona's knowledge file. Only
approved text reaches git; raw questions never do.
"""
import json
import os

OUT = "data/assistant_answers.json"
NOTE = ("Answers the owner approved from real visitor questions to Sona, the "
        "site assistant. Exported daily from the private database by "
        "bot_learn.py; only approved questions and answers are kept here, "
        "never the raw questions.")


def export(rows):
    """The file's contents for these bot_answers rows (active ones only)."""
    answers = [{"q": r["q"].strip(), "a": r["a"].strip(),
                **({"u": r["u"].strip()} if (r.get("u") or "").strip() else {}),
                "d": str(r.get("created_at", ""))[:10]}
               for r in sorted(rows, key=lambda r: r["id"]) if r.get("active", True)]
    return {"note": NOTE, "answers": answers}


def main():
    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    rows = sb.table("bot_answers").select("id, q, a, u, active, created_at") \
             .eq("active", True).execute().data
    data = export(rows)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"bot_learn: {len(data['answers'])} approved answers written to {OUT}")


if __name__ == "__main__":
    main()
