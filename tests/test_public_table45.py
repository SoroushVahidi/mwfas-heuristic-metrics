"""Failure-mode tests use toy data, never the accepted private witness cohort."""
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "table45", Path(__file__).resolve().parents[1] / "release/public_reproducibility/replay_table45.py")
replay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replay)


def test_objective_and_malformed_order(tmp_path):
    p = tmp_path / "triangle.d"
    p.write_text("p edge 3 3\na 1 2 5\na 2 3 7\na 3 1 11\n")
    g = replay.graph(p)
    order = tmp_path / "order.csv"
    order.write_text("Node ID,Order\n1,0\n2,1\n3,2\n")
    assert replay.objective(order, g)[0] == 11
    order.write_text("Node ID,Order\n1,0\n2,1\n2,2\n")
    with pytest.raises(ValueError, match="full permutation"):
        replay.objective(order, g)
    order.write_text("Node ID,Order\n1,0\n2,1\n")
    with pytest.raises(ValueError, match="incomplete ordering"):
        replay.objective(order, g)


def test_duplicate_arcs_are_not_silently_deduplicated(tmp_path):
    p = tmp_path / "duplicate.d"
    p.write_text("p edge 2 2\na 1 2 5\na 1 2 5\n")
    with pytest.raises(ValueError, match="duplicate DIMACS arcs"):
        replay.graph(p)


def test_reference_discrepancy_fails():
    with pytest.raises(ValueError, match="numerical summary mismatch"):
        replay.compare_reference({"median": 0.2}, {"median": "0.3"}, ["median"], "toy")


def test_every_frozen_row_and_cell_must_agree():
    families = ("Erd\\H{o}s--R\\'enyi", "Community", "Scale-free")
    latex = "\\midrule\n" + "\n".join(f"{f} & 45/45 & 0.125\\\\" for f in families) + "\n\\bottomrule"
    frozen = {"tables": {"4": latex}}
    results = {"4": {replay.FAMILIES[f]: [[45, 45], [.125]] for f in families}}
    assert len(replay.displayed_cells(frozen, results)) == 9
    results["4"]["directed_scale_free"][1] = [.126]
    with pytest.raises(ValueError, match="FAIL Table 4"):
        replay.displayed_cells(frozen, results)
