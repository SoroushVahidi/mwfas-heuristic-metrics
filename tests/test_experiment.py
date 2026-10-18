from pathlib import Path

import pytest

from mwfas_data.experiment import command_for


def test_command_pins_seed_and_wmsf_mode():
    command = command_for(Path("source"), "ipsns", Path("graph.d"), Path("ranking.csv"), seed=17, iterations=8)
    assert command[-6:] == ["--rng-seed", "17", "--iters", "8", "--wmsf-seed-mode", "full"]
    assert "run_ipsns.py" in command[1]


def test_unknown_algorithm_rejected():
    with pytest.raises(ValueError):
        command_for(Path("source"), "mystery", Path("graph.d"), Path("ranking.csv"))
