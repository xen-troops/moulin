# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""
Android open source project (AOSP) builder module
"""

import os.path


def get_builder(conf, name, src_stamps, generator):
    """
    Return configured AndroidBuilder class
    """
    return AndroidBuilder(conf, name, src_stamps, generator)


def gen_build_rules(generator):
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
                   pool="console")
    generator.newline()


class AndroidBuilder:
    """
    AndroidBuilder class generates Ninja rules for given Android build configuration
    """
    def __init__(self, conf, name, src_stamps, generator):
        self.conf = conf
        self.name = name
        self.generator = generator
        self.src_stamps = src_stamps
        self.build_dir = self.conf["build-dir"]

    def gen_build(self):
        """Generate ninja rules to build AOSP"""

        env = " ".join(self.conf["env"])
        variables = {
            "build_dir": self.build_dir,
            "env": env,
            "lunch_target": self.conf["lunch-target"]
        }
        targets = [
            os.path.join(self.build_dir, t) for t in self.conf["target_images"]
        ]
        self.generator.build(targets,
                             "android_build",
                             self.src_stamps,
                             variables=variables)
        self.generator.newline()

        return targets

    def capture_state(self):
        """
        This method should capture Android state for a reproducible builds.
        Luckily, there is nothing to do, as Android state is controlled solely by
        its repo state. And repo state is captured by repo fetcher code.
        """
