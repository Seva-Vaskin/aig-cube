"""Benchmark tests using pre-built AIG instances.

Heavy tests are marked with ``@pytest.mark.heavy`` and can be skipped::

    pytest -m "not heavy"
"""

import pathlib

import pytest

from cirbo.core.circuit import Circuit

from aig_cube.aig_parser import load_aig
from aig_cube.solver import CubeAndConquerSolver

ROOT = pathlib.Path(__file__).resolve().parents[1]
AIG_DIR = ROOT / "data" / "aig_test"

def _load(path: pathlib.Path) -> Circuit:
    return load_aig(str(path))


def _solver() -> CubeAndConquerSolver:
    return CubeAndConquerSolver()


# ---------------------------------------------------------------------------
# AIG test instances: classification
# ---------------------------------------------------------------------------

# Classification threshold: circuits with ≤ 2000 gates are "light"
# (finish within seconds with CnC depth=4).

SAT_LIGHT: list[str] = [
    # no SAT file has < 2000 gates
]

SAT_HEAVY = [
    "96_4_sat.aig",               #  3 265 gates,   192 inputs
    "100_50.aig",                 # 11 546 gates,   100 inputs
    "miter_6.aig",                #  7 377 gates, 6 666 inputs
    "miter_16.aig",               #  7 377 gates, 6 666 inputs
    "miter_26.aig",               #  7 383 gates, 6 666 inputs
    "miter_46.aig",               #  7 377 gates, 6 666 inputs
    "miter_188.aig",              #  7 379 gates, 6 666 inputs
    "MOD3_49_sat.aig",            #  6 164 gates,    31 inputs
    "MOD3_77_sat.aig",            #  6 342 gates,    31 inputs
    "MOD3_1_hard_sat.aig",        #  7 342 gates,    34 inputs
    "MOD3_low_density_1_sat.aig", #  5 015 gates,    50 inputs
    "hamming10-2_sat.aig",        # 31 665 gates, 1 024 inputs
    "3300_4.aig",                 #112 201 gates, 6 600 inputs
    "4300_4.aig",                 #146 201 gates, 8 600 inputs
    "6700_4.aig",                 #227 801 gates,13 400 inputs
    "9900_4.aig",                 #336 601 gates,19 800 inputs
    "p_hat300-2_sat.aig",         # 73 527 gates,   300 inputs
]

UNSAT_LIGHT = [
    "logVn_2.aig",                        #     6 gates,   4 inputs
    "logVn_4.aig",                        #    10 gates,   8 inputs
    "miter_identity_php_3_4.aig",         #    14 gates,  12 inputs
    "trVlog_2.aig",                       #    62 gates,   4 inputs
    "trVn_2.aig",                         #    62 gates,   4 inputs
    "miter_identity_php_8_9.aig",         #    74 gates,  72 inputs
    "miter_identity_php_6_19_3.aig",      #   116 gates, 114 inputs
    "miter_identity_php_12_13_1.aig",     #   158 gates, 156 inputs
    "miter_identity_php_13_14_1.aig",     #   184 gates, 182 inputs
    "miter_identity_php_14_15_1.aig",     #   212 gates, 210 inputs
    "miter_identity_php_11_23_2.aig",     #   255 gates, 253 inputs
    "miter_identity_php_10_31_3.aig",     #   312 gates, 310 inputs
    "5_6.aig",                            #   402 gates,  30 inputs
    "BvS_3_3-aigmiter.aig",              #   457 gates,   9 inputs
    "trVlog_4.aig",                       #   526 gates,   8 inputs
    "trVn_4.aig",                         #   526 gates,   8 inputs
    "16_4.aig",                           #   553 gates,  33 inputs
    "miter_identity_php_23_24_1.aig",     #   554 gates, 552 inputs
    "miter_identity_php_24_25_1.aig",     #   602 gates, 600 inputs
    "BvP_4_3-aigmiter.aig",              #   980 gates,  12 inputs
    "PvS_4_3-aigmiter.aig",              # 1 139 gates,  12 inputs
    "logVn_6.aig",                        # 1 332 gates,  12 inputs
    "BvP_4_4-aigmiter.aig",              # 1 340 gates,  16 inputs
    "trVn_6.aig",                         # 1 374 gates,  12 inputs
    "reg_11_6.aig",                       # 1 409 gates,  33 inputs
    "trVlog_6.aig",                       # 1 411 gates,  12 inputs
    "paley_13.aig",                       # 1 665 gates,  39 inputs
]

UNSAT_HEAVY = [
    "72_4.aig",                           #  2 457 gates,   145 inputs
    "trVn_8.aig",                         #  2 606 gates,    16 inputs
    "logVn_8.aig",                        #  2 666 gates,    16 inputs
    "trVlog_8.aig",                       #  2 699 gates,    16 inputs
    "BvS_6_4-aigmiter.aig",              #  3 655 gates,    24 inputs
    "thr2_500.aig",                       #  4 592 gates,   500 inputs
    "MOD3_54.aig",                        #  5 856 gates,    31 inputs
    "BvP_7_4-aigmiter.aig",              #  6 068 gates,    28 inputs
    "miter_3.aig",                        #  7 881 gates, 6 666 inputs
    "miter_8.aig",                        #  7 881 gates, 6 666 inputs
    "miter_33.aig",                       #  7 882 gates, 6 666 inputs
    "miter_68.aig",                       #  7 925 gates, 6 666 inputs
    "miter_85.aig",                       # 15 621 gates, 6 666 inputs
    "miter_91.aig",                       # 16 402 gates, 6 666 inputs
    "miter_129.aig",                      # 15 633 gates, 6 666 inputs
    "miter_123.aig",                      # 27 234 gates, 6 666 inputs
    "miter_174.aig",                      # 15 586 gates, 6 666 inputs
    "miter_197.aig",                      # 15 874 gates, 6 666 inputs
    "thr2_2000.aig",                      # 18 147 gates, 2 000 inputs
    "simple_reg_240_6.aig",               # 30 729 gates,   721 inputs
    "MOD3_NW_4.aig",                      # 36 024 gates,    18 inputs
    "thr2_4000.aig",                      # 36 169 gates, 4 000 inputs
    "thr2_5000.aig",                      # 45 179 gates, 5 000 inputs
    "thr2_6000.aig",                      # 54 187 gates, 6 000 inputs
    "thr2_8000.aig",                      # 72 203 gates, 8 000 inputs
    "thr2_10000.aig",                     # 90 218 gates,10 000 inputs
]


# =============================================================================
# AIG-test SAT (light)
# =============================================================================


class TestAigSATLight:

    @pytest.mark.parametrize("aig_file", SAT_LIGHT, ids=SAT_LIGHT)
    def test_sat(self, aig_file: str):
        result = _solver().solve(_load(AIG_DIR / aig_file))
        assert result.answer is True


# =============================================================================
# AIG-test SAT (heavy)
# =============================================================================


class TestAigSATHeavy:

    @pytest.mark.heavy
    @pytest.mark.parametrize("aig_file", SAT_HEAVY, ids=SAT_HEAVY)
    def test_sat(self, aig_file: str):
        result = _solver().solve(_load(AIG_DIR / aig_file))
        assert result.answer is True


# =============================================================================
# AIG-test UNSAT (light)
# =============================================================================


class TestAigUNSATLight:

    @pytest.mark.parametrize("aig_file", UNSAT_LIGHT, ids=UNSAT_LIGHT)
    def test_unsat(self, aig_file: str):
        result = _solver().solve(_load(AIG_DIR / aig_file))
        assert result.answer is False


# =============================================================================
# AIG-test UNSAT (heavy)
# =============================================================================


class TestAigUNSATHeavy:

    @pytest.mark.heavy
    @pytest.mark.parametrize("aig_file", UNSAT_HEAVY, ids=UNSAT_HEAVY)
    def test_unsat(self, aig_file: str):
        result = _solver().solve(_load(AIG_DIR / aig_file))
        assert result.answer is False


# =============================================================================
# Multiplier miter UNSAT tests (all equivalent pairs -> UNSAT)
# =============================================================================

PAIRS = [
    "column_vs_dadda",
    "column_vs_karatsuba",
    "column_vs_wallace",
    "dadda_vs_karatsuba",
    "dadda_vs_wallace",
    "karatsuba_vs_wallace",
]

MITER_LIGHT_SIZES = list(range(1, 8))
MITER_HEAVY_SIZES = list(range(8, 13))

_miter_light_files = [
    f"mul_{k}_{p}.aig" for k in MITER_LIGHT_SIZES for p in PAIRS
]
_miter_heavy_files = [
    f"mul_{k}_{p}.aig" for k in MITER_HEAVY_SIZES for p in PAIRS
]
