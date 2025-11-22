
def test_flakiness_detector():
    """Test the flakiness detection utility."""
    from metamorphic_guard.stability import detect_flakiness
    
    # 1. Consistent results
    results_consistent = [
        {"result": 42},
        {"result": 42},
        {"result": 42}
    ]
    analysis = detect_flakiness(results_consistent)
    assert not analysis["is_flaky"]
    assert len(analysis["distinct_values"]) == 1
    
    # 2. Flaky results (integer)
    results_flaky = [
        {"result": 42},
        {"result": 43},
        {"result": 42}
    ]
    analysis = detect_flakiness(results_flaky)
    assert analysis["is_flaky"]
    assert len(analysis["distinct_values"]) == 2
    assert analysis["distribution"][42] == 2
    assert analysis["distribution"][43] == 1
    
    # 3. Flaky results (complex object)
    results_complex = [
        {"result": {"a": 1, "b": 2}},
        {"result": {"a": 1, "b": 2}},
        {"result": {"a": 1, "b": 3}}
    ]
    analysis = detect_flakiness(results_complex)
    assert analysis["is_flaky"]
    assert len(analysis["distinct_values"]) == 2
    
    # 4. Float tolerance
    results_float = [
        {"result": 1.000001},
        {"result": 1.000002},
        {"result": 1.000001}
    ]
    # Strict
    assert detect_flakiness(results_float)["is_flaky"]
    # Loose
    assert not detect_flakiness(results_float, tolerance=1e-5)["is_flaky"]

def test_flakiness_detector_empty():
    from metamorphic_guard.stability import detect_flakiness
    res = detect_flakiness([])
    assert not res["is_flaky"]
    assert not res["distinct_values"]


