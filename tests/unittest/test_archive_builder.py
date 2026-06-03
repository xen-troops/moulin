"""
Tests for Archive builder
"""

import unittest
from unittest.mock import patch, ANY

import yaml

from moulin.build_generator import generate_build
from moulin.build_conf import MoulinConfiguration


class TestArchiveBuilder(unittest.TestCase):

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
      type: "archive"
      name: "file.tar.bz2"
      items:
        - "test_item_1"
    sources:
      - type: "null"
        """
        node = yaml.compose(doc)
        conf = MoulinConfiguration(node)
        generate_build(conf, "test.yaml")
        self.Writer.return_value.build.assert_any_call(["test/file.tar.bz2"],
                                                       "tar_pack", ["null.stamp", "./test_item_1"],
                                                       variables=ANY)

    def test_expand_items(self):
        doc = """
desc: "Test build"
common:
  ites: &COMMON_ITEMS
   - "common_item1"
   - "common_item2"
components:
  test:
    builder:
      type: "archive"
      name: "file.tar.bz2"
      items:
        - "test_item_1"
        - *COMMON_ITEMS
    sources:
      - type: "null"
        """
        node = yaml.compose(doc)
        conf = MoulinConfiguration(node)
        generate_build(conf, "test.yaml")
        self.Writer.return_value.build.assert_any_call(
            ["test/file.tar.bz2"],
            "tar_pack", ["null.stamp", "./test_item_1", "./common_item1", "./common_item2"],
            variables=ANY)
