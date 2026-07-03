"""
Tests for component dependency generation.
"""

import io
import os
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

import yaml

from moulin import ninja_syntax
from moulin.build_conf import MoulinConfiguration
from moulin.build_generator import generate_build, generate_component_dyndep
from moulin.main import moulin_entry
from moulin.builders.zephyr import ZephyrBuilder
from moulin.yaml_helpers import YAMLProcessingError
from moulin.yaml_wrapper import YamlValue


def _make_conf(doc):
    return MoulinConfiguration(yaml.compose(doc))


def _make_generator():
    return ninja_syntax.Writer(io.StringIO(), width=120)


def _write_source_archive():
    with open("build-input", "w", encoding="utf-8") as stream:
        stream.write("builder input\n")
    with open("source-file", "w", encoding="utf-8") as stream:
        stream.write("source contents\n")
    with tarfile.open("source.tar", "w") as archive:
        archive.add("source-file")


def _make_zephyr_builder():
    doc = """
type: "zephyr"
board: "native_sim"
target: "app"
work_dir: "zephyr/build"
target_images:
  - "zephyr/zephyr.bin"
    """
    return ZephyrBuilder(YamlValue(yaml.compose(doc)), "test", "workspace", [],
                         _make_generator())


class TestComponentDependencies(unittest.TestCase):

    def _generate_build(self, doc):
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:
                generate_build(_make_conf(doc), "test.yaml")
            finally:
                os.chdir(old_cwd)

    def _generate_depfile(self, doc, setup=None):
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:
                if setup:
                    setup()
                generate_component_dyndep(_make_conf(doc), "test")
                with open(".moulin_test.d", encoding="utf-8") as stream:
                    return stream.read()
            finally:
                os.chdir(old_cwd)

    def test_default_dependency_policy_uses_fetched_files(self):
        """Verifies default dependency_policy uses legacy 'fetched_files' deps policy."""
        doc = """
desc: "Test build dependencies"
components:
  test:
    sources:
      - type: "unpack"
        file: "source.tar"
        archive_type: "tar"
        dir: "fetched"
    builder:
      type: "archive"
      name: "file.tar.bz2"
      items:
        - "build-input"
        """
        depfile = self._generate_depfile(doc, setup=_write_source_archive)
        self.assertIn("test/file.tar.bz2:", depfile)
        self.assertIn("test/fetched/source-file", depfile)
        self.assertNotIn("build-input", depfile)

    def test_build_files_dependency_policy_rejects_unsupported_builder(self):
        """Verifies direct --dep rejects unsupported 'build_files' deps policy."""
        doc = """
desc: "Test build dependencies"
components:
  test:
    dependency_policy: build_files
    builder:
      type: "archive"
      name: "file.tar.bz2"
      items:
        - "build-input"
        """
        with self.assertRaisesRegex(YAMLProcessingError, "Builder 'archive' does not support"):
            self._generate_depfile(doc)

    def test_build_generation_rejects_invalid_policy_before_writing_build_file(self):
        """Verifies invalid dependency config leaves no partial build.ninja file."""
        doc = """
desc: "Test build dependencies"
components:
  test:
    dependency_policy: build_files
    builder:
      type: "archive"
      name: "file.tar.bz2"
      items:
        - "build-input"
        """
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:
                with self.assertRaisesRegex(YAMLProcessingError, "Builder 'archive' does not support"):
                    generate_build(_make_conf(doc), "test.yaml")
                self.assertFalse(os.path.exists("build.ninja"))
            finally:
                os.chdir(old_cwd)

    def test_legacy_fetcherdep_requests_build_file_regeneration(self):
        """Verifies legacy --fetcherdep calls fail with an actionable error."""
        args = Mock(fetcherdep=["test"], dep=None)

        with patch("moulin.main._handle_shared_opts", return_value=(None, args)), \
             patch("moulin.main.build_generator.generate_component_dyndep") as generate_dep, \
             patch("moulin.main.build_generator.generate_build") as generate_build_file:
            with self.assertLogs("moulin.main", level="ERROR") as captured_logs:
                with self.assertRaises(SystemExit) as exit_context:
                    moulin_entry()

        generate_dep.assert_not_called()
        generate_build_file.assert_not_called()
        self.assertEqual(exit_context.exception.code, 1)
        self.assertIn(
            "build.ninja was created with an older version of Moulin. "
            "Please re-run Moulin to update the build file.",
            captured_logs.output[0])

    def test_rejects_unknown_dependency_policy(self):
        """Verifies direct --dep rejects unknown deps policy values."""
        doc = """
desc: "Test build dependencies"
components:
  test:
    dependency_policy: unknown
    builder:
      type: "archive"
      name: "file.tar.bz2"
      items:
        - "build-input"
        """
        with self.assertRaises(YAMLProcessingError):
            self._generate_depfile(doc)

    def test_build_generation_rejects_unknown_dependency_policy(self):
        """Verifies build.ninja generation rejects unknown deps policy values."""
        doc = """
desc: "Test build dependencies"
components:
  test:
    dependency_policy: unknown
    builder:
      type: "archive"
      name: "file.tar.bz2"
      items:
        - "build-input"
        """
        with self.assertRaises(YAMLProcessingError):
            self._generate_build(doc)

    def test_build_generation_rejects_unsupported_fetcher_policy(self):
        """Verifies fetched-file deps policies require get_file_list."""
        doc = """
desc: "Test build dependencies"
components:
  test:
    sources:
      - type: "unsupported"
    builder:
      type: "fake"
        """

        class FakeBuilder:
            def get_targets(self):
                return ["test-output"]

        class FakeBuilderModule:
            @staticmethod
            def get_builder(_conf, _name, _build_dir, _src_stamps, generator):
                return FakeBuilder()

        class FakeFetcherModule:
            @staticmethod
            def get_fetcher(_conf, _build_dir, generator):
                return object()

        with patch("moulin.build_generator._get_modules",
                   return_value=({"fake": FakeBuilderModule}, {"unsupported": FakeFetcherModule})):
            with self.assertRaisesRegex(YAMLProcessingError, "Fetcher 'unsupported' does not support"):
                self._generate_build(doc)


class TestGeneratedDependencyRules(unittest.TestCase):

    def test_zephyr_build_rule_uses_policy_resolver(self):
        """Verifies generated Zephyr rule runs --dep after a successful build."""
        from moulin.builders import zephyr

        with patch("moulin.ninja_syntax.Writer") as writer:
            zephyr.gen_build_rules(writer.return_value)

        rule_call = writer.return_value.rule.call_args_list[0]
        self.assertEqual(rule_call.args[0], "zephyr_build")
        command = rule_call.kwargs["command"]
        self.assertIn("pushd $build_dir > /dev/null", command)
        self.assertIn("popd > /dev/null", command)
        self.assertIn("--dep $name", command)
        self.assertLess(command.index("popd > /dev/null"), command.index("--dep $name"))
        self.assertNotIn("moulin_topdir", command)
        self.assertNotIn("--fetcherdep", command)


class TestZephyrBuildDependencies(unittest.TestCase):

    def test_build_files_dependency_policy_uses_zephyr_builder_files(self):
        """Verifies 'build_files' calls only the builder dependency collector."""
        doc = """
desc: "Test build dependencies"
components:
  test:
    build-dir: workspace
    dependency_policy: build_files
    sources:
      - type: "null"
    builder:
      type: "zephyr"
      board: "native_sim"
      target: "app"
      work_dir: "zephyr/build"
      target_images:
        - "zephyr/zephyr.bin"
        """
        with patch("moulin.build_generator._get_fetcher_file_list",
                   return_value=["workspace/manifest.yml"]) as fetcher_files, \
             patch("moulin.builders.zephyr.ZephyrBuilder.get_build_file_list",
                   return_value=["workspace/app/main.c"]) as builder_files, \
             tempfile.TemporaryDirectory() as tmp_dir:
            old_cwd = os.getcwd()
            os.chdir(tmp_dir)
            try:
                generate_component_dyndep(_make_conf(doc), "test")
                with open(".moulin_test.d", encoding="utf-8") as stream:
                    depfile = stream.read()
            finally:
                os.chdir(old_cwd)

        fetcher_files.assert_not_called()
        builder_files.assert_called_once_with()
        self.assertIn("workspace/zephyr/zephyr.bin:", depfile)
        self.assertIn("workspace/app/main.c", depfile)
        self.assertNotIn("workspace/manifest.yml", depfile)

    def test_build_file_metadata_failure_does_not_write_depfile(self):
        """Verifies failed build metadata collection does not publish a depfile."""
        doc = """
desc: "Test build dependencies"
components:
  test:
    build-dir: workspace
    dependency_policy: build_files
    builder:
      type: "zephyr"
      board: "native_sim"
      target: "app"
      work_dir: "zephyr/build"
      target_images:
        - "zephyr/zephyr.bin"
        """
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp_dir, \
             patch("moulin.builders.zephyr.ZephyrBuilder.get_build_file_list",
                   side_effect=RuntimeError("metadata query failed")):
            os.chdir(tmp_dir)
            try:
                with self.assertRaisesRegex(RuntimeError, "metadata query failed"):
                    generate_component_dyndep(_make_conf(doc), "test")
                self.assertFalse(os.path.exists(".moulin_test.d"))
            finally:
                os.chdir(old_cwd)

    def test_all_files_dependency_policy_uses_fetcher_and_builder_files(self):
        """Verifies 'all_files' deps policy writes fetcher and builder files."""
        doc = """
desc: "Test build dependencies"
components:
  test:
    build-dir: workspace
    dependency_policy: all_files
    sources:
      - type: "null"
    builder:
      type: "zephyr"
      board: "native_sim"
      target: "app"
      work_dir: "zephyr/build"
      target_images:
        - "zephyr/zephyr.bin"
        """
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp_dir, \
             patch("moulin.build_generator._get_fetcher_file_list",
                   return_value=["workspace/manifest.yml"]), \
             patch("moulin.builders.zephyr.ZephyrBuilder.get_build_file_list",
                   return_value=["workspace/app/main.c"]):
            os.chdir(tmp_dir)
            try:
                generate_component_dyndep(_make_conf(doc), "test")
                with open(".moulin_test.d", encoding="utf-8") as stream:
                    depfile = stream.read()

                self.assertIn("workspace/zephyr/zephyr.bin:", depfile)
                self.assertIn("workspace/manifest.yml", depfile)
                self.assertIn("workspace/app/main.c", depfile)
            finally:
                os.chdir(old_cwd)

    def test_build_file_list_reads_compile_commands(self):
        """Verifies Zephyr build-file reporting reads compile_commands.json."""
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:
                os.makedirs("workspace/app")
                os.makedirs("workspace/zephyr/build")
                with open("workspace/app/main.c", "w", encoding="utf-8") as stream:
                    stream.write("int main(void) { return 0; }\n")
                with open("workspace/zephyr/build/compile_commands.json",
                          "w",
                          encoding="utf-8") as stream:
                    stream.write(
                        '[{"directory": "workspace/app", '
                        '"command": "cc -c main.c", "file": "main.c"}]')

                builder = _make_zephyr_builder()
                with patch("moulin.builders.zephyr.subprocess.run",
                           return_value=subprocess.CompletedProcess([], 0, "", "")):
                    self.assertEqual(builder.get_build_file_list(),
                                     ["workspace/app/main.c"])
            finally:
                os.chdir(old_cwd)

    def test_build_file_list_reads_cmake_inputs_from_ninja_query(self):
        """Verifies CMake configure files are discovered through Ninja query."""
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:
                os.makedirs("workspace/app")
                os.makedirs("workspace/config")
                os.makedirs("workspace/zephyr/build")
                with open("workspace/app/CMakeLists.txt", "w", encoding="utf-8") as stream:
                    stream.write("cmake_minimum_required(VERSION 3.20)\n")
                with open("workspace/config/nonstandard-build.conf", "w", encoding="utf-8") as stream:
                    stream.write("build-option=value\n")
                with open("workspace/zephyr/build/build.ninja", "w", encoding="utf-8") as stream:
                    stream.write("# fake CMake Ninja file\n")

                cmake_lists = os.path.abspath("workspace/app/CMakeLists.txt")
                config_file = os.path.abspath("workspace/config/nonstandard-build.conf")
                query_stdout = (
                    "build.ninja:\n"
                    "  input: RERUN_CMAKE\n"
                    f"    | {cmake_lists}\n"
                    f"    | {config_file}\n"
                    "  outputs:\n"
                )

                builder = _make_zephyr_builder()
                get_configure_files = getattr(builder, "_ZephyrBuilder__get_ninja_configure_files")
                with patch("moulin.builders.zephyr.subprocess.run",
                           return_value=subprocess.CompletedProcess([], 0, query_stdout, "")):
                    self.assertEqual(
                        get_configure_files("workspace/zephyr/build"),
                        [
                            "workspace/app/CMakeLists.txt",
                            "workspace/config/nonstandard-build.conf",
                        ],
                    )
            finally:
                os.chdir(old_cwd)

    def test_build_file_list_warns_when_metadata_reports_no_files(self):
        """Verifies empty Zephyr metadata is reported without failing."""
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:
                os.makedirs("workspace")
                builder = _make_zephyr_builder()
                metadata_result = subprocess.CompletedProcess([], 0, "missing-manifest.yml", "")
                with self.assertLogs("moulin.builders.zephyr", level="WARNING") as logs:
                    with patch("moulin.builders.zephyr.subprocess.run",
                               return_value=metadata_result):
                        self.assertEqual(builder.get_build_file_list(), [])
                self.assertIn("did not report any build files", "\n".join(logs.output))
            finally:
                os.chdir(old_cwd)

    def test_metadata_query_failures_raise_with_command_output(self):
        """Verifies failed metadata queries stop dependency generation."""
        builder = _make_zephyr_builder()
        get_deps_files = getattr(builder, "_ZephyrBuilder__get_ninja_deps_files")
        get_query_inputs = getattr(ZephyrBuilder, "_ZephyrBuilder__get_ninja_query_inputs")
        get_manifest_file = getattr(builder, "_ZephyrBuilder__get_west_manifest_file")
        result = subprocess.CompletedProcess([], 1, "query stdout", "query stderr")

        with tempfile.TemporaryDirectory() as tmp_dir:
            cases = [
                ("ninja deps query", lambda: get_deps_files(tmp_dir)),
                ("ninja build.ninja query",
                 lambda: get_query_inputs("workspace/zephyr/build")),
                ("west manifest path query", get_manifest_file),
            ]
            for action, query in cases:
                with self.subTest(action=action):
                    with patch("moulin.builders.zephyr.subprocess.run", return_value=result):
                        with self.assertRaises(RuntimeError) as err_context:
                            query()

                    message = str(err_context.exception)
                    self.assertIn(f"{action} failed with exit code 1", message)
                    self.assertIn("stdout:\nquery stdout", message)
                    self.assertIn("stderr:\nquery stderr", message)

    def test_metadata_query_launch_failures_raise(self):
        """Verifies metadata query launch failures stop dependency generation."""
        builder = _make_zephyr_builder()
        get_deps_files = getattr(builder, "_ZephyrBuilder__get_ninja_deps_files")
        get_query_inputs = getattr(ZephyrBuilder, "_ZephyrBuilder__get_ninja_query_inputs")
        get_manifest_file = getattr(builder, "_ZephyrBuilder__get_west_manifest_file")

        with tempfile.TemporaryDirectory() as tmp_dir:
            cases = [
                ("ninja deps query", lambda: get_deps_files(tmp_dir)),
                ("ninja build.ninja query",
                 lambda: get_query_inputs("workspace/zephyr/build")),
                ("west manifest path query", get_manifest_file),
            ]
            for action, query in cases:
                with self.subTest(action=action):
                    error = OSError(f"{action} missing")
                    with patch("moulin.builders.zephyr.subprocess.run", side_effect=error):
                        with self.assertRaises(RuntimeError) as err_context:
                            query()

                    message = str(err_context.exception)
                    self.assertIn(f"{action} failed to start", message)
                    self.assertIn(str(error), message)


if __name__ == "__main__":
    unittest.main()
