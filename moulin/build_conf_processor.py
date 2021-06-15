# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""This module processes build configuration files"""

import logging
import re
from collections import namedtuple
from functools import partial
from pprint import pformat

log = logging.getLogger(__name__)


def process_config(tree, args):
    """This function process configuration tree in place by applying options
    from 'overrides' node and expanding variables"""
    apply_parameters(tree, args)
    tree = expand_variables(tree)
    log.debug("Processed build tree: \n%s", pformat(tree))
    return tree


# Parameters processor

ParameterDesc = namedtuple("ParameterDesc",
                           ["name", "choices", "default", "desc"])


def get_possible_parameters(tree):
    """Return list of possible parameters for a given configuration tree"""
    ret = []

    for pname, pvariants in tree.get("parameters", {}).items():
        default = None
        choices = []

        if "desc" not in pvariants:
            raise Exception(f"No 'desc' field for parameter {pname}")

        for key, val in pvariants.items():
            # Skip description
            if key == "desc":
                continue

            choices.append(key)
            if val.get("default", False):
                default = key
                continue
        ret.append(ParameterDesc(pname, choices, default, pvariants["desc"]))

    return ret


def _map_yaml_tree(func, tree):
    """Recursive function that traverses parsed YAML structure and
    applies func to every element"""
    if isinstance(tree, list):
        return list(map(partial(_map_yaml_tree, func), tree))
    if isinstance(tree, dict):
        new_dict = {}
        for key, val in tree.items():
            new_dict[func(key)] = _map_yaml_tree(func, val)
        return new_dict
    return func(tree)


def apply_parameters(tree, args):
    """Transmute YAML tree by applying parameters according to chosen args"""
    if "parameters" not in tree:
        return

    parameters = tree["parameters"]
    del tree["parameters"]
    chosen = _choose_parameters(parameters, args)
    for param in chosen:
        _apply_overrides(tree, param["overrides"])


def _choose_parameters(parameters, args):
    """Chose parameters according to user supplied args"""
    ret = []
    for param, variants in parameters.items():
        # Maybe user have some preference
        if param in args:
            chosen = args[param]
            if chosen not in variants:
                raise Exception(f"Unknown option '{chosen}' for '{param}'")
            ret.append(variants[chosen])
            log.debug("User set option '%s' for '%s'", chosen, param)
            continue

        # Look for default value
        chosen = None
        for name, attrs in variants.items():
            if attrs.get("default", False):
                chosen = name
        if chosen:
            ret.append(variants[chosen])
            log.debug("Using default option '%s' for '%s'", chosen, param)
        else:
            log.warning("There is no default value for parameter '%s'", param)

    return ret


def _apply_overrides(tree, overrides):
    """Recursively apply overrides for tree in place"""
    for key, val in overrides.items():
        if key not in tree:
            tree[key] = val
            continue
        if not isinstance(val, type(tree[key])):
            raise Exception(
                f"Different items types in main YAML tree and overrides: {type(val)} != {type(tree[key])}"
            )
        if isinstance(val, list):
            tree[key].extend(val)
        elif isinstance(val, dict):
            _apply_overrides(tree[key], val)
        else:
            tree[key] = val


# Variables processor

escaped_percent = re.compile(r"(%%)")
variable_re = re.compile(r"%\{(\w[\w\d\-]*)\}")

Variable = namedtuple("Variable", ["name"])


def expand_variables(tree):
    """Expand variables in configuration tree"""
    tree, variables = _expand_vars_vars(tree)
    if variables:
        tree = _map_yaml_tree(
            partial(_substitute_variables, variables=variables), tree)
    return tree


def _extract_vars(string):
    parts = variable_re.split(string)
    ret = []
    for i, part in enumerate(parts):
        # Even (zero-based) entries are just strings
        # Odd entries are variable names
        if i % 2 == 0 and part:
            ret.append(part)
        elif part:
            ret.append(Variable(part))
    return ret


def _tokenize(string):
    ret = []
    parts = escaped_percent.split(string)
    for part in parts:
        if part:
            if escaped_percent.fullmatch(part):
                ret.append("%%")
            else:
                ret.extend(_extract_vars(part))

    return ret


def _map_token(token, variables):
    if isinstance(token, str):
        return token
    if isinstance(token, Variable):
        name = token.name
        if name not in variables:
            return token
        return variables[name]
    raise Exception(
        f"Could not expand variable inside variable of type '{type(token)}'")


def _substitute_variables(val, variables):
    if not isinstance(val, str):
        return val
    tokens = _tokenize(val)
    return "".join(map(partial(_map_token, variables=variables), tokens))


def _contains_variable(tokens):
    for token in tokens:
        if isinstance(token, Variable):
            return True
    return False


def _try_to_expand_variables(variables):
    # This is not most effective way. But it good enough.
    # Iterate over all variables, trying to expand one of them
    expanded_variables = {}
    stop = False
    while not stop:
        stop = True
        for key, val in variables.items():
            val = list(
                map(partial(_map_token, variables=expanded_variables), val))
            if not _contains_variable(val):
                expanded_variables[key] = "".join(val)
                del variables[key]
                stop = False
                break
    return expanded_variables


def _expand_vars_vars(tree):
    """Expand variables that can refer to other variables"""

    if "variables" not in tree:
        return tree, {}

    variables = tree["variables"]
    del tree["variables"]

    log.debug("expanding variables:\n%s", pformat(variables))

    for key, val in variables.items():
        variables[key] = _tokenize(val)
        # Sanity check
        for token in variables[key]:
            if isinstance(token, Variable):
                if token.name == key:
                    raise Exception(f"Variable {key} refers to self")

    expanded_variables = _try_to_expand_variables(variables)
    # We can't expand more variables Either all are expanded, or there
    # is a some user error. Perform sanity check.
    for key, val in variables.items():
        for token in val:
            if isinstance(token, Variable):
                if token.name == key:
                    raise Exception(
                        f"Variable {key} indirectly refers to self")
                if token.name not in variables:
                    raise Exception(
                        f"Variable {key} refers to unknown variable {token.name}"
                    )

    if variables:
        raise Exception(
            f"Found circular dependency in variables {list(variables.keys())}")

    log.debug("Expanded variables:\n%s", pformat(expanded_variables))
    return tree, expanded_variables
