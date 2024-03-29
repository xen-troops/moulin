# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""
Android open source project (AOSP) builder module
"""

import os.path
from typing import List
from moulin.yaml_wrapper import YamlValue
from moulin import ninja_syntax
from moulin import utils


def get_builder(conf: YamlValue, name: str, build_dir: str, src_stamps: List[str],
                generator: ninja_syntax.Writer):
    """
    Return configured AndroidBuilder class
    """
    return AndroidBuilder(conf, name, build_dir, src_stamps, generator)


def gen_build_rules(generator: ninja_syntax.Writer):
    """
    Generate yocto build rules for ninja
    """
    cmd = " && ".join([
        "export $env",
        "cd $build_dir",
        "source build/envsetup.sh",
        "lunch $lunch_target",
        "m -j",
    ])
    generator.rule("android_build",
                   command=f'bash -c "{cmd}"',
                   description="Invoke Android build system",
                   pool="console",
                   restat=True)
    generator.newline()


class AndroidBuilder:
    """
    AndroidBuilder class generates Ninja rules for given Android build configuration
    """
    def __init__(self, conf: YamlValue, name: str, build_dir: str, src_stamps: List[str],
                 generator: ninja_syntax.Writer):
        self.conf = conf
        self.name = name
        self.generator = generator
        self.src_stamps = src_stamps
        self.build_dir = build_dir

    def gen_build(self):
        """Generate ninja rules to build AOSP"""
        env_node = self.conf.get("env", None)
        if env_node:
            env_values = [x.as_str for x in env_node]
        else:
            env_values = []
        env = " ".join(env_values)

        env = utils.escape(env)

        variables = {
            "build_dir": self.build_dir,
            "env": env,
            "lunch_target": self.conf["lunch_target"].as_str,
            "name": self.name,
        }
        targets = self.get_targets()
        deps = list(self.src_stamps)

        additional_deps_node = self.conf.get("additional_deps", None)
        if additional_deps_node:
            deps.extend([os.path.join(self.build_dir, d.as_str) for d in additional_deps_node])

        self.generator.build(targets, "android_build", deps, variables=variables)
        self.generator.newline()

        return targets

    def get_targets(self):
        "Return list of targets that are generated by this build"
        return [os.path.join(self.build_dir, t.as_str) for t in self.conf["target_images"]]

    def capture_state(self):
        """
        This method should capture Android state for a reproducible builds.
        Luckily, there is nothing to do, as Android state is controlled solely by
        its repo state. And repo state is captured by repo fetcher code.
        """
