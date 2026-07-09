import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

import pytest


VAR_PATHS = [
    "/",
    "/lib",
    "/lib/app",
    "/lib/app/state.db",
    "/log",
    "/log/app.log",
    "/log/state-link",
]


def _run_rouge(work_dir: Path, image_name: str, output_name: str) -> None:
    command = [
        sys.executable,
        "-c",
        "from moulin.main import rouge_entry; rouge_entry()",
        "build.yaml",
        "-i",
        image_name,
        "-o",
        output_name,
        "-f",
    ]
    result = subprocess.run(command,
                            cwd=work_dir,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=False)
    assert result.returncode == 0, (
        f"rouge failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def _run_rouge_failure(work_dir: Path, image_name: str, output_name: str) -> str:
    command = [
        sys.executable,
        "-c",
        "from moulin.main import rouge_entry; rouge_entry()",
        "build.yaml",
        "-i",
        image_name,
        "-o",
        output_name,
        "-f",
    ]
    result = subprocess.run(command,
                            cwd=work_dir,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=False)
    assert result.returncode != 0, "rouge unexpectedly succeeded"
    return result.stdout + result.stderr


def _debugfs_stat(image_path: Path, target: str) -> str:
    result = subprocess.run(["debugfs", "-R", f"stat {target}", str(image_path)],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=False)
    assert result.returncode == 0, (
        f"debugfs stat {target} failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return result.stdout


def _mode(stat_output: str) -> str:
    match = re.search(r"Mode:\s+([0-7]+)", stat_output)
    assert match, stat_output
    return match.group(1)


def _owner(stat_output: str) -> str:
    user = re.search(r"User:\s+(\d+)", stat_output)
    group = re.search(r"Group:\s+(\d+)", stat_output)
    assert user and group, stat_output
    return f"{user.group(1)}:{group.group(1)}"


def _file_type(stat_output: str) -> str:
    match = re.search(r"Type:\s+([a-z]+)", stat_output)
    assert match, stat_output
    return match.group(1)


def _source_type(path: Path) -> str:
    file_mode = os.lstat(path).st_mode
    if stat.S_ISDIR(file_mode):
        return "directory"
    if stat.S_ISLNK(file_mode):
        return "symlink"
    if stat.S_ISREG(file_mode):
        return "regular"
    return "other"


def _source_mode(path: Path) -> str:
    return f"{stat.S_IMODE(os.lstat(path).st_mode):04o}"


def _image_attributes(image_path: Path, target: str) -> dict:
    stat_output = _debugfs_stat(image_path, target)
    return {
        "type": _file_type(stat_output),
        "permissions": _mode(stat_output),
        "owner": _owner(stat_output),
    }


def _source_attributes(root: Path, relative: str) -> dict:
    source_path = root if relative == "/" else root / relative.lstrip("/")
    return {
        "type": _source_type(source_path),
        "permissions": _source_mode(source_path),
    }


def _prepare_workspace(tmp_path: Path) -> Path:
    resources_dir = Path(__file__).resolve().parent / "resources" / "workspace"
    shutil.copytree(resources_dir, tmp_path, dirs_exist_ok=True, symlinks=True)

    var = tmp_path / "ro-rootfs" / "var"
    var.chmod(0o755)
    (var / "lib").chmod(0o750)
    (var / "lib/app").chmod(0o700)
    (var / "lib/app/state.db").chmod(0o640)
    (var / "log").chmod(0o755)
    (var / "log/app.log").chmod(0o600)
    return var


def _assert_var_metadata(source_var: Path, image: Path) -> None:
    assert _owner(_debugfs_stat(image, "/")) == "123:456"

    for path in VAR_PATHS:
        source_attrs = _source_attributes(source_var, path)
        image_attrs = _image_attributes(image, path)

        assert image_attrs["type"] == source_attrs["type"]
        assert image_attrs["permissions"] == source_attrs["permissions"]


@pytest.mark.integration
def test_root_directory_builds_wic_like_var_partition(tmp_path: Path):
    """Builds a separate RW /var partition from a prepared rootfs folder."""
    var = _prepare_workspace(tmp_path)

    _run_rouge(tmp_path, "rw_var_from_root_directory", "var-root-directory.ext4")
    _assert_var_metadata(var, tmp_path / "var-root-directory.ext4")


@pytest.mark.integration
def test_items_builds_wic_like_var_partition(tmp_path: Path):
    """Builds a separate RW /var partition from items."""
    var = _prepare_workspace(tmp_path)

    _run_rouge(tmp_path, "rw_var_from_items", "var-items.ext4")
    _assert_var_metadata(var, tmp_path / "var-items.ext4")


@pytest.mark.integration
def test_ext4_root_directory_validation_errors(tmp_path: Path):
    """Rejects unsupported root_directory combinations."""
    _prepare_workspace(tmp_path)

    invalid_ext4 = _run_rouge_failure(tmp_path, "invalid_ext4_mix", "invalid-ext4.ext4")
    assert "'root_directory' cannot be used with 'items' or 'files'" in invalid_ext4

    invalid_vfat = _run_rouge_failure(tmp_path, "invalid_vfat_root_directory", "invalid-vfat.img")
    assert "'root_directory' is supported only by ext4" in invalid_vfat
