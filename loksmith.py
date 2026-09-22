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
from typing import Dict, List, Set, Tuple


class LoksmithHelpFormatter(argparse.HelpFormatter):
    """Custom formatter providing extra width, clean metavars, spacing, and preserved epilog formatting."""

    def __init__(self, prog):
        super().__init__(prog, max_help_position=34, width=100)

    def _split_lines(self, text, width):
        lines = super()._split_lines(text, width)
        lines.append("")
        return lines

    def _fill_text(self, text, width, indent):
        return "\n".join(f"{indent}{line}" for line in text.splitlines())


def parse_exclusions(exclude_args: List[str], num_wheels: int) -> Dict[int, Set[int]]:
    """
    Parses exclusion specifications across three supported formats:
      1. Dial-targeted: '1:45,3:0' or 'all:4' (1-indexed wheel:digits)
      2. Positional:    '45,,0' (comma-separated matching wheel count)
      3. Global:        '45' (digits excluded across all wheels)
    """
    excluded: Dict[int, Set[int]] = {w: set() for w in range(num_wheels)}
    if not exclude_args:
        return excluded

    for raw_arg in exclude_args:
        raw_arg = raw_arg.strip()
        if not raw_arg:
            continue

        if ":" in raw_arg:
            items = [item.strip() for item in raw_arg.split(",") if item.strip()]
            for item in items:
                if ":" not in item:
                    raise ValueError(f"Malformed exclusion entry '{item}'. Expected format 'dial:digits'")
                dial_spec, digits_spec = item.split(":", 1)
                dial_spec = dial_spec.strip().lower()
                digits = [int(d) for d in digits_spec.strip() if d.isdigit()]
                if not digits:
                    raise ValueError(f"No digits specified in exclusion entry '{item}'")

                if dial_spec in ("all", "*"):
                    for w in range(num_wheels):
                        excluded[w].update(digits)
                elif dial_spec.isdigit():
                    w_idx = int(dial_spec) - 1
                    if not (0 <= w_idx < num_wheels):
                        raise ValueError(
                            f"Dial index '{dial_spec}' out of range. Lock has dials 1 through {num_wheels}"
                        )
                    excluded[w_idx].update(digits)
                else:
                    raise ValueError(f"Unrecognized dial identifier '{dial_spec}' in exclusion '{item}'")

        elif "," in raw_arg:
            parts = raw_arg.split(",")
            if len(parts) != num_wheels:
                raise ValueError(
                    f"Positional exclusion '{raw_arg}' specifies {len(parts)} dials, "
                    f"but lock has {num_wheels} dials."
                )
            for w, part in enumerate(parts):
                for ch in part.strip():
                    if ch.isdigit():
                        excluded[w].add(int(ch))

        else:
            if not raw_arg.isdigit():
                raise ValueError(f"Invalid global exclusion '{raw_arg}'. Must contain only digits 0-9.")
            for ch in raw_arg:
                for w in range(num_wheels):
                    excluded[w].add(int(ch))

    return excluded


def get_candidate_dial_values(
    base_char: str, rotations: int, excluded: Set[int]
) -> List[int]:
    """
    Returns contiguous physical wheel values arranged in cyclic dial order,
    omitting any digits specified in `excluded`.

    - If base_char is '?', candidate values represent a full sweep across
      all non-excluded dial faces (0-9).
    - If base_char is a digit (0-9), candidates sweep from (base - rotations)
      up to (base + rotations) in cyclic dial order with duplicates and
      exclusions removed.
    """
    if base_char == "?":
        return [d for d in range(10) if d not in excluded]

    base_digit = int(base_char)
    if rotations == 0:
        return [] if base_digit in excluded else [base_digit]

    raw_values = [
        (base_digit - rotations + i) % 10 for i in range(2 * rotations + 1)
    ]

    seen = set()
    unique_dial_values = []
    for val in raw_values:
        if val not in seen and val not in excluded:
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
    key_str: str,
    wheel_rotations: List[int],
    excluded_map: Dict[int, Set[int]],
) -> Tuple[List[Dict], int, List[List[int]]]:
    """
    Constructs candidate spaces per wheel taking into account per-wheel offsets,
    pattern wildcards, and excluded digits. Traverses the resulting state space
    using a multi-radix Reflected Gray Code.
    """
    num_wheels = len(key_str)

    wheel_candidates = [
        get_candidate_dial_values(
            key_str[i], rotations=wheel_rotations[i], excluded=excluded_map[i]
        )
        for i in range(num_wheels)
    ]

    for w, cand in enumerate(wheel_candidates):
        if not cand:
            print(
                f"Error: Wheel {w + 1} has 0 valid candidate values after exclusions.",
                file=sys.stderr,
            )
            sys.exit(1)

    radices = [len(c) for c in wheel_candidates]
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

            for w in range(num_wheels):
                if combo_digits[w] != prev_digits[w]:
                    changed_wheel = w + 1
                    diff = (combo_digits[w] - prev_digits[w]) % 10
                    if diff <= 5:
                        direction = f"UP (+{diff})"
                        delta = diff
                    else:
                        down_clicks = 10 - diff
                        direction = f"DOWN (-{down_clicks})"
                        delta = -down_clicks
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

    return sequence, total_rotations, wheel_candidates


def export_txt(
    filepath: Path,
    sequence: List[Dict],
    base_key: str,
    wheel_rotations: List[int],
    wheel_candidates: List[List[int]],
    excluded_map: Dict[int, Set[int]],
    total_rotations: int,
    iterations_only: bool = False,
):
    with open(filepath, "w", encoding="utf-8") as f:
        if iterations_only:
            for item in sequence:
                f.write(f"{item['combination']}\n")
            return

        num_wheels = len(base_key)
        f.write("=" * 68 + "\n")
        f.write("LOKSMITH COMBINATION CRACKER\n")
        f.write(f"Base Combination   : {base_key} ({num_wheels} wheels)\n")
        offsets_str = ", ".join(f"W{i+1}: +/-{r}" for i, r in enumerate(wheel_rotations))
        f.write(f"Rotations Offset   : {offsets_str}\n")
        cand_str = ", ".join(f"W{i+1}: {len(c)}" for i, c in enumerate(wheel_candidates))
        f.write(f"Candidates / Wheel : {cand_str}\n")

        has_excl = any(bool(excluded_map[w]) for w in range(num_wheels))
        if has_excl:
            excl_str = ", ".join(
                f"W{w+1}: {{{','.join(str(d) for d in sorted(excluded_map[w]))}}}"
                for w in range(num_wheels)
                if excluded_map[w]
            )
            f.write(f"Excluded Digits    : {excl_str}\n")

        f.write(f"Total Combinations : {len(sequence):,} (0 duplicates)\n")
        f.write(f"Total Dial Clicks  : {total_rotations:,}\n")
        f.write("Optimization       : Reflected Gray Code Traversal\n")
        f.write("=" * 68 + "\n\n")

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
    wheel_rotations: List[int],
    wheel_candidates: List[List[int]],
    excluded_map: Dict[int, Set[int]],
    total_rotations: int,
    iterations_only: bool = False,
):
    if iterations_only:
        payload = [item["combination"] for item in sequence]
    else:
        num_wheels = len(base_key)
        payload = {
            "metadata": {
                "base_key": base_key,
                "wheel_count": num_wheels,
                "wheel_offsets": wheel_rotations,
                "candidates_per_wheel": [len(c) for c in wheel_candidates],
                "candidate_values": wheel_candidates,
                "excluded_digits": {
                    f"wheel_{w+1}": sorted(list(excluded_map[w]))
                    for w in range(num_wheels)
                    if excluded_map[w]
                },
                "total_combinations": len(sequence),
                "duplicates_count": 0,
                "total_rotations": total_rotations,
                "rotations_per_test_average": round(
                    total_rotations / (len(sequence) - 1), 4
                )
                if len(sequence) > 1
                else 0.0,
                "strategy": "Constrained Multi-Radix Reflected Gray Code",
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
        "  python loksmith.py -k 7?3 -c 1\n"
        "  python loksmith.py -k 7531 -c 0,1,3,5\n"
        "  python loksmith.py -k 08?5 -x 1:45,3:0 -e json\n"
        "  python loksmith.py -k 4921 -c 2 -x 45,,0,9 -e csv"
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
        metavar="PATTERN",
        help="Lock combination (1-6 chars): digits (0-9) and '?' wildcards (e.g. 753, 7?3, ??)",
    )

    gen_group = parser.add_argument_group("Cracking Parameters")
    gen_group.add_argument(
        "-c",
        "--count",
        type=str,
        default="2",
        metavar="COUNTS",
        help="Dial ticks offset (0-5) per wheel: single integer or comma-separated vector (default: 2)",
    )
    gen_group.add_argument(
        "-x",
        "--exclude",
        action="append",
        default=[],
        metavar="SPEC",
        help="Exclude digits: dial-targeted (1:45,3:0), positional (45,,0), or global (45)",
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

    # Validate key pattern (1 to 6 chars, 0-9 or '?')
    key = args.key.strip()
    if not (1 <= len(key) <= 6) or not all(ch.isdigit() or ch == "?" for ch in key):
        print(
            f"Error: Key must be 1 to 6 characters containing digits (0-9) or '?' wildcards. Received: '{args.key}'",
            file=sys.stderr,
        )
        sys.exit(1)

    num_wheels = len(key)

    # Parse and validate rotation counts (0 to 5 per wheel)
    count_str = args.count.strip()
    if "," in count_str:
        raw_counts = count_str.split(",")
        if len(raw_counts) != num_wheels:
            print(
                f"Error: Count vector length ({len(raw_counts)}) does not match key length ({num_wheels}).",
                file=sys.stderr,
            )
            sys.exit(1)
        wheel_rotations = []
        for idx, val in enumerate(raw_counts):
            val_clean = val.strip()
            if not val_clean.isdigit() or not (0 <= int(val_clean) <= 5):
                print(
                    f"Error: Offset for wheel {idx + 1} must be an integer between 0 and 5. Received: '{val_clean}'",
                    file=sys.stderr,
                )
                sys.exit(1)
            wheel_rotations.append(int(val_clean))
    else:
        if not count_str.isdigit() or not (0 <= int(count_str) <= 5):
            print(
                f"Error: Count offset must be an integer between 0 and 5. Received: '{count_str}'",
                file=sys.stderr,
            )
            sys.exit(1)
        base_count = int(count_str)
        # Wildcards default to full sweep (5), while known digits use base_count
        wheel_rotations = [5 if ch == "?" else base_count for ch in key]

    # Wildcard dials must have an offset of 5
    for idx, ch in enumerate(key):
        if ch == "?" and wheel_rotations[idx] != 5:
            print(
                f"Error: Wildcard dial {idx + 1} ('?') requires full sweep (count 5). Received count: {wheel_rotations[idx]}",
                file=sys.stderr,
            )
            sys.exit(1)

    # Parse exclusions
    try:
        excluded_map = parse_exclusions(args.exclude, num_wheels)
    except ValueError as err:
        print(f"Error parsing exclusion argument: {err}", file=sys.stderr)
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

    clean_key_name = key.replace("?", "X")
    out_format = args.export.lower()
    out_file = output_dir / f"loksmith_{clean_key_name}.{out_format}"

    sequence, total_rotations, wheel_candidates = build_cracking_sequence(
        key, wheel_rotations, excluded_map
    )
    total_combos = len(sequence)

    # Export to requested format
    if out_format == "txt":
        export_txt(
            out_file,
            sequence,
            key,
            wheel_rotations,
            wheel_candidates,
            excluded_map,
            total_rotations,
            iterations_only=args.iterations_only,
        )
    elif out_format == "json":
        export_json(
            out_file,
            sequence,
            key,
            wheel_rotations,
            wheel_candidates,
            excluded_map,
            total_rotations,
            iterations_only=args.iterations_only,
        )
    elif out_format == "csv":
        export_csv(
            out_file,
            sequence,
            num_wheels,
            iterations_only=args.iterations_only,
        )

    offsets_display = ", ".join(f"W{i+1}: +/-{r}" for i, r in enumerate(wheel_rotations))
    cand_display = ", ".join(f"W{i+1}: {len(c)}" for i, c in enumerate(wheel_candidates))
    has_excl = any(bool(excluded_map[w]) for w in range(num_wheels))

    print("\n+======================================================+")
    print("|  LOKSMITH: Code-Breaking Sequence Generator          |")
    print("+======================================================+")
    print(f"  Base Key           : {key} ({num_wheels} wheels)")
    print(f"  Offsets Per Wheel  : {offsets_display}")
    print(f"  Candidates / Wheel : {cand_display}")
    if has_excl:
        excl_disp = ", ".join(
            f"W{w+1}: {{{','.join(str(d) for d in sorted(excluded_map[w]))}}}"
            for w in range(num_wheels)
            if excluded_map[w]
        )
        print(f"  Excluded Digits    : {excl_disp}")
    print(f"  Total Combinations : {total_combos:,} (0 duplicates)")
    print(f"  Total Dial Clicks  : {total_rotations:,}")
    avg_clicks = total_rotations / (total_combos - 1) if total_combos > 1 else 0.0
    print(f"  Average Clicks/Step: {avg_clicks:.2f}")
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