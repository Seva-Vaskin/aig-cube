#!/usr/bin/env python3
"""Solve an AIG circuit using the internal PySAT-backed Cube-and-Conquer solver.

This uses PySAT's bundled solvers (e.g. CaDiCaL 1.9.5) for the Conquer phase.
For paper benchmarks the external solver scripts should be used instead.

Usage::

    python scripts/solve_internal.py circuit.aig --depth 4
    python scripts/solve_internal.py circuit.aig --depth 3 --solver cadical195 -o result.csv
"""

import argparse
import csv
import os
import sys
import time

sys.setrecursionlimit(10**6)

from aig_cube.aig_parser import load_aig
from aig_cube.sat import PySATSolverNames
from aig_cube.solver import CubeAndConquerSolver


def main() -> None:
    solver_choices = [s.value for s in PySATSolverNames]

    parser = argparse.ArgumentParser(
        description="Solve AIG with internal PySAT Cube-and-Conquer"
    )
    parser.add_argument("input", help="Path to the AIG file")
    parser.add_argument("-d", "--depth", type=int, default=4, help="Cube-stage depth (default: 4)")
    parser.add_argument("-k", "--candidates", type=int, default=10, help="Lookahead candidate set size K (default: 10)")
    parser.add_argument("-s", "--solver", type=str, default="cadical195",
                        choices=solver_choices, help="PySAT solver name (default: cadical195)")
    parser.add_argument("-o", "--output", type=str, default=None, help="Write CSV result to this file")
    args = parser.parse_args()

    circuit = load_aig(args.input)
    solver = CubeAndConquerSolver(
        max_depth=args.depth,
        candidates_limit=args.candidates,
        solver_name=PySATSolverNames(args.solver),
    )

    t0 = time.time()
    result = solver.solve(circuit)
    total_time = time.time() - t0

    status = "SAT" if result.answer else "UNSAT"
    print(f"Answer: {status}")
    print(f"Total time: {total_time:.2f}s")

    if args.output:
        with open(args.output, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["filename", "answer", "total_time"])
            w.writerow([os.path.basename(args.input), status, f"{total_time:.6f}"])
        print(f"Results written to {args.output}")


if __name__ == "__main__":
    main()
