"""
Intergration-level test for build generator
"""

import unittest
from unittest.mock import patch, ANY

import yaml

from moulin.build_generator import generate_build
from moulin.build_conf import MoulinConfiguration


class TestBuilder(unittest.TestCase):
    def setUp(self):
        patcher = patch('moulin.ninja_syntax.Writer')
        self.Writer = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch('moulin.build_generator.open')
        self.opener = patcher.start()
        self.addCleanup(patcher.stop)

    def test_minimal(self):
        doc = """
desc: "Test build"
components:
  test:
    builder:
      type: "null"
    sources:
      - type: "null"
        """
        node = yaml.compose(doc)
        conf = MoulinConfiguration(node)
        generate_build(conf, "test.yaml")
        self.Writer.return_value.build.assert_any_call("fetch-test", "phony", ANY)
        self.Writer.return_value.build.assert_any_call("test", "phony", ANY)
        self.Writer.return_value.build.assert_any_call("build.ninja", "regenerate", ANY)

    def test_set_default(self):
        doc = """
desc: "Test build"
components:
  test:
    sources:
      - type: "null"
    default: true
    builder:
      type: "null"
        """
        node = yaml.compose(doc)
        conf = MoulinConfiguration(node)
        generate_build(conf, "test.yaml")
        self.Writer.return_value.default.assert_called_with("test")

    def test_no_default(self):
        doc = """
desc: "Test build"
components:
  test:
    sources:
      - type: "null"
    builder:
      type: "null"
        """
        node = yaml.compose(doc)
        conf = MoulinConfiguration(node)
        generate_build(conf, "test.yaml")
        self.Writer.return_value.default.assert_not_called()

    def test_flatten_sources(self):
        doc = """
desc: "Test build"
components:
  test:
    builder:
      type: "null"
    sources:
      -
        - type: "null"
        """
        node = yaml.compose(doc)
        conf = MoulinConfiguration(node)
        generate_build(conf, "test.yaml")
