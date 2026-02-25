import dataclasses
import enum

import pysat.formula
import pysat.solvers

from aig_cube.cnf import Cnf


class PySATSolverNames(enum.Enum):
    CADICAL103 = 'cadical103'
    CADICAL153 = 'cadical153'
    CADICAL195 = 'cadical195'
    GLUECARD3 = 'gluecard3'
    GLUECARD4 = 'gluecard4'
    GLUCOSE3 = 'glucose3'
    GLUCOSE4 = 'glucose4'
    GLUCOSE42 = 'glucose42'
    LINGELING = 'lingeling'
    MAPLECHRONO = 'maplechrono'
    MAPLECM = 'maplecm'
    MAPLESAT = 'maplesat'
    MERGESAT3 = 'mergesat3'
    MINICARD = 'minicard'
    MINISAT22 = 'minisat22'
    MINISATGH = 'minisat-gh'


@dataclasses.dataclass(frozen=True)
class PySatResult:
    answer: bool
    model: list[int] | None


def is_satisfiable(
    cnf: Cnf,
    *,
    solver_name: PySATSolverNames | str = PySATSolverNames.CADICAL195,
) -> PySatResult:
    """Check CNF satisfiability with PySAT."""
    solver_name = PySATSolverNames(solver_name)
    _pysat_cnf = pysat.formula.CNF(from_clauses=cnf.get_raw())
    with pysat.solvers.Solver(name=solver_name.value) as _solver:
        _solver.append_formula(_pysat_cnf)
        return PySatResult(_solver.solve(), _solver.get_model())
