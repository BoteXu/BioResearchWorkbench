#!/usr/bin/env python3
"""Validate a planning template and print hypothetical job counts; never run chemistry."""
import argparse
import json
import math
from pathlib import Path
import re
import sys


PLACEHOLDER = re.compile(r"__FILL_[A-Z0-9_]+__")


def number(value, name, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric.")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive.")
    if integer and not isinstance(value, int):
        raise ValueError(f"{name} must be an integer.")
    return value


def placeholders(value, path="$"):
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            found.extend(placeholders(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(placeholders(item, f"{path}[{index}]"))
    elif isinstance(value, str) and PLACEHOLDER.search(value):
        found.append(path)
    return found


def plan(config):
    if config.get("mode") != "planning_only":
        raise ValueError("Only mode='planning_only' is supported.")
    execution = config["execution"]
    if execution.get("automated_execution_enabled") is not False:
        raise ValueError("This planner never enables automated execution.")
    if execution.get("external_paid_compute_enabled") is not False:
        raise ValueError("This planner never enables paid compute.")
    budget = config["budget_example"]
    if budget.get("hypothetical") is not True:
        raise ValueError("Budget calculations must be labelled hypothetical.")
    start = number(budget["starting_parent_capacity"], "starting_parent_capacity", True)
    stage_ids = set()
    stages = []
    for item in budget["docking_stages"]:
        stage_id = item["stage_id"]
        if not isinstance(stage_id, str) or not stage_id.strip():
            raise ValueError("Every stage_id must be a non-empty string.")
        if stage_id in stage_ids:
            raise ValueError(f"Duplicate stage_id: {stage_id}")
        stage_ids.add(stage_id)
        capacity = number(item["parent_capacity"], f"{stage_id}.parent_capacity", True)
        if capacity > start:
            raise ValueError(f"{stage_id} capacity exceeds the registered parent capacity.")
        state_mean = number(item["assumed_mean_states"], f"{stage_id}.assumed_mean_states")
        conf_mean = number(item["assumed_mean_conformers_per_state"], f"{stage_id}.assumed_mean_conformers_per_state")
        receptor_count = number(item["receptor_count"], f"{stage_id}.receptor_count", True)
        poses = number(item["max_output_poses_per_task"], f"{stage_id}.max_output_poses_per_task", True)
        number(item["suggested_exhaustiveness"], f"{stage_id}.suggested_exhaustiveness", True)
        seeds = item["seeds"]
        if not isinstance(seeds, list) or not seeds:
            raise ValueError(f"{stage_id}.seeds must be a non-empty list.")
        for seed in seeds:
            number(seed, f"{stage_id}.seed", True)
            if seed > 2147483647:
                raise ValueError(f"{stage_id} seed exceeds this template's positive 32-bit range.")
        if len(set(seeds)) != len(seeds):
            raise ValueError(f"Duplicate random seeds within {stage_id}.")
        tasks = capacity * state_mean * conf_mean * receptor_count * len(seeds)
        stages.append({
            "stage_id": stage_id,
            "parent_capacity": capacity,
            "hypothetical_task_count": tasks,
            "maximum_pose_records_under_assumed_task_count": tasks * poses,
            "seed_count": len(seeds),
            "not_an_observed_result": True,
        })
    if not stages:
        raise ValueError("At least one planning stage is required.")
    by_id = {item["stage_id"]: item for item in stages}
    if "fine" in by_id:
        quotas = budget["fine_entry_unique_parent_quotas"]
        quota_sum = sum(number(v, f"fine_quota.{k}", True) for k, v in quotas.items())
        if quota_sum != by_id["fine"]["parent_capacity"]:
            raise ValueError("Fine-entry quotas must sum to the fine parent capacity.")
    exp_capacity = number(budget["experimental_new_candidate_capacity"], "experimental_new_candidate_capacity", True)
    exp_sum = sum(number(v, f"experimental_quota.{k}", True) for k, v in budget["experimental_candidate_quotas"].items())
    if exp_sum != exp_capacity:
        raise ValueError("Experimental candidate quotas must sum to their parent capacity.")
    review_capacity = number(budget["manual_review_parent_capacity"], "manual_review_parent_capacity", True)
    md_capacity = number(budget["md_new_candidate_capacity"], "md_new_candidate_capacity", True)
    if max(review_capacity, exp_capacity, md_capacity) > start:
        raise ValueError("A downstream capacity exceeds the starting parent capacity.")
    if max(exp_capacity, md_capacity) > review_capacity:
        raise ValueError("Experimental/MD parent capacity exceeds the manual-review capacity.")
    if "fine" in by_id and review_capacity > by_id["fine"]["parent_capacity"]:
        raise ValueError("Manual-review capacity exceeds the fine-stage parent capacity.")
    timing_report = None
    timing = budget.get("illustrative_fast_timing")
    if timing is not None:
        if timing.get("hypothetical") is not True or "fast" not in by_id:
            raise ValueError("Illustrative timing requires a fast stage and hypothetical=true.")
        minutes = number(timing["minutes_per_task"], "minutes_per_task")
        cores = number(timing["allocated_cpu_cores_per_task"], "allocated_cpu_cores_per_task", True)
        total_cores = number(timing["ideal_total_busy_cores"], "ideal_total_busy_cores", True)
        core_hours = by_id["fast"]["hypothetical_task_count"] * minutes * cores / 60
        timing_report = {
            "hypothetical_cpu_core_hours": core_hours,
            "ideal_wall_clock_lower_bound_hours": core_hours / total_cores,
            "measured_runtime": False,
            "excludes": ["queue_time", "I/O", "load_imbalance", "controls", "preparation", "retries"],
        }
    unresolved = placeholders(config)
    return {
        "mode": "planning_only",
        "project_id": config.get("project_id"),
        "execution_performed": False,
        "chemistry_or_docking_performed": False,
        "screening_validated": False,
        "budget_numbers_are_hypothetical": True,
        "unfilled_field_count": len(unresolved),
        "unfilled_fields": unresolved,
        "stages": stages,
        "illustrative_timing": timing_report,
        "actual_parent_state_conformer_table_required_before_submission": True,
        "controls_validation_retries_and_preparation_are_additional": True,
    }


def invalid_constant(value):
    raise ValueError(f"Non-finite JSON constant is not allowed: {value}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("screening_plan.example.json"))
    parser.add_argument("--out", type=Path, help="Optional NEW report path. Existing files are never overwritten.")
    args = parser.parse_args()
    try:
        with args.config.open(encoding="utf-8") as handle:
            config = json.load(handle, parse_constant=invalid_constant)
        report = plan(config)
        serialized = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.out is None:
            sys.stdout.write(serialized)
        else:
            if PLACEHOLDER.search(str(args.out)):
                raise ValueError("Replace the output path placeholder before writing a report.")
            with args.out.open("x", encoding="utf-8") as handle:
                handle.write(serialized)
            print(f"Planning report written to {args.out}; no screening performed.")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
