#!/usr/bin/env python3
"""
Loksmith: Mechanical Code-Breaking Assistant
Generates an optimal single-rotation path for testing local dial perturbations
on a combination lock (1 to 6 dials) with zero duplicate combinations.
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Enable Virtual Terminal / ANSI processing on Windows consoles
if os.name == "nt":
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        os.system("")  # Fallback VT initializer on Windows 10/11

# ANSI Color Codes
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_BLUE = "\033[94m"
C_MAGENTA = "\033[95m"
C_CYAN = "\033[96m"
C_WHITE = "\033[97m"

# 5-Row High-Legibility Block Digits (8 columns wide)
BIG_DIGITS = {
    0: [
        " ▄████▄ ",
        "██    ██",
        "██    ██",
        "██    ██",
        " ▀████▀ ",
    ],
    1: [
        "   ██   ",
        " ▄███   ",
        "   ██   ",
        "   ██   ",
        " ██████ ",
    ],
    2: [
        " ██████ ",
        "     ██ ",
        " ▄████▀ ",
        "██      ",
        "███████ ",
    ],
    3: [
        "███████ ",
        "     ██ ",
        " ▄████▀ ",
        "     ██ ",
        "███████ ",
    ],
    4: [
        "██   ██ ",
        "██   ██ ",
        "███████ ",
        "     ██ ",
        "     ██ ",
    ],
    5: [
        "███████ ",
        "██      ",
        "██████▄ ",
        "     ██ ",
        "██████▀ ",
    ],
    6: [
        " ▄████▄ ",
        "██      ",
        "██████▄ ",
        "██    ██",
        " ▀████▀ ",
    ],
    7: [
        "████████",
        "   ▄██▀ ",
        "  ▄██▀  ",
        " ▄██▀   ",
        "██▀     ",
    ],
    8: [
        " ▄████▄ ",
        "██    ██",
        " ▀████▀ ",
        "██    ██",
        " ▀████▀ ",
    ],
    9: [
        " ▄████▄ ",
        "██    ██",
        " ▀██████",
        "     ██ ",
        " ▀████▀ ",
    ],
}


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


def get_key() -> str:
    """Reads a single keypress from standard input across platforms."""
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        return line.strip().lower()

    try:
        # Windows
        import msvcrt

        ch = msvcrt.getch()
        if ch in (b"\x00", b"\xe0"):
            ext = msvcrt.getch()
            if ext == b"H":
                return "up"
            if ext == b"P":
                return "down"
            if ext == b"K":
                return "left"
            if ext == b"M":
                return "right"
            return ""
        if ch in (b"\r", b"\n"):
            return "enter"
        if ch == b" ":
            return "space"
        if ch == b"\x1b":
            return "esc"
        if ch == b"\x03":
            raise KeyboardInterrupt
        return ch.decode("utf-8", errors="ignore").lower()
    except ImportError:
        # Unix / macOS
        try:
            import select
            import termios
            import tty

            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
                if ch == "\x1b":
                    r, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if r:
                        seq = sys.stdin.read(2)
                        if seq == "[A":
                            return "up"
                        if seq == "[B":
                            return "down"
                        if seq == "[C":
                            return "right"
                        if seq == "[D":
                            return "left"
                    return "esc"
                if ch in ("\r", "\n"):
                    return "enter"
                if ch == " ":
                    return "space"
                if ch == "\x03":
                    raise KeyboardInterrupt
                return ch.lower()
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except Exception:
            try:
                return input().strip().lower()[:1]
            except (KeyboardInterrupt, EOFError):
                return "q"


def format_time(seconds: float) -> str:
    """Formats seconds into MM:SS or HH:MM:SS."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def parse_exclusions(exclude_args: List[str], num_wheels: int) -> Dict[int, Set[int]]:
    """Parses exclusion specifications across targeted, positional, and global formats."""
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
    """Returns candidate physical values in cyclic dial order without duplicates or exclusions."""
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
    """Generates an n-dimensional Reflected Gray Code sequence across arbitrary radices."""
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
    """Builds step-by-step traversal using multi-radix Gray code."""
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
                f"{C_RED}Error: Wheel {w + 1} has 0 valid candidate values after exclusions.{C_RESET}",
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


def run_interactive_stepper(sequence: List[Dict], base_key: str):
    """Interactive HUD with enlarged block digits and ANSI highlights."""
    total_steps = len(sequence)
    if total_steps == 0:
        print("No combinations to step through.")
        return

    current_idx = 0
    start_time = time.time()
    num_wheels = len(base_key)

    # Precalculate cumulative clicks
    cum_rotations = [0] * total_steps
    acc = 0
    for idx, item in enumerate(sequence):
        acc += abs(item.get("delta", 0))
        cum_rotations[idx] = acc

    while True:
        # Clear screen and return cursor to home
        sys.stdout.write("\033[H\033[J")
        sys.stdout.flush()

        item = sequence[current_idx]
        step_num = item["step"]
        pct = (step_num / total_steps) * 100.0

        elapsed = time.time() - start_time
        elapsed_str = format_time(elapsed)

        rate = (current_idx / (elapsed / 60.0)) if elapsed > 1 and current_idx > 0 else 0.0
        rate_str = f"{rate:.1f}/min" if rate > 0 else "--"

        if rate > 0:
            remaining_steps = total_steps - step_num
            est_seconds = (remaining_steps / rate) * 60.0
            est_str = format_time(est_seconds)
        else:
            est_str = "--:--"

        clicks_so_far = cum_rotations[current_idx]

        # Top Header & Live Metrics
        print(f"{C_CYAN}+==============================================================================+{C_RESET}")
        print(f"{C_CYAN}|{C_RESET}  {C_BOLD}LOKSMITH INTERACTIVE STEPPER{C_RESET}                                                {C_CYAN}|{C_RESET}")
        print(f"{C_CYAN}+==============================================================================+{C_RESET}")
        print(
            f"  {C_BOLD}Step{C_RESET}   : {C_BOLD}{C_WHITE}{step_num:,}{C_RESET} of {total_steps:,} ({C_YELLOW}{pct:5.1f}%{C_RESET}) "
            f"   {C_BOLD}Elapsed{C_RESET} : {C_WHITE}{elapsed_str}{C_RESET}    {C_BOLD}Cadence{C_RESET}  : {C_GREEN}{rate_str}{C_RESET}"
        )
        print(
            f"  {C_BOLD}Clicks{C_RESET} : {C_YELLOW}{clicks_so_far:,}{C_RESET} total clicks"
            f"         {C_BOLD}Est Left{C_RESET}: {C_WHITE}{est_str}{C_RESET}"
        )
        print(f"{C_CYAN}--------------------------------------------------------------------------------{C_RESET}")

        digits = item["digits"]
        changed_wheel = item["wheel_changed"]
        direction = item["direction"]

        # 1. Dial Header Row
        header_cols = []
        status_cols = []
        for w in range(num_wheels):
            is_active = (w + 1) == changed_wheel
            if is_active:
                header_cols.append(f"{C_BOLD}{C_YELLOW} DIAL {w+1} {C_RESET}")
                status_cols.append(f"{C_BOLD}{C_YELLOW}[ACTIVE]{C_RESET}")
            elif step_num == 1:
                header_cols.append(f"{C_BOLD}{C_GREEN} DIAL {w+1} {C_RESET}")
                status_cols.append(f"{C_BOLD}{C_GREEN}[ INIT ]{C_RESET}")
            else:
                header_cols.append(f"{C_DIM}{C_WHITE} DIAL {w+1} {C_RESET}")
                status_cols.append(f"{C_DIM}{C_WHITE}[ HOLD ]{C_RESET}")

        print("  " + "   ".join(header_cols))
        print("  " + "   ".join(status_cols))
        print()

        # 2. Large ASCII Block Digits (5 rows tall)
        for r in range(5):
            row_segments = []
            for w in range(num_wheels):
                d = digits[w]
                is_active = (w + 1) == changed_wheel or step_num == 1
                color = (C_BOLD + C_YELLOW) if is_active else (C_BOLD + C_WHITE)
                glyph_line = BIG_DIGITS.get(d, ["        "] * 5)[r]
                row_segments.append(f"{color}{glyph_line}{C_RESET}")
            print("  " + "   ".join(row_segments))

        # 3. Pointer Indicators Below Digits
        pointer_cols = []
        for w in range(num_wheels):
            if (w + 1) == changed_wheel:
                pointer_cols.append(f"{C_BOLD}{C_YELLOW}  ▲▲▲▲  {C_RESET}")
            elif step_num == 1:
                pointer_cols.append(f"{C_BOLD}{C_GREEN}  ▲▲▲▲  {C_RESET}")
            else:
                pointer_cols.append("        ")
        print("  " + "   ".join(pointer_cols))

        # 4. Highlighted Action Banner
        print(f"{C_CYAN}--------------------------------------------------------------------------------{C_RESET}")
        if changed_wheel is not None:
            if "UP" in direction:
                dir_styled = f"{C_BOLD}{C_GREEN}{direction}{C_RESET}"
            elif "DOWN" in direction:
                dir_styled = f"{C_BOLD}{C_RED}{direction}{C_RESET}"
            else:
                dir_styled = f"{C_BOLD}{C_YELLOW}{direction}{C_RESET}"
            print(f"  {C_BOLD}ACTION{C_RESET} : >>>  Turn {C_BOLD}{C_YELLOW}Wheel {changed_wheel}{C_RESET} {dir_styled}  <<<")
        else:
            print(f"  {C_BOLD}ACTION{C_RESET} : >>>  {C_BOLD}{C_GREEN}{item['action']}{C_RESET}  <<<")

        spaced_code = "  ".join(str(d) for d in digits)
        print(f"  {C_BOLD}TARGET{C_RESET} : [  {C_BOLD}{C_YELLOW}{spaced_code}{C_RESET}  ]")
        print(f"{C_CYAN}================================================================================{C_RESET}")
        print(
            f"  {C_BOLD}[Space/Enter/n]{C_RESET} Next  |  {C_BOLD}[b/p]{C_RESET} Back  |  "
            f"{C_BOLD}[g]{C_RESET} Jump  |  {C_BOLD}[f]{C_RESET} Found!  |  {C_BOLD}[q]{C_RESET} Quit"
        )
        print(f"{C_CYAN}--------------------------------------------------------------------------------{C_RESET}")

        key = get_key()

        if key in ("space", "enter", "n", "right", "down"):
            if current_idx < total_steps - 1:
                current_idx += 1
        elif key in ("b", "p", "left", "up"):
            if current_idx > 0:
                current_idx -= 1
        elif key == "f":
            sys.stdout.write("\033[H\033[J")
            sys.stdout.flush()
            total_elapsed = time.time() - start_time
            final_rate = (
                (current_idx + 1) / (total_elapsed / 60.0) if total_elapsed > 0 else 0.0
            )
            print(f"\n{C_GREEN}+======================================================+{C_RESET}")
            print(f"{C_GREEN}|  {C_BOLD}LOCK CRACKED! COMBINATION FOUND!{C_RESET}{C_GREEN}                    |{C_RESET}")
            print(f"{C_GREEN}+======================================================+{C_RESET}")
            print(f"  Winning Combination : {C_BOLD}{C_YELLOW}{item['combination']}{C_RESET}")
            print(f"  Found at Step       : {step_num:,} of {total_steps:,}")
            print(f"  Total Dial Clicks   : {clicks_so_far:,}")
            print(f"  Time Elapsed        : {format_time(total_elapsed)}")
            print(f"  Testing Cadence     : {final_rate:.1f} combinations / min")
            print(f"{C_GREEN}+======================================================+{C_RESET}\n")
            return
        elif key == "g":
            print()
            try:
                target_str = input(f"Enter target step (1-{total_steps}): ").strip()
                if target_str.isdigit():
                    target = int(target_str)
                    if 1 <= target <= total_steps:
                        current_idx = target - 1
            except (KeyboardInterrupt, EOFError):
                pass
        elif key in ("q", "esc"):
            print(f"\nExited interactive stepper at step {step_num:,} ([{item['combination']}]).\n")
            return


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
        "  python loksmith.py -k 08?5 -x 1:45,3:0 -I\n"
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
        "-I",
        "--interactive",
        action="store_true",
        help="Launch directly into Interactive CLI Stepper Mode",
    )
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

    # Validate key pattern
    key = args.key.strip()
    if not (1 <= len(key) <= 6) or not all(ch.isdigit() or ch == "?" for ch in key):
        print(
            f"{C_RED}Error: Key must be 1 to 6 characters containing digits (0-9) or '?' wildcards. Received: '{args.key}'{C_RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    num_wheels = len(key)

    # Parse and validate rotation counts
    count_str = args.count.strip()
    if "," in count_str:
        raw_counts = count_str.split(",")
        if len(raw_counts) != num_wheels:
            print(
                f"{C_RED}Error: Count vector length ({len(raw_counts)}) does not match key length ({num_wheels}).{C_RESET}",
                file=sys.stderr,
            )
            sys.exit(1)
        wheel_rotations = []
        for idx, val in enumerate(raw_counts):
            val_clean = val.strip()
            if not val_clean.isdigit() or not (0 <= int(val_clean) <= 5):
                print(
                    f"{C_RED}Error: Offset for wheel {idx + 1} must be an integer between 0 and 5. Received: '{val_clean}'{C_RESET}",
                    file=sys.stderr,
                )
                sys.exit(1)
            wheel_rotations.append(int(val_clean))
    else:
        if not count_str.isdigit() or not (0 <= int(count_str) <= 5):
            print(
                f"{C_RED}Error: Count offset must be an integer between 0 and 5. Received: '{count_str}'{C_RESET}",
                file=sys.stderr,
            )
            sys.exit(1)
        base_count = int(count_str)
        wheel_rotations = [5 if ch == "?" else base_count for ch in key]

    for idx, ch in enumerate(key):
        if ch == "?" and wheel_rotations[idx] != 5:
            print(
                f"{C_RED}Error: Wildcard dial {idx + 1} ('?') requires full sweep (count 5). Received count: {wheel_rotations[idx]}{C_RESET}",
                file=sys.stderr,
            )
            sys.exit(1)

    try:
        excluded_map = parse_exclusions(args.exclude, num_wheels)
    except ValueError as err:
        print(f"{C_RED}Error parsing exclusion argument: {err}{C_RESET}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output).expanduser().resolve()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as err:
        print(
            f"{C_RED}Error: Could not create output directory '{output_dir}': {err}{C_RESET}",
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

    print(f"\n{C_CYAN}+======================================================+{C_RESET}")
    print(f"{C_CYAN}|{C_RESET}  {C_BOLD}LOKSMITH: Code-Breaking Sequence Generator{C_RESET}          {C_CYAN}|{C_RESET}")
    print(f"{C_CYAN}+======================================================+{C_RESET}")
    print(f"  Base Key           : {C_BOLD}{key}{C_RESET} ({num_wheels} wheels)")
    print(f"  Offsets Per Wheel  : {offsets_display}")
    print(f"  Candidates / Wheel : {cand_display}")
    if has_excl:
        excl_disp = ", ".join(
            f"W{w+1}: {{{','.join(str(d) for d in sorted(excluded_map[w]))}}}"
            for w in range(num_wheels)
            if excluded_map[w]
        )
        print(f"  Excluded Digits    : {excl_disp}")
    print(f"  Total Combinations : {C_BOLD}{total_combos:,}{C_RESET} (0 duplicates)")
    print(f"  Total Dial Clicks  : {C_YELLOW}{total_rotations:,}{C_RESET}")
    avg_clicks = total_rotations / (total_combos - 1) if total_combos > 1 else 0.0
    print(f"  Average Clicks/Step: {avg_clicks:.2f}")
    print(f"  Iterations Only    : {'Enabled' if args.iterations_only else 'Disabled'}")
    print(f"  Exported File      : {out_file}\n")

    # Interactive prompt or direct launch
    if args.interactive:
        run_interactive_stepper(sequence, key)
    elif sys.stdin.isatty():
        print(f"{C_YELLOW}Press 'i' to enter interactive mode (or Enter to exit): {C_RESET}", end="", flush=True)
        try:
            ch = get_key()
            print()
            if ch == "i":
                run_interactive_stepper(sequence, key)
        except (KeyboardInterrupt, EOFError):
            print()


if __name__ == "__main__":
    main()