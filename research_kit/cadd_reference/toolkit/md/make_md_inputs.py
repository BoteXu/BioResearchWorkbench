#!/usr/bin/env python3
"""Render reviewed-example MD inputs. It does not build a system or run an MD engine."""
import argparse
import json
import hashlib
import re
from pathlib import Path

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--engine", choices=("amber", "gromacs"), required=True)
    p.add_argument("--out", type=Path, required=True, help="New output directory; never overwritten")
    p.add_argument("--replicate", type=int, required=True)
    p.add_argument("--base-seed", type=int, required=True)
    p.add_argument("--production-segments", type=int, default=5, help="Planned 20-ns segments; GROMACS uses one TPR plus extensions")
    p.add_argument("--amber-mask", help="Reviewed Amber solute-heavy-atom mask, required for Amber")
    args = p.parse_args()
    if not 1 <= args.replicate <= 1000:
        p.error("--replicate must be 1..1000")
    if not 1 <= args.production_segments <= 1000:
        p.error("--production-segments must be 1..1000")
    if args.base_seed < 1:
        p.error("--base-seed must be positive")
    if args.engine == "amber":
        mask = args.amber_mask or ""
        if not mask or len(mask) > 256 or any(c in mask for c in "'\"\n\r"):
            p.error("A nonempty, <=256-character mask without quotes/newlines is required")
    else:
        mask = ""
    here = Path(__file__).resolve().parent
    suffix = "in" if args.engine == "amber" else "mdp"
    templates = sorted((here / (args.engine + "_templates")).glob("*." + suffix + ".template"))
    if len(templates) != 10:
        p.error("Expected exactly 10 staged templates adjacent to this script")
    outputs = []
    manifest = {
        "engine": args.engine,
        "replicate_id": args.replicate,
        "base_seed": args.base_seed,
        "planned_production_ns": 20 * args.production_segments,
        "profile": "illustrative soluble system, ff14SB/TIP3P, 300 K, 1 bar",
        "review_status": "rendered example inputs; topology/masks/engine-specific validation required",
        "amber_restraint_mask": mask if args.engine == "amber" else None,
        "files": [],
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_template_sha256": {},
        "simulation_run": False,
    }
    seeds = set()
    for template in templates:
        stage = int(template.name[:2])
        repeats = range(1, args.production_segments + 1) if stage == 9 and args.engine == "amber" else (0,)
        for segment in repeats:
            seed = args.base_seed + args.replicate * 1000000 + stage * 10000 + segment * 10
            velocity_seed = seed + 1
            if velocity_seed >= 2147483647:
                p.error("Seed overflow; choose a smaller base seed or replicate number")
            if seed in seeds or velocity_seed in seeds:
                p.error("Internal seed collision")
            seeds.update((seed, velocity_seed))
            manifest["source_template_sha256"][template.name] = hashlib.sha256(template.read_bytes()).hexdigest()
            content = template.read_text(encoding="utf-8")
            content = content.replace("__SEED__", str(seed)).replace("__VELOCITY_SEED__", str(velocity_seed))
            content = content.replace("__AMBER_MASK__", mask)
            if re.search(r"__[A-Z][A-Z0-9_]*__", content):
                p.error("An unresolved placeholder remains in " + template.name)
            filename = template.name.removesuffix(".template")
            if segment:
                filename = "09_production_" + str(segment).zfill(3) + "." + suffix
            outputs.append((filename, content))
            manifest["files"].append({
                "name": filename, "stage": stage, "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "segment_id": segment if segment else None,
                "thermal_seed": seed if stage >= 2 else None,
                "velocity_seed": velocity_seed if stage == 2 and args.engine == "gromacs" else None,
            })
    # All validation happens before creating the directory; existing results are never overwritten.
    args.out.mkdir(parents=True, exist_ok=False)
    for filename, content in outputs:
        (args.out / filename).write_text(content, encoding="utf-8", newline="\n")
    (args.out / "STAGE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.out.resolve()), "inputs_written": len(outputs),
                      "simulation_run": False}, ensure_ascii=False))

if __name__ == "__main__":
    main()

