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
from moulin.builders.yocto import _get_yocto_generated_dirs
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


def _write_yocto_layer(layer_dir):
    os.makedirs(os.path.join(layer_dir, "conf"))
    os.makedirs(os.path.join(layer_dir, "recipes-core/images"))
    with open(os.path.join(layer_dir, "conf/layer.conf"), "w",
              encoding="utf-8") as stream:
        stream.write("# layer configuration\n")
    with open(os.path.join(layer_dir, "recipes-core/images/image.bb"), "w",
              encoding="utf-8") as stream:
        stream.write("DESCRIPTION = \"test image\"\n")


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

    def _generate_yocto_depfile(self, doc, setup=None):
        generated_dirs = []

        def setup_with_generated_dirs():
            if setup:
                generated_dirs.extend(setup() or [])

        with patch("moulin.builders.yocto._get_yocto_generated_dirs",
                   return_value=generated_dirs):
            return self._generate_depfile(doc, setup=setup_with_generated_dirs)

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

    def test_yocto_layer_files_are_always_added_to_depfile(self):
        """Verifies Yocto layer files are tracked without extra YAML options."""
        doc = """
desc: "Test build dependencies"
components:
  test:
    sources:
      - type: "null"
    builder:
      type: "yocto"
      build_target: core-image-minimal
      conf:
      target_images:
        - "target-image"
      layers:
        - "../meta-product"
        """

        def setup():
            _write_yocto_layer("test/meta-product")

        depfile = self._generate_yocto_depfile(doc, setup=setup)

        self.assertIn("test/build/target-image:", depfile)
        self.assertIn("test/meta-product/conf/layer.conf", depfile)
        self.assertIn("test/meta-product/recipes-core/images/image.bb", depfile)

    def test_yocto_layer_deps_exclude_git_directory(self):
        """Verifies Git metadata below a layer is not tracked."""
        doc = """
desc: "Test build dependencies"
components:
  test:
    sources:
      - type: "null"
    builder:
      type: "yocto"
      build_target: core-image-minimal
      conf:
      target_images:
        - "target-image"
      layers:
        - "../meta-product"
        """

        def setup():
            _write_yocto_layer("test/meta-product")
            os.makedirs("test/meta-product/.git/objects")
            with open("test/meta-product/.git/objects/object", "w",
                      encoding="utf-8") as stream:
                stream.write("git object\n")

        depfile = self._generate_yocto_depfile(doc, setup=setup)

        self.assertIn("test/meta-product/conf/layer.conf", depfile)
        self.assertIn("test/meta-product/recipes-core/images/image.bb", depfile)
        self.assertNotIn("test/meta-product/.git/objects/object", depfile)

    def test_yocto_layer_deps_exclude_work_dir_nested_under_layer(self):
        """Verifies Yocto build dir nested under a layer is not tracked."""
        doc = """
desc: "Test build dependencies"
components:
  test:
    sources:
      - type: "null"
    builder:
      type: "yocto"
      build_target: core-image-minimal
      work_dir: yocto/meta-product/yocto/build/secure-image
      conf:
      target_images:
        - "target-image"
      layers:
        # layers are relative to work_dir; this resolves to test/yocto/meta-product,
        # which contains test/yocto/meta-product/yocto/build/secure-image.
        - "../../.."
        """

        def setup():
            layer_dir = "test/yocto/meta-product"
            build_dir = os.path.join(layer_dir, "yocto/build/secure-image")

            _write_yocto_layer(layer_dir)
            os.makedirs(os.path.join(build_dir, "buildhistory/packages/acl"))
            os.makedirs(os.path.join(build_dir, "tmp/work"))
            with open(os.path.join(build_dir, "buildhistory/packages/acl/latest"), "w",
                      encoding="utf-8") as stream:
                stream.write("generated buildhistory\n")
            with open(os.path.join(build_dir, "tmp/work/generated.bb"), "w",
                      encoding="utf-8") as stream:
                stream.write("generated recipe\n")
            return [os.path.abspath(build_dir)]

        depfile = self._generate_yocto_depfile(doc, setup=setup)

        self.assertIn("test/yocto/meta-product/yocto/build/secure-image/target-image:",
                      depfile)
        self.assertIn("test/yocto/meta-product/conf/layer.conf", depfile)
        self.assertIn("test/yocto/meta-product/recipes-core/images/image.bb", depfile)
        self.assertNotIn("buildhistory/packages/acl/latest", depfile)
        self.assertNotIn("test/yocto/meta-product/yocto/build/secure-image/tmp/work/generated.bb",
                         depfile)

    def test_yocto_layer_deps_keep_layer_nested_under_work_dir(self):
        """Verifies explicitly configured layers inside work_dir remain tracked."""
        doc = """
desc: "Test build dependencies"
components:
  test:
    sources:
      - type: "null"
    builder:
      type: "yocto"
      build_target: core-image-minimal
      work_dir: build
      conf:
      target_images:
        - "target-image"
      layers:
        - "generated-layer"
        """

        def setup():
            _write_yocto_layer("test/build/generated-layer")

        depfile = self._generate_yocto_depfile(doc, setup=setup)

        self.assertIn("test/build/target-image:", depfile)
        self.assertIn("test/build/generated-layer/conf/layer.conf", depfile)
        self.assertIn("test/build/generated-layer/recipes-core/images/image.bb", depfile)

    def test_yocto_layer_deps_exclude_bitbake_generated_dirs(self):
        """Verifies BitBake-reported generated dirs are not tracked."""
        doc = """
desc: "Test build dependencies"
components:
  test:
    sources:
      - type: "null"
    builder:
      type: "yocto"
      build_target: core-image-minimal
      work_dir: yocto/meta-product/yocto/build/secure-image
      conf:
      target_images:
        - "target-image"
      layers:
        - "../../.."
        """

        def setup():
            layer_dir = "test/yocto/meta-product"
            secure_image = os.path.join(layer_dir, "yocto/build/secure-image")
            common_data = os.path.join(layer_dir, "yocto/build/common_data")

            _write_yocto_layer(layer_dir)
            os.makedirs(os.path.join(secure_image, "tmp/work"))
            os.makedirs(os.path.join(common_data, "downloads/git2"))
            with open(os.path.join(secure_image, "tmp/work/generated.bb"), "w",
                      encoding="utf-8") as stream:
                stream.write("generated recipe\n")
            with open(os.path.join(common_data, "downloads/git2/mirror.tar.gz"), "w",
                      encoding="utf-8") as stream:
                stream.write("generated download\n")

            return [
                os.path.abspath(secure_image),
                os.path.abspath(common_data),
            ]

        depfile = self._generate_yocto_depfile(doc, setup=setup)

        self.assertIn("test/yocto/meta-product/yocto/build/secure-image/target-image:",
                      depfile)
        self.assertIn("test/yocto/meta-product/conf/layer.conf", depfile)
        self.assertIn("test/yocto/meta-product/recipes-core/images/image.bb", depfile)
        self.assertNotIn("tmp/work/generated.bb", depfile)
        self.assertNotIn("common_data/downloads/git2/mirror.tar.gz", depfile)

    def test_yocto_layer_deps_prune_generated_dirs_through_layer_symlink(self):
        """Verifies generated dirs are pruned when the layer path is a symlink."""
        doc = """
desc: "Test build dependencies"
components:
  test:
    sources:
      - type: "null"
    builder:
      type: "yocto"
      build_target: core-image-minimal
      work_dir: yocto/build/secure-image
      conf:
      target_images:
        - "target-image"
      layers:
        - "../../meta-product"
        """

        def setup():
            layer_dir = "test/meta-product"
            build_dir = os.path.join(layer_dir, "yocto/build/secure-image")
            symlink_path = "test/yocto/meta-product"

            _write_yocto_layer(layer_dir)
            os.makedirs(os.path.join(build_dir, "tmp/work"))
            os.makedirs(os.path.dirname(symlink_path))
            os.symlink("../meta-product", symlink_path)

            with open(os.path.join(build_dir, "tmp/work/generated.bb"), "w",
                      encoding="utf-8") as stream:
                stream.write("generated recipe\n")
            return [os.path.abspath(build_dir)]

        depfile = self._generate_yocto_depfile(doc, setup=setup)

        self.assertIn("test/yocto/build/secure-image/target-image:", depfile)
        self.assertIn("test/yocto/meta-product/conf/layer.conf", depfile)
        self.assertIn("test/yocto/meta-product/recipes-core/images/image.bb", depfile)
        self.assertNotIn("tmp/work/generated.bb", depfile)

    def test_yocto_generated_dirs_are_read_with_bitbake_getvar(self):
        """Verifies generated dirs are read with bitbake-getvar."""
        run_results = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout=value)
            for value in [
                "/work/yocto/build/secure-image\n",
                "/work/yocto/build/secure-image/tmp\n",
                "/work/yocto/build/common_data/downloads\n",
                "/work/yocto/build/common_data/sstate-cache\n",
                "relative/path\n",
                "\n",
                "\n",
                "\n",
                "\n",
                "\n",
            ]
        ]

        with patch("moulin.builders.yocto._run_bash", side_effect=run_results) as run_bash:
            paths = _get_yocto_generated_dirs("/work", "poky", "yocto/build/secure-image")

        self.assertEqual(paths, [
            "/work/yocto/build/common_data/downloads",
            "/work/yocto/build/common_data/sstate-cache",
            "/work/yocto/build/secure-image",
            "/work/yocto/build/secure-image/tmp",
        ])
        self.assertEqual(run_bash.call_count, 10)
        self.assertIn("oe-init-build-env yocto/build/secure-image >/dev/null",
                      run_bash.call_args_list[0].args[0])
        self.assertIn("bitbake-getvar --ignore-undefined --value TOPDIR",
                      run_bash.call_args_list[0].args[0])

    def test_yocto_generated_dir_query_failure_warns_and_continues(self):
        """Verifies missing BitBake variables do not abort dep generation."""
        values = [
            subprocess.CalledProcessError(1, "bitbake-getvar", stderr="missing"),
            subprocess.CompletedProcess(args=[], returncode=0,
                                        stdout="/work/yocto/build/secure-image/tmp\n"),
        ]
        values.extend(subprocess.CompletedProcess(args=[], returncode=0, stdout="\n")
                      for _ in range(8))

        with patch("moulin.builders.yocto._run_bash", side_effect=values), \
                self.assertLogs("moulin.builders.yocto", level="WARNING") as logs:
            paths = _get_yocto_generated_dirs("/work", "poky", "yocto/build/secure-image")

        self.assertEqual(paths, ["/work/yocto/build/secure-image/tmp"])
        self.assertIn("Can't query BitBake generated directory variable TOPDIR",
                      logs.output[0])

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
