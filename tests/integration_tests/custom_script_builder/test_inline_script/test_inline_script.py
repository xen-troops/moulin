import os
import subprocess
import tempfile

import pytest


def _run_moulin(tmp_dir, yaml_file, env):
    return subprocess.run(["python", "../../../../../moulin.py", yaml_file],
                          cwd=tmp_dir,
                          stderr=subprocess.PIPE,
                          text=True,
                          env=env)


def _test_paths():
    script_path = os.path.abspath(__file__)
    script_dir_path = os.path.dirname(script_path)
    repo_dir = os.path.abspath(os.path.join(script_dir_path, "../../../.."))
    return script_dir_path, repo_dir


@pytest.mark.integration
def test_inline_script():
    script_dir_path, repo_dir = _test_paths()
    yaml_file = os.path.join(script_dir_path, "resources/test_inline_script.yaml")

    with tempfile.TemporaryDirectory(dir=script_dir_path) as tmp_dir:
        os.symlink(os.path.join(repo_dir, "moulin.py"), os.path.join(tmp_dir, "moulin.py"))

        env = os.environ.copy()
        env["PATH"] = tmp_dir + os.pathsep + env["PATH"]
        env["PYTHONPATH"] = repo_dir + os.pathsep + env.get("PYTHONPATH", "")

        result = _run_moulin(tmp_dir, yaml_file, env)

        assert result.returncode == 0, result.stderr

        with open(os.path.join(tmp_dir, "build.ninja"), encoding="utf-8") as stream:
            ninja_file = stream.read()
            assert "cs_inline_build" in ninja_file
            assert "--utility-builders-custom_script --run-inline-script" in ninja_file

        result = subprocess.run(["ninja", "Image"],
                                cwd=tmp_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                env=env)

        assert result.returncode == 0, result.stderr

        with open(os.path.join(tmp_dir, "Image"), encoding="utf-8") as stream:
            assert stream.read() == "payload\n"

        with open(os.path.join(tmp_dir, "inline-config-path.txt"), encoding="utf-8") as stream:
            assert stream.read().strip() == "script_workdir/conf-test.yaml"

        work_dir_entries = os.listdir(os.path.join(tmp_dir, "script_workdir"))
        assert not [name for name in work_dir_entries if name.startswith(".moulin-inline-")]


@pytest.mark.integration
def test_inline_script_failure_reports_script_output_without_traceback():
    script_dir_path, repo_dir = _test_paths()
    yaml_file = os.path.join(script_dir_path, "resources/test_inline_script_failure.yaml")

    with tempfile.TemporaryDirectory(dir=script_dir_path) as tmp_dir:
        os.symlink(os.path.join(repo_dir, "moulin.py"), os.path.join(tmp_dir, "moulin.py"))

        env = os.environ.copy()
        env["PATH"] = tmp_dir + os.pathsep + env["PATH"]
        env["PYTHONPATH"] = repo_dir + os.pathsep + env.get("PYTHONPATH", "")

        result = _run_moulin(tmp_dir, yaml_file, env)

        assert result.returncode == 0, result.stderr

        result = subprocess.run(["ninja", "Image"],
                                cwd=tmp_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                env=env)

        assert result.returncode != 0
        combined_output = result.stdout + result.stderr
        assert "inline stdout" in combined_output
        assert "inline stderr" in combined_output
        assert "Traceback" not in combined_output


@pytest.mark.integration
def test_inline_script_passes_list_and_string_args():
    script_dir_path, repo_dir = _test_paths()
    yaml_file = os.path.join(script_dir_path, "resources/test_inline_script_args.yaml")

    with tempfile.TemporaryDirectory(dir=script_dir_path) as tmp_dir:
        os.symlink(os.path.join(repo_dir, "moulin.py"), os.path.join(tmp_dir, "moulin.py"))

        env = os.environ.copy()
        env["PATH"] = tmp_dir + os.pathsep + env["PATH"]
        env["PYTHONPATH"] = repo_dir + os.pathsep + env.get("PYTHONPATH", "")

        result = _run_moulin(tmp_dir, yaml_file, env)

        assert result.returncode == 0, result.stderr

        result = subprocess.run(["ninja", "list-args-image", "string-args-image"],
                                cwd=tmp_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                env=env)

        assert result.returncode == 0, result.stderr

        with open(os.path.join(tmp_dir, "list-args.txt"), encoding="utf-8") as stream:
            assert stream.read().splitlines() == [
                "--mode",
                "list value",
                "script_workdir/conf-list_args.yaml",
            ]

        with open(os.path.join(tmp_dir, "string-args.txt"), encoding="utf-8") as stream:
            assert stream.read().splitlines() == [
                "--mode",
                "string value",
                "script_workdir/conf-string_args.yaml",
            ]


@pytest.mark.parametrize(
    "yaml_name, expected_error",
    [
        ("test_inline_script_conflict.yaml",
         "'script' and 'inline_script' are mutually exclusive"),
        ("test_inline_script_missing.yaml",
         "Either 'script' or 'inline_script' is required"),
    ],
)
@pytest.mark.integration
def test_inline_script_config_errors(yaml_name, expected_error):
    script_dir_path, repo_dir = _test_paths()
    yaml_file = os.path.join(script_dir_path, "resources", yaml_name)

    with tempfile.TemporaryDirectory(dir=script_dir_path) as tmp_dir:
        os.symlink(os.path.join(repo_dir, "moulin.py"), os.path.join(tmp_dir, "moulin.py"))

        env = os.environ.copy()
        env["PATH"] = tmp_dir + os.pathsep + env["PATH"]
        env["PYTHONPATH"] = repo_dir + os.pathsep + env.get("PYTHONPATH", "")

        result = _run_moulin(tmp_dir, yaml_file, env)

        assert result.returncode != 0
        assert expected_error in result.stderr


if __name__ == "__main__":
    pytest.main([__file__])
