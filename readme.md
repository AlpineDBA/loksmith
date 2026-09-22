# Loksmith

**Mechanical Code-Breaking Assistant** — An optimal, minimum-rotation combination search tool for physical multi-dial locks (1 to 6 wheels)[cite: 2].

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Loksmith generates traversal paths for testing local dial perturbations around an observed, estimated, or partially decoded lock state[cite: 2]. By modeling candidate spaces as a generalized mixed-radix Cartesian product and traversing them using an n-dimensional **Reflected Gray Code**, Loksmith guarantees that **each subsequent combination differs by a single dial adjustment with zero duplicate combinations**[cite: 2].

---

## Features

- **Reflected Gray Code Traversal**: Sequences dial adjustments so consecutive attempts require turning only one dial at a time[cite: 2].
- **Pattern Masking (`?` Wildcards)**: Mix known digits with unknown wildcards (e.g., `7?3?`), allowing complete exploration of uncertain wheels alongside tight sweeps on partially decoded wheels.
- **Vector Offsets**: Set asymmetric, per-wheel search radii (e.g., `-c 0,1,5`) to keep confirmed dials stationary while sweeping others.
- **Digit Exclusions**: Exclude false gates or mechanically impossible numbers globally, positionally, or on specific dials.
- **Zero Duplicate States**: Exhaustively visits every valid combination in the search space without redundancy[cite: 2].
- **Multiple Export Formats**: Exports step-by-step instructions in plain text (`.txt`), structured data (`.json`), or spreadsheet-ready format (`.csv`)[cite: 2].
- **Zero External Dependencies**: Implemented entirely with the Python standard library[cite: 2].

---

## How It Works

When decoding a combination lock by feel or physical manipulation, uncertainty is rarely uniform across all wheels[cite: 2]. Some gates may be firmly identified, some narrowed down to adjacent numbers, and others completely unknown.

Loksmith builds a candidate set $C_i$ for each dial $i \in \{1, \dots, n\}$:
- Known dials with offset $c_i \in [0, 5]$ explore $\{(\text{base}_i - c_i + k) \pmod{10} \mid k \in [0, 2c_i]\} \setminus \text{Excluded}_i$.
- Wildcard dials (`?`) explore $\{0, 1, \dots, 9\} \setminus \text{Excluded}_i$.

The total search space is the Cartesian product:

$$\prod_{i=1}^{n} \vert{}C_i\vert{}$$

The sequence is generated via a mixed-radix Reflected Gray Code across the radices $r_i = \vert{}C_i\vert{}$, ensuring adjacent combinations differ in index by exactly $\pm 1$.

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

Run `loksmith.py` from your terminal[cite: 2]:

```bash
python3 loksmith.py -k <PATTERN> [-c <COUNTS>] [-x <EXCLUSION>] [-o <OUTPUT_DIR>] [-e <FORMAT>]
```

### Options

| Flag | Long Flag | Description | Default |
|------|-----------|-------------|---------|
| `-k` | `--key` | **Required.** Lock pattern (1-6 chars): digits `0-9` or `?` wildcards (e.g., `753`, `7?3`, `????`).[cite: 2] | — |
| `-c` | `--count` | Dial ticks forward and backward ($0 \le c \le 5$). Single integer or comma-separated vector (e.g., `0,1,5`). | `2`[cite: 2] |
| `-x` | `--exclude` | Excluded digits: dial-targeted (`1:45,3:0`), positional (`45,,0`), or global (`45`). Repeatable. | — |
| `-o` | `--output` | Directory where output files will be written.[cite: 2] | `.`[cite: 2] |
| `-e` | `--export` | Output format: `txt`, `json`, or `csv`.[cite: 2] | `txt`[cite: 2] |
| `-i` | `--iterations-only` | Output raw combinations only (omits step instructions and headers).[cite: 1] | `False` |

---

## Examples

### 1. Uniform Perturbation ($\pm 2$ Clicks)
Test $\pm 2$ clicks around estimated code `753`[cite: 2]:

```bash
python3 loksmith.py -k 753 -c 2
```

Tests 5 candidate digits per dial ($5^3 = 125$ combinations) in 124 single-click steps[cite: 2].

---

### 2. Wildcard Masking with Automatic Expansion
Test a 4-dial lock where dial 1 is `7`, dial 3 is `3`, and dials 2 and 4 are unknown:

```bash
python3 loksmith.py -k 7?3? -c 1
```

- Dial 1 (`7`) sweeps $\pm 1$ click: $\{6, 7, 8\}$ (3 values).
- Dial 2 (`?`) sweeps all faces: $\{0, 1, 2, 3, 4, 5, 6, 7, 8, 9\}$ (10 values).
- Dial 3 (`3`) sweeps $\pm 1$ click: $\{2, 3, 4\}$ (3 values).
- Dial 4 (`?`) sweeps all faces: $\{0, 1, 2, 3, 4, 5, 6, 7, 8, 9\}$ (10 values).

Total space: $3 \times 10 \times 3 \times 10 = 900$ unique combinations.

---

### 3. Vector Offsets (Asymmetric Precision)
Pin confirmed dials while expanding search on loose dials:

```bash
python3 loksmith.py -k 7531 -c 0,1,3,5
```

- Dial 1: stationary on `7` ($c = 0$).
- Dial 2: sweeps $\pm 1$ click around `5`.
- Dial 3: sweeps $\pm 3$ clicks around `3`.
- Dial 4: sweeps all 10 faces ($c = 5$).

---

### 4. Dial-Targeted Digit Exclusions
Exclude confirmed false gates on specific wheels:

```bash
python3 loksmith.py -k 7?3 -c 2 -x 1:45,2:09 -e json
```

- Dial 1 ($7 \pm 2$) excludes digits `4` and `5`.
- Dial 2 (wildcard `?`) excludes digits `0` and `9`.
- Exports machine-readable instructions to JSON.

---

### 5. Positional Exclusions with CSV Output
Use positional syntax matching the dial count:

```bash
python3 loksmith.py -k 4921 -c 2 -x 45,,0,9 -e csv -o ./runs
```

- Dial 1 excludes `4, 5`.
- Dial 2 has no exclusions.
- Dial 3 excludes `0`.
- Dial 4 excludes `9`.
- Exports spreadsheet-ready CSV to `./runs/loksmith_4921.csv`.

---

### 6. Global Exclusions
Exclude digits across all wheels (e.g., digits sticking mechanically):

```bash
python3 loksmith.py -k 082 -c 3 -x 45
```

Removes digits `4` and `5` from every dial candidate set.

---

## Output Formats

### Plain Text (`.txt`)
Designed for direct manipulation at the bench[cite: 2]:

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
Formatted for tracking or automated fixtures[cite: 2]:

```csv
step,combination,wheel_1,wheel_2,wheel_3,wheel_changed,direction,action
1,612,6,1,2,,,Set initial position
2,613,6,1,3,3,UP (+1),Wheel 3: Turn UP (+1)
3,614,6,1,4,3,UP (+1),Wheel 3: Turn UP (+1)
4,624,6,2,4,2,UP (+1),Wheel 2: Turn UP (+1)
```

### JSON (`.json`)
Structured metadata and sequence steps[cite: 2]:

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

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details[cite: 2].