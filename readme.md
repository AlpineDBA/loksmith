# Loksmith

**Mechanical Code-Breaking Assistant** — An optimal, minimum-rotation combination search tool for physical multi-dial locks (1 to 6 wheels)[cite: 1, 2].

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Loksmith generates efficient traversal paths for testing local dial perturbations around an observed, estimated, or partially decoded lock state[cite: 2]. By framing candidate spaces as a generalized mixed-radix Cartesian product and traversing them using an n-dimensional **Reflected Gray Code**, Loksmith guarantees that **each subsequent combination differs by a single dial adjustment (+1 or -1 tick) with zero duplicate combinations**[cite: 1, 2].

---

## Features

- **Reflected Gray Code Traversal**: Sequences dial adjustments so consecutive attempts require turning only one dial by a single tick ($O(1)$ physical movement per step)[cite: 1, 2].
- **Interactive CLI Stepper HUD**: Step through combinations live in your terminal with large 5-row ASCII block digits, color-coded wheel indicators, live cadence metrics (attempts/min), and ETA tracking.
- **Pattern Masking (`?` Wildcards)**: Mix known digits with unknown wildcards (e.g., `7?3?`), allowing complete sweeps of uncertain wheels alongside tight offsets on estimated digits.
- **Vector Offsets**: Set asymmetric, per-wheel search radii (e.g., `-c 0,1,3,5`) to keep confirmed dials stationary while sweeping loose wheels.
- **Digit Exclusions**: Exclude confirmed false gates or mechanically jammed numbers globally, positionally, or on targeted dials.
- **Zero Duplicate States**: Exhaustively explores the search space with zero redundant checks[cite: 2].
- **Multiple Export Formats**: Exports step-by-step instructions in plain text (`.txt`), structured data (`.json`), or spreadsheet-ready format (`.csv`)[cite: 1, 2].
- **Zero External Dependencies**: Implemented entirely with the Python standard library[cite: 2].

---

## How It Works

When decoding a combination lock physically, uncertainty is rarely uniform across all wheels[cite: 2]. Some gates may be firmly confirmed, others estimated within a click or two, and some completely unknown.

Loksmith builds an ordered candidate set $C_i$ for each dial $i \in \{1, \dots, n\}$:
- **Known dials** with offset $c_i \in [0, 5]$ explore $\{(\text{base}_i - c_i + k) \pmod{10} \mid k \in [0, 2c_i]\} \setminus \text{Excluded}_i$.
- **Wildcard dials (`?`)** explore $\{0, 1, \dots, 9\} \setminus \text{Excluded}_i$.

The total search space size is the mixed-radix product[cite: 2]:

$$\prod_{i=1}^{n} \vert{}C_i\vert{}$$

The sequence is generated via a mixed-radix Reflected Gray Code across the radices $r_i = \vert{}C_i\vert{}$[cite: 1], guaranteeing adjacent steps differ in index by exactly $\pm 1$.

---

## Installation

Clone the repository[cite: 2]:

```bash
git clone [https://github.com/jackworthen/loksmith.git](https://github.com/jackworthen/loksmith.git)
cd loksmith
```

Ensure Python 3.8+ is installed[cite: 2]. No third-party packages are required[cite: 2].

---

## Usage

Run `loksmith.py` from your terminal:

```bash
python loksmith.py -k <PATTERN> [-c <COUNTS>] [-x <EXCLUSION>] [-I] [-o <OUTPUT_DIR>] [-e <FORMAT>]
```

### Command-Line Arguments

| Flag | Long Flag | Description | Default |
|------|-----------|-------------|---------|
| `-k` | `--key` | **Required.** Lock pattern (1-6 chars): digits `0-9` or `?` wildcards (e.g., `753`, `7?3`, `????`)[cite: 1]. | — |
| `-c` | `--count` | Dial ticks forward and backward ($0 \le c \le 5$). Single integer or comma-separated vector (e.g., `0,1,5`)[cite: 1]. | `2`[cite: 1] |
| `-x` | `--exclude` | Excluded digits: dial-targeted (`1:45,3:0`), positional (`45,,0`), or global (`45`). Repeatable. | — |
| `-I` | `--interactive` | Launch directly into the Interactive CLI Stepper Mode. | `False` |
| `-o` | `--output` | Directory where exported plans are saved[cite: 2]. | `.`[cite: 1] |
| `-e` | `--export` | Output format: `txt`, `json`, or `csv`[cite: 1, 2]. | `txt`[cite: 1] |
| `-i` | `--iterations-only` | Output raw combinations only (omits step actions and headers)[cite: 1]. | `False` |

---

## Interactive Stepper Controls

When running with `-I` (or pressing `i` after generating a sequence), Loksmith displays a live terminal HUD:

| Key | Action |
|-----|--------|
| `Space` / `Enter` / `n` / `Right` | Advance to the next combination. |
| `b` / `p` / `Left` | Step backward (backtrack previous turn). |
| `g` | Jump directly to a specific step number. |
| `f` | **Found!** Mark lock as cracked; displays elapsed time, total clicks, and average cadence. |
| `q` / `Esc` | Exit interactive mode. |

---

## Examples

### 1. Interactive Stepper Mode
Launch an interactive session on a 3-dial lock:

```bash
python loksmith.py -k 753 -I
```

### 2. Wildcard Masking with Automatic Full Sweep
Test a 4-dial lock where dial 1 is `7`, dial 3 is `3`, and dials 2 and 4 are unknown:

```bash
python loksmith.py -k 7?3? -c 1
```

- Dial 1 (`7`) sweeps $\pm 1$ click: $\{6, 7, 8\}$ (3 candidates).
- Dial 2 (`?`) sweeps all 10 faces ($c = 5$).
- Dial 3 (`3`) sweeps $\pm 1$ click: $\{2, 3, 4\}$ (3 candidates).
- Dial 4 (`?`) sweeps all 10 faces ($c = 5$).
- Total search space: $3 \times 10 \times 3 \times 10 = \mathbf{900}$ combinations.

### 3. Pinned Digits & Vector Offsets
Keep confirmed dials stationary while sweeping uncertain dials:

```bash
python loksmith.py -k 7531 -c 0,1,3,5
```

- Dial 1: pinned at `7` ($c = 0$, 1 candidate).
- Dial 2: sweeps $\pm 1$ click around `5` (3 candidates).
- Dial 3: sweeps $\pm 3$ clicks around `3` (7 candidates).
- Dial 4: sweeps all faces ($c = 5$, 10 candidates).

### 4. Dial-Targeted Digit Exclusions
Exclude confirmed false gates on designated wheels:

```bash
python loksmith.py -k 7?3 -c 2 -x 1:45,2:09 -e json
```

- Dial 1 ($7 \pm 2$) excludes digits `4` and `5`.
- Dial 2 (wildcard `?`) excludes digits `0` and `9`.
- Exports instructions to machine-readable JSON[cite: 2].

### 5. Positional Exclusions with CSV Export
Use commas to match exclusions directly to dial positions:

```bash
python loksmith.py -k 4921 -c 2 -x 45,,0,9 -e csv -o ./runs
```

- Dial 1 excludes `4, 5`.
- Dial 2 has no exclusions.
- Dial 3 excludes `0`.
- Dial 4 excludes `9`.
- Saves spreadsheet output to `./runs/loksmith_4921.csv`.

### 6. Global Exclusions
Exclude digits across all wheels (e.g., sticking mechanical gates):

```bash
python loksmith.py -k 082 -c 3 -x 45
```

Removes digits `4` and `5` from every wheel candidate set.

---

## Output Formats

### Plain Text (`.txt`)
Designed for manual bench manipulation[cite: 2]:

```text
====================================================================
LOKSMITH COMBINATION CRACKER
Base Combination   : 7?3 (3 wheels)
Rotations Offset   : W1: +/-1, W2: +/-5, W3: +/-1
Candidates / Wheel : W1: 3, W2: 8, W3: 3
Excluded Digits    : W2: {0,9}
Total Combinations : 72 (0 duplicates)
Total Dial Clicks  : 71
Optimization       : Reflected Gray Code Traversal
====================================================================

Step 0000001: [612]  <-- Set initial position
Step 0000002: [613]  --> Wheel 3: Turn UP (+1)
Step 0000003: [614]  --> Wheel 3: Turn UP (+1)
Step 0000004: [624]  --> Wheel 2: Turn UP (+1)
Step 0000005: [623]  --> Wheel 3: Turn DOWN (-1)
Step 0000006: [622]  --> Wheel 3: Turn DOWN (-1)
```

### CSV (`.csv`)
Granular tabular columns for tracking or automated fixtures[cite: 2]:

```csv
step,combination,wheel_1,wheel_2,wheel_3,wheel_changed,direction,action
1,612,6,1,2,,,Set initial position
2,613,6,1,3,3,UP (+1),Wheel 3: Turn UP (+1)
3,614,6,1,4,3,UP (+1),Wheel 3: Turn UP (+1)
4,624,6,2,4,2,UP (+1),Wheel 2: Turn UP (+1)
```

### JSON (`.json`)
Structured metadata and step-by-step instructions[cite: 2]:

```json
{
  "metadata": {
    "base_key": "7?3",
    "wheel_count": 3,
    "wheel_offsets": [1, 5, 1],
    "candidates_per_wheel": [3, 8, 3],
    "candidate_values": [
      [6, 7, 8],
      [1, 2, 3, 4, 5, 6, 7, 8],
      [2, 3, 4]
    ],
    "excluded_digits": {
      "wheel_2": [0, 9]
    },
    "total_combinations": 72,
    "duplicates_count": 0,
    "total_rotations": 71,
    "rotations_per_test_average": 1.0,
    "strategy": "Constrained Multi-Radix Reflected Gray Code"
  },
  "sequence": [
    {
      "step": 1,
      "combination": "612",
      "action": "Set initial position",
      "wheel_changed": null,
      "direction": null
    },
    {
      "step": 2,
      "combination": "613",
      "action": "Wheel 3: Turn UP (+1)",
      "wheel_changed": 3,
      "direction": "UP (+1)"
    }
  ]
}
```

---

## License

This project is licensed under the GNU GENERAL PUBLIC LICENSE — see the [LICENSE](LICENSE) file for details[cite: 2].