#!/usr/bin/env python3
"""Prepare one receptor/ligand state and run multiple Vina seeds.

Default: validate the configuration and print commands without executing tools.
This is an execution template, not a scientific validation engine.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def placeholders(value):
    if isinstance(value, str):
        return "__FILL_" in value
    if isinstance(value, dict):
        return any(placeholders(v) for v in value.values())
    if isinstance(value, list):
        return any(placeholders(v) for v in value)
    return False


def positive_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def vector3(value, name, positive=False):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{name} must contain exactly three numbers")
    if any(isinstance(v, bool) or not isinstance(v, (int, float))
           or not math.isfinite(v) or (positive and v <= 0) for v in value):
        raise ValueError(f"{name} contains invalid values")
    return value


def path_from_config(value, base):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("File paths must be nonempty strings")
    path = Path(value).expanduser()
    return (base / path).resolve() if not path.is_absolute() else path.resolve()


def load_config(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != "1.0":
        raise ValueError("Expected a JSON object with schema_version 1.0")
    if placeholders(data):
        raise ValueError("Replace every __FILL_*__ placeholder before planning a run")
    for name in ("receptor_id", "ligand_parent_id", "ligand_state_id", "conformer_id",
                 "site_definition", "chemical_state_record"):
        if not isinstance(data.get(name), str) or not data[name].strip():
            raise ValueError(f"{name} must be a nonempty description or identifier")
    base = path.parent
    for name, suffix in (("receptor_pdb", ".pdb"), ("ligand_sdf", ".sdf")):
        p = path_from_config(data.get(name), base)
        if not p.is_file() or p.stat().st_size == 0 or p.suffix.lower() != suffix:
            raise ValueError(f"{name} must be a nonempty {suffix} file: {p}")
        lines = p.read_text(encoding="utf-8").splitlines()
        if name == "ligand_sdf" and sum(line.strip() == "$$$$" for line in lines) != 1:
            raise ValueError("ligand_sdf must contain exactly one SDF record ending with $$$$")
        if name == "receptor_pdb" and sum(line.startswith("MODEL ") for line in lines) > 1:
            raise ValueError("Select exactly one receptor model before using this template")
        data[name] = str(p)
    data["output_dir"] = str(path_from_config(data.get("output_dir"), base))
    if Path(data["output_dir"]).exists():
        raise ValueError("Choose a new output_dir; existing output will not be overwritten")
    box = data.get("box")
    if not isinstance(box, dict):
        raise ValueError("box must be an object")
    vector3(box.get("center_A"), "box.center_A")
    vector3(box.get("size_A"), "box.size_A", positive=True)
    seeds = data.get("seeds")
    if not isinstance(seeds, list) or not seeds:
        raise ValueError("seeds must be a nonempty list")
    for seed in seeds:
        positive_int(seed, "seed")
        if seed > 2147483647:
            raise ValueError("seed must fit a positive signed 32-bit integer")
    if len(set(seeds)) != len(seeds):
        raise ValueError("Use distinct seeds")
    for name in ("exhaustiveness", "num_modes", "cpu"):
        positive_int(data.get(name), name)
    energy = data.get("energy_range_kcal_mol")
    if isinstance(energy, bool) or not isinstance(energy, (int, float)):
        raise ValueError("energy_range_kcal_mol must be numeric")
    if not math.isfinite(energy) or energy <= 0:
        raise ValueError("energy_range_kcal_mol must be finite and positive")
    return data


def commands_for(data):
    out = Path(data["output_dir"])
    rec = out / "receptor"
    lig = out / "ligand.pdbqt"
    commands = [
        ("prepare_receptor",
         ["mk_prepare_receptor.py", "--read_pdb", data["receptor_pdb"],
          "-o", str(rec), "-p", "-v", "--box_center",
          *map(str, data["box"]["center_A"]), "--box_size",
          *map(str, data["box"]["size_A"])],
         [out / "receptor.pdbqt", out / "receptor.box.txt", out / "receptor.box.pdb"]),
        ("prepare_ligand",
         ["mk_prepare_ligand.py", "-i", data["ligand_sdf"], "-o", str(lig)],
         [lig]),
    ]
    for seed in data["seeds"]:
        seed_dir = out / f"seed_{seed}"
        pdbqt = seed_dir / "poses.pdbqt"
        sdf = seed_dir / "poses.sdf"
        commands.extend([
            (f"dock_{seed}",
             ["vina", "--receptor", str(out / "receptor.pdbqt"),
              "--ligand", str(lig), "--config", str(out / "receptor.box.txt"),
              "--scoring", "vina", "--seed", str(seed),
              "--exhaustiveness", str(data["exhaustiveness"]),
              "--num_modes", str(data["num_modes"]),
              "--energy_range", str(data["energy_range_kcal_mol"]),
              "--cpu", str(data["cpu"]), "--out", str(pdbqt)],
             [pdbqt]),
            (f"export_{seed}", ["mk_export.py", str(pdbqt), "-s", str(sdf)], [sdf]),
        ])
    return commands


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def execute(data, commands, config_path):
    required_options = {
        "mk_prepare_receptor.py": ["--read_pdb", "--box_center", "--box_size"],
        "mk_prepare_ligand.py": ["-i", "-o"],
        "mk_export.py": ["-s"],
        "vina": ["--seed", "--cpu", "--num_modes", "--energy_range", "--exhaustiveness"],
    }
    tool_paths = {}
    helps = {}
    for name, options in required_options.items():
        executable = shutil.which(name)
        if not executable:
            raise ValueError(f"Missing executable in the active PATH: {name}")
        check = subprocess.run([executable, "--help"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, check=False)
        if check.returncode != 0 or any(option not in check.stdout for option in options):
            raise ValueError(f"Installed CLI does not match required options: {name}")
        tool_paths[name] = executable
        helps[name] = check.stdout
    out = Path(data["output_dir"])
    out.mkdir(parents=True, exist_ok=False)
    for seed in data["seeds"]:
        (out / f"seed_{seed}").mkdir()
    (out / "logs").mkdir()
    for name, content in helps.items():
        (out / "logs" / f"{name}.help.txt").write_text(content, encoding="utf-8")
    write_json(out / "config.resolved.json", data)
    package_versions = {}
    for name in ("meeko", "rdkit"):
        try:
            package_versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            package_versions[name] = "not visible to runner Python"
    manifest = {
        "status": "running", "scientific_qc_status": "pending",
        "created_utc": utc_now(), "source_config": str(config_path),
        "source_config_sha256": digest(config_path),
        "input_sha256": {name: digest(Path(data[name]))
                         for name in ("receptor_pdb", "ligand_sdf")},
        "python": sys.executable, "python_version": platform.python_version(),
        "packages_visible_to_runner": package_versions,
        "tool_paths": tool_paths, "commands": [], "outputs": []
    }
    manifest_path = out / "execution_manifest.json"
    write_json(manifest_path, manifest)
    try:
        version = subprocess.run([tool_paths["vina"], "--version"],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, check=False)
        manifest["vina_version_output"] = version.stdout.strip()
        for name, args, outputs in commands:
            actual = [tool_paths[args[0]], *args[1:]]
            entry = {"stage": name, "argv": actual, "started_utc": utc_now()}
            manifest["commands"].append(entry)
            write_json(manifest_path, manifest)
            with (out / "logs" / f"{name}.log").open("w", encoding="utf-8") as log:
                log.write(shlex.join(actual) + "\n")
                log.flush()
                result = subprocess.run(actual, stdout=log, stderr=subprocess.STDOUT,
                                        check=False)
            entry.update(returncode=result.returncode, ended_utc=utc_now())
            write_json(manifest_path, manifest)
            if result.returncode != 0:
                raise RuntimeError(f"{name} failed; inspect logs/{name}.log")
            for output in outputs:
                if not output.is_file() or output.stat().st_size == 0:
                    raise RuntimeError(f"{name} did not produce a nonempty {output.name}")
                manifest["outputs"].append({
                    "path": str(output), "sha256": digest(output),
                    "bytes": output.stat().st_size
                })
        manifest["status"] = "execution_complete"
    except BaseException as exc:
        manifest["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        manifest["error"] = str(exc)
        raise
    finally:
        manifest["ended_utc"] = utc_now()
        write_json(manifest_path, manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--execute", action="store_true",
                        help="Run installed tools; otherwise print a plan only")
    args = parser.parse_args()
    config = args.config.resolve()
    try:
        data = load_config(config)
        commands = commands_for(data)
        if not args.execute:
            print("Plan only; no external program has been executed and no output folder created.")
            for name, argv, _ in commands:
                print(name + ": " + shlex.join(argv))
            print("Scientific prerequisites: input identity/state/geometry and box must already be checked.")
            return 0
        execute(data, commands, config)
        print(f"Execution complete: {data['output_dir']}")
        print("Scientific QC remains pending: validate poses, chemistry and selection before MD.")
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
