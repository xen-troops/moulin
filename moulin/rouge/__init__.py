# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""
Rouge Image generator
"""
from typing import List, NamedTuple

from yaml.nodes import MappingNode
from moulin.yaml_helpers import get_scalar_node, get_mapping_node


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
