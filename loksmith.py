#!/usr/bin/env python3
"""
Loksmith: Mechanical Code-Breaking Assistant
Generates an optimal single-rotation path for testing local dial perturbations
on a combination lock (1 to 6 dials) with zero duplicate combinations.
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class LoksmithHelpFormatter(argparse.HelpFormatter):
    """Custom formatter providing extra width, clean metavars, spacing, and preserved epilog formatting."""

    def __init__(self, prog):
        super().__init__(prog, max_help_position=32, width=100)

    def _split_lines(self, text, width):
        lines = super()._split_lines(text, width)
        lines.append("")
        return lines

    def _fill_text(self, text, width, indent):
        # Preserve raw linebreaks and indentations for epilog examples
        return "\n".join(f"{indent}{line}" for line in text.splitlines())


def get_candidate_dial_values(base_digit: int, rotations: int) -> List[int]:
    """
    Returns contiguous physical wheel values arranged in cyclic dial order
    from (base - rotations) up to (base + rotations), with duplicates removed.

    Because a dial has only 10 unique faces (0-9), any sweep where
    (2 * rotations + 1) > 10 wraps around itself. We deduplicate prior
    to sequence generation while strictly preserving adjacent dial order.
    """
    raw_values = [
        (base_digit - rotations + i) % 10 for i in range(2 * rotations + 1)
    ]

    seen = set()
    unique_dial_values = []
    for val in raw_values:
        if val not in seen:
            seen.add(val)
            unique_dial_values.append(val)

    return unique_dial_values


def generate_reflected_gray_indices(radices: List[int]) -> List[Tuple[int, ...]]:
    """
    Generates an n-dimensional Reflected Gray Code sequence across arbitrary radices.
    Guarantees that between any consecutive tuple, exactly ONE coordinate changes
    by exactly +1 or -1 in its index.
    """
    tuples: List[Tuple[int, ...]] = [()]
    for r in radices:
        next_tuples = []
        for idx, prefix in enumerate(tuples):
            if idx % 2 == 0:
                for val in range(r):
                    next_tuples.append(prefix + (val,))
            else:
                for val in range(r - 1, -1, -1):
                    next_tuples.append(prefix + (val,))
        tuples = next_tuples
    return tuples


def build_cracking_sequence(
    key_str: str, rotations: int
) -> Tuple[List[Dict], int, int]:
    """
    Deduplicates wheel candidate spaces and builds the step-by-step
    minimum-rotation Gray code sequence for any key length up to 6 dials.
    """
    base_digits = [int(char) for char in key_str]
    num_wheels = len(base_digits)

    # 1. Deduplicate candidate values per wheel prior to organizing sequence
    wheel_candidates = [
        get_candidate_dial_values(d, rotations=rotations) for d in base_digits
    ]
    radices = [len(c) for c in wheel_candidates]

    # 2. Generate minimal single-rotation Gray code traversal
    gray_tuples = generate_reflected_gray_indices(radices)

    sequence = []
    total_rotations = 0

    for step_num, idx_tuple in enumerate(gray_tuples, start=1):
        combo_digits = [
            wheel_candidates[wheel_idx][idx_val]
            for wheel_idx, idx_val in enumerate(idx_tuple)
        ]
        combo_str = "".join(str(d) for d in combo_digits)

        if step_num == 1:
            sequence.append({
                "step": step_num,
                "combination": combo_str,
                "digits": combo_digits,
                "action": "Set initial position",
                "wheel_changed": None,
                "direction": None,
                "delta": 0,
            })
        else:
            prev_digits = sequence[-1]["digits"]
            changed_wheel = None
            direction = None
            delta = 0

            # Dynamic check across all wheels
            for w in range(num_wheels):
                if combo_digits[w] != prev_digits[w]:
                    changed_wheel = w + 1  # 1-indexed for manual dialing
                    diff = (combo_digits[w] - prev_digits[w]) % 10
                    if diff == 1:
                        direction = "UP (+1)"
                        delta = 1
                    elif diff == 9:
                        direction = "DOWN (-1)"
                        delta = -1
                    else:
                        direction = f"SHIFT ({diff:+d})"
                        delta = diff
                    break

            total_rotations += abs(delta)
            sequence.append({
                "step": step_num,
                "combination": combo_str,
                "digits": combo_digits,
                "action": f"Wheel {changed_wheel}: Turn {direction}",
                "wheel_changed": changed_wheel,
                "direction": direction,
                "delta": delta,
            })

    return sequence, total_rotations, radices[0]


def export_txt(
    filepath: Path,
    sequence: List[Dict],
    base_key: str,
    rotations: int,
    unique_per_wheel: int,
    total_rotations: int,
    iterations_only: bool = False,
):
    with open(filepath, "w", encoding="utf-8") as f:
        if iterations_only:
            for item in sequence:
                f.write(f"{item['combination']}\n")
            return

        num_wheels = len(base_key)
        f.write("=" * 64 + "\n")
        f.write("LOKSMITH COMBINATION CRACKER\n")
        f.write(f"Base Combination   : {base_key} ({num_wheels} wheels)\n")
        f.write(f"Rotations Offset   : +/- {rotations} clicks per wheel\n")
        f.write(f"Unique Digits/Dial : {unique_per_wheel} (out of 10)\n")
        f.write(f"Total Combinations : {len(sequence):,} (0 duplicates)\n")
        f.write(f"Total Dial Clicks  : {total_rotations:,}\n")
        f.write("Optimization       : Reflected Gray Code (1 tick / step)\n")
        f.write("=" * 64 + "\n\n")

        for item in sequence:
            if item["step"] == 1:
                f.write(
                    f"Step {item['step']:07d}: [{item['combination']}]  <-- {item['action']}\n"
                )
            else:
                f.write(
                    f"Step {item['step']:07d}: [{item['combination']}]  --> {item['action']}\n"
                )


def export_json(
    filepath: Path,
    sequence: List[Dict],
    base_key: str,
    rotations: int,
    unique_per_wheel: int,
    total_rotations: int,
    iterations_only: bool = False,
):
    if iterations_only:
        payload = [item["combination"] for item in sequence]
    else:
        payload = {
            "metadata": {
                "base_key": base_key,
                "wheel_count": len(base_key),
                "rotations_offset": rotations,
                "unique_values_per_wheel": unique_per_wheel,
                "total_combinations": len(sequence),
                "duplicates_count": 0,
                "total_rotations": total_rotations,
                "rotations_per_test_average": round(
                    total_rotations / (len(sequence) - 1), 4
                )
                if len(sequence) > 1
                else 0.0,
                "strategy": "Deduplicated Multi-Radix Reflected Gray Code",
            },
            "sequence": [
                {
                    "step": item["step"],
                    "combination": item["combination"],
                    "action": item["action"],
                    "wheel_changed": item["wheel_changed"],
                    "direction": item["direction"],
                }
                for item in sequence
            ],
        }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def export_csv(
    filepath: Path,
    sequence: List[Dict],
    num_wheels: int,
    iterations_only: bool = False,
):
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        if iterations_only:
            writer = csv.writer(f)
            for item in sequence:
                writer.writerow([item["combination"]])
            return

        wheel_headers = [f"wheel_{i+1}" for i in range(num_wheels)]
        fieldnames = [
            "step",
            "combination",
            *wheel_headers,
            "wheel_changed",
            "direction",
            "action",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in sequence:
            row = {
                "step": item["step"],
                "combination": item["combination"],
                "wheel_changed": item["wheel_changed"] or "",
                "direction": item["direction"] or "",
                "action": item["action"],
            }
            for i, header in enumerate(wheel_headers):
                row[header] = item["digits"][i]
            writer.writerow(row)


def main():
    sample_usage = (
        "Examples:\n"
        "  python loksmith.py -k 042\n"
        "  python loksmith.py -k 7531 -c 3 -e csv\n"
        "  python loksmith.py -k 0875 -c 2 -e txt -i -o ./output"
    )

    parser = argparse.ArgumentParser(
        prog="loksmith",
        description="Generate an optimal, minimum-rotation code-cracking sequence for a 1-to-6 dial lock.\n",
        epilog=sample_usage,
        formatter_class=LoksmithHelpFormatter,
        add_help=False,
    )

    req_group = parser.add_argument_group("Required Arguments")
    req_group.add_argument(
        "-k",
        "--key",
        required=True,
        type=str,
        metavar="DIGITS",
        help="Current lock state between 1 and 6 digits (e.g. 753, 0875, 123456)",
    )

    gen_group = parser.add_argument_group("Cracking Parameters")
    gen_group.add_argument(
        "-c",
        "--count",
        type=int,
        default=2,
        metavar="1-9",
        help="Dial ticks forward and backward per wheel (default: 2)",
    )

    out_group = parser.add_argument_group("Output Options")
    out_group.add_argument(
        "-e",
        "--export",
        default="txt",
        choices=["txt", "json", "csv"],
        metavar="FORMAT",
        help="File format to export: txt, json, or csv (default: txt)",
    )
    out_group.add_argument(
        "-o",
        "--output",
        type=str,
        default=".",
        metavar="PATH",
        help="Directory path to save the output file (default: current directory)",
    )
    out_group.add_argument(
        "-i",
        "--iterations-only",
        action="store_true",
        help="Export raw combinations only, omitting headers and step actions",
    )

    info_group = parser.add_argument_group("Help")
    info_group.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this help message and exit",
    )

    args = parser.parse_args()

    # Validate lock key: must be between 1 and 6 digits
    key = args.key.strip()
    if not (1 <= len(key) <= 6) or not key.isdigit():
        print(
            f"Error: Key must be between 1 and 6 digits (0-9). Received: '{args.key}' ({len(key)} digits)",
            file=sys.stderr,
        )
        sys.exit(1)

    # Validate rotation count (1 to 9)
    if not (1 <= args.count <= 9):
        print(
            f"Error: Rotation count (-c) must be an integer between 1 and 9. Received: {args.count}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Resolve output directory
    output_dir = Path(args.output).expanduser().resolve()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as err:
        print(
            f"Error: Could not create output directory '{output_dir}': {err}",
            file=sys.stderr,
        )
        sys.exit(1)

    out_format = args.export.lower()
    out_file = output_dir / f"loksmith_{key}.{out_format}"

    sequence, total_rotations, unique_per_wheel = build_cracking_sequence(
        key, rotations=args.count
    )
    total_combos = len(sequence)

    # Export to requested format
    if out_format == "txt":
        export_txt(
            out_file,
            sequence,
            key,
            args.count,
            unique_per_wheel,
            total_rotations,
            iterations_only=args.iterations_only,
        )
    elif out_format == "json":
        export_json(
            out_file,
            sequence,
            key,
            args.count,
            unique_per_wheel,
            total_rotations,
            iterations_only=args.iterations_only,
        )
    elif out_format == "csv":
        export_csv(
            out_file,
            sequence,
            len(key),
            iterations_only=args.iterations_only,
        )

    print("\n+======================================================+")
    print("|  LOKSMITH: Code-Breaking Sequence Generator          |")
    print("+======================================================+")
    print(f"  Base Key           : {key} ({len(key)} wheels)")
    print(f"  Requested Sweep    : +/- {args.count} clicks")
    print(f"  Unique Values/Dial : {unique_per_wheel} of 10")
    print(f"  Total Combinations : {total_combos:,} (0 duplicates)")
    print(f"  Total Dial Clicks  : {total_rotations:,}")
    print(f"  Efficiency         : Exactly 1 tick per test step")
    print(f"  Iterations Only    : {'Enabled' if args.iterations_only else 'Disabled'}")
    print(f"  Exported File      : {out_file}\n")

    preview_count = min(6, total_combos)
    print(f"Preview of first {preview_count} steps:")
    for item in sequence[:preview_count]:
        if args.iterations_only:
            print(f"  {item['combination']}")
        else:
            action_desc = f"({item['action']})" if item["action"] else ""
            print(f"  [{item['step']:07d}]  {item['combination']}  {action_desc}")
    if total_combos > preview_count:
        print(f"  ... ({total_combos - preview_count:,} more steps saved to {out_file.name})\n")


if __name__ == "__main__":
    main()