# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""
Rouge Image generator
"""
import sys
from typing import List, NamedTuple

from yaml.nodes import MappingNode
from moulin.yaml_helpers import get_scalar_node, get_mapping_node
from moulin import ninja_syntax
from .block_entry import construct_entry


class RougeImage(NamedTuple):
    "Represents rouge image"
    name: str
    desc: str
    node: MappingNode


def get_available_images(root_node: MappingNode) -> List[RougeImage]:
    "Return list of available images from YAML config"
    images_node = get_mapping_node(root_node, "images")
    if not images_node:
        return []

    ret: List[RougeImage] = []
    for image_name_node, image_node in images_node.value:
        name: str = image_name_node.value
        desc_node = get_scalar_node(image_node, "desc")
        if not desc_node:
            desc = "No description available"
        else:
            desc = desc_node.value
        ret.append(RougeImage(name, desc, image_node))
    return ret


def gen_build_rules(generator: ninja_syntax.Writer):
    "Generate ninja rules to build images via rouge"
    moulin_args = " ".join(sys.argv[1:])
    generator.rule("rouge", f"rouge {moulin_args} -fi $image_name -o $out")
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
        generator.build(f"image-{image.name}", "phony", f"{image.name}.img")
