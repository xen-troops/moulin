# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""
Moulin main entry point
"""

import argparse
import yaml
import sys

from moulin import build_generator
from moulin import build_conf_processor

try:
    from yaml import CLoader as YamlLoader
except ImportError:
    from yaml import Loader as YamlLoader


def console_entry():
    """Console entry point"""

    parser = argparse.ArgumentParser(description='Moulin meta-build system')
    parser.add_argument('conf',
                        metavar='build.yaml',
                        type=str,
                        help='YAML file with build description')
    parser.add_argument('--help-config',
                        action='store_true',
                        help="Show help for given config file")

    args, extra_opts = parser.parse_known_args()
    conf = yaml.load(open(args.conf), Loader=YamlLoader)

    if "desc" not in conf:
        raise Exception("'desc' field in config file is mandatory!")

    prog = f"{sys.argv[0]} {args.conf}"
    desc = f"Config file description: {conf['desc']}"
    config_argparser = argparse.ArgumentParser(description=desc,
                                               prog=prog,
                                               add_help=False)
    for parameter in build_conf_processor.get_possible_parameters(conf):
        config_argparser.add_argument(f"--{parameter.name}",
                                      choices=parameter.choices,
                                      default=parameter.default,
                                      help=parameter.desc)

    if args.help_config:
        config_argparser.print_help()
        return

    config_args = config_argparser.parse_args(extra_opts)
    conf = build_conf_processor.process_config(conf, vars(config_args))
    build_generator.generate_build(conf, args.conf)
