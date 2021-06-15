# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""
This module takes processed YAML config tree (with variables expanded
and parameters applied) and produces Ninja build file
"""

import os.path
import sys

from importlib import import_module
from moulin import ninja_syntax

BUILD_FILENAME = 'build.ninja'


def generate_build(conf,
                   conf_file_name,
                   ninja_build_fname=BUILD_FILENAME) -> None:
    """
    Write Ninja build file based on pre-processed config tree
    """
    generator = ninja_syntax.Writer(open(ninja_build_fname, 'w'))

    _gen_regenerate(conf_file_name, generator)
    # We want to have all Ninja build rules before all actual build
    # commands. So we need to scan conf twice. On the first scan we will
    # determine and load all required plugins. On the same time, we'll ask them
    # to generate Ninja rules.
    builder_modules, fetcher_modules = _get_modules(conf, generator)

    # Now we have all plugins loaded and we can generate some build rules
    for comp_name, component in conf["components"].items():
        # build-dir parameter is optional
        builder_conf = component["builder"]
        build_dir = builder_conf.get("build-dir", comp_name)
        if "build-dir" not in builder_conf:
            builder_conf["build-dir"] = build_dir

        source_stamps = []
        for source in component["sources"]:
            fetcher_module = fetcher_modules[source["type"]]
            fetcher = fetcher_module.get_fetcher(source, build_dir, generator)
            source_stamps.append(fetcher.gen_fetch())

        # Generate handy 'fetch-{component}' rule
        generator.build(f"fetch-{comp_name}", "phony", source_stamps)
        generator.newline()

        builder_module = builder_modules[builder_conf["type"]]
        builder = builder_module.get_builder(builder_conf, comp_name,
                                             source_stamps, generator)

        build_stamps = builder.gen_build()
        generator.build(comp_name, "phony", build_stamps)
        generator.newline()
        if component.get("default", False):
            generator.default(comp_name)


def _gen_regenerate(conf_file_name, generator):
    this_script = os.path.abspath(sys.argv[0])
    args = " ".join(sys.argv[1:])
    generator.rule("regenerate", command=f"{this_script} {args}", generator=1)
    generator.newline()
    generator.build(BUILD_FILENAME, "regenerate",
                    [this_script, conf_file_name])
    generator.newline()


def _get_modules(conf, generator):
    builder_modules = {}
    fetcher_modules = {}
    for component in conf["components"].values():
        b_type = component["builder"]["type"]
        if b_type not in builder_modules:
            builder_modules[b_type] = _prepare_builder(b_type, generator)
        for source in component["sources"]:
            f_type = source["type"]
            if f_type not in fetcher_modules:
                fetcher_modules[f_type] = _prepare_fetcher(f_type, generator)
    return builder_modules, fetcher_modules


def _prepare_builder(builder, generator):
    module = import_module(f".builders.{builder}", __package__)
    module.gen_build_rules(generator)
    return module


def _prepare_fetcher(fetcher, generator):
    module = import_module(f".fetchers.{fetcher}", __package__)
    module.gen_build_rules(generator)
    return module
