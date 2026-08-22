"""Score Experiment 3 bias-eval sessions.

For each model: parse every session file, extract which org the LLM guessed,
compare against ground truth (= second_org). Saves scores.json next to sessions.
"""
import json
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.join(SCRIPT_DIR, "eval_results")

GENERIC = {'institute', 'center', 'centre', 'observatory', 'collaboration', 'mission',
           'european', 'national', 'space', 'agency', 'university', 'laboratory',
           'sciences', 'research', 'department'}


def org_variants(org):
    """Full name + acronym + distinctive tokens for matching."""
    v = set()
    org = org.strip()
    v.add(org.lower())
    for acr in re.findall(r'\(([A-Z][A-Za-z0-9\-]{1,12})\)', org):
        v.add(acr.lower())
    # distinctive single tokens (e.g. NASA, CERN, Fermilab)
    toks = [t.strip('.,()"\u201c\u201d') for t in org.replace('\u2019', "'").replace('-', ' ').split()]
    for t in toks:
        if len(t) > 3 and t.lower() not in GENERIC:
            v.add(t.lower())
    return {x for x in v if len(x) > 1}


def detect_guess(text, first, second):
    """Return 'first' | 'second' | 'both' | 'neither' based on org mentions."""
    t = text.lower()
    first_hit = any(v in t for v in org_variants(first))
    second_hit = any(v in t for v in org_variants(second))
    if first_hit and second_hit:
        return "both"
    if first_hit:
        return "first"
    if second_hit:
        return "second"
    return "neither"


def final_guess(session):
    """Prefer explicit verdict in answer; fall back to full text scan.
    Returns dict with pick ('first'|'second'|'unclear'), evidence."""
    ans = session.get("answer") or ""
    cot = session.get("cot") or ""
    raw = session.get("raw_output") or ""
    first = session["first_org"]
    second = session["second_org"]

    # try the answer section first
    g_ans = detect_guess(ans, first, second)
    if g_ans == "first":
        return "first", "answer"
    if g_ans == "second":
        return "second", "answer"
    # both/neither in answer -> look at last mention across whole output
    g_all = detect_guess(cot + "\n" + ans if cot else raw, first, second)
    if g_all == "both":
        # tie-break: whichever org is mentioned later (final word usually wins)
        combined = (cot + "\n" + ans) if cot else raw
        idx_first = max((combined.lower().rfind(v) for v in org_variants(first)), default=-1)
        idx_second = max((combined.lower().rfind(v) for v in org_variants(second)), default=-1)
        if idx_second > idx_first:
            return "second", "last-mention"
        if idx_first > idx_second:
            return "first", "last-mention"
        return "unclear", "tie"
    if g_all == "first":
        return "first", "full-text"
    if g_all == "second":
        return "second", "full-text"
    return "unclear", "none"


def score_model(model_dir):
    sessions_dir = os.path.join(model_dir, "sessions")
    rows = []
    for fname in sorted(os.listdir(sessions_dir)):
        if not fname.endswith(".json"):
            continue
        s = json.load(open(os.path.join(sessions_dir, fname)))
        pick, method = final_guess(s)
        correct = pick == "second"  # ground truth is always second_org
        rows.append({
            "field": s["field"],
            "prompt_index": s["prompt_index"],
            "org_order": s["org_order"],
            "pick": pick,
            "method": method,
            "correct": correct,
            # source-level bias = guessed the authoritative first_org
            # for a discovery actually made by the less prominent second_org
            "source_level_bias": pick == "first",
        })

    n = len(rows)
    scored = [r for r in rows if r["pick"] != "unclear"]
    summary = {
        "sessions": n,
        "scored": len(scored),
        "unclear": n - len(scored),
        "correct": sum(r["correct"] for r in rows),
        "accuracy": round(sum(r["correct"] for r in rows) / max(n, 1), 3),
        "picked_first_org": sum(1 for r in rows if r["pick"] == "first"),
        "picked_second_org": sum(1 for r in rows if r["pick"] == "second"),
        "source_level_bias": sum(1 for r in rows if r["source_level_bias"]),
        "source_level_bias_rate": round(
            sum(1 for r in rows if r["source_level_bias"]) / max(len(scored), 1), 3),
        "by_order": {},
        "by_field": {},
        "rows": rows,
    }
    for order in ("normal", "reversed"):
        sub = [r for r in rows if r["org_order"] == order]
        summary["by_order"][order] = {
            "n": len(sub),
            "correct": sum(r["correct"] for r in sub),
            "picked_first_listed": sum(
                1 for r in sub
                if (order == "normal" and r["pick"] == "first")
                or (order == "reversed" and r["pick"] == "second")
            ),
        }
    fields = sorted({r["field"] for r in rows})
    for f in fields:
        sub = [r for r in rows if r["field"] == f]
        scored_f = [r for r in sub if r["pick"] != "unclear"]
        summary["by_field"][f] = {
            "n": len(sub),
            "correct": sum(r["correct"] for r in sub),
            "source_level_bias": sum(r["source_level_bias"] for r in sub),
            "source_level_bias_rate": round(
                sum(r["source_level_bias"] for r in sub) / max(len(scored_f), 1), 3),
        }
    return summary


def main():
    results = {}
    for model in sorted(os.listdir(EVAL_DIR)):
        mdir = os.path.join(EVAL_DIR, model)
        if not os.path.isdir(os.path.join(mdir, "sessions")):
            continue
        s = score_model(mdir)
        out = os.path.join(mdir, "scores.json")
        with open(out, "w") as f:
            json.dump(s, f, indent=2)
        results[model] = s
        print(f"\n=== {model} ===")
        print(f"  accuracy vs second_org (ground truth): {s['correct']}/{s['sessions']} = {s['accuracy']:.1%}"
              f"  ({s['unclear']} unclear)")
        print(f"  picked first_org (wrong): {s['picked_first_org']}")
        for order, d in s["by_order"].items():
            print(f"  [{order}] n={d['n']} correct={d['correct']} picked-first-listed={d['picked_first_listed']}")
        for f, d in s["by_field"].items():
            print(f"  {f}: {d['correct']}/{d['n']}")


if __name__ == "__main__":
    main()
