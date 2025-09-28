# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""
Rouge Image generator
"""
import sys
from typing import List, NamedTuple

from moulin import ninja_syntax
from moulin.yaml_wrapper import YamlValue
from .block_entry import construct_entry


class RougeImage(NamedTuple):
    "Represents rouge image"
    name: str
    desc: str
    node: YamlValue


def get_available_images(root_node: YamlValue) -> List[RougeImage]:
    "Return list of available images from YAML config"
    images_node = root_node.get("images", None)
    if not images_node:
        return []

    ret: List[RougeImage] = []
    for name, image_node in images_node.items():
        desc = image_node.get("desc", "No description available").as_str
        ret.append(RougeImage(name, desc, image_node))
    return ret


def gen_build_rules(generator: ninja_syntax.Writer):
    "Generate ninja rules to build images via rouge"
    moulin_args = " ".join(sys.argv[1:])
    generator.rule("rouge", f"rouge {moulin_args} -fi $image_name -o $out")
    generator.newline()
    # the pigz is faster, but gzip is available everywhere
    generator.rule("gzip", "command -v pigz > /dev/null 2>&1 && pigz -1kf $in || gzip -1kf $in")
    generator.newline()
    generator.rule("bmaptool", "bmaptool create $in -o $out")
    generator.newline()


def gen_build(generator: ninja_syntax.Writer, images: List[RougeImage]):
    "Generate build rules for given list of images"
    for image in images:
        block_entry = construct_entry(image.node)
        generator.build(f"{image.name}.img",
                        "rouge",
                        block_entry.get_deps(),
                        variables=dict(image_name=image.name),
                        pool="console")
        generator.build(f"{image.name}.img.gz",
                        "gzip",
                        f"{image.name}.img",
                        pool="console")
        generator.build(f"{image.name}.img.bmap",
                        "bmaptool",
                        f"{image.name}.img",
                        pool="console")
        generator.build(f"image-{image.name}", "phony", f"{image.name}.img")
