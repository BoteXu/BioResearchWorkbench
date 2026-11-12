#!/usr/bin/env python3
"""Read-only executable/version inventory. Does not install or submit jobs."""
import argparse
import importlib.metadata
import json
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def command_output(argv):
    exe = shutil.which(argv[0])
    if exe is None:
        return {"available": False, "command": argv}
    try:
        result = subprocess.run([exe, *argv[1:]], capture_output=True, text=True, timeout=15, check=False)
        return {"available": True, "executable": exe, "command": argv, "exit_code": result.returncode, "stdout": result.stdout[:16000], "stderr": result.stderr[:4000]}
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"available": True, "executable": exe, "command": argv, "error": str(exc)}


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=Path("environment_audit.json"))
args = parser.parse_args()
if args.output.exists():
    parser.error("Choose a new report path; existing receipts are never overwritten")
report = {
    "recorded_utc": datetime.now(timezone.utc).isoformat(),
    "platform": {"system": platform.system(), "release": platform.release(), "machine": platform.machine(), "python": platform.python_version()},
    "executables": {name: shutil.which(name) for name in ("gmx", "gmx_mpi", "pmemd.cuda", "pmemd", "sander", "tleap", "antechamber", "parmchk2", "cpptraj", "MMPBSA.py", "vina", "mk_prepare_ligand.py", "mk_prepare_receptor.py", "mk_export.py", "gmx_MMPBSA")},
    "version_commands": [command_output(["gmx", "--version"]), command_output(["gmx_mpi", "--version"]), command_output(["vina", "--version"]), command_output(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"])],
    "python_packages": {},
    "notes": ["Executable presence does not prove force-field or GPU-feature compatibility.", "Amber/AmberTools build/version and applicable manual must also be copied from installation records or a verified engine log.", "No environment variables, authentication tokens or molecular inputs are collected."]
}
for package in ("MDAnalysis", "mdtraj", "pymbar", "ParmEd", "meeko", "rdkit", "numpy", "scipy", "matplotlib", "gmx-MMPBSA"):
    try:
        report["python_packages"][package] = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        report["python_packages"][package] = None
with args.output.open("x", encoding="utf-8") as stream:
    stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(args.output.resolve())
