from setuptools import setup

from typing import Dict, Any

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

SETUP_ARGS: Dict[str, Any] = dict(
    name='moulin',  # Required
    version='0.3',  # Required
    description='Meta-build system',  # Required
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/xen-troops/moulin',  # Optional
    author='Volodymyr Babchuk',  # Optional
    author_email='volodymyr_babchuk@epam.com',  # Optional

    # Note that this is a string of words separated by whitespace, not a list.
    keywords='build ninja yocto android repo git',
    packages=[
        "moulin",
        "moulin.fetchers",
        "moulin.builders",
    ],  # Required
    install_requires=[
        'pygit2',
        'importlib_metadata',
        'packaging',
    ],
    python_requires=">=3.6",
    entry_points={'console_scripts': ['moulin = moulin.main:console_entry']})
setup(**SETUP_ARGS)
