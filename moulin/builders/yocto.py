# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""
Yocto builder module
"""

import os.path
import shlex
from moulin.utils import create_stamp_name


def get_builder(conf, name, build_dir, src_stamps, generator):
    """
    Return configured YoctoBuilder class
    """
    return YoctoBuilder(conf, name, build_dir, src_stamps, generator)


def gen_build_rules(generator):
    """
    Generate yocto build rules for ninja
    """
    # Create build dir by calling poky/oe-init-build-env script
    cmd = " && ".join([
        "cd $yocto_dir",
        "source poky/oe-init-build-env $work_dir",
    ])
    generator.rule("yocto_init_env",
                   command=f'bash -c "{cmd}"',
                   description="Initialize Yocto build environment")
    generator.newline()

    # Add bitbake layers by calling bitbake-layers script
    cmd = " && ".join([
        "cd $yocto_dir",
        "source poky/oe-init-build-env $work_dir",
        "bitbake-layers add-layer $layers",
        "touch $out",
    ])
    generator.rule("yocto_add_layers",
                   command=f'bash -c "{cmd}"',
                   description="Add yocto layers",
                   pool="console")
    generator.newline()

    # Append local.conf with our own configuration
    cmd = " && ".join([
        "cd $yocto_dir",
        "for x in $conf; do echo $$x >> $work_dir/conf/local.conf; done",
        "touch $out",
    ])
    generator.rule("yocto_update_conf",
                   command=cmd,
                   description="Update local.conf")
    generator.newline()

    # Invoke bitbake. This rule uses "console" pool so we can see the bitbake output.
    cmd = " && ".join([
        "cd $yocto_dir",
        "source poky/oe-init-build-env $work_dir",
        "bitbake $target",
    ])
    generator.rule("yocto_build",
                   command=f'bash -c "{cmd}"',
                   description="Yocto Build: $name",
                   pool="console")


def _flatten_yocto_conf(conf):
    """
    Flatten conf entries. While using YAML *entries syntax, we will get list of conf
    entries inside of other list. To overcome this, we need to move inner list 'up'
    """

    # Problem is conf entries that it is list itself
    # But we can convert inner lists to tuples, which is also good thing
    result = []
    for entry in conf:
        if isinstance(entry[0], list):
            result.extend(entry)
        else:
            result.append(entry)
    return list(map(tuple, result))


class YoctoBuilder:
    """
    YoctoBuilder class generates Ninja rules for given build configuration
    """
    def __init__(self, conf, name, build_dir, src_stamps, generator):
        self.conf = conf
        self.name = name
        self.generator = generator
        self.src_stamps = src_stamps
        # With yocto builder it is possible to have multiple builds with the same set of
        # layers. Thus, we have two variables - build_dir and work_dir
        # - yocto_dir is the upper directory where layers are stored. Basically, we should
        #   have "poky" in our yocto_dir
        # - work_dir is the build directory where we can find conf/local.conf, tmp and other
        #   directories. It is called "build" by default
        self.yocto_dir = build_dir
        self.work_dir = self.conf.get("work_dir", "build")

    def _get_external_src(self):
        if "external_src" not in self.conf:
            return []

        ret = []
        for (key, val) in self.conf["external_src"].items():
            if isinstance(val, list):
                path = os.path.join(val)
            else:
                path = val
            path = os.path.abspath(path)
            ret.append((f"EXTERNALSRC_pn-{key}", path))

        return ret

    def gen_build(self):
        """Generate ninja rules to build yocto/poky"""
        common_variables = {
            "yocto_dir": self.yocto_dir,
            "work_dir": self.work_dir
        }

        # First we need to ensure that "conf" dir exists
        env_target = os.path.join(self.yocto_dir, self.work_dir, "conf")
        self.generator.build(env_target,
                             "yocto_init_env",
                             self.src_stamps,
                             variables=common_variables)

        # Then we need to add layers
        layers = " ".join(self.conf.get("layers", []))
        layers_stamp = create_stamp_name(self.yocto_dir, self.work_dir,
                                         "yocto", "layers")
        self.generator.build(layers_stamp,
                             "yocto_add_layers",
                             env_target,
                             variables=dict(common_variables, layers=layers))

        # Next - update local.conf
        local_conf_stamp = create_stamp_name(self.yocto_dir, self.work_dir,
                                             "yocto", "lolcal_conf")
        if "conf" in self.conf:
            local_conf = _flatten_yocto_conf(self.conf["conf"])
        else:
            local_conf = []

        # Handle external sources (like build artifacts from some other build)
        local_conf.extend(self._get_external_src())

        # '$' is a ninja escape character so we need to quote it
        local_conf_lines = [
            shlex.quote(f'{k.replace("$", "$$")} = "{v.replace("$", "$$")}"')
            for k, v in local_conf
        ]

        self.generator.build(local_conf_stamp,
                             "yocto_update_conf",
                             layers_stamp,
                             variables=dict(common_variables,
                                            conf=" ".join(local_conf_lines)))
        self.generator.newline()

        self.generator.build(f"conf-{self.name}", "phony", local_conf_stamp)
        self.generator.newline()

        # Next step - invoke bitbake. At last :)
        targets = [
            os.path.join(self.yocto_dir, self.work_dir, t)
            for t in self.conf["target_images"]
        ]
        deps = [
            os.path.join(self.yocto_dir, d)
            for d in self.conf.get("additional_deps", [])
        ]
        deps.append(local_conf_stamp)
        self.generator.build(targets,
                             "yocto_build",
                             deps,
                             variables=dict(common_variables,
                                            target=self.conf["build_target"],
                                            name=self.name))

        return targets

    def capture_state(self):
        """
        Update stored local conf with actual SRCREVs for VCS-based recipes.
        This should ensure that we can reproduce this exact build later
        """
