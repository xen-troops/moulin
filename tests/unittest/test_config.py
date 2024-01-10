"""
Intergration-level test for MoulinConfiguration
"""

import unittest
import unittest.mock

import yaml

from packaging.version import Version

from moulin.yaml_helpers import YAMLProcessingError
from moulin.build_conf import MoulinConfiguration


def gen_config(doc: str) -> MoulinConfiguration:
    node = yaml.compose(doc)
    return MoulinConfiguration(node)


class TestMoulinConfigurationBasic(unittest.TestCase):
    def test_desc(self):
        doc = """
desc: "Test build"
        """
        conf = gen_config(doc)
        self.assertEqual(conf.desc, "Test build")

    def test_no_desc(self):
        doc = """
 nodesc: ""
        """
        with self.assertRaisesRegex(YAMLProcessingError, "desc key is mandatory"):
            gen_config(doc)

    def test_min_ver(self):
        doc = """
desc: "Test build"
min_ver: "0.3"
        """
        conf = gen_config(doc)
        self.assertEqual(conf.min_ver, Version("0.3"))

    def test_no_min_ver(self):
        doc = """
desc: "Test build"
        """
        conf = gen_config(doc)
        self.assertIsNone(conf.min_ver)


class TestMoulinConfigurationVariables(unittest.TestCase):
    def test_simple(self):
        doc = """
desc: "Test build"
variables:
        A: test
        B: "%{A}%{A}"
        C: "%{B}%{B}"
        D: "%{A}x%{A}"
test:
        - "%{A}"
        - "%{B}"
        - "%{C}"
        - "%{D}"
"""
        expected = ["test", "testtest", "testtesttesttest", "testxtest"]
        conf = gen_config(doc)
        conf.complete_init(None)
        root = conf.get_root()
        self.assertEqual([x.as_str for x in root["test"]], expected)

    def test_loop(self):
        doc = """
desc: "Test build"
variables:
        A: "%{B}"
        B: "%{A}"
"""
        conf = gen_config(doc)
        with self.assertRaisesRegex(Exception, "circular dependency"):
            conf.complete_init(None)

    def test_self_loop(self):
        doc = """
desc: "Test build"
variables:
        A: "%{A}"
"""
        conf = gen_config(doc)
        with self.assertRaisesRegex(YAMLProcessingError, "refers to self"):
            conf.complete_init(None)

    def test_no_var(self):
        doc = """
desc: "Test build"
test: "%{A}"
"""
        conf = gen_config(doc)
        with self.assertRaisesRegex(YAMLProcessingError, "unknown variable"):
            conf.complete_init(None)

    def test_escape(self):
        doc = """
desc: "Test build"
test:
  - "%"
  - "%%"
  - "%%{A}"
  - "%{A"
"""
        expected = ["%", "%%", "%%{A}", "%{A"]
        conf = gen_config(doc)
        conf.complete_init(None)
        root = conf.get_root()
        self.assertEqual([x.as_str for x in root["test"]], expected)


class TestMoulinConfigurationOptions(unittest.TestCase):
    def test_list_params(self):
        doc = """
desc: "Test build"
parameters:
  paramA:
    desc: "Parameter A"
  paramB:
    desc: "Parameter B"
"""
        expected = ["paramA", "paramB"]
        conf = gen_config(doc)
        params = conf.get_parameters()
        self.assertEqual(list(params.keys()), expected)

    def test_list_variants(self):
        doc = """
desc: "Test build"
parameters:
  paramA:
    desc: "Parameter A"
    variantA:
      default: false
    variantB:
      default: false
    variantC:
      default: false
"""
        expected = ["variantA", "variantB", "variantC"]
        conf = gen_config(doc)
        param = conf.get_parameters()["paramA"]
        self.assertEqual(list(param.variants.keys()), expected)

    def test_default_variant(self):
        doc = """
desc: "Test build"
val: X
parameters:
  paramA:
    desc: "Parameter A"
    variantA:
      default: true
    variantB:
      default: false
"""
        conf = gen_config(doc)
        param = conf.get_parameters()["paramA"]
        self.assertIsNotNone(param.default)

    def test_apply_variant(self):
        doc = """
desc: "Test build"
val: X
parameters:
  paramA:
    desc: "Parameter A"
    variantA:
      overrides:
        val: A
    variantB:
      overrides:
        val: B
"""
        conf = gen_config(doc)
        conf.complete_init({"paramA": "variantA"})
        root = conf.get_root()
        self.assertEqual(root["val"].as_str, "A")

        conf = gen_config(doc)
        conf.complete_init({"paramA": "variantB"})
        root = conf.get_root()
        self.assertEqual(root["val"].as_str, "B")
