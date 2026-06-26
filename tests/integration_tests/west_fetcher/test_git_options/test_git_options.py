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


def clone_bare(source_path, target_path, cwd):
    run_cmd(["git", "clone", "--bare", source_path, target_path], cwd)


@pytest.mark.integration
def test_west_fetcher_git_options():
    script_path = os.path.abspath(__file__)
    script_dir_path = os.path.dirname(script_path)
    moulin_path = os.path.abspath(os.path.join(script_dir_path, "../../../../moulin.py"))
    yaml_template = os.path.join(script_dir_path, "resources/test_git_options.yaml")

    with tempfile.TemporaryDirectory(dir=script_dir_path) as tmp_dir:
        project_repo = os.path.join(tmp_dir, "project")
        project_remote = os.path.join(tmp_dir, "project.git")
        manifest_repo = os.path.join(tmp_dir, "manifest")
        manifest_remote = os.path.join(tmp_dir, "manifest.git")
        build_dir = os.path.join(tmp_dir, "build")

        init_git_repo(project_repo)
        commit_file(project_repo, "README", "first\n", "project: first")
        commit_file(project_repo, "README", "second\n", "project: second")
        clone_bare(project_repo, project_remote, tmp_dir)

        init_git_repo(manifest_repo)
        manifest = f"""manifest:
  projects:
    - name: project
      url: file://{project_remote}
      revision: main
      path: project
"""
        commit_file(manifest_repo, "west.yml", manifest, "manifest: add project")
        clone_bare(manifest_repo, manifest_remote, tmp_dir)

        os.makedirs(build_dir)
        manifest_repo_url = f"file://{manifest_remote}"
        yaml_file = os.path.join(build_dir, "test_git_options.yaml")
        with open(yaml_template, encoding="utf-8") as stream:
            yaml_content = stream.read().replace("%{MANIFEST_REPO_URL}", manifest_repo_url)
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

        with open(os.path.join(build_dir, "build.ninja"), encoding="utf-8") as stream:
            build_ninja = stream.read()
        assert "-o=--depth=1" in build_ninja

        result = subprocess.run(["ninja", "workspace/.west"],
                                cwd=build_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True)
        assert result.returncode == 0, (
            f"ninja failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

        result = run_cmd(["git", "rev-parse", "--is-shallow-repository"],
                         os.path.join(build_dir, "workspace/manifest.git"))
        assert result.stdout.strip() == "true"


if __name__ == "__main__":
    pytest.main([__file__])
