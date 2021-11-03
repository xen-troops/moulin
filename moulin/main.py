# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""
Moulin main entry point
"""

import argparse
import logging
import sys
from time import time
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Any
import importlib_metadata
import yaml

from packaging.version import Version

from moulin import build_generator
from moulin.build_conf import MoulinConfiguration
import moulin.rouge
import moulin.rouge.block_entry

log = logging.getLogger(__name__)

OptionDef = Tuple[List[str], Dict[str, Any]]


def _prepre_shared_opts(description: str,
                        additional_opts: List[OptionDef] = None,
                        exclusive_opts: List[List[OptionDef]] = None):

    parser = argparse.ArgumentParser(description=description)
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
                            f" while you are running mouilin {our_ver}")

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

    build_generator.generate_build(conf, args.conf)


def rouge_entry():
    """Console entry point for rouge"""

    start_time = time()

    additional_opts = [
        (["-f", "--force"], dict(action="store_true", help="Force overwrite output file")),
        (["-s", "--special"],
         dict(action="store_true", help="Allow writing to special files (like block devices)")),
        (["-o"],
         dict(nargs=1,
              metavar="FILE",
              dest="output",
              help="Output file name (defaults to <image_name>.img")),
    ]
    exclusive_opts = [
        [
            (["-l", "--list-images"], dict(action="store_true",
                                           help="List images defined in config")),
            (["-i", "--image-name"],
             dict(nargs=1,
                  metavar="image_name",
                  help="Name of image (which is defined in config file)")),
        ],
    ]

    conf, args = _handle_shared_opts(
        f'Rouge boot image generator v{Version(importlib_metadata.version("moulin"))}',
        additional_opts, exclusive_opts)
    root = conf.get_root_node()
    images = moulin.rouge.get_available_images(root)

    if not images:
        log.error("No images defined in the provided build description file")
        sys.exit(1)

    if args.list_images:
        print("Listing available images")
        for image in images:
            print(f" - {image.name}: {image.desc}")
        sys.exit(0)

    if not args.image_name:
        log.error("Either -l or -i parameter is required")
        sys.exit(1)

    output_file: str
    if args.output:
        output_file = args.output[0]
    else:
        output_file = f"{args.image_name[0]}.img"

    # Okay, time to really write something
    for image in images:
        if image.name == args.image_name[0]:
            chosen_image = image
            break
    else:
        log.error("Can't find requested image. Use '-l' option to see available images.")
        sys.exit(1)

    output_path = _rouge_validate_output(output_file, args)

    block_entry = moulin.rouge.block_entry.construct_entry(chosen_image.node)
    with open(output_file, "wb") as fileo:
        if not output_path.is_block_device():
            fileo.truncate(block_entry.size())
        block_entry.write(fileo, 0)

    end_time = time()
    log.info("Done in %s", timedelta(seconds=(end_time - start_time)))

    # Good advice
    if output_path.is_file():
        log.info(" ".join([
            "You can write result to your SD card.",
            "Don't forget to pass 'conv=sparse' option to dd.",
            "This will improve writing speed greatly."
        ]))


def _rouge_validate_output(output_file: str, args):
    output_path = Path(output_file)
    if output_path.is_file() and not args.force:
        log.error("Output file %s already exists and no '-f' flag provided. Exiting.", output_file)
        sys.exit(1)

    if output_path.is_block_device() and not args.special:
        log.error("Output file %s is a block device and no '-s' flag provided. Exiting.",
                  output_file)
        sys.exit(1)
    else:
        if output_path.exists() and not output_path.is_file() and not output_path.is_block_device():
            log.error("Output path %s exists and it is not a file or a block device. Exiting.",
                      output_file)
            sys.exit(1)

    if output_path.is_block_device():
        log.warning("Writing directly to block device %s. We hope you provided correct one.",
                    output_file)

    if output_path.is_file():
        log.warning("Overwriting file %s", output_file)

    return output_path
