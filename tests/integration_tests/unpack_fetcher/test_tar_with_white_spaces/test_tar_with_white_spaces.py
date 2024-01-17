import subprocess
import pytest
import os
import tempfile
from pathlib import Path


@pytest.mark.integration
def test_tar_with_white_spaces():
    script_path = os.path.abspath(__file__)
    script_dir_path = os.path.dirname(script_path)
    yaml_file = os.path.join(script_dir_path, "resources/test_tar_with_white_spaces.yaml")
    resources_dir = os.path.join(script_dir_path, "resources/")
    expected_items = sorted(["very_test_dir", "dir with white space", "filename with space", "simple_dir", "test1.txt",
                             "test2.txt"])
    list_names_test_1_subdir_1 = []
    list_names_test_1_subdir_2 = []
    list_names_test_2_subdir_1 = []
    list_names_test_2_subdir_2 = []

    with tempfile.TemporaryDirectory(dir=script_dir_path) as tmp_dir:

        result = subprocess.run(["tar", "-czf", "test.tar.gz", "--directory", resources_dir,
                                 "very_test_dir"],
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
                                stdout=subprocess.PIPE,
                                text=True)

        assert result.returncode == 0, ("The return code is equal to '0'")

        unpacked_files_list_test_1_subdir_1 = os.path.join(script_dir_path, tmp_dir, "test_1/subdir_1")
        path = Path(unpacked_files_list_test_1_subdir_1)

        for item_name in path.rglob('*'):
            list_names_test_1_subdir_1.append(item_name.name)
        sorted_list1 = sorted(list_names_test_1_subdir_1)

        if expected_items != sorted_list1:
            raise AssertionError("The lists of files do not match")

        unpacked_files_list_test_1_subdir_2 = os.path.join(script_dir_path, tmp_dir, "test_1/subdir_2")
        path = Path(unpacked_files_list_test_1_subdir_2)

        for item_name in path.rglob('*'):
            list_names_test_1_subdir_2.append(item_name.name)
        sorted_list2 = sorted(list_names_test_1_subdir_2)

        if expected_items != sorted_list2:
            raise AssertionError("The lists of files do not match")

        unpacked_files_list_test_2_subdir_1 = os.path.join(script_dir_path, tmp_dir, "test_2/subdir_1")
        path = Path(unpacked_files_list_test_2_subdir_1)

        for item_name in path.rglob('*'):
            list_names_test_2_subdir_1.append(item_name.name)
        sorted_list3 = sorted(list_names_test_2_subdir_1)

        if expected_items != sorted_list3:
            raise AssertionError("The lists of files do not match")

        unpacked_files_list_test_2_subdir_2 = os.path.join(script_dir_path, tmp_dir, "test_2/subdir_2")
        path = Path(unpacked_files_list_test_2_subdir_2)

        for item_name in path.rglob('*'):
            list_names_test_2_subdir_2.append(item_name.name)
        sorted_list4 = sorted(list_names_test_2_subdir_2)

        if expected_items != sorted_list4:
            raise AssertionError("The lists of files do not match")


if __name__ == "__main__":
    pytest.main([__file__])
