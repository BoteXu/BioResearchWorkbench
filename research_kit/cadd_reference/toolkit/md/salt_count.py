#!/usr/bin/env python3
"""Plan monovalent 1:1 salt for an initially salt-free box; no coordinate edits."""
import argparse
import json
import math

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--volume-nm3", type=float, required=True)
    p.add_argument("--salt-molar", type=float, required=True)
    p.add_argument("--solute-charge", type=int, required=True, help="Integer charge before adding neutralizing ions")
    a = p.parse_args()
    if not math.isfinite(a.volume_nm3) or a.volume_nm3 <= 0:
        p.error("volume must be finite and positive")
    if not math.isfinite(a.salt_molar) or a.salt_molar < 0:
        p.error("salt concentration must be finite and nonnegative")
    scale = 0.602214076 * a.volume_nm3
    pairs = int(math.floor(scale * a.salt_molar + 0.5))
    positive = pairs + max(0, -a.solute_charge)
    negative = pairs + max(0, a.solute_charge)
    commands = []
    if positive:
        commands.append("addIonsRand sys Na+ " + str(positive))
    if negative:
        commands.append("addIonsRand sys Cl- " + str(negative))
    result = {
        "assumptions": "No pre-existing salt; monovalent NaCl; box volume, not excluded solvent volume",
        "salt_pairs": pairs, "positive_ions": positive, "negative_ions": negative,
        "neutralizing_counterions": abs(a.solute_charge),
        "net_charge_after_addition": a.solute_charge + positive - negative,
        "nominal_added_salt_molar": pairs / scale,
        "nominal_positive_ion_molar": positive / scale,
        "nominal_negative_ion_molar": negative / scale,
        "mobile_monovalent_ion_strength_molar": 0.5 * (positive + negative) / scale,
        "leap_commands_for_review": commands,
        "note": "Review topology ion names and counts. Empty command list means omit ion-addition lines; do not replace it with a zero-count neutralization command."
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
if __name__ == "__main__":
    main()

