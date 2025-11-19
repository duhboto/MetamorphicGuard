import os
from pathlib import Path
from click.testing import CliRunner
from metamorphic_guard.cli.init import init_command

def test_init_interactive_flow_generic():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Simulate inputs: 
        # 1. Project type: generic
        # 2. Task name: my_generic_task
        # 3. Scaffold project? Yes (default)
        # 4. Project directory: (default: my_generic_task)
        # We need explicit newlines for each input.
        inputs = "generic\nmy_generic_task\nY\n\n"
        
        result = runner.invoke(init_command, ["--interactive"], input=inputs)
        
        assert result.exit_code == 0, result.output
        assert "Scaffolded project in my_generic_task" in result.output
        
        project_dir = Path("my_generic_task")
        assert project_dir.exists()
        config_file = project_dir / "metamorphic.toml"
        assert config_file.exists()
        content = config_file.read_text()
        assert 'name = "my_generic_task"' in content
        # Check for generic default
        assert 'timeout_s = 5.0' in content

def test_init_interactive_flow_llm():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Simulate inputs:
        # 1. Project type: llm
        # 2. Task name: my_llm_task
        # 3. Scaffold project? No
        # 4. Baseline: base.py
        # 5. Candidate: cand.py
        inputs = "llm\nmy_llm_task\nN\nbase.py\ncand.py\n"
        
        result = runner.invoke(init_command, ["--interactive"], input=inputs)
        
        assert result.exit_code == 0, result.output
        assert "Created configuration from 'llm' template" in result.output
        
        config_file = Path("metamorphic.toml")
        assert config_file.exists()
        content = config_file.read_text()
        assert 'name = "my_llm_task"' in content
        assert 'timeout_s = 30.0' in content # LLM default
        assert 'executor = "openai"' in content

def test_init_custom_template():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Simulate inputs:
        # 1. Project type: custom
        # 2. Template: minimal
        # 3. Task name: minimal_task
        # 4. Scaffold: N
        # 5. Baseline: default
        # 6. Candidate: default
        # 7. Distributed: default
        # 8. Monitors: default
        inputs = "custom\nminimal\nminimal_task\nN\n\n\n\n\n"
        
        result = runner.invoke(init_command, ["--interactive"], input=inputs)
        
        assert result.exit_code == 0, result.output
        assert "Created configuration from 'minimal' template" in result.output
        
        config_file = Path("metamorphic.toml")
        assert config_file.exists()
        content = config_file.read_text()
        assert 'name = "minimal_task"' in content
