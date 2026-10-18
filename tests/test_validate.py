from mwfas_data.validate import check_key_uniqueness, check_objective, check_split_leakage


def test_objective_arithmetic_detects_error():
    assert check_objective([{"total_weight": 3, "forward_weight": 2, "backward_weight": 1}], "x")["status"] == "PASS"
    assert check_objective([{"total_weight": 3, "forward_weight": 2, "backward_weight": 2}], "x")["status"] == "FAIL"
    assert check_objective([{"objective_weight": 1}], "x")["status"] == "NOT_VERIFIABLE"


def test_duplicate_keys_detected_without_repair():
    row = {"benchmark_resource": "b", "instance_id": "g", "algorithm": "lrta"}
    result = check_key_uniqueness([row, dict(row)], "core_benchmark")
    assert result["status"] == "FAIL" and result["count"] == 1


def test_tuning_holdout_overlap():
    rows = [{"benchmark_resource": "b", "instance_id": "g", "split": "tuning"},
            {"benchmark_resource": "b", "instance_id": "g", "split": "holdout"}]
    assert check_split_leakage(rows)["status"] == "FAIL"
