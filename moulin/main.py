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
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

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
        return

    config_args = config_argparser.parse_args(extra_opts)
    conf.complete_init(vars(config_args))
    log.info("Generating build.ninja")

    document = conf.get_document()
    build_generator.generate_build(document, args.conf)
