#!/usr/bin/env python3
"""Build cubes from an AIG circuit and save each sub-problem as DIMACS CNF.

Usage::

    python scripts/make_cubes.py circuit.aig -o cubes_dir/ --depth 4
    python scripts/make_cubes.py circuit.aig -o cubes_dir/ --depth 3 --candidates 10
"""

import argparse
import os
import sys
import time

sys.setrecursionlimit(10**6)

from aig_cube.aig_parser import load_aig
from aig_cube.solver import CubeAndConquerSolver


def write_dimacs(clauses: list[list[int]], path: str) -> None:
    num_vars = max(abs(lit) for clause in clauses for lit in clause)
    with open(path, "w") as f:
        f.write(f"p cnf {num_vars} {len(clauses)}\n")
        for clause in clauses:
            f.write(" ".join(map(str, clause)) + " 0\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build cubes and save as DIMACS CNF")
    parser.add_argument("input", help="Path to the AIG file")
    parser.add_argument("-o", "--output-dir", required=True, help="Directory to save cube CNFs")
    parser.add_argument("-d", "--depth", type=int, default=4, help="Cube-stage depth (default: 4)")
    parser.add_argument("-k", "--candidates", type=int, default=10, help="Lookahead candidate set size K (default: 10)")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    circuit = load_aig(args.input)
    solver = CubeAndConquerSolver(max_depth=args.depth, candidates_limit=args.candidates)

    t0 = time.time()
    cubes = solver.cube(circuit)
    cube_time = time.time() - t0

    if solver._trivial_result is not None:
        status = "SAT" if solver._trivial_result.answer else "UNSAT"
        print(f"Trivially {status} (no cubes to write)")
        print(f"Cube time: {cube_time:.2f}s")
        return

    print(f"Generated {len(cubes)} cubes in {cube_time:.2f}s")
    for i, instance in enumerate(cubes):
        path = os.path.join(args.output_dir, f"cube_{i:04d}.cnf")
        write_dimacs(instance.cnf.get_raw(), path)
    print(f"Saved to {args.output_dir}/")


if __name__ == "__main__":
    main()
