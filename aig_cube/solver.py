import copy
import logging
import sys
from dataclasses import dataclass

from cirbo.core.circuit import Circuit, Transformer
from cirbo.core.circuit.gate import ALWAYS_TRUE, ALWAYS_FALSE, INPUT, AND, NOT
from cirbo.minimization import MergeUnaryOperators

from aig_cube.circuit_instance import CircuitSatInstance, AssignmentStatus
from aig_cube.remove_constant_gates import RemoveConstantGates
from aig_cube.sat import PySatResult, PySATSolverNames, is_satisfiable

logger = logging.getLogger(__name__)

@dataclass
class _GateWeightResult:
    weight: int | None = None
    forced_value: bool | None = None

    @property
    def is_forced(self) -> bool:
        return self.forced_value is not None


@dataclass
class _CubeGateSelection:
    label: str
    forced_value: bool | None = None

    @property
    def is_forced(self) -> bool:
        return self.forced_value is not None


class CubeAndConquerSolver:
    """Cube-and-Conquer solver operating natively on AIG circuits.

    Parameters
    ----------
    max_depth : int
        Maximum recursion depth *d* for the Cube stage (default 4).
    candidates_limit : int
        Number of top-scoring gates *K* to evaluate during lookahead
        (Stage 2 of gate selection).  Default is 10.
    solver_name : PySATSolverNames
        PySAT solver used in the Conquer stage.
    """

    DEFAULT_MAX_DEPTH = 4
    DEFAULT_CANDIDATES_LIMIT = 10
    DEFAULT_SOLVER_NAME = PySATSolverNames.CADICAL195

    def __init__(
        self,
        max_depth: int = DEFAULT_MAX_DEPTH,
        candidates_limit: int = DEFAULT_CANDIDATES_LIMIT,
        solver_name: PySATSolverNames = DEFAULT_SOLVER_NAME,
    ):
        self.max_depth = max_depth
        self.candidates_limit = candidates_limit
        self.solver_name = solver_name
        self._trivial_result: PySatResult | None = None

    def solve(self, circuit: Circuit) -> PySatResult:
        """Run full Cube-and-Conquer (Algorithm 1)."""
        sys.setrecursionlimit(max(sys.getrecursionlimit(), 10 ** 6))
        self._trivial_result = None
        cubes = self.cube(circuit)
        if self._trivial_result is not None:
            return self._trivial_result
        result = self.conquer(cubes)
        return result

    def cube(self, circuit: Circuit) -> list[CircuitSatInstance]:
        """Cube stage: decompose *circuit* into sub-problems."""
        assert circuit.output_size == 1, (
            f"CnC solver expects a single-output circuit, got {circuit.output_size}"
        )
        original_circuit = circuit
        circuit = Transformer.apply_transformers(
            circuit, [RemoveConstantGates(), MergeUnaryOperators()]
        )
        logger.info(
            "Cube stage: circuit has %d gates", circuit.size
        )
        if circuit.output_size == 0:
            zero_inputs = [False] * original_circuit.input_size
            [is_true] = original_circuit.evaluate(zero_inputs)
            logger.info(
                "Output is constant %s — trivially %s",
                is_true, "SAT" if is_true else "UNSAT",
            )
            self._trivial_result = PySatResult(answer=is_true, model=None)
            return []
        instance = CircuitSatInstance.from_circuit(circuit)

        if instance is None:
            return []

        logger.info(
            "Instance: %d gates, %d clauses",
            instance.circuit.size,
            len(instance.cnf.get_raw()),
        )
        return list(self._cube(instance))

    def conquer(self, cubes: list[CircuitSatInstance]) -> PySatResult:
        """Conquer stage: solve each sub-problem with CDCL."""
        for instance in cubes:
            result = is_satisfiable(
                cnf=instance.cnf,
                solver_name=self.solver_name,
            )
            if result.answer:
                model: list[int] = [0] * len(instance.gates_config)
                for gc in instance.gates_config.values():
                    if not gc.is_input:
                        continue
                    assert result.model is not None
                    model[gc.idx - 1] = gc.idx if gc.value else -gc.idx
                return PySatResult(answer=True, model=model)
        return PySatResult(answer=False, model=None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cube(
        self, instance: CircuitSatInstance, depth: int = 0
    ) -> list[CircuitSatInstance]:
        """Recursive cubing (Algorithm 2)."""
        if self._should_stop(instance, depth):
            logger.info(
                "Leaf at depth %d: %d gates, %d clauses",
                depth,
                instance.circuit.size,
                len(instance.cnf.get_raw()),
            )
            return [instance]

        selection = self._select_gate(instance)
        if selection is None:
            return [instance]

        if selection.is_forced:
            logger.debug(
                "Forced %s=%s (other branch conflicts)",
                selection.label,
                selection.forced_value,
            )
            instance.assign(selection.label, selection.forced_value)
            return self._cube(instance, depth + 1)

        result = []
        for value in (False, True):
            branch = copy.deepcopy(instance)
            branch.assign(selection.label, value)
            result.extend(self._cube(branch, depth + 1))
        return result

    def _should_stop(self, instance: CircuitSatInstance, depth: int) -> bool:
        if instance.circuit.input_size == 0:
            return True
        if depth >= self.max_depth:
            return True
        return False

    def _select_gate(
        self, instance: CircuitSatInstance
    ) -> _CubeGateSelection | None:
        """Select the best branching gate (Section 3.4)."""
        candidates = self._rank_candidates(instance)
        if not candidates:
            return None

        best_label = None
        best_weight = 0

        for label in candidates:
            wr = self._weight_gate(instance, label)
            if wr.is_forced:
                return _CubeGateSelection(label=label, forced_value=wr.forced_value)
            if wr.weight > best_weight:
                best_label, best_weight = label, wr.weight

        assert best_label is not None
        return _CubeGateSelection(label=best_label)

    def _rank_candidates(self, instance: CircuitSatInstance) -> list[str]:
        """Stage 1: structural scoring sigma(g) = (indeg+1)*(outdeg+1)."""
        circuit = instance.circuit
        scores: list[tuple[int, str]] = []

        for label in circuit.gates:
            g = circuit.get_gate(label)
            if g.gate_type in (ALWAYS_TRUE, ALWAYS_FALSE, NOT):
                continue
            assert g.gate_type in (AND, INPUT)

            indegree = len(g.operands)

            outdegree = 0
            for user_label in circuit.get_gate_users(label):
                user = circuit.get_gate(user_label)
                if user.gate_type == NOT:
                    outdegree += len(circuit.get_gate_users(user_label))
                else:
                    outdegree += 1

            score = (indegree + 1) * (outdegree + 1)
            scores.append((score, label))

        scores.sort(key=lambda x: x[0], reverse=True)
        return [label for _, label in scores[: self.candidates_limit]]

    def _weight_gate(
        self, instance: CircuitSatInstance, label: str
    ) -> _GateWeightResult:
        """Stage 2: lookahead mu(g) = Delta_0(g) * Delta_1(g)."""
        start_size = instance.circuit.size
        weight = 1
        for val in (False, True):
            branch = copy.deepcopy(instance)
            status = branch.assign(label, val)
            if status != AssignmentStatus.OK:
                return _GateWeightResult(forced_value=not val)
            delta = start_size - branch.circuit.size
            assert delta > 0
            weight *= delta
        return _GateWeightResult(weight=weight)
