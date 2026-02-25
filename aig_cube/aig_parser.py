import io
import logging
import pathlib

from cirbo.core.circuit import gate
from cirbo.core.circuit.circuit import Circuit

logger = logging.getLogger(__name__)


class AIGParseError(Exception):
    pass


def load_aig(file_path: str) -> Circuit:
    """Load an AIG/AAG file and return a Circuit."""
    return AIGParser().parse_file(file_path)


class AIGParser:
    """Parser for AIGER format files (both ASCII .aag and binary .aig)."""

    def __init__(self):
        self._circuit: Circuit = Circuit()
        self._literal_to_label: dict[int, gate.Label] = {}
        self._symbols: dict[str, dict[int, str]] = {'i': {}, 'o': {}, 'l': {}}

    def parse_file(
        self, file_path: str, *, binary: bool | None = None
    ) -> Circuit:
        path = pathlib.Path(file_path)
        if binary:
            with path.open('rb') as f:
                return self._parse_binary(f, strict_header=False)
        elif binary is False:
            with path.open('r') as f:
                return self._parse_ascii(f, strict_header=False)
        else:
            if path.suffix == '.aag':
                with path.open('r') as f:
                    return self._parse_ascii(f)
            elif path.suffix == '.aig':
                with path.open('rb') as f:
                    return self._parse_binary(f)
            else:
                raise AIGParseError(
                    f"Unknown file extension: {path.suffix}"
                )

    # ----- ASCII format -----

    def _parse_ascii(self, stream, *, strict_header: bool = True) -> Circuit:
        self._circuit = Circuit()
        self._literal_to_label = {}
        self._symbols = {'i': {}, 'o': {}, 'l': {}}

        header_line = stream.readline().strip()
        header_parts = header_line.split()
        valid_headers = ['aag'] if strict_header else ['aag', 'aig']
        if len(header_parts) < 6 or header_parts[0] not in valid_headers:
            raise AIGParseError(f"Invalid AAG header: {header_line}")

        m, i, l, o, a = map(int, header_parts[1:6])
        if l != 0:
            raise AIGParseError("Latches not supported (L must be 0).")

        self._literal_to_label[0] = self._get_or_create_false()
        self._literal_to_label[1] = self._get_or_create_true()

        input_literals: list[int] = []
        for idx in range(i):
            lit = int(stream.readline().strip())
            input_literals.append(lit)
            label = f"i{idx}"
            self._circuit._emplace_gate(label, gate.INPUT)
            self._literal_to_label[lit] = label

        output_literals: list[int] = []
        for _ in range(o):
            output_literals.append(int(stream.readline().strip()))

        and_gates: list[tuple[int, int, int]] = []
        for _ in range(a):
            parts = stream.readline().strip().split()
            lhs, rhs0, rhs1 = map(int, parts)
            and_gates.append((lhs, rhs0, rhs1))
            self._literal_to_label[lhs] = f"n{lhs // 2}"

        self._create_and_gates_topological(and_gates)

        for line in stream:
            line = line.strip()
            if not line or line.startswith('c'):
                break
            if line[0] in 'ilo' and len(line) > 1:
                self._parse_symbol(line)

        self._apply_symbols(input_literals, output_literals)
        self._set_outputs(output_literals)
        return self._circuit

    # ----- Binary format -----

    def _parse_binary(self, stream, *, strict_header: bool = True) -> Circuit:
        self._circuit = Circuit()
        self._literal_to_label = {}
        self._symbols = {'i': {}, 'o': {}, 'l': {}}

        header_line = b''
        while True:
            ch = stream.read(1)
            if ch == b'\n':
                break
            if not ch:
                raise AIGParseError("Unexpected EOF in header")
            header_line += ch

        header_str = header_line.decode('ascii').strip()
        header_parts = header_str.split()
        valid_headers = ['aig'] if strict_header else ['aag', 'aig']
        if len(header_parts) < 6 or header_parts[0] not in valid_headers:
            raise AIGParseError(f"Invalid AIG header: {header_str}")

        m, i, l, o, a = map(int, header_parts[1:6])
        if l != 0:
            raise AIGParseError("Latches not supported (L must be 0).")

        self._literal_to_label[0] = self._get_or_create_false()
        self._literal_to_label[1] = self._get_or_create_true()

        input_literals: list[int] = []
        for idx in range(i):
            lit = 2 * (idx + 1)
            input_literals.append(lit)
            label = f"i{idx}"
            self._circuit._emplace_gate(label, gate.INPUT)
            self._literal_to_label[lit] = label

        output_literals: list[int] = []
        for _ in range(o):
            line = b''
            while True:
                ch = stream.read(1)
                if ch == b'\n':
                    break
                if not ch:
                    raise AIGParseError("Unexpected EOF in outputs")
                line += ch
            output_literals.append(int(line.decode('ascii').strip()))

        for idx in range(a):
            lhs = 2 * (i + l + idx + 1)
            delta0 = self._decode_binary_number(stream)
            delta1 = self._decode_binary_number(stream)
            rhs0 = lhs - delta0
            rhs1 = rhs0 - delta1
            self._add_and_gate(lhs, rhs0, rhs1)

        try:
            remaining = stream.read()
            if remaining:
                text_part = remaining.decode('ascii', errors='ignore')
                for text_line in text_part.split('\n'):
                    text_line = text_line.strip()
                    if not text_line or text_line.startswith('c'):
                        break
                    if text_line[0] in 'ilo' and len(text_line) > 1:
                        self._parse_symbol(text_line)
        except Exception:
            pass

        self._apply_symbols(input_literals, output_literals)
        self._set_outputs(output_literals)
        return self._circuit

    # ----- Shared helpers -----

    @staticmethod
    def _decode_binary_number(stream) -> int:
        result = 0
        shift = 0
        while True:
            byte_data = stream.read(1)
            if not byte_data:
                raise AIGParseError("Unexpected EOF decoding number")
            byte = byte_data[0]
            result |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                break
            shift += 7
        return result

    def _add_and_gate(self, lhs: int, rhs0: int, rhs1: int) -> None:
        and_label = f"n{lhs // 2}"
        self._literal_to_label[lhs] = and_label
        self._add_and_gate_internal(lhs, rhs0, rhs1)

    def _add_and_gate_internal(self, lhs: int, rhs0: int, rhs1: int) -> None:
        op0 = self._get_literal_label(rhs0)
        op1 = self._get_literal_label(rhs1)
        and_label = self._literal_to_label[lhs]
        self._circuit._emplace_gate(and_label, gate.AND, (op0, op1))

    def _create_and_gates_topological(
        self, and_gates: list[tuple[int, int, int]]
    ) -> None:
        lhs_set = {lhs for lhs, _, _ in and_gates}
        gate_map = {lhs: (rhs0, rhs1) for lhs, rhs0, rhs1 in and_gates}
        created: set[int] = set()

        def create_gate(lhs: int) -> None:
            if lhs in created:
                return
            rhs0, rhs1 = gate_map[lhs]
            for rhs in (rhs0, rhs1):
                base = rhs & ~1
                if base in lhs_set and base not in created:
                    create_gate(base)
            self._add_and_gate_internal(lhs, rhs0, rhs1)
            created.add(lhs)

        for lhs, _, _ in and_gates:
            create_gate(lhs)

    def _get_literal_label(self, literal: int) -> gate.Label:
        if literal in self._literal_to_label:
            return self._literal_to_label[literal]
        if literal % 2 == 1:
            base = literal - 1
            if base not in self._literal_to_label:
                raise AIGParseError(f"Undefined base literal {base}")
            base_label = self._literal_to_label[base]
            not_label = f"not_{base_label}"
            if not_label not in self._circuit.gates:
                self._circuit._emplace_gate(not_label, gate.NOT, (base_label,))
            self._literal_to_label[literal] = not_label
            return not_label
        raise AIGParseError(f"Undefined literal: {literal}")

    def _get_or_create_false(self) -> gate.Label:
        label = "__false__"
        if label not in self._circuit.gates:
            self._circuit._emplace_gate(label, gate.ALWAYS_FALSE)
        return label

    def _get_or_create_true(self) -> gate.Label:
        label = "__true__"
        if label not in self._circuit.gates:
            self._circuit._emplace_gate(label, gate.ALWAYS_TRUE)
        return label

    def _parse_symbol(self, line: str) -> None:
        if len(line) < 2:
            return
        sym_type = line[0]
        rest = line[1:]
        space_idx = rest.find(' ')
        if space_idx == -1:
            return
        try:
            pos = int(rest[:space_idx])
            name = rest[space_idx + 1:]
            self._symbols[sym_type][pos] = name
        except ValueError:
            pass

    def _apply_symbols(
        self, input_literals: list[int], output_literals: list[int]
    ) -> None:
        for idx, lit in enumerate(input_literals):
            if idx in self._symbols['i']:
                old_label = self._literal_to_label[lit]
                new_label = self._symbols['i'][idx]
                if old_label != new_label and old_label in self._circuit.gates:
                    self._rename_gate(old_label, new_label, lit)

    def _rename_gate(
        self, old_label: gate.Label, new_label: gate.Label, literal: int
    ) -> None:
        if new_label in self._circuit.gates:
            return
        old_gate = self._circuit.gates[old_label]
        old_not = f"not_{old_label}"
        new_not = f"not_{new_label}"

        if old_not in self._circuit.gates:
            del self._circuit._gates[old_not]
            if old_not in self._circuit._gate_to_users:
                del self._circuit._gate_to_users[old_not]
            for lit, lbl in list(self._literal_to_label.items()):
                if lbl == old_not:
                    self._literal_to_label[lit] = new_not

        del self._circuit._gates[old_label]
        if old_label in self._circuit._inputs:
            self._circuit._inputs.remove(old_label)
        if old_label in self._circuit._gate_to_users:
            del self._circuit._gate_to_users[old_label]

        self._circuit._emplace_gate(
            new_label, old_gate.gate_type, old_gate.operands
        )
        self._literal_to_label[literal] = new_label

        for lit, lbl in list(self._literal_to_label.items()):
            if lbl == new_not and new_not not in self._circuit.gates:
                self._circuit._emplace_gate(new_not, gate.NOT, (new_label,))
                break

        for gate_label, g in list(self._circuit._gates.items()):
            new_ops = []
            changed = False
            for op in g.operands:
                if op == old_label:
                    new_ops.append(new_label)
                    changed = True
                elif op == old_not:
                    new_ops.append(new_not)
                    changed = True
                else:
                    new_ops.append(op)
            if changed:
                self._circuit._gates[gate_label] = gate.Gate(
                    gate_label, g.gate_type, tuple(new_ops)
                )
                for nl in (new_label, new_not):
                    if nl in new_ops:
                        if nl not in self._circuit._gate_to_users:
                            self._circuit._gate_to_users[nl] = []
                        if gate_label not in self._circuit._gate_to_users[nl]:
                            self._circuit._gate_to_users[nl].append(gate_label)

    def _set_outputs(self, output_literals: list[int]) -> None:
        output_labels: list[gate.Label] = []
        for idx, lit in enumerate(output_literals):
            label = self._get_literal_label(lit)
            if idx in self._symbols['o']:
                output_name = self._symbols['o'][idx]
                if output_name not in self._circuit.gates:
                    self._circuit._emplace_gate(
                        output_name, gate.IFF, (label,)
                    )
                    label = output_name
            output_labels.append(label)
        self._circuit.set_outputs(output_labels)
