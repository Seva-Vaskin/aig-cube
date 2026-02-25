#!/usr/bin/env python3
"""Cube-and-Conquer with an external CDCL solver for the Conquer phase.

Builds cubes from an AIG circuit, writes each sub-problem as DIMACS CNF,
then invokes the external solver (e.g. kissat, cadical) on each cube.

Usage::

    python scripts/solve_external.py circuit.aig --solver /path/to/kissat --depth 4
    python scripts/solve_external.py circuit.aig --solver /path/to/cadical --depth 3 -o result.csv
"""

import argparse
import csv
import os
import subprocess
import sys
import tempfile
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


def run_external_solver(solver_path: str, cnf_path: str, timeout: float | None = None) -> tuple[bool | None, float]:
    """Run an external SAT solver and return (answer, elapsed).

    External solvers follow the SAT competition convention:
    exit code 10 = SAT, 20 = UNSAT.
    """
    t0 = time.time()
    try:
        result = subprocess.run(
            [solver_path, cnf_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.time() - t0
        if result.returncode == 10:
            return True, elapsed
        if result.returncode == 20:
            return False, elapsed
        print(f"  Warning: solver returned unexpected code {result.returncode}", file=sys.stderr)
        return None, elapsed
    except subprocess.TimeoutExpired:
        return None, time.time() - t0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cube-and-Conquer with an external solver"
    )
    parser.add_argument("input", help="Path to the AIG file")
    parser.add_argument("-s", "--solver", required=True, help="Path to the external solver executable")
    parser.add_argument("-d", "--depth", type=int, default=4, help="Cube-stage depth (default: 4)")
    parser.add_argument("-k", "--candidates", type=int, default=10, help="Lookahead candidate set size K (default: 10)")
    parser.add_argument("-o", "--output", type=str, default=None, help="Write CSV results to this file")
    parser.add_argument("--timeout", type=float, default=None, help="Per-cube timeout in seconds")
    parser.add_argument("--keep-cnfs", type=str, default=None, help="Directory to keep cube CNFs (otherwise uses temp)")
    args = parser.parse_args()

    circuit = load_aig(args.input)
    cnc = CubeAndConquerSolver(max_depth=args.depth, candidates_limit=args.candidates)

    t_cube_start = time.time()
    cubes = cnc.cube(circuit)
    t_cube_end = time.time()
    cube_time = t_cube_end - t_cube_start

    if cnc._trivial_result is not None:
        status = "SAT" if cnc._trivial_result.answer else "UNSAT"
        total = cube_time
        print(f"Trivially {status}")
        print(f"Cube: {cube_time:.2f}s | Conquer: 0.00s | Total: {total:.2f}s")
        return

    print(f"Cubes: {len(cubes)} (cube time: {cube_time:.2f}s)")
    print(f"Solver: {args.solver}")
    print("-" * 80)

    cnf_dir = args.keep_cnfs
    tmp_dir = None
    if cnf_dir is None:
        tmp_dir = tempfile.mkdtemp(prefix="aig_cube_")
        cnf_dir = tmp_dir
    else:
        os.makedirs(cnf_dir, exist_ok=True)

    answer = False
    conquer_time = 0.0
    for i, instance in enumerate(cubes):
        cnf_path = os.path.join(cnf_dir, f"cube_{i:04d}.cnf")
        write_dimacs(instance.cnf.get_raw(), cnf_path)

        sat, elapsed = run_external_solver(args.solver, cnf_path, args.timeout)
        conquer_time += elapsed

        status_str = {True: "SAT", False: "UNSAT", None: "UNKNOWN"}[sat]
        print(f"  cube {i:4d}/{len(cubes)}: {status_str}  ({elapsed:.2f}s)")

        if sat is True:
            answer = True
            break

    total_time = cube_time + conquer_time
    final = "SAT" if answer else "UNSAT"
    print("-" * 80)
    print(f"Answer: {final}")
    print(f"Cube: {cube_time:.2f}s | Conquer: {conquer_time:.2f}s | Total: {total_time:.2f}s")

    if args.output:
        with open(args.output, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["filename", "answer", "cubes", "cube_time", "conquer_time", "total_time"])
            w.writerow([
                os.path.basename(args.input), final, len(cubes),
                f"{cube_time:.6f}", f"{conquer_time:.6f}", f"{total_time:.6f}",
            ])
        print(f"Results written to {args.output}")

    if tmp_dir is not None:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
