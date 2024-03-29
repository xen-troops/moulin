import subprocess
import pytest
import os
import tempfile


@pytest.mark.integration
def test_args_is_string():
    script_path = os.path.abspath(__file__)
    script_dir_path = os.path.dirname(script_path)
    yaml_file = os.path.join(script_dir_path, "resources/test_args_is_string.yaml")

    with tempfile.TemporaryDirectory(dir=script_dir_path) as tmp_dir:

        result = subprocess.run(["python", "../../../../../moulin.py", yaml_file],
                                cwd=tmp_dir,
                                stderr=subprocess.PIPE,
                                text=True)

        assert result.returncode == 0, ("The return code is not equal to '0'")

        with open(tmp_dir + "/build.ninja") as f:
            ninja_file = f.read()
            assert "args = -string" in ninja_file


if __name__ == "__main__":
    pytest.main([__file__])
