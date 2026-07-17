import os
import subprocess
import sys
import tempfile

import pytest


def run_cmd(args, cwd):
    result = subprocess.run(args,
                            cwd=cwd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True)
    assert result.returncode == 0, (
        f"Command failed: {' '.join(args)}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    return result


def init_git_repo(path):
    os.makedirs(path)
    run_cmd(["git", "init", "-b", "main"], path)
    run_cmd(["git", "config", "user.name", "Moulin Test"], path)
    run_cmd(["git", "config", "user.email", "moulin-test@example.com"], path)


def commit_file(repo_path, filename, content, message):
    file_path = os.path.join(repo_path, filename)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as stream:
        stream.write(content)
    run_cmd(["git", "add", filename], repo_path)
    run_cmd(["git", "commit", "-m", message], repo_path)


GROUP_FILTER_WITH_LEADING_PLUS = "+kept,-dropped"
GROUP_FILTER_WITH_LEADING_MINUS = "-dropped,+kept"
GROUP_FILTER_STRING = f'        group_filter: "{GROUP_FILTER_WITH_LEADING_PLUS}"'
GROUP_FILTER_LEADING_MINUS_STRING = f'        group_filter: "{GROUP_FILTER_WITH_LEADING_MINUS}"'
GROUP_FILTER_LIST = "\n".join([
    "        group_filter:",
    "          - \"+kept\"",
    "          - \"-dropped\"",
])


def create_bare_remote(source_path, target_path, cwd):
    run_cmd(["git", "clone", "--bare", source_path, target_path], cwd)


@pytest.mark.parametrize(
    ("group_filter_yaml", "expected_group_filter"),
    [
        (GROUP_FILTER_STRING, GROUP_FILTER_WITH_LEADING_PLUS),
        (GROUP_FILTER_LIST, GROUP_FILTER_WITH_LEADING_PLUS),
        (GROUP_FILTER_LEADING_MINUS_STRING, GROUP_FILTER_WITH_LEADING_MINUS),
    ],
    ids=["string", "list", "leading-minus-string"],
)
@pytest.mark.integration
def test_west_fetcher_group_filter(group_filter_yaml, expected_group_filter):
    script_path = os.path.abspath(__file__)
    script_dir_path = os.path.dirname(script_path)
    moulin_path = os.path.abspath(os.path.join(script_dir_path,
                                               "../../../../moulin.py"))
    yaml_template = os.path.join(script_dir_path,
                                 "resources/test_group_filter.yaml")

    with tempfile.TemporaryDirectory(dir=script_dir_path) as tmp_dir:
        kept_repo = os.path.join(tmp_dir, "kept")
        kept_remote = os.path.join(tmp_dir, "kept.git")
        dropped_repo = os.path.join(tmp_dir, "dropped")
        dropped_remote = os.path.join(tmp_dir, "dropped.git")
        manifest_repo = os.path.join(tmp_dir, "manifest")
        manifest_remote = os.path.join(tmp_dir, "manifest.git")
        build_dir = os.path.join(tmp_dir, "build")

        init_git_repo(kept_repo)
        commit_file(kept_repo, "README", "kept\n", "kept: add README")
        create_bare_remote(kept_repo, kept_remote, tmp_dir)

        init_git_repo(dropped_repo)
        commit_file(dropped_repo, "README", "dropped\n", "dropped: add README")
        create_bare_remote(dropped_repo, dropped_remote, tmp_dir)

        init_git_repo(manifest_repo)
        manifest = f"""manifest:
  projects:
    - name: kept
      url: file://{kept_remote}
      revision: main
      path: kept
      groups:
        - kept
    - name: dropped
      url: file://{dropped_remote}
      revision: main
      path: dropped
      groups:
        - dropped
"""
        commit_file(manifest_repo, "west.yml", manifest,
                    "manifest: add projects")
        create_bare_remote(manifest_repo, manifest_remote, tmp_dir)

        os.makedirs(build_dir)
        manifest_repo_url = f"file://{manifest_remote}"
        yaml_file = os.path.join(build_dir, "test_group_filter.yaml")
        with open(yaml_template, encoding="utf-8") as stream:
            yaml_content = stream.read().replace("%{MANIFEST_REPO_URL}",
                                                 manifest_repo_url)
        yaml_content = yaml_content.replace("%{GROUP_FILTER}",
                                            group_filter_yaml)
        with open(yaml_file, "w", encoding="utf-8") as stream:
            stream.write(yaml_content)

        result = subprocess.run([sys.executable, moulin_path, yaml_file],
                                cwd=build_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True)
        assert result.returncode == 0, (
            f"moulin failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

        with open(os.path.join(build_dir, "build.ninja"),
                  encoding="utf-8") as stream:
            build_ninja = stream.read()
        assert "west config manifest.group-filter -- \"$group_filter\"" in build_ninja
        assert f"group_filter = {expected_group_filter}" in build_ninja

        result = subprocess.run(["ninja", "fetch-test"],
                                cwd=build_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True)
        assert result.returncode == 0, (
            f"ninja failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

        result = run_cmd(["west", "config", "manifest.group-filter"],
                         os.path.join(build_dir, "workspace"))
        assert result.stdout.strip() == expected_group_filter

        result = run_cmd(["west", "list", "--format={name}"],
                         os.path.join(build_dir, "workspace"))
        projects = result.stdout.splitlines()
        assert "kept" in projects
        assert "dropped" not in projects

        assert os.path.isdir(os.path.join(build_dir, "workspace/kept/.git"))
        assert not os.path.exists(os.path.join(build_dir, "workspace/dropped"))


if __name__ == "__main__":
    pytest.main([__file__])
