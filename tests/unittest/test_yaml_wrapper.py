"""
Tests for Yaml wrapper
"""


import unittest
import yaml
from moulin.yaml_wrapper import YamlValue, _YamlDefaultValue
from moulin.yaml_helpers import YAMLProcessingError
from typing import Tuple


def gen_wrappers(val) -> Tuple[YamlValue, _YamlDefaultValue]:
    mnode = yaml.compose(f"test: {val}")
    _, node = mnode.value[0]
    yval = YamlValue(node)
    ydefval = _YamlDefaultValue(val)
    return yval, ydefval


class TestMoulinYamlWrapper(unittest.TestCase):

    def test_str(self):
        val = "test"
        intval = 42

        yval, ydefval = gen_wrappers(val)

        self.assertEqual(yval.as_str, val)
        self.assertEqual(ydefval.as_str, val)

        yval, ydefval = gen_wrappers(intval)

        with self.assertRaisesRegex(YAMLProcessingError, "Expected string value"):
            yval.as_str

        with self.assertRaisesRegex(TypeError, "Expected string value"):
            ydefval.as_str

    def test_int(self):
        val = 42
        strval = "test"

        yval, ydefval = gen_wrappers(val)

        self.assertEqual(yval.as_int, val)
        self.assertEqual(ydefval.as_int, val)

        yval, ydefval = gen_wrappers(strval)

        with self.assertRaisesRegex(YAMLProcessingError, "Expected integer value"):
            yval.as_int

        with self.assertRaisesRegex(TypeError, "Expected integer value"):
            ydefval.as_int

    def test_float(self):
        val = 42.0
        intval = 42

        yval, ydefval = gen_wrappers(val)

        self.assertEqual(yval.as_float, val)
        self.assertEqual(ydefval.as_float, val)

        yval, ydefval = gen_wrappers(intval)

        with self.assertRaisesRegex(YAMLProcessingError, "Expected floating point value"):
            yval.as_float

        with self.assertRaisesRegex(TypeError, "Expected floating point value"):
            ydefval.as_float

    def test_boolean(self):
        val = True
        intval = 42

        yval, ydefval = gen_wrappers(val)

        self.assertEqual(yval.as_bool, val)
        self.assertEqual(ydefval.as_bool, val)

        yval, ydefval = gen_wrappers(intval)

        with self.assertRaisesRegex(YAMLProcessingError, "Expected boolean value"):
            yval.as_bool

        with self.assertRaisesRegex(TypeError, "Expected boolean value"):
            ydefval.as_bool

    def test_list(self):
        val = [1, 2, 3]
        doc = """
test:
  - 1
  - 2
  - 3
"""
        mnode = yaml.compose(doc)
        _, node = mnode.value[0]
        yval = YamlValue(node)
        ydefval = _YamlDefaultValue(val)

        self.assertTrue(yval.is_list)
        self.assertTrue(ydefval.is_list)
        self.assertEqual(len(yval), len(val))
        self.assertEqual(len(ydefval), len(val))

        for i in range(len(val)):
            self.assertEqual(yval[i].as_int, val[i])
            self.assertEqual(ydefval[i].as_int, val[i])

        for i, item in enumerate(yval):
            self.assertEqual(item.as_int, val[i])

        for i, item in enumerate(ydefval):
            self.assertEqual(item.as_int, val[i])

        yval[0] = 4
        ydefval[0] = 4
        self.assertEqual(yval[0].as_int, 4)
        self.assertEqual(ydefval[0].as_int, 4)

        with self.assertRaises(IndexError):
            yval[5]
        with self.assertRaises(IndexError):
            ydefval[5]

    def test_list_false(self):
        val = 1

        yval, ydefval = gen_wrappers(val)

        self.assertFalse(yval.is_list)
        self.assertFalse(ydefval.is_list)

        with self.assertRaisesRegex(YAMLProcessingError, "SequenceNode node is expected"):
            yval[0]

        with self.assertRaisesRegex(TypeError, "Expected list value"):
            ydefval[0]

    def test_dict(self):
        val = {"A": 1, "B": 2, "C": 3}
        doc = """
test:
    A: 1
    B: 2
    C: 3
"""
        mnode = yaml.compose(doc)
        _, node = mnode.value[0]
        yval = YamlValue(node)
        ydefval = _YamlDefaultValue(val)

        for k in val.keys():
            self.assertTrue(k in yval.keys())
            self.assertEqual(yval[k].as_int, val[k])
            self.assertEqual(yval.get(k, 1).as_int, val[k])
            self.assertTrue(k in ydefval.keys())
            self.assertEqual(ydefval[k].as_int, val[k])
            self.assertEqual(ydefval.get(k, 1).as_int, val[k])

        for k, v in yval.items():
            self.assertEqual(v.as_int, val[k])

        for k, v in ydefval.items():
            self.assertEqual(v.as_int, val[k])

        self.assertEqual(yval.get("WRONGKEY", 99).as_int, 99)
        self.assertEqual(ydefval.get("WRONGKEY", 99).as_int, 99)

        yval["A"] = 4
        ydefval["A"] = 4
        yval["B"] = "test"
        ydefval["B"] = "test"
        yval["C"] = 42.0
        ydefval["C"] = 42.0

        self.assertEqual(yval["A"].as_int, 4)
        self.assertEqual(ydefval["A"].as_int, 4)
        self.assertEqual(yval["B"].as_str, "test")
        self.assertEqual(ydefval["B"].as_str, "test")
        self.assertEqual(yval["C"].as_float, 42.0)
        self.assertEqual(ydefval["C"].as_float, 42.0)

        with self.assertRaisesRegex(KeyError, "Key should have either type 'str' or 'int"):
            yval[42.0] = 1

        with self.assertRaisesRegex(KeyError, "Key should have either type 'str' or 'int"):
            ydefval[42.0] = 1

    def test_dict_false(self):
        val = 1

        yval, ydefval = gen_wrappers(val)

        self.assertFalse(yval.is_list)
        self.assertFalse(ydefval.is_list)

        with self.assertRaisesRegex(YAMLProcessingError, "Mapping node is expected"):
            yval["A"]

        with self.assertRaisesRegex(TypeError, "Expected dict value"):
            ydefval["A"]
