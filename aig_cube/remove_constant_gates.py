import logging

from cirbo.core.circuit import Circuit, Gate, gate, Label
from cirbo.core.circuit.transformer import Transformer

__all__ = [
    'RemoveConstantGates',
]

logger = logging.getLogger(__name__)


class RemoveConstantGates(Transformer):
    """Simplify a circuit by propagating and removing constant gates.

    When a gate has a constant (ALWAYS_TRUE or ALWAYS_FALSE) operand, the
    transformer computes the simplified form based on truth-table evaluation
    with the known constant value.
    """

    __idempotent__: bool = True

    def __init__(self):
        super().__init__(post_transformers=())

    def _transform(self, circuit: Circuit) -> Circuit:
        for g in circuit.gates.values():
            if len(g.operands) > 2:
                raise ValueError(
                    f"Gate {g.label} has {len(g.operands)} operands. "
                    "Only binary/unary/nullary gates are supported."
                )

        new_circuit = Circuit()

        const_map: dict[Label, bool] = {}
        label_remap: dict[Label, Label] = {}

        def resolve_label(lbl: Label) -> Label:
            return label_remap.get(lbl, lbl)

        for g in circuit.top_sort(inverse=True):
            resolved_operands = tuple(resolve_label(op) for op in g.operands)

            if g.gate_type == gate.INPUT:
                new_circuit.emplace_gate(g.label, g.gate_type, g.operands)
                continue

            if g.gate_type == gate.ALWAYS_TRUE:
                const_map[g.label] = True
                continue
            if g.gate_type == gate.ALWAYS_FALSE:
                const_map[g.label] = False
                continue

            const_indices = [
                i for i, op in enumerate(resolved_operands) if op in const_map
            ]

            if not const_indices:
                new_circuit.emplace_gate(g.label, g.gate_type, resolved_operands)
                continue

            if len(const_indices) == 1 and len(resolved_operands) == 2:
                const_idx = const_indices[0]
                const_val = const_map[resolved_operands[const_idx]]
                non_const_idx = 1 - const_idx
                non_const_op = resolved_operands[non_const_idx]

                args0 = [None] * 2
                args0[const_idx] = const_val
                args0[non_const_idx] = False
                val0 = g.operator(*args0)

                args1 = [None] * 2
                args1[const_idx] = const_val
                args1[non_const_idx] = True
                val1 = g.operator(*args1)

                if val0 == val1:
                    const_map[g.label] = val0
                elif val0 is False and val1 is True:
                    label_remap[g.label] = non_const_op
                elif val0 is True and val1 is False:
                    operand_gate = new_circuit.gates.get(non_const_op)
                    if operand_gate and operand_gate.gate_type == gate.NOT:
                        label_remap[g.label] = operand_gate.operands[0]
                    else:
                        new_circuit.emplace_gate(
                            g.label, gate.NOT, (non_const_op,)
                        )
                else:
                    raise RuntimeError(
                        f"Unexpected evaluation result for gate {g.label}: "
                        f"val0={val0}, val1={val1}"
                    )
                continue

            if len(const_indices) == len(resolved_operands):
                args = [const_map[op] for op in resolved_operands]
                val = g.operator(*args)
                const_map[g.label] = val
                continue

            raise RuntimeError(f"Unexpected case: gate {g.label}.")

        final_inputs = [in_ for in_ in circuit.inputs if in_ not in const_map]
        new_circuit.set_inputs(final_inputs)

        final_outputs = [
            out
            for out in map(resolve_label, circuit.outputs)
            if out not in const_map
        ]
        new_circuit.set_outputs(final_outputs)

        return new_circuit
