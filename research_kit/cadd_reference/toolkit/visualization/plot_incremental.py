#!/usr/bin/env python3
"""Render task reuse and rank-change reports from the incremental helpers."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("reuse", "rank-change"))
    parser.add_argument("report", type=Path)
    parser.add_argument("--output-prefix", type=Path, required=True)
    parser.add_argument("--font-file", type=Path)
    args = parser.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    if args.font_file:
        font_manager.fontManager.addfont(str(args.font_file))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(args.font_file)).get_name()
    plt.rcParams.update({"svg.fonttype": "none", "font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.unicode_minus": False})
    data = json.loads(args.report.read_text(encoding="utf-8"))
    destinations = [Path(str(args.output_prefix) + x) for x in (".svg", ".png")]
    if any(p.exists() for p in destinations):
        raise ValueError("Output already exists; choose a new versioned prefix")
    if any(not p.parent.is_dir() for p in destinations):
        raise ValueError("Output directory must already exist")
    if args.kind == "reuse":
        rows = data.get("tasks", [])
        if data.get("mode") != "plan_only" or not rows:
            raise ValueError("Expected a nonempty plan_incremental report")
        if len(rows) > 80:
            raise ValueError("More than 80 tasks; plan selected --targets for a readable panel")
        colors = {"reuse": "#26806B", "run": "#315D99", "waiting": "#C08A31", "blocked": "#B54B55"}
        if any(r.get("status") not in colors for r in rows):
            raise ValueError("Unknown task status")
        actual = {s: sum(r["status"] == s for r in rows) for s in colors}
        if actual != data.get("counts"):
            raise ValueError("Plan counts do not match task rows")
        fig, ax = plt.subplots(figsize=(10, max(3.8, len(rows) * 0.28 + 1.6)))
        ax.barh(range(len(rows)), [1] * len(rows), color=[colors[r["status"]] for r in rows], height=0.65)
        for i, row in enumerate(rows):
            ax.text(0.02, i, row["status"], color="white", va="center", fontsize=9)
        ax.set_yticks(range(len(rows)), [r["id"] for r in rows])
        ax.invert_yaxis()
        ax.set_xticks([])
        ax.set_xlim(0, 1)
        ax.set_title("Incremental task plan — " + str(data.get("project_id", "")), loc="left", pad=14)
        fig.text(0.02, 0.012, "Readiness only. Scientific validity is determined by the recorded review evidence.", fontsize=9)
        fig.tight_layout(rect=(0, 0.04, 1, 1))
    else:
        rows = [r for r in data.get("records", [])
                if r.get("old_status") == "scored" and r.get("new_status") == "scored"]
        if not rows:
            raise ValueError("No common scored parents to plot")
        for r in rows:
            for key in ("old_rank_full_library", "new_rank_full_library"):
                value = r.get(key)
                if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                    raise ValueError("Ranks must be finite positive numbers")
        if len(rows) != data.get("common_scored_parents"):
            raise ValueError("Common-parent count mismatch")
        fig, ax = plt.subplots(figsize=(7.8, 7.2))
        xs = [r["old_rank_full_library"] for r in rows]
        ys = [r["new_rank_full_library"] for r in rows]
        ax.scatter(xs, ys, s=26, color="#315D99", alpha=0.7, edgecolor="none")
        high = max(xs + ys) * 1.03
        ax.plot([0, high], [0, high], color="#888888", linestyle="--", linewidth=1)
        ax.set(xlim=(0, high), ylim=(0, high), xlabel="Old rank within the old library",
               ylabel="New rank within the new library")
        ax.set_aspect("equal", adjustable="box")
        rho = data.get("spearman_on_common_members")
        rho_text = "not available" if rho is None else f"{rho:.3f}"
        ax.set_title(f"Common scored parents: {len(rows)}\nSpearman on re-ranked common members: {rho_text}",
                     loc="left", pad=12)
        fig.text(0.05, 0.025,
                 "Library size and membership can change full-library ranks.\n"
                 "Scores and rank stability do not establish biological activity.", fontsize=9)
        fig.tight_layout(rect=(0, 0.08, 1, 1))
    # All validation is complete before either artifact is opened.
    for path in destinations:
        with path.open("xb") as handle:
            fig.savefig(handle, format=path.suffix[1:], dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(json.dumps({"files": [str(p) for p in destinations]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, ImportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
