import subprocess
import pytest
import os
import tempfile


@pytest.mark.integration
def test_zip_archive_successfully_unpacked():
    script_path = os.path.abspath(__file__)
    script_dir_path = os.path.dirname(script_path)
    yaml_file = os.path.join(script_dir_path, "resources/test_zip_archive_successfully_unpacked.yaml")
    resources_dir = os.path.join(script_dir_path, "resources/")
    expected_files = sorted(["test_file1", "test_file2"])

    with tempfile.TemporaryDirectory(dir=script_dir_path) as tmp_dir:

        result = subprocess.run(["zip", "-j", "test.zip", os.path.join(resources_dir,
                                "test_file1"), os.path.join(resources_dir, "test_file2")],
                                cwd=tmp_dir,
                                stderr=subprocess.PIPE,
                                text=True)

        assert result.returncode == 0, ("The return code is equal to '0'")

        result = subprocess.run(["python", "../../../../../moulin.py", yaml_file],
                                cwd=tmp_dir,
                                stderr=subprocess.PIPE,
                                text=True)

        assert result.returncode == 0, ("The return code is equal to '0'")

        result = subprocess.run(["ninja"],
                                cwd=tmp_dir,
                                stderr=subprocess.PIPE,
                                text=True)

        assert result.returncode == 0, ("The return code is equal to '0'")

        unpacked_files_list = sorted(os.listdir(os.path.join(script_dir_path, tmp_dir, "test/")))

        if expected_files != unpacked_files_list:
            raise AssertionError("The lists of files do not match")


if __name__ == "__main__":
    pytest.main([__file__])
