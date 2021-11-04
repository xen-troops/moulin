# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""
This module takes processed YAML config tree (with variables expanded
and parameters applied) and produces Ninja build file
"""

import os.path
import sys
from typing import Optional, List

from importlib import import_module
from moulin import ninja_syntax
from moulin import rouge
from moulin import yaml_helpers as yh
from moulin.build_conf import MoulinConfiguration

BUILD_FILENAME = 'build.ninja'


def generate_build(conf: MoulinConfiguration,
                   conf_file_name,
                   ninja_build_fname=BUILD_FILENAME) -> None:
    """
    Write Ninja build file based on pre-processed config tree
    """
    generator = ninja_syntax.Writer(open(ninja_build_fname, 'w'), width=120)

    _gen_regenerate(conf_file_name, generator)

    _gen_fetcherdep_rules(generator)
    rouge.gen_build_rules(generator)

    _flatten_sources(conf)
    # We want to have all Ninja build rules before all actual build
    # commands. So we need to scan conf twice. On the first scan we will
    # determine and load all required plugins. On the same time, we'll ask them
    # to generate Ninja rules.
    builder_modules, fetcher_modules = _get_modules(conf, generator)

    # Now we have all plugins loaded and we can generate some build rules
    for comp_name_node, component in yh.get_mandatory_mapping(conf.get_root_node(), "components"):
        comp_name: str = comp_name_node.value
        build_dir = yh.get_str_value(component, "build-dir", default=comp_name)[0]
        builder_conf = yh.get_mandatory_mapping_node(component, "builder")

        source_stamps = []
        for source in yh.get_mandatory_sequence(component, "sources"):
            source_type = yh.get_mandatory_str_value(source, "type")[0]
            fetcher_module = fetcher_modules[source_type]
            fetcher = fetcher_module.get_fetcher(source, build_dir, generator)
            source_stamps.append(fetcher.gen_fetch())

        # Generate handy 'fetch-{component}' rule
        generator.build(f"fetch-{comp_name}", "phony", source_stamps)
        generator.newline()

        builder_type = yh.get_mandatory_str_value(builder_conf, "type")[0]
        builder_module = builder_modules[builder_type]
        builder = builder_module.get_builder(builder_conf, comp_name, build_dir, source_stamps,
                                             generator)

        build_stamps = builder.gen_build()
        generator.build(comp_name, "phony", build_stamps)
        generator.newline()
        if yh.get_boolean_value(component, "default")[0]:
            generator.default(comp_name)

        generator.build(f".moulin_{comp_name}_dyndep",
                        "fetcherdep",
                        variables=dict(component=comp_name))
    rouge.gen_build(generator, rouge.get_available_images(conf.get_root_node()))


def generate_fetcher_dyndep(conf: MoulinConfiguration, component: str):
    _flatten_sources(conf)
    generator = ninja_syntax.Writer(open(f".moulin_{component}_dyndep", 'w'), width=120)
    generator.variable("ninja_dyndep_version", 1)
    generator.newline()

    builder_modules, fetcher_modules = _get_modules(conf, None)
    components_node = yh.get_mandatory_mapping_node(conf.get_root_node(), "components")
    component_node = yh.get_mandatory_mapping_node(components_node, component)
    build_dir = yh.get_str_value(component_node, "build-dir", default=component)[0]
    builder_node = yh.get_mandatory_mapping_node(component_node, "builder")
    builder_type = yh.get_mandatory_str_value(builder_node, "type")[0]
    builder_module = builder_modules[builder_type]
    builder = builder_module.get_builder(builder_node, component, build_dir, [], generator)

    deps: List[str] = []
    targets = builder.get_targets()
    for source in yh.get_mandatory_sequence(component_node, "sources"):
        source_type = yh.get_mandatory_str_value(source, "type")[0]
        fetcher_module = fetcher_modules[source_type]
        fetcher = fetcher_module.get_fetcher(source, build_dir, generator)
        deps.extend(fetcher.get_file_list())
    generator.build(targets[0], "dyndep", implicit=deps)


def _gen_regenerate(conf_file_name, generator: ninja_syntax.Writer):
    this_script = os.path.abspath(sys.argv[0])
    args = " ".join(sys.argv[1:])
    generator.rule("regenerate", command=f"{this_script} {args}", generator=1)
    generator.newline()
    generator.build(BUILD_FILENAME, "regenerate", [this_script, conf_file_name])
    generator.newline()


def _gen_fetcherdep_rules(generator: ninja_syntax.Writer):
    this_script = os.path.abspath(sys.argv[0])
    args = " ".join(sys.argv[1:])
    generator.rule("fetcherdep",
                   command=f"{this_script} {args} --fetcherdep $component",
                   description="Generate dyndeps for '$component'")
    generator.newline()


def _flatten_sources(conf: MoulinConfiguration):
    for _, component in yh.get_mandatory_mapping(conf.get_root_node(), "components"):
        yh.flatten_list(yh.get_mandatory_sequence_node(component, "sources"))


def _get_modules(conf: MoulinConfiguration, generator: Optional[ninja_syntax.Writer]):
    builder_modules = {}
    fetcher_modules = {}
    for _, component in yh.get_mandatory_mapping(conf.get_root_node(), "components"):
        builder_node = yh.get_mandatory_mapping_node(component, "builder")
        b_type = yh.get_mandatory_str_value(builder_node, "type")[0]
        if b_type not in builder_modules:
            builder_modules[b_type] = _prepare_builder(b_type, generator)
        for source in yh.get_mandatory_sequence(component, "sources"):
            f_type = yh.get_mandatory_str_value(source, "type")[0]
            if f_type not in fetcher_modules:
                fetcher_modules[f_type] = _prepare_fetcher(f_type, generator)
    return builder_modules, fetcher_modules


def _prepare_builder(builder, generator):
    module = import_module(f".builders.{builder}", __package__)
    if generator:
        module.gen_build_rules(generator)
    return module


def _prepare_fetcher(fetcher, generator):
    module = import_module(f".fetchers.{fetcher}", __package__)
    if generator:
        module.gen_build_rules(generator)
    return module
