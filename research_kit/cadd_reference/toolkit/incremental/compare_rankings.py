#!/usr/bin/env python3
"""Compare two parent-level ranking snapshots without converting scores to activity."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

from plan_incremental import Invalid, emit, need, read_json, text_value


def read_snapshot(path):
    obj = read_json(path)
    need(isinstance(obj, dict), "Snapshot must be an object")
    need(set(obj) == {"schema_version", "snapshot_id", "comparison_key", "score_model",
                     "score_name", "unit", "direction", "rows"}, "Invalid snapshot fields")
    need(type(obj["schema_version"]) is int and obj["schema_version"] == 1,
         "Unsupported snapshot schema")
    for key in ("snapshot_id", "comparison_key", "score_model", "score_name", "unit"):
        need(text_value(obj[key]), f"Missing {key}")
    need(obj["direction"] in {"higher", "lower"}, "direction must be higher or lower")
    need(isinstance(obj["rows"], list), "rows must be an array")
    rows = {}
    for row in obj["rows"]:
        need(isinstance(row, dict) and set(row) == {"parent_id", "status", "value"},
             "Each row requires parent_id, status, value")
        pid = row["parent_id"]
        need(text_value(pid) and pid not in rows, f"Missing or duplicate parent_id: {pid}")
        need(row["status"] in {"scored", "failed", "not_evaluated"}, "Unknown status")
        value = row["value"]
        if row["status"] == "scored":
            need(type(value) in (int, float) and math.isfinite(value),
                 f"{pid}: scored value must be a finite number")
        else:
            need(value is None, f"{pid}: failed/not_evaluated value must be null")
        rows[pid] = row
    return obj, rows


def ranks(rows, direction):
    ordered = sorted(((r["value"], p) for p, r in rows.items() if r["status"] == "scored"),
                     key=lambda x: ((-x[0] if direction == "higher" else x[0]), x[1]))
    result = {}
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and ordered[j][0] == ordered[i][0]:
            j += 1
        average = ((i + 1) + j) / 2
        for _, pid in ordered[i:j]:
            result[pid] = average
        i = j
    return result, ordered


def top_with_ties(ordered, number, direction):
    if not ordered:
        return set()
    limit = ordered[min(number, len(ordered)) - 1][0]
    return {pid for value, pid in ordered
            if value >= limit} if direction == "higher" else {
                pid for value, pid in ordered if value <= limit}


def correlation(xs, ys):
    if len(xs) < 3:
        return None, "fewer_than_three_common_scored_parents"
    xm, ym = sum(xs) / len(xs), sum(ys) / len(ys)
    numerator = sum((x - xm) * (y - ym) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - xm) ** 2 for x in xs) * sum((y - ym) ** 2 for y in ys))
    if den == 0:
        return None, "constant_ranks"
    return max(-1.0, min(1.0, numerator / den)), None


def compare(left, right, top_n, allow_model_change=False):
    a, ar = read_snapshot(left)
    b, br = read_snapshot(right)
    for field in ("comparison_key", "direction", "score_name", "unit"):
        need(a[field] == b[field], f"Incompatible ranking definition: {field}")
    same_model = a["score_model"] == b["score_model"]
    need(same_model or allow_model_change,
         "Different score_model; use --allow-model-change only for rank comparison")
    ra, oa = ranks(ar, a["direction"])
    rb, ob = ranks(br, b["direction"])
    common = sorted(set(ra) & set(rb))
    # Rerank only the common members for Spearman; full-library ranks give a
    # different metric when new molecules are inserted between existing ones.
    ca, _ = ranks({p: ar[p] for p in common}, a["direction"])
    cb, _ = ranks({p: br[p] for p in common}, b["direction"])
    rho, rho_reason = correlation([ca[p] for p in common], [cb[p] for p in common])
    ta = top_with_ties(oa, top_n, a["direction"])
    tb = top_with_ties(ob, top_n, b["direction"])
    records = []
    for pid in sorted(set(ar) | set(br)):
        records.append({"parent_id": pid, "old_status": ar.get(pid, {}).get("status", "absent"),
                        "new_status": br.get(pid, {}).get("status", "absent"),
                        "old_rank_full_library": ra.get(pid), "new_rank_full_library": rb.get(pid),
                        "rank_change_positive_is_improvement":
                            ra[pid] - rb[pid] if pid in ra and pid in rb else None,
                        "score_delta_new_minus_old":
                            br[pid]["value"] - ar[pid]["value"]
                            if same_model and pid in ra and pid in rb else None})
    def counts(rows):
        return {s: sum(x["status"] == s for x in rows.values())
                for s in ("scored", "failed", "not_evaluated")}
    return {"schema_version": 1, "old_snapshot": a["snapshot_id"], "new_snapshot": b["snapshot_id"],
            "comparison_key": a["comparison_key"], "score_models_equal": same_model,
            "score_delta_interpretable_under_same_declared_model": same_model,
            "old_counts": counts(ar), "new_counts": counts(br),
            "common_scored_parents": len(common),
            "coverage_of_old_scored": len(common) / len(ra) if ra else None,
            "coverage_of_new_scored": len(common) / len(rb) if rb else None,
            "spearman_on_common_members": rho, "spearman_unavailable_reason": rho_reason,
            "requested_top_n": top_n, "tie_policy": "include_all_exact_ties_at_boundary",
            "old_top_count": len(ta), "new_top_count": len(tb),
            "top_intersection": sorted(ta & tb), "top_old_only": sorted(ta - tb),
            "top_new_only": sorted(tb - ta),
            "top_jaccard": len(ta & tb) / len(ta | tb) if ta | tb else None,
            "newly_registered_parents": sorted(set(br) - set(ar)),
            "absent_from_new_snapshot": sorted(set(ar) - set(br)),
            "records": records,
            "interpretation": "Rank stability and library composition only; no activity, affinity, or significance claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old_snapshot", type=Path)
    parser.add_argument("new_snapshot", type=Path)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--allow-model-change", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    need(args.top_n > 0, "--top-n must be positive")
    emit(compare(args.old_snapshot, args.new_snapshot, args.top_n, args.allow_model_change), args.output)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Invalid, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
