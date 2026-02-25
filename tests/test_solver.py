"""Unit tests for CubeAndConquerSolver."""

import copy

import pytest

from cirbo.core.circuit import Circuit
from cirbo.core.circuit.gate import Gate, AND, NOT, INPUT, ALWAYS_TRUE, ALWAYS_FALSE

from aig_cube.solver import CubeAndConquerSolver


# =============================================================================
# Helpers
# =============================================================================


def create_aig_xor() -> Circuit:
    """XOR(A, B) built from AND/NOT gates."""
    xor_ckt = Circuit.bare_circuit(input_size=2)
    in_a = xor_ckt.inputs[0]
    in_b = xor_ckt.inputs[1]

    xor_ckt.add_gate(Gate('not_a', NOT, (in_a,)))
    xor_ckt.add_gate(Gate('not_b', NOT, (in_b,)))
    xor_ckt.add_gate(Gate('both_false', AND, ('not_a', 'not_b')))
    xor_ckt.add_gate(Gate('both_true', AND, (in_a, in_b)))
    xor_ckt.add_gate(Gate('not_both_false', NOT, ('both_false',)))
    xor_ckt.add_gate(Gate('not_both_true', NOT, ('both_true',)))
    xor_ckt.add_gate(Gate('xor_out', AND, ('not_both_false', 'not_both_true')))
    xor_ckt.mark_as_output('xor_out')
    return xor_ckt


AIG_XOR_CIRCUIT = create_aig_xor()


def build_aig_miter(left: Circuit, right: Circuit) -> Circuit:
    """Single-output miter using AIG gates only."""
    if left.output_size != 1 or right.output_size != 1:
        raise ValueError("Both circuits must have exactly 1 output")
    if left.input_size != right.input_size:
        raise ValueError("Both circuits must have the same number of inputs")

    miter = Circuit().add_circuit(left, name="ckt1")
    miter.connect_circuit(
        right,
        miter.get_block("ckt1").inputs,
        right.inputs,
        name="ckt2",
    )
    miter.connect_circuit(
        AIG_XOR_CIRCUIT,
        miter.get_block("ckt1").outputs + miter.get_block("ckt2").outputs,
        AIG_XOR_CIRCUIT.inputs,
        name="xor",
    )
    miter.set_outputs(miter.get_block("xor").outputs)
    return miter


def build_multi_output_aig_miter(left: Circuit, right: Circuit) -> Circuit:
    """Multi-output miter using AIG gates only."""
    if left.input_size != right.input_size:
        raise ValueError("Both circuits must have the same number of inputs")
    if left.output_size != right.output_size:
        raise ValueError("Both circuits must have the same number of outputs")

    miter = Circuit().add_circuit(left, name="ckt1")
    miter.connect_circuit(
        right,
        miter.get_block("ckt1").inputs,
        right.inputs,
        name="ckt2",
    )

    xor_outputs = []
    for i, (left_out, right_out) in enumerate(
        zip(
            miter.get_block("ckt1").outputs,
            miter.get_block("ckt2").outputs,
        )
    ):
        xor_ckt = create_aig_xor()
        miter.connect_circuit(
            xor_ckt,
            [left_out, right_out],
            xor_ckt.inputs,
            name=f"xor_{i}",
        )
        xor_outputs.append(miter.get_block(f"xor_{i}").outputs[0])

    if len(xor_outputs) == 1:
        miter.set_outputs(xor_outputs)
    else:
        current_outputs = xor_outputs
        or_idx = 0
        while len(current_outputs) > 1:
            next_outputs = []
            for i in range(0, len(current_outputs), 2):
                if i + 1 < len(current_outputs):
                    a, b = current_outputs[i], current_outputs[i + 1]
                    not_a = f"or_not_a_{or_idx}"
                    not_b = f"or_not_b_{or_idx}"
                    and_gate = f"or_and_{or_idx}"
                    or_gate = f"or_out_{or_idx}"
                    miter.emplace_gate(not_a, NOT, (a,))
                    miter.emplace_gate(not_b, NOT, (b,))
                    miter.emplace_gate(and_gate, AND, (not_a, not_b))
                    miter.emplace_gate(or_gate, NOT, (and_gate,))
                    next_outputs.append(or_gate)
                    or_idx += 1
                else:
                    next_outputs.append(current_outputs[i])
            current_outputs = next_outputs
        miter.set_outputs(current_outputs)

    return miter


# =============================================================================
# Basic SAT
# =============================================================================


class TestBasicSAT:

    def test_and_gate_sat(self):
        circuit = Circuit()
        circuit.add_gate(Gate('a', INPUT))
        circuit.add_gate(Gate('b', INPUT))
        circuit.add_gate(Gate('out', AND, ('a', 'b')))
        circuit.mark_as_output('out')

        result = CubeAndConquerSolver().solve(circuit)
        assert result.answer is True
        assert result.model is not None

    def test_not_gate_sat(self):
        circuit = Circuit()
        circuit.add_gate(Gate('a', INPUT))
        circuit.add_gate(Gate('not_a', NOT, ('a',)))
        circuit.mark_as_output('not_a')

        result = CubeAndConquerSolver().solve(circuit)
        assert result.answer is True
        assert result.model is not None

    def test_chain_and_not_sat(self):
        circuit = Circuit()
        circuit.add_gate(Gate('a', INPUT))
        circuit.add_gate(Gate('b', INPUT))
        circuit.add_gate(Gate('and1', AND, ('a', 'b')))
        circuit.add_gate(Gate('not1', NOT, ('and1',)))
        circuit.add_gate(Gate('not2', NOT, ('not1',)))
        circuit.mark_as_output('not2')

        result = CubeAndConquerSolver().solve(circuit)
        assert result.answer is True

    def test_three_input_and_sat(self):
        circuit = Circuit()
        circuit.add_gate(Gate('a', INPUT))
        circuit.add_gate(Gate('b', INPUT))
        circuit.add_gate(Gate('c', INPUT))
        circuit.add_gate(Gate('and1', AND, ('a', 'b')))
        circuit.add_gate(Gate('and2', AND, ('and1', 'c')))
        circuit.mark_as_output('and2')

        result = CubeAndConquerSolver().solve(circuit)
        assert result.answer is True
        assert result.model is not None


# =============================================================================
# Basic UNSAT
# =============================================================================


class TestBasicUNSAT:

    def test_and_with_negation_unsat(self):
        circuit = Circuit()
        circuit.add_gate(Gate('x', INPUT))
        circuit.add_gate(Gate('not_x', NOT, ('x',)))
        circuit.add_gate(Gate('out', AND, ('x', 'not_x')))
        circuit.mark_as_output('out')

        result = CubeAndConquerSolver().solve(circuit)
        assert result.answer is False

    def test_complex_unsat(self):
        circuit = Circuit()
        circuit.add_gate(Gate('a', INPUT))
        circuit.add_gate(Gate('b', INPUT))
        circuit.add_gate(Gate('not_a', NOT, ('a',)))
        circuit.add_gate(Gate('and1', AND, ('a', 'b')))
        circuit.add_gate(Gate('and2', AND, ('not_a', 'b')))
        circuit.add_gate(Gate('out', AND, ('and1', 'and2')))
        circuit.mark_as_output('out')

        result = CubeAndConquerSolver().solve(circuit)
        assert result.answer is False

    def test_triple_contradiction_unsat(self):
        circuit = Circuit()
        circuit.add_gate(Gate('a', INPUT))
        circuit.add_gate(Gate('b', INPUT))
        circuit.add_gate(Gate('not_a', NOT, ('a',)))
        circuit.add_gate(Gate('and1', AND, ('a', 'not_a')))
        circuit.add_gate(Gate('out', AND, ('and1', 'b')))
        circuit.mark_as_output('out')

        result = CubeAndConquerSolver().solve(circuit)
        assert result.answer is False


# =============================================================================
# XOR
# =============================================================================


class TestXOR:

    def test_xor_is_sat(self):
        result = CubeAndConquerSolver().solve(create_aig_xor())
        assert result.answer is True

    def test_xor_correctness(self):
        xor_ckt = create_aig_xor()
        assert xor_ckt.evaluate([False, False]) == [False]
        assert xor_ckt.evaluate([False, True]) == [True]
        assert xor_ckt.evaluate([True, False]) == [True]
        assert xor_ckt.evaluate([True, True]) == [False]


# =============================================================================
# Equivalence (UNSAT miters)
# =============================================================================


class TestEquivalence:

    def test_identity_circuit(self):
        circuit = Circuit()
        circuit.add_gate(Gate('x', INPUT))
        circuit.add_gate(Gate('not_x', NOT, ('x',)))
        circuit.add_gate(Gate('not_not_x', NOT, ('not_x',)))
        circuit.mark_as_output('not_not_x')

        miter = build_aig_miter(circuit, copy.copy(circuit))
        result = CubeAndConquerSolver().solve(miter)
        assert result.answer is False

    def test_double_negation(self):
        c1 = Circuit()
        c1.add_gate(Gate('x', INPUT))
        c1.mark_as_output('x')

        c2 = Circuit()
        c2.add_gate(Gate('x', INPUT))
        c2.add_gate(Gate('not_x', NOT, ('x',)))
        c2.add_gate(Gate('not_not_x', NOT, ('not_x',)))
        c2.mark_as_output('not_not_x')

        result = CubeAndConquerSolver().solve(build_aig_miter(c1, c2))
        assert result.answer is False

    def test_and_commutativity(self):
        c1 = Circuit()
        c1.add_gate(Gate('a', INPUT))
        c1.add_gate(Gate('b', INPUT))
        c1.add_gate(Gate('out', AND, ('a', 'b')))
        c1.mark_as_output('out')

        c2 = Circuit()
        c2.add_gate(Gate('a', INPUT))
        c2.add_gate(Gate('b', INPUT))
        c2.add_gate(Gate('out', AND, ('b', 'a')))
        c2.mark_as_output('out')

        result = CubeAndConquerSolver().solve(build_aig_miter(c1, c2))
        assert result.answer is False

    def test_de_morgan(self):
        c1 = Circuit()
        c1.add_gate(Gate('a', INPUT))
        c1.add_gate(Gate('b', INPUT))
        c1.add_gate(Gate('and_ab', AND, ('a', 'b')))
        c1.add_gate(Gate('out', NOT, ('and_ab',)))
        c1.mark_as_output('out')

        c2 = Circuit()
        c2.add_gate(Gate('a', INPUT))
        c2.add_gate(Gate('b', INPUT))
        c2.add_gate(Gate('not_a', NOT, ('a',)))
        c2.add_gate(Gate('not_b', NOT, ('b',)))
        c2.add_gate(Gate('not_not_a', NOT, ('not_a',)))
        c2.add_gate(Gate('not_not_b', NOT, ('not_b',)))
        c2.add_gate(Gate('and_nn', AND, ('not_not_a', 'not_not_b')))
        c2.add_gate(Gate('out', NOT, ('and_nn',)))
        c2.mark_as_output('out')

        result = CubeAndConquerSolver().solve(build_aig_miter(c1, c2))
        assert result.answer is False


# =============================================================================
# Non-equivalence (SAT miters)
# =============================================================================


class TestNonEquivalence:

    def test_not_vs_identity(self):
        c1 = Circuit()
        c1.add_gate(Gate('x', INPUT))
        c1.mark_as_output('x')

        c2 = Circuit()
        c2.add_gate(Gate('x', INPUT))
        c2.add_gate(Gate('not_x', NOT, ('x',)))
        c2.mark_as_output('not_x')

        result = CubeAndConquerSolver().solve(build_aig_miter(c1, c2))
        assert result.answer is True

    def test_and_vs_first_input(self):
        c1 = Circuit()
        c1.add_gate(Gate('a', INPUT))
        c1.add_gate(Gate('b', INPUT))
        c1.mark_as_output('a')

        c2 = Circuit()
        c2.add_gate(Gate('a', INPUT))
        c2.add_gate(Gate('b', INPUT))
        c2.add_gate(Gate('out', AND, ('a', 'b')))
        c2.mark_as_output('out')

        result = CubeAndConquerSolver().solve(build_aig_miter(c1, c2))
        assert result.answer is True

    def test_xor_vs_and(self):
        xor_ckt = create_aig_xor()

        and_ckt = Circuit()
        and_ckt.add_gate(Gate('0', INPUT))
        and_ckt.add_gate(Gate('1', INPUT))
        and_ckt.add_gate(Gate('out', AND, ('0', '1')))
        and_ckt.mark_as_output('out')

        result = CubeAndConquerSolver().solve(build_aig_miter(xor_ckt, and_ckt))
        assert result.answer is True


# =============================================================================
# Buggy circuits
# =============================================================================


class TestBuggyCircuits:

    def _buggy_and_for_zeros(self) -> Circuit:
        """AND that returns 1 when both inputs are 0."""
        circuit = Circuit()
        circuit.add_gate(Gate('a', INPUT))
        circuit.add_gate(Gate('b', INPUT))
        circuit.add_gate(Gate('and_ab', AND, ('a', 'b')))
        circuit.add_gate(Gate('not_a', NOT, ('a',)))
        circuit.add_gate(Gate('not_b', NOT, ('b',)))
        circuit.add_gate(Gate('both_zero', AND, ('not_a', 'not_b')))
        circuit.add_gate(Gate('not_and_ab', NOT, ('and_ab',)))
        circuit.add_gate(Gate('not_both_zero', NOT, ('both_zero',)))
        circuit.add_gate(Gate('or_inner', AND, ('not_and_ab', 'not_both_zero')))
        circuit.add_gate(Gate('out', NOT, ('or_inner',)))
        circuit.mark_as_output('out')
        return circuit

    def test_buggy_and_differs_from_normal(self):
        normal = Circuit()
        normal.add_gate(Gate('a', INPUT))
        normal.add_gate(Gate('b', INPUT))
        normal.add_gate(Gate('out', AND, ('a', 'b')))
        normal.mark_as_output('out')

        miter = build_aig_miter(normal, self._buggy_and_for_zeros())
        result = CubeAndConquerSolver().solve(miter)
        assert result.answer is True

    def test_stuck_at_one(self):
        normal = Circuit()
        normal.add_gate(Gate('x', INPUT))
        normal.add_gate(Gate('out', NOT, ('x',)))
        normal.mark_as_output('out')

        buggy = Circuit()
        buggy.add_gate(Gate('x', INPUT))
        buggy.add_gate(Gate('true', ALWAYS_TRUE))
        buggy.mark_as_output('true')

        result = CubeAndConquerSolver().solve(build_aig_miter(normal, buggy))
        assert result.answer is True

    def test_stuck_at_zero(self):
        normal = Circuit()
        normal.add_gate(Gate('x', INPUT))
        normal.mark_as_output('x')

        faulty = Circuit()
        faulty.add_gate(Gate('x', INPUT))
        faulty.add_gate(Gate('false', ALWAYS_FALSE))
        faulty.mark_as_output('false')

        result = CubeAndConquerSolver().solve(build_aig_miter(normal, faulty))
        assert result.answer is True

    def test_inverted_output(self):
        normal = Circuit()
        normal.add_gate(Gate('a', INPUT))
        normal.add_gate(Gate('b', INPUT))
        normal.add_gate(Gate('and', AND, ('a', 'b')))
        normal.mark_as_output('and')

        buggy = Circuit()
        buggy.add_gate(Gate('a', INPUT))
        buggy.add_gate(Gate('b', INPUT))
        buggy.add_gate(Gate('and', AND, ('a', 'b')))
        buggy.add_gate(Gate('not_and', NOT, ('and',)))
        buggy.mark_as_output('not_and')

        result = CubeAndConquerSolver().solve(build_aig_miter(normal, buggy))
        assert result.answer is True


# =============================================================================
# Multi-output miters
# =============================================================================


class TestMultiOutput:

    def test_two_output_equivalent(self):
        c1 = Circuit()
        c1.add_gate(Gate('a', INPUT))
        c1.add_gate(Gate('b', INPUT))
        c1.add_gate(Gate('and', AND, ('a', 'b')))
        c1.add_gate(Gate('not_and', NOT, ('and',)))
        c1.mark_as_output('and')
        c1.mark_as_output('not_and')

        c2 = Circuit()
        c2.add_gate(Gate('a', INPUT))
        c2.add_gate(Gate('b', INPUT))
        c2.add_gate(Gate('and', AND, ('a', 'b')))
        c2.add_gate(Gate('not_and', NOT, ('and',)))
        c2.mark_as_output('and')
        c2.mark_as_output('not_and')

        result = CubeAndConquerSolver().solve(
            build_multi_output_aig_miter(c1, c2)
        )
        assert result.answer is False

    def test_two_output_different(self):
        c1 = Circuit()
        c1.add_gate(Gate('a', INPUT))
        c1.add_gate(Gate('b', INPUT))
        c1.add_gate(Gate('and', AND, ('a', 'b')))
        c1.add_gate(Gate('not_and', NOT, ('and',)))
        c1.mark_as_output('and')
        c1.mark_as_output('not_and')

        c2 = Circuit()
        c2.add_gate(Gate('a', INPUT))
        c2.add_gate(Gate('b', INPUT))
        c2.mark_as_output('a')
        c2.mark_as_output('b')

        result = CubeAndConquerSolver().solve(
            build_multi_output_aig_miter(c1, c2)
        )
        assert result.answer is True


# =============================================================================
# max_depth parameter
# =============================================================================


class TestMaxDepth:

    def test_depth_zero_single_cube(self):
        circuit = Circuit()
        circuit.add_gate(Gate('a', INPUT))
        circuit.add_gate(Gate('b', INPUT))
        circuit.add_gate(Gate('and', AND, ('a', 'b')))
        circuit.mark_as_output('and')

        cubes = CubeAndConquerSolver(max_depth=0).cube(circuit)
        assert len(cubes) == 1

    def test_depth_one_at_most_two_cubes(self):
        circuit = Circuit()
        circuit.add_gate(Gate('a', INPUT))
        circuit.add_gate(Gate('b', INPUT))
        circuit.add_gate(Gate('c', INPUT))
        circuit.add_gate(Gate('and1', AND, ('a', 'b')))
        circuit.add_gate(Gate('and2', AND, ('and1', 'c')))
        circuit.mark_as_output('and2')

        cubes = CubeAndConquerSolver(max_depth=1).cube(circuit)
        assert len(cubes) <= 2

    def test_depth_default(self):
        circuit = Circuit()
        circuit.add_gate(Gate('a', INPUT))
        circuit.add_gate(Gate('b', INPUT))
        circuit.add_gate(Gate('and', AND, ('a', 'b')))
        circuit.mark_as_output('and')

        cubes_default = CubeAndConquerSolver().cube(circuit)
        cubes_explicit = CubeAndConquerSolver(max_depth=4).cube(circuit)
        assert len(cubes_default) == len(cubes_explicit)

    def test_depth_sat_correctness(self):
        circuit = Circuit()
        circuit.add_gate(Gate('a', INPUT))
        circuit.add_gate(Gate('b', INPUT))
        circuit.add_gate(Gate('and', AND, ('a', 'b')))
        circuit.mark_as_output('and')

        result = CubeAndConquerSolver(max_depth=1).solve(circuit)
        assert result.answer is True

    def test_depth_unsat_correctness(self):
        circuit = Circuit()
        circuit.add_gate(Gate('x', INPUT))
        circuit.add_gate(Gate('not_x', NOT, ('x',)))
        circuit.add_gate(Gate('out', AND, ('x', 'not_x')))
        circuit.mark_as_output('out')

        result = CubeAndConquerSolver(max_depth=1).solve(circuit)
        assert result.answer is False

    def test_higher_depth_more_cubes(self):
        circuit = Circuit()
        circuit.add_gate(Gate('a', INPUT))
        circuit.add_gate(Gate('b', INPUT))
        circuit.add_gate(Gate('c', INPUT))
        circuit.add_gate(Gate('and1', AND, ('a', 'b')))
        circuit.add_gate(Gate('and2', AND, ('and1', 'c')))
        circuit.mark_as_output('and2')

        c0 = CubeAndConquerSolver(max_depth=0).cube(circuit)
        c1 = CubeAndConquerSolver(max_depth=1).cube(circuit)
        c2 = CubeAndConquerSolver(max_depth=2).cube(circuit)
        assert len(c0) <= len(c1) <= len(c2)

    def test_depth_beyond_natural(self):
        circuit = Circuit()
        circuit.add_gate(Gate('a', INPUT))
        circuit.add_gate(Gate('b', INPUT))
        circuit.add_gate(Gate('and', AND, ('a', 'b')))
        circuit.mark_as_output('and')

        cubes_high = CubeAndConquerSolver(max_depth=1000).cube(circuit)
        cubes_moderate = CubeAndConquerSolver(max_depth=100).cube(circuit)
        assert len(cubes_high) == len(cubes_moderate)

    def test_depth_limiting(self):
        xor_ckt = create_aig_xor()
        c0 = CubeAndConquerSolver(max_depth=0).cube(xor_ckt)
        c1 = CubeAndConquerSolver(max_depth=1).cube(xor_ckt)
        c_all = CubeAndConquerSolver(max_depth=1000).cube(xor_ckt)

        assert len(c0) == 1
        assert len(c1) <= 2
        assert len(c1) <= len(c_all)
