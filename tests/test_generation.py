from mwfas_data.generation import generate_candidate, structural_properties


def test_generated_families_deterministic_and_measured():
    for family in ("erdos_renyi_directed", "directed_scale_free", "directed_community"):
        first = structural_properties(generate_candidate(family, 20, 42))
        second = structural_properties(generate_candidate(family, 20, 42))
        assert first == second
        assert first["n_vertices"] == 20
        assert 0 <= first["density"] <= 1
        assert first["weight_min"] >= 1
