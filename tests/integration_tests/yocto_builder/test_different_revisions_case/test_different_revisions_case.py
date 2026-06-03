import subprocess
import pytest
import os
import tempfile


@pytest.mark.integration
def test_different_revisions():
    script_path = os.path.abspath(__file__)
    script_dir_path = os.path.dirname(script_path)
    yaml_file = os.path.join(script_dir_path, "resources/test_different_revisions_case.yaml")

    with tempfile.TemporaryDirectory(dir=script_dir_path) as tmp_dir:

        result = subprocess.run(["python", "../../../../../moulin.py", yaml_file],
                                cwd=tmp_dir,
                                stderr=subprocess.PIPE,
                                text=True)

        assert result.returncode != 0, ("The return code is not equal to '0'")
        assert "YAMLProcessingError" in result.stderr, ("The expected error type is missing in the moulin output")


if __name__ == "__main__":
    pytest.main([__file__])
