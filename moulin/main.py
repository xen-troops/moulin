# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""
Moulin main entry point
"""

import argparse
import logging
import sys
import importlib_metadata
import yaml
from packaging.version import Version

from moulin import build_generator
from moulin.build_conf import MoulinConfiguration

log = logging.getLogger(__name__)


def moulin_entry():
    """Console entry point for moulin"""

    parser = argparse.ArgumentParser(description='Moulin meta-build system')
    parser.add_argument('conf',
                        metavar='build.yaml',
                        type=str,
                        help='YAML file with build description')
    parser.add_argument('--help-config',
                        action='store_true',
                        help="Show help for given config file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--dump", action="store_true", help="Dump processed YAML document")

    if additional_opts:
        for option_args, option_kwargs in additional_opts:
            parser.add_argument(*option_args, **option_kwargs)
    if exclusive_opts:
        for exclusive_set in exclusive_opts:
            group = parser.add_mutually_exclusive_group()
            for option_args, option_kwargs in exclusive_set:
                group.add_argument(*option_args, **option_kwargs)

    return parser


def _handle_shared_opts(description: str,
                        additional_opts: List[OptionDef] = None,
                        exclusive_opts: List[List[OptionDef]] = None):

    parser = _prepre_shared_opts(description, additional_opts, exclusive_opts)

    args, extra_opts = parser.parse_known_args()

    loglevel = logging.INFO
    if args.verbose:
        loglevel = logging.DEBUG
    logging.basicConfig(level=loglevel, format="[%(levelname)s] %(message)s")

    conf = MoulinConfiguration(yaml.compose(open(args.conf)))

    if conf.min_ver:
        our_ver = Version(importlib_metadata.version("moulin"))
        if our_ver < conf.min_ver:
            raise Exception(f"Config file requires version {conf.min_ver}," +
                            " while you are running mouilin {our_ver}")

    prog = f"{sys.argv[0]} {args.conf}"
    desc = f"Config file description: {conf.desc}"
    config_argparser = argparse.ArgumentParser(description=desc, prog=prog, add_help=False)
    for parameter in conf.get_parameters().values():
        config_argparser.add_argument(f"--{parameter.name}",
                                      choices=[x.name for x in parameter.variants.values()],
                                      default=parameter.default.name,
                                      help=parameter.desc)

    if args.help_config:
        config_argparser.print_help()
        sys.exit(0)

    config_args = config_argparser.parse_args(extra_opts)
    conf.complete_init(vars(config_args))

    if args.dump:
        print(conf.dumps())

    return conf, args


def moulin_entry():
    """Console entry point for moulin"""

    conf, args = _handle_shared_opts(
        f'Moulin meta-build system v{Version(importlib_metadata.version("moulin"))}')
    log.info("Generating build.ninja")

    document = conf.get_document()
    build_generator.generate_build(document, args.conf)
