# Loksmith

**Mechanical Code-Breaking Assistant** — An optimal, minimum-rotation combination search tool for physical multi-dial locks (1 to 6 wheels).

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Loksmith generates search trajectories for testing local dial perturbations around an observed or estimated lock position. By utilizing an n-dimensional **Reflected Gray Code** over arbitrary radices, it guarantees that **consecutive combinations differ by exactly one dial movement (+1 or -1 click)**, eliminating wasted physical dial turns and duplicate combinations.

---

## Features

- **Optimal Movement Path**: Uses reflected Gray code sequences so that each step requires only a single click on a single dial ($O(1)$ physical work per attempt).
- **Zero Duplicate States**: Exhaustively explores the perturbation search space with zero redundant checks.
- **Configurable Exploration Window**: Test $\pm c$ clicks around any starting combination (supports 1 to 6 wheels).
- **Multiple Export Formats**: Exports step-by-step instructions in plain text (`.txt`), structured data (`.json`), or spreadsheet-ready format (`.csv`).
- **Zero External Dependencies**: Implemented entirely with the Python Standard Library.

---

## How It Works

When recovering or testing a combination lock where some digits are partially known or likely offset by a few clicks, standard brute-force approaches require rotating multiple wheels back and forth. 

Loksmith frames the local perturbation space as a generalized mixed-radix Cartesian product and traverses it via an n-dimensional Reflected Gray Code:

$$\prod_{i=1}^{n} (2c + 1)$$

Between any step $k$ and step $k+1$, exactly one dial changes by $\pm 1$ tick.

---

## Installation

Clone the repository:

```bash
git clone https://github.com/jackworthen/loksmith.git
cd loksmith
```

Ensure Python 3.8+ is installed. No third-party packages are required.

---

## Usage

Run `loksmith.py` directly from your terminal:

```bash
python3 loksmith.py -k <KEY> [-c <COUNT>] [-o <OUTPUT_DIR>] [-e <FORMAT>]
```

### Options

| Flag | Long Flag | Description | Default |
|------|-----------|-------------|---------|
| `-k` | `--key` | **Required.** Base lock combination (1 to 6 digits, e.g., `753`, `0875`). | — |
| `-c` | `--count` | Search offset: dial ticks forward and backward per wheel ($1 \le c \le 5$). | `2` |
| `-o` | `--output` | Directory where the generated plan should be saved. | `.` |
| `-e` | `--export` | Output format: `txt`, `json`, or `csv`. | `txt` |

---

## Examples

### 1. Default Perturbation ($\pm 2$ clicks)
Test $\pm 2$ ticks around combination `753`:

```bash
python3 loksmith.py -k 753
```

This tests 5 candidate digits per dial ($5^3 = 125$ combinations) with exactly 124 single-click dial turns.

### 2. Export to CSV for Logging
Generate a CSV file to log attempts or script a physical test fixture:

```bash
python3 loksmith.py -k 0421 -c 1 -e csv -o ./output
```

### 3. Machine-Readable JSON Export
Generate structured JSON output containing step-by-step instructions and metadata:

```bash
python3 loksmith.py -k 9182 -c 3 -e json
```

---

## Output Formats

### Text (`.txt`)
Human-readable, step-by-step instructions designed for manual manipulation:

```text
Step 0000001: [531]  <-- Set initial position
Step 0000002: [532]  --> Wheel 3: Turn UP (+1)
Step 0000003: [533]  --> Wheel 3: Turn UP (+1)
Step 0000004: [534]  --> Wheel 3: Turn UP (+1)
Step 0000005: [535]  --> Wheel 3: Turn UP (+1)
Step 0000006: [545]  --> Wheel 2: Turn UP (+1)
```

### CSV (`.csv`)
Includes granular per-wheel columns for automation or tracking:

```csv
step,combination,wheel_1,wheel_2,wheel_3,wheel_changed,direction,action
1,531,5,3,1,,,Set initial position
2,532,5,3,2,3,UP (+1),Wheel 3: Turn UP (+1)
```

### JSON (`.json`)
Structured output containing run statistics and the sequence:

```json
{
  "metadata": {
    "base_key": "753",
    "wheel_count": 3,
    "rotations_offset": 2,
    "unique_values_per_wheel": 5,
    "total_combinations": 125,
    "duplicates_count": 0,
    "total_rotations": 124,
    "rotations_per_test_average": 1.0,
    "strategy": "Deduplicated Multi-Radix Reflected Gray Code"
  },
  "sequence": [ ... ]
}
```

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.