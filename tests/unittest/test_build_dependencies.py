"""
Tests for component dependency generation.
"""

import os
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

import yaml

from moulin.build_conf import MoulinConfiguration
from moulin.build_generator import generate_build, generate_component_dyndep
from moulin.main import moulin_entry
from moulin.yaml_helpers import YAMLProcessingError


def _make_conf(doc):
    return MoulinConfiguration(yaml.compose(doc))


def _write_source_archive():
    with open("build-input", "w", encoding="utf-8") as stream:
        stream.write("builder input\n")
    with open("source-file", "w", encoding="utf-8") as stream:
        stream.write("source contents\n")
    with tarfile.open("source.tar", "w") as archive:
        archive.add("source-file")


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
                assert generator is None
                return FakeBuilder()

        class FakeFetcherModule:
            @staticmethod
            def get_fetcher(_conf, _build_dir, generator):
                assert generator is None
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


if __name__ == "__main__":
    unittest.main()
