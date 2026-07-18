import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from textwrap import dedent

import pytest


def _write(path: Path, text: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def _assert_success(result, label: str):
    assert result.returncode == 0, (
        f"{label} failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


class FakeYoctoBuild:
    def __init__(self, script_dir: Path):
        self.tmp_ctx = tempfile.TemporaryDirectory(dir=script_dir)
        self.tmp_dir = Path(self.tmp_ctx.name)
        self.workspace = self.tmp_dir / "workspace"
        self.fake_bin = self.tmp_dir / "bin"
        self.moulin_path = script_dir.parents[3] / "moulin.py"
        self.resources_dir = script_dir / "resources"
        self.env = os.environ.copy()
        self.env["PATH"] = f"{self.fake_bin}{os.pathsep}{self.env['PATH']}"
        self.yaml_file = self.tmp_dir / "build.yaml"

    def __enter__(self):
        self._copy_resources()
        self._write_moulin_wrapper()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.tmp_ctx.cleanup()

    def run_moulin(self):
        return subprocess.run(
            [sys.executable, str(self.moulin_path), str(self.yaml_file)],
            cwd=self.tmp_dir,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def run_ninja(self, *args):
        return subprocess.run(
            ["ninja", *args],
            cwd=self.tmp_dir,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def depfile_copy(self) -> str:
        return (self.tmp_dir / "depfile.d").read_text(encoding="utf-8")

    def bitbake_build_count(self) -> int:
        log = self.workspace / "bitbake.log"
        if not log.exists():
            return 0
        return len(log.read_text(encoding="utf-8").splitlines())

    def _copy_resources(self):
        shutil.copytree(self.resources_dir / "workspace", self.workspace)
        shutil.copytree(self.resources_dir / "bin", self.fake_bin)
        shutil.copy2(self.resources_dir / "build.yaml", self.yaml_file)
        tools = ["bitbake", "bitbake-getvar", "bitbake-layers"]
        for tool in [self.fake_bin / name for name in tools]:
            tool.chmod(0o755)

    def _write_moulin_wrapper(self):
        # Ninja invokes the generated rule through PATH. Keep this wrapper first
        # so --dep calls use the real Moulin entry point and leave a stable copy
        # of the generated depfile for assertions.
        _write(
            self.fake_bin / "moulin.py",
            dedent(f"""\
                #!/bin/sh
                {sys.executable} {self.moulin_path} "$@"
                status=$?
                echo "$2 $3 $status" >> "{self.tmp_dir}/dep-invocations.log"
                if [ "$2" = "--dep" ] && [ -f ".moulin_$3.d" ]; then
                    cp ".moulin_$3.d" "{self.tmp_dir}/depfile.d"
                fi
                exit $status
            """),
            executable=True,
        )


@pytest.mark.integration
def test_yocto_layer_file_change_rebuilds_component():
    """Verifies Moulin/Ninja rebuild a Yocto target when a layer file changes."""
    if not shutil.which("ninja"):
        pytest.skip("ninja is required for this integration test")
    script_dir = Path(__file__).resolve().parent

    with FakeYoctoBuild(script_dir) as case:
        _assert_success(case.run_moulin(), "moulin")
        _assert_success(case.run_ninja("test"), "first ninja")

        depfile = case.depfile_copy()
        assert "workspace/./deploy/image.txt:" in depfile
        assert "workspace/meta-product/conf/layer.conf" in depfile
        assert "workspace/meta-product/recipes-core/images/test-image.bb" in depfile

        _assert_success(case.run_ninja("test"), "no-op ninja")
        assert case.bitbake_build_count() == 1

        time.sleep(1.1)
        layer_conf = case.workspace / "meta-product/conf/layer.conf"
        layer_conf.write_text("# changed layer config\n", encoding="utf-8")

        result = case.run_ninja("-d", "explain", "test")
        _assert_success(result, "layer dependency rebuild")

        explain = result.stdout + result.stderr
        assert "workspace/meta-product/conf/layer.conf" in explain
        assert "dirty" in explain or "older than most recent input" in explain
        assert case.bitbake_build_count() == 2
