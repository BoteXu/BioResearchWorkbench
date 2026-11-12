#!/usr/bin/env python3
"""Audit project metadata; never validate chemistry or launch simulations."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys


def audit(config: dict, root: Path, ready: bool, check_files: bool) -> dict:
    errors, warnings, missing = [], [], []
    object_fields = {
        "identity": ["species", "target_accession", "sequence_or_isoform", "construct_and_assembly", "residue_mapping_file"],
        "software": ["engine_version", "parameterization_version", "analysis_environment"],
        "physical_model": ["protein_force_field", "ligand_force_field_or_not_applicable", "water_and_ion_parameters", "protonation_and_charge_decisions", "temperature_K", "pressure_bar", "added_salt_mol_L", "timestep_ps", "constraints", "timestep_rationale"]
    }
    list_fields = {
        "inputs": ["role", "path", "sha256"],
        "systems": ["system_id", "model_id", "state_id", "role", "description"],
        "runs": ["system_id", "replicate_id", "seed", "planned_production_ns", "equilibration_history"],
        "primary_metrics": ["metric_id", "definition", "unit", "selection_definition_file", "comparison_and_uncertainty_method"],
        "scientific_reviews": ["gate", "status", "evidence"]
    }

    def require_fields(obj, keys, prefix):
        for key in keys:
            if key not in obj:
                errors.append(f"Missing field: {prefix}.{key}")

    def walk(value, field="project"):
        if value is None or value == {} or value == [] or (isinstance(value, str) and (not value.strip() or "__FILL" in value or value.strip().lower() in {"tbd", "unknown", "na", "null"})):
            missing.append(field)
        elif isinstance(value, dict):
            for key, item in value.items():
                walk(item, f"{field}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{field}[{index}]")

    walk(config)
    require_fields(config, ["schema_version", "project_id", "question", "scope", "main_engine", *object_fields, *list_fields], "project")
    if config.get("schema_version") not in {"2.0", "2.1"}:
        errors.append("Only schema_version 2.0/2.1 is supported.")
    if ready and config.get("schema_version") != "2.1":
        errors.append("Ready metadata review requires schema 2.1 hash-bound evidence; migrate the legacy template.")
    if config.get("main_engine") not in (None, "amber", "gromacs"):
        errors.append("main_engine must be amber or gromacs.")
    for name, fields in object_fields.items():
        obj = config.get(name)
        if not isinstance(obj, dict):
            errors.append(f"{name} must be an object.")
        else:
            require_fields(obj, fields, name)
    for name, fields in list_fields.items():
        items = config.get(name)
        if not isinstance(items, list) or not items:
            errors.append(f"{name} must be a non-empty list.")
            continue
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"{name}[{i}] must be an object.")
            else:
                require_fields(item, fields, f"{name}[{i}]")
    if errors:
        return {"errors": errors, "warnings": warnings, "missing_fields": missing, "metadata_ready": False, "execution_allowed": False, "scientific_validity": "not_established"}

    pm = config["physical_model"]
    for field in ("temperature_K", "pressure_bar", "timestep_ps"):
        val = pm[field]
        if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val) or val <= 0:
            errors.append(f"physical_model.{field} must be finite and positive for this profile.")
    salt = pm["added_salt_mol_L"]
    if not isinstance(salt, (int, float)) or isinstance(salt, bool) or not math.isfinite(salt) or salt < 0:
        errors.append("added_salt_mol_L must be finite and nonnegative.")
    if isinstance(pm["timestep_ps"], (int, float)) and pm["timestep_ps"] > 0.002:
        warnings.append("Timestep exceeds the illustrative 2 fs profile; validate the specific constraint/mass scheme.")
    systems = {}
    for item in config["systems"]:
        sid = item["system_id"]
        if not isinstance(sid, str) or not sid:
            errors.append("system_id must be a non-empty string.")
            continue
        if sid in systems:
            errors.append(f"Duplicate system_id: {sid}")
        systems[sid] = item
    run_keys, seed_keys, run_counts, explicit_run_ids = set(), set(), {}, set()
    for run in config["runs"]:
        # The current schema identifies a run by (system_id, replicate_id).
        # Also validate a supplied global run_id instead of silently ignoring it.
        if "run_id" in run:
            run_id = run["run_id"]
            if not isinstance(run_id, str) or not run_id.strip():
                errors.append("An explicit run_id must be a non-empty string.")
            elif run_id in explicit_run_ids:
                errors.append(f"Duplicate run_id: {run_id}")
            else:
                explicit_run_ids.add(run_id)
        sid, rid, seed = run["system_id"], run["replicate_id"], run["seed"]
        if not isinstance(sid, str) or not isinstance(rid, str) or not rid:
            errors.append("Run identities must be non-empty strings.")
            continue
        if sid not in systems:
            errors.append(f"Unknown run system: {sid}")
        key = (sid, rid)
        if key in run_keys:
            errors.append(f"Duplicate run identity: {key}")
        run_keys.add(key)
        run_counts[sid] = run_counts.get(sid, 0) + 1
        if not isinstance(seed, int) or isinstance(seed, bool) or seed <= 0:
            errors.append(f"Record an explicit positive initialization seed for {key}.")
        else:
            if (sid, seed) in seed_keys:
                warnings.append(f"Repeated initialization seed in {sid}; review independence and shared histories.")
            seed_keys.add((sid, seed))
        duration = run["planned_production_ns"]
        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or not math.isfinite(duration) or duration <= 0:
            errors.append(f"planned_production_ns must be finite and positive for {key}.")
    for sid in systems:
        if run_counts.get(sid, 0) < 3:
            warnings.append(f"{sid} has fewer than the illustrative three-run budget; justify the design and report uncertainty.")

    for item in config["inputs"]:
        rel, expected = item["path"], item["sha256"]
        if expected and not re.fullmatch(r"[a-fA-F0-9]{64}", str(expected)):
            errors.append(f"Invalid SHA256 format for {rel}.")
        if check_files:
            if not isinstance(rel, str) or not rel:
                errors.append("Input path is missing.")
                continue
            path = Path(rel)
            path = path if path.is_absolute() else root / path
            if not path.is_file():
                errors.append(f"Input file does not exist: {path}")
                continue
            if isinstance(expected, str) and re.fullmatch(r"[a-fA-F0-9]{64}", expected):
                digest = hashlib.sha256()
                with path.open("rb") as handle:
                    for block in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(block)
                if digest.hexdigest() != expected.lower():
                    errors.append(f"Input checksum mismatch: {path}")

    def verify_reference(ref, label):
        if not isinstance(ref, dict) or set(ref) != {"path", "sha256", "bytes"}:
            errors.append(f"{label}: evidence requires path, sha256, bytes.")
            return
        rel, expected = ref["path"], ref["sha256"]
        if not isinstance(rel, str) or not rel.strip() or not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
            errors.append(f"{label}: invalid evidence reference.")
            return
        if type(ref["bytes"]) is not int or ref["bytes"] <= 0:
            errors.append(f"{label}: evidence must be nonempty.")
            return
        if check_files:
            path = (root / rel).resolve()
            if not path.is_relative_to(root.resolve()) or not path.is_file():
                errors.append(f"{label}: evidence outside selected root or unavailable.")
                return
            before = path.stat()
            h = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(block)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or after.st_size != ref["bytes"] or h.hexdigest() != expected:
                errors.append(f"{label}: evidence snapshot mismatch.")

    expected_gates = {"identity_and_structure", "chemical_state_and_parameters", "system_and_pilot", "sampling_and_statistics"}
    found_gates = [x["gate"] for x in config["scientific_reviews"]]
    if len(found_gates) != len(set(found_gates)):
        errors.append("Scientific review gates must not be duplicated.")
    if not expected_gates.issubset(set(found_gates)):
        errors.append("Required scientific review gates are missing.")
    for item in config["scientific_reviews"]:
        if item["status"] not in ("passed", "pending", "exploratory", "stopped"):
            errors.append(f"Unknown review status: {item['gate']}.")
        if ready and item["status"] != "passed":
            errors.append(f"Scientific review is not passed: {item['gate']}.")
        if ready:
            refs = item["evidence"]
            if not isinstance(refs, list) or not refs:
                errors.append(f"{item['gate']}: a nonempty evidence snapshot list is required.")
            else:
                for ref in refs:
                    verify_reference(ref, item["gate"])
    if missing:
        (errors if ready else warnings).append(f"{len(missing)} fields remain empty or explicitly unfilled.")
    if ready and not check_files:
        errors.append("Ready mode requires --check-files to verify registered input hashes.")
    warnings.append("Metadata audit only. Chemistry, force fields, trajectory quality and sampling require the documented scientific reviews.")
    return {"errors": errors, "warnings": warnings, "missing_fields": missing, "metadata_ready": ready and not errors, "execution_allowed": False, "scientific_validity": "not_established", "audit_scope": "declared MD-profile metadata and selected file integrity; not independent scientific validation"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Base for registered input paths")
    parser.add_argument("--ready", action="store_true", help="Final handover audit: require filled fields and passed review records")
    parser.add_argument("--check-files", action="store_true", help="Read registered inputs and check SHA256 hashes")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("The project configuration must be a JSON object.")
        result = audit(config, args.root, args.ready, args.check_files)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result = {"errors": [str(exc)], "warnings": [], "missing_fields": [], "metadata_ready": False, "execution_allowed": False, "scientific_validity": "not_established"}
    report = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        try:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(report + "\n")
        except OSError as exc:
            print(f"ERROR: report not written: {exc}", file=sys.stderr)
            return 2
    print(report)
    return 2 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
