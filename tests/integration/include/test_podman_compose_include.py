# SPDX-License-Identifier: GPL-2.0

import os
import unittest

from parameterized import parameterized

from tests.integration.test_utils import RunSubprocessMixin
from tests.integration.test_utils import podman_compose_path
from tests.integration.test_utils import test_path


def compose_yaml_path(suffix: str = "") -> str:
    return os.path.join(os.path.join(test_path(), "include"), f"docker-compose{suffix}.yaml")


def include_fixture_path(name: str) -> str:
    return os.path.join(test_path(), "include", name, "docker-compose.yaml")


class TestPodmanComposeInclude(unittest.TestCase, RunSubprocessMixin):
    @parameterized.expand([
        ("string", ""),
        ("dict", "_include_dict"),
    ])
    def test_podman_compose_include(self, name: str, compose_suffix: str) -> None:
        try:
            self.run_subprocess_assert_returncode([
                "coverage",
                "run",
                podman_compose_path(),
                "-f",
                compose_yaml_path(f"{compose_suffix}"),
                "up",
                "-d",
            ])

            out, _ = self.run_subprocess_assert_returncode([
                "podman",
                "ps",
                "-a",
                "--filter",
                "label=io.podman.compose.project=include",
                "--format",
                '"{{.Names}}"',
            ])
            # two services from included compose files were created
            self.assertEqual(out, b'"include_web_1"\n"include_web2_1"\n')
        finally:
            self.run_subprocess_assert_returncode([
                podman_compose_path(),
                "-f",
                compose_yaml_path(),
                "down",
                "-t",
                "0",
            ])


class TestPodmanComposeIncludeObjectForm(unittest.TestCase, RunSubprocessMixin):
    """End-to-end check of the `include` object form via `config`. The individual
    resolution rules are covered by tests/unit/test_include.py."""

    def _config(self, compose_file: str) -> str:
        out, _ = self.run_subprocess_assert_returncode([
            podman_compose_path(),
            "-f",
            compose_file,
            "config",
        ])
        return out.decode("utf-8")

    def test_env_file(self) -> None:
        """Variables from an include's env_file feed the included file's
        interpolation but do not leak into the parent compose file."""
        out = self._config(include_fixture_path("env_file"))
        self.assertIn("image: localhost/child-from-env-file", out)
        self.assertIn("image: localhost/parent-fallback", out)

    def test_project_directory(self) -> None:
        """`project_directory` relocates the default `.env` lookup and is the base
        for relative paths inside the included file, including the path and
        `project_directory` of a nested include."""
        out = self._config(include_fixture_path("project_directory"))
        self.assertIn("image: localhost/mid-from-toplevel-projdir", out)
        self.assertIn("image: localhost/from-mid-alt", out)
        self.assertNotIn("wrong-from", out)
