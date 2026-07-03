"""
Tests for component dependency generation.
"""

import os
import tarfile
import tempfile
import unittest

import yaml

from moulin.build_conf import MoulinConfiguration
from moulin.build_generator import generate_fetcher_dyndep


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

    def _generate_legacy_fetcher_depfile(self, doc, setup=None):
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:
                if setup:
                    setup()
                generate_fetcher_dyndep(_make_conf(doc), "test")
                with open(".moulin_test.d", encoding="utf-8") as stream:
                    return stream.read()
            finally:
                os.chdir(old_cwd)

    def test_legacy_fetcherdep_uses_fetched_files(self):
        """Verifies legacy fetcher deps are still generated."""
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
        depfile = self._generate_legacy_fetcher_depfile(doc, setup=_write_source_archive)
        self.assertIn("test/file.tar.bz2:", depfile)
        self.assertIn("test/fetched/source-file", depfile)
        self.assertNotIn("build-input", depfile)


if __name__ == "__main__":
    unittest.main()
