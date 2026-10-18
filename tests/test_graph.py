from pathlib import Path

import pytest

from mwfas_data.graph import GraphInputError, acyclic_after_removal, backward_weight, read_dimacs


def graph_file(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "test.dimacs"
    path.write_text(text)
    return path


def test_objective_and_feedback_arc_set(tmp_path):
    graph = read_dimacs(graph_file(tmp_path, "p sp 4 4\na 1 2 3\na 2 3 2\na 3 1 1\na 1 2 4\n"))
    assert graph.vertices == ("1", "2", "3", "4")  # isolated vertex retained
    assert len(graph.arcs) == 3  # parallel arcs aggregated
    assert backward_weight(graph, ["1", "2", "3", "4"]) == 1
    assert not acyclic_after_removal(graph, set())
    assert acyclic_after_removal(graph, {("3", "1")})


def test_self_loop_counts_as_backward_and_requires_removal(tmp_path):
    graph = read_dimacs(graph_file(tmp_path, "p sp 2 1\na 1 1 2\n"))
    assert backward_weight(graph, ["1", "2"]) == 2
    assert not acyclic_after_removal(graph, set())
    assert acyclic_after_removal(graph, {("1", "1")})


@pytest.mark.parametrize("text", ["p sp 2 1\na 1 2 -1\n", "p sp 2 1\na 1 2 junk\n", "p sp 2 1\na 1 2\n", "p sp 2 2\na 1 2 1\n"])
def test_bad_inputs_fail_explicitly(tmp_path, text):
    with pytest.raises(GraphInputError):
        read_dimacs(graph_file(tmp_path, text))


def test_bad_order_rejected(tmp_path):
    graph = read_dimacs(graph_file(tmp_path, "p sp 2 1\na 1 2 1\n"))
    with pytest.raises(ValueError):
        backward_weight(graph, ["1", "1"])
