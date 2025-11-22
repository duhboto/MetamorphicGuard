import pytest
from pathlib import Path
from metamorphic_guard.policy import load_policy_file, PolicyLoadError

def test_load_policy_v1_legacy(tmp_path):
    """Test loading a V1 policy file (legacy format)."""
    policy_path = tmp_path / "policy_v1.toml"
    policy_path.write_text("""
name = "test-v1"
[gating]
min_delta = 0.05
min_pass_rate = 0.9
alpha = 0.05
""")
    
    result = load_policy_file(policy_path)
    assert result["version"] == "v1"
    assert result["gating"]["min_delta"] == 0.05
    assert result["gating"]["min_pass_rate"] == 0.9

def test_load_policy_v2_valid(tmp_path):
    """Test loading a valid V2 policy file."""
    policy_path = tmp_path / "policy_v2.toml"
    policy_path.write_text("""
version = "v2"
name = "test-v2"

[evaluation]
n = 100
alpha = 0.01

[gate]
method = "bootstrap"
threshold = 0.02
min_pass_rate = 0.85
""")
    
    result = load_policy_file(policy_path)
    assert result["version"] == "v2"
    # Check flattened gating keys
    assert result["gating"]["min_delta"] == 0.02
    assert result["gating"]["min_pass_rate"] == 0.85
    assert result["gating"]["alpha"] == 0.01
    
    # Check full config preservation
    v2 = result["v2_config"]
    assert v2["evaluation"]["n"] == 100
    assert v2["gate"]["method"] == "bootstrap"

def test_load_policy_v2_invalid(tmp_path):
    """Test schema validation for V2 policy."""
    policy_path = tmp_path / "policy_v2_bad.toml"
    policy_path.write_text("""
version = "v2"
[gate]
threshold = "not-a-float"
""")
    
    with pytest.raises(PolicyLoadError) as exc:
        load_policy_file(policy_path)
    
    assert "Policy validation failed" in str(exc.value)
    assert "Input should be a valid number" in str(exc.value)

def test_load_policy_invalid_version(tmp_path):
    """Test loading policy with unknown version."""
    policy_path = tmp_path / "policy_v3.toml"
    policy_path.write_text("""
version = "v3"
""")
    
    with pytest.raises(PolicyLoadError) as exc:
        load_policy_file(policy_path)
    
    assert "Unsupported policy version: v3" in str(exc.value)


