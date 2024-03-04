import subprocess
import pytest
import os
import tempfile
import re


@pytest.mark.integration
def test_zephyr_one_snippet():
    script_path = os.path.abspath(__file__)
    script_dir_path = os.path.dirname(script_path)
    yaml_file = os.path.join(script_dir_path, "resources/zephyr_builder_with_one_snippet.yaml")

    with tempfile.TemporaryDirectory(dir=script_dir_path) as tmp_dir:

        result = subprocess.run(["python", "../../../../../moulin.py", yaml_file],
                                cwd=tmp_dir,
                                stderr=subprocess.PIPE,
                                text=True)

        assert result.returncode == 0, ("The return code is equal to '0'")

        with open(tmp_dir + "/build.ninja") as f:
            ninja_file = f.read()
            assert re.search(r"west build .*(\$\n)?.* \$snippets .*", ninja_file) is not None, \
                   "Snippets paremeter present"
            assert "snippets = -S xen_dom0" in ninja_file


@pytest.mark.integration
def test_zephyr_two_snippets():
    script_path = os.path.abspath(__file__)
    script_dir_path = os.path.dirname(script_path)
    yaml_file = os.path.join(script_dir_path, "resources/zephyr_builder_with_two_snippets.yaml")

    with tempfile.TemporaryDirectory(dir=script_dir_path) as tmp_dir:

        result = subprocess.run(["python", "../../../../../moulin.py", yaml_file],
                                cwd=tmp_dir,
                                stderr=subprocess.PIPE,
                                text=True)

        assert result.returncode == 0, ("The return code is equal to '0'")

        with open(tmp_dir + "/build.ninja") as f:
            ninja_file = f.read()
            assert re.search(r"west build .*(\$\n)?.* \$snippets .*", ninja_file) is not None, \
                   "Snippets paremeter present"
            assert "snippets = -S xen_dom0 -S xen_dom1" in ninja_file


@pytest.mark.integration
def test_zephyr_snippet_and_shield():
    script_path = os.path.abspath(__file__)
    script_dir_path = os.path.dirname(script_path)
    yaml_file = os.path.join(script_dir_path, "resources/zephyr_builder_with_snippet_and_shield.yaml")

    with tempfile.TemporaryDirectory(dir=script_dir_path) as tmp_dir:

        result = subprocess.run(["python", "../../../../../moulin.py", yaml_file],
                                cwd=tmp_dir,
                                stderr=subprocess.PIPE,
                                text=True)

        assert result.returncode != 0, ("The return code is not equal to '0'")
        assert "Both shields and snippets are specified, only one of them is allowed" in result.stderr, \
               ("The expected error message")


@pytest.mark.integration
def test_zephyr_no_snippets():
    script_path = os.path.abspath(__file__)
    script_dir_path = os.path.dirname(script_path)
    yaml_file = os.path.join(script_dir_path, "resources/zephyr_builder_with_no_snippets.yaml")

    with tempfile.TemporaryDirectory(dir=script_dir_path) as tmp_dir:

        result = subprocess.run(["python", "../../../../../moulin.py", yaml_file],
                                cwd=tmp_dir,
                                stderr=subprocess.PIPE,
                                text=True)

        assert result.returncode == 0, ("The return code is equal to '0'")

        with open(tmp_dir + "/build.ninja") as f:
            ninja_file = f.read()
            print(ninja_file)
            print(re.search(r"snippets = $", ninja_file, re.M))
            assert re.search(r"snippets = $", ninja_file, re.M) is not None, "Snippets paremeter not present"


if __name__ == "__main__":
    pytest.main([__file__])
