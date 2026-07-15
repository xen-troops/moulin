"""
Tests for Yocto builder
"""

import unittest
from unittest.mock import patch, ANY

import yaml

from moulin.build_generator import generate_build
from moulin.build_conf import MoulinConfiguration


class TestYoctoBuilder(unittest.TestCase):

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
      type: "yocto"
      build_target: core-image-minimal
      conf:
      target_images:
        - "target-image"
    sources:
      - type: "null"
        """
        node = yaml.compose(doc)
        conf = MoulinConfiguration(node)
        generate_build(conf, "test.yaml")
        self.Writer.return_value.build.assert_any_call(["test/build/target-image"],
                                                       "yocto_build",
                                                       ANY,
                                                       variables=ANY)

    def test_default_distro(self):
        doc = """
desc: "Test build"
components:
  test:
    builder:
      type: "yocto"
      build_target: core-image-minimal
      conf:
      target_images:
        - "target-image"
    sources:
      - type: "null"
        """
        node = yaml.compose(doc)
        conf = MoulinConfiguration(node)
        generate_build(conf, "test.yaml")
        # Find build call and analyze variables
        for call in self.Writer.return_value.build.call_args_list:
            if call.args[1] == 'yocto_build':
                self.assertIn("variables", call.kwargs)
                self.assertIn("distro_dir", call.kwargs["variables"])
                self.assertEqual(call.kwargs["variables"]["distro_dir"], "poky")
                break
        else:
            self.fail("Could not find yocto_build target")

    def test_set_distro(self):
        doc = """
desc: "Test build"
components:
  test:
    builder:
      type: "yocto"
      build_target: core-image-minimal
      base_distro: test-distro
      conf:
      target_images:
        - "target-image"
    sources:
      - type: "null"
        """
        node = yaml.compose(doc)
        conf = MoulinConfiguration(node)
        generate_build(conf, "test.yaml")
        # Find build call and analyze variables
        for call in self.Writer.return_value.build.call_args_list:
            if call.args[1] == 'yocto_build':
                self.assertIn("variables", call.kwargs)
                self.assertIn("distro_dir", call.kwargs["variables"])
                self.assertEqual(call.kwargs["variables"]["distro_dir"], "test-distro")
                break
        else:
            self.fail("Could not find yocto_build target")

    def test_layer_sync_passes_distro_dir(self):
        doc = """
desc: "Test build"
components:
  test:
    builder:
      type: "yocto"
      build_target: core-image-minimal
      base_distro: openembedded-core
      conf:
      layers:
        - "../meta-layer"
      target_images:
        - "target-image"
    sources:
      - type: "null"
        """
        node = yaml.compose(doc)
        conf = MoulinConfiguration(node)
        generate_build(conf, "test.yaml")

        self.Writer.return_value.rule.assert_any_call(
            "yocto_update_layers",
            command=ANY,
            description="Synchronize Yocto layers with a moulin configuration file",
            pool="console",
            restat=True,
        )
        for call in self.Writer.return_value.rule.call_args_list:
            if call.args[0] == "yocto_update_layers":
                command = call.kwargs["command"]
                self.assertIn("--distro-dir $distro_dir", command)
                break
        else:
            self.fail("Could not find yocto_update_layers rule")

    def test_target_images_expansion(self):
        doc = """
desc: "Test build"
common_data:
  common_target_images: &COMMON_TARGET_IMAGES
    - "common_image_1"
    - "common_image_2"
components:
  test:
    builder:
      type: "yocto"
      build_target: core-image-minimal
      conf:
      target_images:
        - "target-image"
        - *COMMON_TARGET_IMAGES
    sources:
      - type: "null"
        """
        node = yaml.compose(doc)
        conf = MoulinConfiguration(node)
        generate_build(conf, "test.yaml")
        # Find build call and analyze variables
        for call in self.Writer.return_value.build.call_args_list:
            if call.args[1] == 'yocto_build':
                self.assertListEqual(call.args[0], [
                    "test/build/target-image", "test/build/common_image_1",
                    "test/build/common_image_2"
                ])
                break
        else:
            self.fail("Could not find yocto_build target")

    def test_default_deps(self):
        doc = """
desc: "Test build"
components:
  test:
    builder:
      type: "yocto"
      build_target: core-image-minimal
      conf:
      target_images:
        - "target-image"
    sources:
      - type: "null"
        """
        node = yaml.compose(doc)
        conf = MoulinConfiguration(node)
        generate_build(conf, "test.yaml")
        # Find build call and analyze variables
        for call in self.Writer.return_value.build.call_args_list:
            if call.args[1] == 'yocto_init_env':
                self.assertListEqual(call.args[2], ["null.stamp"])
                break
        else:
            self.fail("Could not find yocto_init_env target")

    def test_additional_deps_expansion(self):
        doc = """
desc: "Test build"
common_data:
  common_deps: &COMMON_DEPS
    - "common_dep_1"
    - "common_dep_2"
components:
  test:
    builder:
      type: "yocto"
      build_target: core-image-minimal
      conf:
      target_images:
        - "target-image"
      additional_deps:
        - "explicit-dep"
        - *COMMON_DEPS
    sources:
      - type: "null"
        """
        node = yaml.compose(doc)
        conf = MoulinConfiguration(node)
        generate_build(conf, "test.yaml")
        # Find build call and analyze variables
        for call in self.Writer.return_value.build.call_args_list:
            if call.args[1] == 'yocto_init_env':
                self.assertListEqual(
                    call.args[2],
                    ["null.stamp", "test/explicit-dep", "test/common_dep_1", "test/common_dep_2"])
                break
        else:
            self.fail("Could not find yocto_init_env target")
