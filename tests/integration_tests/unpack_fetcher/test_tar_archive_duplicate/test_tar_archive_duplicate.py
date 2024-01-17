import subprocess
import pytest
import os
import tempfile


@pytest.mark.integration
def test_tar_archive_duplicate():
    script_path = os.path.abspath(__file__)
    script_dir_path = os.path.dirname(script_path)
    yaml_file = os.path.join(script_dir_path, "resources/test_tar_archive_duplicate.yaml")
    resources_dir = os.path.join(script_dir_path, "resources/")
    expected_files = sorted(['test_file1', 'test_file2'])

    with tempfile.TemporaryDirectory(dir=script_dir_path) as tmp_dir:

        result = subprocess.run(["tar", "-czf", "test.tar.gz", "--directory", resources_dir,
                                 "test_file1", "test_file2"],
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

        unpacked_files_list_test_1_subdir_1 = sorted(os.listdir(os.path.join(script_dir_path, tmp_dir,
                                                                             "test_1/subdir_1")))
        unpacked_files_list_test_1_subdir_2 = sorted(os.listdir(os.path.join(script_dir_path, tmp_dir,
                                                                             "test_1/subdir_2")))
        unpacked_files_list_test_2_subdir_1 = sorted(os.listdir(os.path.join(script_dir_path, tmp_dir,
                                                                             "test_2/subdir_1")))
        unpacked_files_list_test_2_subdir_2 = sorted(os.listdir(os.path.join(script_dir_path, tmp_dir,
                                                                             "test_2/subdir_2")))

        if expected_files != unpacked_files_list_test_1_subdir_1:
            raise AssertionError("The lists of files do not match")

        if expected_files != unpacked_files_list_test_1_subdir_2:
            raise AssertionError("The lists of files do not match")

        if expected_files != unpacked_files_list_test_2_subdir_1:
            raise AssertionError("The lists of files do not match")

        if expected_files != unpacked_files_list_test_2_subdir_2:
            raise AssertionError("The lists of files do not match")


if __name__ == "__main__":
    pytest.main([__file__])
