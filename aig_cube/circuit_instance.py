import enum
from dataclasses import dataclass

from cirbo.core.circuit import Circuit, INPUT, Transformer
from cirbo.core.circuit.gate import NOT, AND, ALWAYS_FALSE, ALWAYS_TRUE, Gate

from aig_cube.cnf import Cnf, tseytin_transformation
from aig_cube.remove_constant_gates import RemoveConstantGates


class AssignmentStatus(enum.Enum):
    OK = "OK"
    CONFLICT = "CONFLICT"


@dataclass
class GateConfig:
    label: str
    idx: int
    is_input: bool
    value: bool | None = None


class CircuitSatInstance:
    """A mutable (circuit, CNF) pair used during cubing."""

    def __init__(self, circuit: Circuit):
        self.circuit = circuit
        self._check_circuit()
        self.gates_config: dict[str, GateConfig] = {}
        self.cnf = tseytin_transformation(self.circuit)
        for label in self.circuit.gates:
            gate_idx = self.cnf.get_var(label)
            is_input = self.circuit.get_gate(label).gate_type == INPUT
            self.gates_config[label] = GateConfig(
                label=label, idx=gate_idx, is_input=is_input
            )

    @classmethod
    def from_circuit(cls, circuit: Circuit) -> "CircuitSatInstance | None":
        """Build an instance and fix the output to True."""
        assert circuit.output_size == 1
        instance = cls(circuit)
        status = instance.assign(instance.circuit.outputs[0], True)
        if status != AssignmentStatus.OK:
            return None
        return instance

    def simplify(self) -> None:
        """Propagate constants through the AIG (output-direction, Table 1)."""
        self.circuit = Transformer.apply_transformers(
            self.circuit, [RemoveConstantGates()]
        )

    def assign(self, label: str, value: bool) -> AssignmentStatus:
        """Assign *value* to gate *label* and propagate (Section 3.3)."""
        status = self._assign_and_propagate(label, value)
        if status != AssignmentStatus.OK:
            return status
        self.simplify()
        return AssignmentStatus.OK

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_circuit(self) -> None:
        for g in self.circuit.gates.values():
            if g.gate_type == INPUT:
                continue
            if g.gate_type == AND:
                if len(g.operands) != 2:
                    raise ValueError(
                        f"AND gate {g.label} has {len(g.operands)} operands"
                    )
                continue
            if g.gate_type == NOT:
                if len(g.operands) != 1:
                    raise ValueError(
                        f"NOT gate {g.label} has {len(g.operands)} operands"
                    )
                continue
            raise ValueError(
                f"Gate {g.label} has unsupported type {g.gate_type.name}"
            )

    def _assign_and_propagate(
        self, label: str, value: bool
    ) -> AssignmentStatus:
        gate = self.circuit.get_gate(label)

        if gate.gate_type in (ALWAYS_TRUE, ALWAYS_FALSE):
            if gate.operator() != value:
                return AssignmentStatus.CONFLICT
            return AssignmentStatus.OK

        lit = self.gates_config[label].idx
        self.cnf.add_clause([lit if value else -lit])

        if gate.gate_type == INPUT:
            inputs_to_true: list[str] = []
            inputs_to_false: list[str] = []
            (inputs_to_true if value else inputs_to_false).append(label)
            self.circuit = self.circuit.replace_inputs(
                inputs_to_true, inputs_to_false
            )
            self.gates_config[label].value = value
            return AssignmentStatus.OK

        for operand in gate.operands:
            self.circuit._remove_user(gate_label=operand, user=label)

        new_gate_type = ALWAYS_TRUE if value else ALWAYS_FALSE
        new_gate = Gate(label=label, gate_type=new_gate_type, operands=())
        self.circuit._gates[label] = new_gate

        if gate.gate_type == NOT:
            return self._assign_and_propagate(gate.operands[0], not value)

        if gate.gate_type == AND and value:
            for operand_label in gate.operands:
                status = self._assign_and_propagate(operand_label, True)
                if status != AssignmentStatus.OK:
                    return status
            return AssignmentStatus.OK

        if gate.gate_type == AND and not value:
            assert len(gate.operands) == 2
            lit0 = self.gates_config[gate.operands[0]].idx
            lit1 = self.gates_config[gate.operands[1]].idx
            self.cnf.add_clause([-lit0, -lit1])
            return AssignmentStatus.OK

        raise RuntimeError(
            f"Propagation error: unsupported gate type {gate.gate_type}"
        )
