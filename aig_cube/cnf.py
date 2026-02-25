import collections

from cirbo.core.circuit import (
    ALWAYS_FALSE,
    ALWAYS_TRUE,
    AND,
    Circuit,
    GateType,
    INPUT,
    NOT,
)

Lit = int
Clause = list[Lit]
CnfRaw = list[Clause]
VarMap = dict[str, Lit]


class Cnf:
    """CNF formula with gate-label-to-variable mapping."""

    def __init__(
        self,
        cnf: CnfRaw | None = None,
        var_map: VarMap | None = None,
    ):
        self._cnf: CnfRaw = cnf if cnf is not None else []
        self._var_map: VarMap = var_map if var_map is not None else {}

    def add_clause(self, clause: Clause) -> None:
        self._cnf.append(clause)

    def get_raw(self) -> CnfRaw:
        return self._cnf

    @property
    def var_map(self) -> VarMap:
        return self._var_map

    def get_var(self, label: str) -> Lit | None:
        return self._var_map.get(label)


def tseytin_transformation(circuit: Circuit) -> Cnf:
    """Convert an AIG circuit to CNF via Tseytin encoding (iterative)."""
    next_lit = 0

    def _new_lit() -> Lit:
        nonlocal next_lit
        next_lit += 1
        return next_lit

    saved_lits: dict[str, Lit] = collections.defaultdict(_new_lit)

    for input_label in circuit.inputs:
        _ = saved_lits[input_label]

    cnf: CnfRaw = []

    def _process_all(root: str) -> Lit:
        """Iterative post-order traversal to encode all gates reachable from *root*."""
        stack: list[tuple[str, bool]] = [(root, False)]
        while stack:
            label, expanded = stack.pop()
            if label in saved_lits:
                continue
            if not expanded:
                gate = circuit.get_gate(label)
                stack.append((label, True))
                for op in reversed(gate.operands):
                    if op not in saved_lits:
                        stack.append((op, False))
                continue
            gate = circuit.get_gate(label)
            lits = [saved_lits[op] for op in gate.operands]
            top = saved_lits[label]

            if gate.gate_type == INPUT:
                pass
            elif gate.gate_type == ALWAYS_TRUE:
                cnf.append([top])
            elif gate.gate_type == ALWAYS_FALSE:
                cnf.append([-top])
            elif gate.gate_type == NOT:
                cnf.append([lits[0], top])
                cnf.append([-lits[0], -top])
            elif gate.gate_type == AND:
                common = [top]
                for lit in lits:
                    common.append(-lit)
                    cnf.append([lit, -top])
                cnf.append(common)
            else:
                raise ValueError(
                    f"Unsupported gate type: {gate.gate_type} for gate {label}"
                )
        return saved_lits[root]

    for i in range(circuit.output_size):
        out_lit = _process_all(circuit.output_at_index(i))
        cnf.append([out_lit])

    return Cnf(cnf, var_map=dict(saved_lits))
