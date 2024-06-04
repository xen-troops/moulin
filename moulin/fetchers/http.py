# SPDX-License-Identifier: Apache-2.0
# Copyright 2024 EPAM Systems
"""HTTP(S) fetcher module"""

import os.path
from typing import List
from moulin.yaml_helpers import YAMLProcessingError
from moulin.yaml_wrapper import YamlValue
from moulin import ninja_syntax


def get_fetcher(conf: YamlValue, build_dir: str, generator: ninja_syntax.Writer):
    """Construct and return HTTP/S fetcher object"""
    return HTTPFetcher(conf, build_dir, generator)


def gen_build_rules(generator: ninja_syntax.Writer):
    """Generate build rules using Ninja generator"""
    generator.rule("curl_download", command="curl $url -o $out ", description="curl download $url")
    generator.newline()


def _guess_filename(url: str):
    # TODO: Add support for corner cases
    if url.endswith("/"):
        return None
    return url.split("/")[-1]


class HTTPFetcher:
    """HTTP/S fetcher class. Provides methods to generate rules for downloading files over HTTP/S"""

    def __init__(self, conf: YamlValue, build_dir: str, generator: ninja_syntax.Writer):
        self.conf = conf
        self.build_dir = build_dir
        self.generator = generator
        self.url = conf["url"].as_str
        dirname = conf.get("dir", default=".").as_str
        self.download_dir = os.path.join(build_dir, dirname)
        filename = conf.get("filename", default="").as_str
        if not filename:
            filename = _guess_filename(self.url)
            if not filename:
                raise YAMLProcessingError("Can't determine output file name for HTTP/S download",
                                          conf.mark)
        self.output_file = os.path.join(self.download_dir, filename)

    def gen_fetch(self):
        """Generate instruction to download a file"""

        self.generator.build(self.output_file, "curl_download", variables={"url": self.url})
        self.generator.newline()

        return self.output_file

    def get_file_list(self) -> List[str]:
        return [self.output_file]

    def capture_state(self):
        """
        Capture state, but it is not applicable for this fetcher. Do nothing.
        """
        pass
