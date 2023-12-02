# SPDX-License-Identifier: Apache-2.0
# Copyright 2022 EPAM Systems
"""
Zephyr build generator
"""

import os.path
from typing import List, cast
from moulin.yaml_wrapper import YamlValue
from moulin import ninja_syntax
from moulin.utils import construct_fetcher_dep_cmd
from moulin import utils


def get_builder(conf: YamlValue, name: str, build_dir: str, src_stamps: List[str],
                generator: ninja_syntax.Writer):
    """
    Return configured Zephyr builder
    """
    return ZephyrBuilder(conf, name, build_dir, src_stamps, generator)


def gen_build_rules(generator: ninja_syntax.Writer):
    """
    Generate Zephyr build rules for ninja
    """
    cmd = " && ".join([
        # Generate fetcher dependency file
        construct_fetcher_dep_cmd(),
        "cd $build_dir",
        "$pull_ext_sources",
        "source zephyr/zephyr-env.sh",
        "$env west build -p auto -b $board -d $work_dir $target -- $shields $vars",
    ])
    generator.rule("zephyr_build",
                   command=f'bash -c "{cmd}"',
                   description="Invoke Zephyr build system",
                   pool="console",
                   deps="gcc",
                   depfile=".moulin_$name.d",
                   restat=True)
    generator.newline()


class ZephyrBuilder:
    """
    ZephyrBuilder class generates Ninja rules for Zephyr build configuration
    """
    def __init__(self, conf: YamlValue, name: str, build_dir: str, src_stamps: List[str],
                 generator: ninja_syntax.Writer):
        self.conf = conf
        self.name = name
        self.generator = generator
        self.src_stamps = src_stamps
        self.build_dir = build_dir

    def gen_build(self):
        """Generate Ninja rules to build Zephyr"""

        list_of_commands = []
        ext_deps = []
        ext_files_node = self.conf.get("ext_files", None)
        if ext_files_node:
            # if 'ext_files' node is present, then we:
            # - collect filenames to `ext_deps` to add them to build dependencies
            # - create destination directories, if required
            # - copy external files to build-dir (or destination subdirectory, is specified)
            for dest_name, src_node in cast(YamlValue, ext_files_node).items():
                ext_deps.append(src_node.as_str)
                rel_src_name = os.path.relpath(src_node.as_str, self.build_dir)
                dst_path_and_name = os.path.split(dest_name)
                if dst_path_and_name[0]:
                    list_of_commands.append(f"mkdir -p {dst_path_and_name[0]}")
                list_of_commands.append(f"cp {rel_src_name} {dest_name}")
        else:
            # if 'ext_files' are not provided, we need to use 'true' to avoid
            # '&&  &&' in 'gen_build_rules()' due to empty 'list_of_commands'
            list_of_commands.append("true")
        pull_ext_sources = " && ".join(list_of_commands)

        env_node = self.conf.get("env", None)
        if env_node:
            env_values = [x.as_str for x in env_node]
        else:
            env_values = []
        env = " ".join(env_values)

        env = utils.escape(env)

        shields_node = self.conf.get("shields", None)
        if shields_node:
            shields_vals = [x.as_str for x in shields_node]
            shields = f'-DSHIELD=\\"{" ".join(shields_vals)}\\"'
        else:
            shields = ""

        vars_node = self.conf.get("vars", None)
        if vars_node:
            vars_vals = [ZephyrBuilder.__escape_vars_vals(x.as_str) for x in vars_node]
            vars_value = " ".join([f"-D{var}" for var in vars_vals])
        else:
            vars_value = ""

        variables = {
            "name": self.name,
            "build_dir": self.build_dir,
            "board": self.conf["board"].as_str,
            "target": self.conf["target"].as_str,
            "work_dir": self.conf.get("work_dir", "zephyr/build").as_str,
            "shields": shields,
            "vars": vars_value,
            "env": env,
            "pull_ext_sources": pull_ext_sources,
        }
        targets = self.get_targets()
        deps = list(self.src_stamps)

        # we add 'ext_files' to dependencies, so ninja will be able
        # to start required tasks
        deps += ext_deps

        additional_deps_node = self.conf.get("additional_deps", None)

        if additional_deps_node:
            deps.extend([d.as_str for d in additional_deps_node])

        self.generator.build(targets, "zephyr_build", deps, variables=variables)
        self.generator.newline()

        return targets

    @staticmethod
    def __escape_vars_vals(var: str) -> str:
        """
        Escape the given variable value.

        Parameters:
        - var (str): The variable value to be escaped.

        Returns:
        - str: The escaped variable value.

        If the variable value starts with "CONFIG_", double quotation mark escaping is added,
        following the:
        https://github.com/zephyrproject-rtos/zephyr/pull/49267/commits/d77597783a4c148b70c389c8996112f8b6d1e5ed
        """
        if var.startswith("CONFIG_"):
            vars_vals = utils.escape(utils.escape(var))
        else:
            vars_vals = utils.escape(var)
        return vars_vals

    def get_targets(self):
        "Return list of targets that are generated by this build"
        return [os.path.join(self.build_dir, t.as_str) for t in self.conf["target_images"]]

    def capture_state(self):
        """
        This method should capture state for reproducible builds.
        """
