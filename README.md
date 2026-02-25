# aig-cube: Adapting Cube-and-Conquer to CircuitSAT

This repository contains the source code and benchmark data for the paper
**"Adapting Cube-and-Conquer technology to CircuitSAT"** (Submitted to MIPRO 2026, AIS Track).

## Installation

```bash
poetry install
```

## Usage

### Internal solver (PySAT)

Uses one of the SAT solvers bundled with PySAT for the Conquer phase.

```bash
python scripts/solve_internal.py data/miters/mul/mul_8_dadda_vs_column.aig --depth 4
```

Available `--solver` choices (default: `cadical195`):

`cadical103`, `cadical153`, `cadical195`,
`gluecard3`, `gluecard4`,
`glucose3`, `glucose4`, `glucose42`,
`lingeling`,
`maplechrono`, `maplecm`, `maplesat`,
`mergesat3`,
`minicard`, `minisat22`, `minisat-gh`

Example with a specific solver and CSV output:

```bash
python scripts/solve_internal.py data/miters/mul/mul_9_dadda_vs_column.aig \
    --depth 3 --solver cadical195 -o result.csv
```

### External solver (kissat, CaDiCaL, etc.)

Builds cubes from the circuit, writes each sub-problem as DIMACS CNF, and
invokes an external solver binary for the Conquer phase.

```bash
python scripts/solve_external.py data/miters/mul/mul_11_dadda_vs_column.aig \
    --solver /path/to/kissat --depth 4
```

Any solver that follows the SAT competition convention (exit code 10 = SAT,
20 = UNSAT) will work. Additional options:

| Flag | Description |
|------|-------------|
| `--timeout SEC` | Per-cube timeout in seconds |
| `--keep-cnfs DIR` | Save generated DIMACS files instead of using a temp directory |
| `-o FILE` | Write results to a CSV file |

### Cubing only

Runs only the Cube phase — decomposes the circuit into sub-problems and
writes each one as a DIMACS CNF file. The resulting files can then be solved
independently with any SAT solver.

```bash
python scripts/make_cubes.py data/miters/mul_11_dadda_vs_column.aig \
    -o cubes_dir/ --depth 4
```

This produces `cubes_dir/cube_0000.cnf`, `cubes_dir/cube_0001.cnf`, etc.
You can then feed these files to a solver of your choice:

```bash
for f in cubes_dir/*.cnf; do kissat "$f"; done
```

## Benchmarks

The `data/miters/` directory contains miter circuits for integer
multiplier equivalence checking. Four multiplier families are compared:
Dadda (D), Column (C), Karatsuba (K), and Wallace (W). Miters are
provided for bit-widths up to 20.

## Tests

Tests verify solver correctness against the instances in `data/aig_test/`.

```bash
# Run all light tests
pytest -m "not heavy"

# Run all tests including heavy benchmarks
pytest
```


