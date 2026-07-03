import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from textwrap import dedent

import pytest


def _write(path: Path, text: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def _require_cmake_ninja_toolchain():
    for tool in ["cmake", "ninja", "cc"]:
        if not shutil.which(tool):
            pytest.skip(f"{tool} is required for this integration test")


class FakeZephyrBuild:
    def __init__(self, script_dir: Path, policy: str, fail_build: bool = False):
        self.tmp_ctx = tempfile.TemporaryDirectory(dir=script_dir)
        self.tmp_dir = Path(self.tmp_ctx.name)
        self.workspace = self.tmp_dir / "workspace"
        self.fake_bin = self.tmp_dir / "bin"
        self.moulin_path = script_dir.parents[3] / "moulin.py"
        self.resources_dir = script_dir / "resources"
        self.policy = policy
        self.fail_build = fail_build
        self.env = os.environ.copy()
        self.env["PATH"] = f"{self.fake_bin}{os.pathsep}{self.env['PATH']}"
        self.yaml_file = self.tmp_dir / "build.yaml"

    def __enter__(self):
        self._write_workspace()
        self._write_moulin_wrapper()
        self._write_fake_west()
        self._write_yaml()
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

    def west_invocations(self) -> str:
        return (self.workspace / "west-invocation.log").read_text(encoding="utf-8")

    def west_build_count(self) -> int:
        return sum(line.startswith("build ") for line in self.west_invocations().splitlines())

    def dep_invocations(self) -> str:
        return (self.tmp_dir / "dep-invocations.log").read_text(encoding="utf-8")

    def _write_workspace(self):
        shutil.copytree(self.resources_dir / "workspace", self.workspace)
        with tarfile.open(self.tmp_dir / "source.tar", "w") as archive:
            archive.add(self.workspace / "manifest.yml", arcname="manifest.yml")

    def _write_moulin_wrapper(self):
        # Ninja runs the generated build rule through PATH, so the test places
        # this wrapper before the real moulin.py. It delegates to the real
        # script, then records --dep calls and copies the generated depfile to
        # a stable test path.
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

    def _write_fake_west(self):
        fail_build = "True" if self.fail_build else "False"
        _write(
            self.fake_bin / "west",
            dedent(f"""\
                #!/usr/bin/env python3
                from pathlib import Path
                import subprocess
                import sys

                log = Path("west-invocation.log")
                previous = log.read_text(encoding="utf-8") if log.exists() else ""
                log.write_text(previous + " ".join(sys.argv[1:]) + "\\n", encoding="utf-8")

                args = sys.argv[1:]
                if args == ["manifest", "--path"]:
                    print(Path("manifest.yml").resolve())
                    raise SystemExit(0)

                if {fail_build}:
                    raise SystemExit("intentional fake west build failure")

                if not args or args[0] != "build":
                    raise SystemExit("unexpected west command")
                work_dir = args[args.index("-d") + 1] if "-d" in args else "build"
                build_dir = Path(work_dir)
                # The fake west command creates real CMake/Ninja metadata,
                # which the later --dep invocation reads to produce the final
                # depfile.
                subprocess.run([
                    "cmake",
                    "-S", "app",
                    "-B", str(build_dir),
                    "-G", "Ninja",
                    "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
                ], check=True)
                subprocess.run(["ninja", "-C", str(build_dir)], check=True)
                (build_dir / "zephyr").mkdir(parents=True, exist_ok=True)
                (build_dir / "zephyr" / "zephyr.bin").write_text("fake image\\n", encoding="utf-8")
            """),
            executable=True,
        )

    def _write_yaml(self):
        # fetched_files and all_files need a fetcher source; build_files should
        # contain builder-reported dependencies without the fetched manifest.
        lines = [
            'desc: "Integration test Zephyr build dependencies"',
            "components:",
            "  test:",
            '    build-dir: "workspace"',
            "    default: true",
            f"    dependency_policy: {self.policy}",
        ]
        if self.policy in ("fetched_files", "all_files"):
            lines.extend([
                "    sources:",
                '      - type: "unpack"',
                '        file: "source.tar"',
                '        archive_type: "tar"',
                '        dir: "fetched"',
            ])
        lines.extend([
            "    builder:",
            "      type: zephyr",
            '      board: "native_sim"',
            "      target: app",
            "      work_dir: build",
            "      target_images:",
            '        - "build/zephyr/zephyr.bin"',
        ])
        _write(
            self.yaml_file,
            "\n".join(lines) + "\n",
        )


def _assert_success(result, label: str):
    assert result.returncode == 0, (
        f"{label} failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


@pytest.mark.integration
def test_zephyr_build_files_dependency_policy_uses_post_build_metadata():
    """Verifies 'build_files' deps policy writes Zephyr/CMake build metadata."""
    _require_cmake_ninja_toolchain()
    script_dir = Path(__file__).resolve().parent

    with FakeZephyrBuild(script_dir, "build_files") as case:
        _assert_success(case.run_moulin(), "moulin")
        _assert_success(case.run_ninja("test"), "ninja")

        depfile = case.depfile_copy()
        assert "workspace/build/zephyr/zephyr.bin:" in depfile
        assert "workspace/app/src/main.c" in depfile
        assert "workspace/app/CMakeLists.txt" in depfile
        assert "workspace/config/nonstandard-build.conf" in depfile
        assert "workspace/manifest.yml" in depfile
        assert "workspace/fetched/manifest.yml" not in depfile
        assert (case.workspace / "west-invocation.log").is_file()


@pytest.mark.integration
def test_zephyr_fetched_files_dependency_policy_uses_fetcher_deps_only():
    """Verifies 'fetched_files' deps policy writes fetched files only."""
    _require_cmake_ninja_toolchain()
    script_dir = Path(__file__).resolve().parent

    with FakeZephyrBuild(script_dir, "fetched_files") as case:
        _assert_success(case.run_moulin(), "moulin")
        _assert_success(case.run_ninja("test"), "ninja")

        depfile = case.depfile_copy()
        assert "workspace/build/zephyr/zephyr.bin:" in depfile
        assert "workspace/fetched/manifest.yml" in depfile
        assert "workspace/app/src/main.c" not in depfile


@pytest.mark.integration
def test_zephyr_all_files_dependency_policy_merges_fetcher_and_builder_deps():
    """Verifies 'all_files' deps policy writes fetched and Zephyr/CMake metadata."""
    _require_cmake_ninja_toolchain()
    script_dir = Path(__file__).resolve().parent

    with FakeZephyrBuild(script_dir, "all_files") as case:
        _assert_success(case.run_moulin(), "moulin")
        _assert_success(case.run_ninja("test"), "ninja")

        depfile = case.depfile_copy()
        assert "workspace/build/zephyr/zephyr.bin:" in depfile
        assert "workspace/app/src/main.c" in depfile
        assert "workspace/config/nonstandard-build.conf" in depfile
        assert "workspace/manifest.yml" in depfile
        assert "workspace/fetched/manifest.yml" in depfile


@pytest.mark.integration
def test_zephyr_build_dependency_file_is_not_rewritten_after_failed_build():
    """Verifies failed west build does not run --dep or publish a depfile."""
    _require_cmake_ninja_toolchain()
    script_dir = Path(__file__).resolve().parent

    with FakeZephyrBuild(script_dir, "build_files", fail_build=True) as case:
        _assert_success(case.run_moulin(), "moulin")
        result = case.run_ninja("test")

        assert result.returncode != 0
        assert "intentional fake west build failure" in result.stderr
        assert not (case.tmp_dir / "depfile.d").exists()
        invocations_file = case.tmp_dir / "dep-invocations.log"
        invocations = invocations_file.read_text(encoding="utf-8") if invocations_file.exists() else ""
        assert "--dep test" not in invocations


@pytest.mark.integration
def test_zephyr_build_dependency_file_survives_repeat_ninja_runs():
    """Verifies a no-op second Ninja run keeps the depfile and skips --dep."""
    _require_cmake_ninja_toolchain()
    script_dir = Path(__file__).resolve().parent

    with FakeZephyrBuild(script_dir, "build_files") as case:
        _assert_success(case.run_moulin(), "moulin")
        _assert_success(case.run_ninja("test"), "first ninja")
        first_depfile = case.depfile_copy()
        assert "workspace/app/src/main.c" in first_depfile

        _assert_success(case.run_ninja("test"), "second ninja")
        assert "workspace/app/src/main.c" in case.depfile_copy()
        invocations = (case.tmp_dir / "dep-invocations.log").read_text(encoding="utf-8")
        assert invocations.count("--dep test 0") == 1


@pytest.mark.integration
def test_zephyr_configure_input_change_rebuilds_component():
    """Verifies a configure input outside the app tree makes the outer target dirty."""
    _require_cmake_ninja_toolchain()
    script_dir = Path(__file__).resolve().parent

    with FakeZephyrBuild(script_dir, "build_files") as case:
        _assert_success(case.run_moulin(), "moulin")
        _assert_success(case.run_ninja("test"), "first ninja")
        _assert_success(case.run_ninja("test"), "no-op ninja")
        assert case.west_build_count() == 1

        config = case.workspace / "config" / "nonstandard-build.conf"
        config.write_text("build-option=changed\n", encoding="utf-8")
        result = case.run_ninja("-d", "explain", "test")
        _assert_success(result, "configure-input rebuild")

        explain = result.stdout + result.stderr
        assert "workspace/config/nonstandard-build.conf" in explain
        assert "dirty" in explain or "older than most recent input" in explain
        assert case.west_build_count() == 2
        assert case.dep_invocations().count("--dep test 0") == 2


@pytest.mark.integration
def test_zephyr_source_dependency_change_rebuilds_component():
    """Verifies changing a compiler source dependency reruns the outer target."""
    _require_cmake_ninja_toolchain()
    script_dir = Path(__file__).resolve().parent

    with FakeZephyrBuild(script_dir, "build_files") as case:
        _assert_success(case.run_moulin(), "moulin")
        _assert_success(case.run_ninja("test"), "first ninja")
        _assert_success(case.run_ninja("test"), "no-op ninja")
        assert case.west_build_count() == 1

        source = case.workspace / "app" / "src" / "main.c"
        source.write_text("int main(void) { return 1; }\n", encoding="utf-8")
        result = case.run_ninja("-d", "explain", "test")
        _assert_success(result, "source rebuild")

        explain = result.stdout + result.stderr
        assert "workspace/app/src/main.c" in explain
        assert "dirty" in explain or "older than most recent input" in explain
        assert case.west_build_count() == 2
        assert case.dep_invocations().count("--dep test 0") == 2
