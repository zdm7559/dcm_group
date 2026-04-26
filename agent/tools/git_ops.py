from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import subprocess


ToolResult = dict[str, Any]
ENV_LOADED = False


def ok(data: Any = None) -> ToolResult:
    return {"ok": True, "data": data, "error": None}


def fail(error: str, data: Any = None) -> ToolResult:
    return {"ok": False, "data": data, "error": error}


def run_command(
    args: list[str],
    *,
    cwd: str | Path = ".",
    timeout: int = 60,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env=env,
    )


def sync_base_branch(
    base: str = "main",
    *,
    repo_path: str | Path = ".",
    remote: str = "origin",
) -> ToolResult:
    """Switch to the base branch and pull the latest remote changes."""
    if not base.strip():
        return fail("base branch is required")

    repo = Path(repo_path)

    repo_check = run_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo)
    if repo_check.returncode != 0:
        return fail(repo_check.stderr.strip() or "not inside a git repository")

    switch_result = run_command(["git", "switch", base], cwd=repo)
    if switch_result.returncode != 0:
        return fail(switch_result.stderr.strip() or f"failed to switch to {base}")

    pull_result = run_command(["git", "pull", remote, base], cwd=repo, timeout=120)
    if pull_result.returncode != 0:
        return fail(pull_result.stderr.strip() or f"failed to pull {remote}/{base}")

    return ok(
        {
            "base": base,
            "remote": remote,
            "stdout": pull_result.stdout.strip(),
        }
    )


def create_branch(
    branch_name: str,
    *,
    repo_path: str | Path = ".",
) -> ToolResult:
    """Create and switch to a new git branch."""
    if not branch_name.strip():
        return fail("branch name is required")

    repo = Path(repo_path)

    repo_check = run_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo)
    if repo_check.returncode != 0:
        return fail(repo_check.stderr.strip() or "not inside a git repository")

    branch_check = run_command(
        ["git", "rev-parse", "--verify", branch_name],
        cwd=repo,
    )
    if branch_check.returncode == 0:
        return fail(f"branch already exists: {branch_name}")

    switch_result = run_command(["git", "switch", "-c", branch_name], cwd=repo)
    if switch_result.returncode != 0:
        return fail(switch_result.stderr.strip() or "git switch failed")

    return ok(
        {
            "branch": branch_name,
            "stdout": switch_result.stdout.strip(),
        }
    )


def git_diff(
    *,
    repo_path: str | Path = ".",
    staged: bool = False,
    include_untracked: bool = True,
) -> ToolResult:
    """Return the current git diff."""
    repo = Path(repo_path)

    repo_check = run_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo)
    if repo_check.returncode != 0:
        return fail(repo_check.stderr.strip() or "not inside a git repository")

    args = ["git", "diff"]
    if staged:
        args.append("--cached")

    diff_result = run_command(args, cwd=repo)
    if diff_result.returncode != 0:
        return fail(diff_result.stderr.strip() or "git diff failed")

    diff_text = diff_result.stdout
    if include_untracked and not staged:
        untracked_result = run_command(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=repo,
        )
        if untracked_result.returncode != 0:
            return fail(untracked_result.stderr.strip() or "failed to list untracked files")

        for file_path in untracked_result.stdout.splitlines():
            file_diff_result = run_command(
                ["git", "diff", "--no-index", "--", "/dev/null", file_path],
                cwd=repo,
            )
            if file_diff_result.returncode not in (0, 1):
                return fail(file_diff_result.stderr.strip() or "failed to diff untracked file")
            if file_diff_result.stdout:
                diff_text += file_diff_result.stdout

    return ok(
        {
            "diff": diff_text,
        }
    )


def git_commit(
    message: str,
    *,
    repo_path: str | Path = ".",
    paths: list[str] | None = None,
) -> ToolResult:
    """Stage files and create a git commit."""
    load_local_env()

    if not message.strip():
        return fail("commit message is required")

    repo = Path(repo_path)
    add_paths = paths or ["."]

    repo_check = run_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo)
    if repo_check.returncode != 0:
        return fail(repo_check.stderr.strip() or "not inside a git repository")

    add_result = run_command(["git", "add", *add_paths], cwd=repo)
    if add_result.returncode != 0:
        return fail(add_result.stderr.strip() or "git add failed")

    diff_result = run_command(["git", "diff", "--cached", "--quiet"], cwd=repo)
    if diff_result.returncode == 0:
        return fail("no staged changes to commit")
    if diff_result.returncode not in (0, 1):
        return fail(diff_result.stderr.strip() or "git diff failed")

    commit_result = run_command(
        ["git", "commit", "-m", message],
        cwd=repo,
        env=_git_commit_env(),
    )
    if commit_result.returncode != 0:
        return fail(commit_result.stderr.strip() or "git commit failed")

    sha_result = run_command(["git", "rev-parse", "HEAD"], cwd=repo)
    commit_sha = sha_result.stdout.strip() if sha_result.returncode == 0 else None

    return ok(
        {
            "commit_sha": commit_sha,
            "message": message,
            "stdout": commit_result.stdout.strip(),
        }
    )


def create_pr(
    title: str,
    body: str,
    *,
    repo_path: str | Path = ".",
    base: str = "main",
    head: str | None = None,
    remote: str = "origin",
    token: str | None = None,
    push: bool = True,
) -> ToolResult:
    """Create a GitHub pull request."""
    load_local_env()

    if not title.strip():
        return fail("PR title is required")

    repo = Path(repo_path)
    head_branch_result = run_command(
        ["git", "branch", "--show-current"],
        cwd=repo,
    )
    if head_branch_result.returncode != 0:
        return fail(head_branch_result.stderr.strip() or "failed to get branch")

    head_branch = head or head_branch_result.stdout.strip()
    if not head_branch:
        return fail("current branch is empty")

    remote_url_result = run_command(
        ["git", "remote", "get-url", remote],
        cwd=repo,
    )
    if remote_url_result.returncode != 0:
        return fail(remote_url_result.stderr.strip() or f"remote not found: {remote}")

    repo_full_name = _parse_github_repo(remote_url_result.stdout.strip())
    if not repo_full_name:
        return fail(f"cannot parse GitHub repo from remote url: {remote_url_result.stdout.strip()}")

    if push:
        push_result = run_command(["git", "push", "-u", remote, head_branch], cwd=repo, timeout=120)
        if push_result.returncode != 0:
            return fail(push_result.stderr.strip() or "git push failed")

    github_token = token or os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not github_token:
        return fail("GITHUB_TOKEN or GH_TOKEN is not configured")

    request_body = {
        "title": title,
        "body": body,
        "base": base,
        "head": head_branch,
    }
    api_url = f"https://api.github.com/repos/{repo_full_name}/pulls"

    request = urllib.request.Request(
        api_url,
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {github_token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2026-03-10",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        return fail(f"GitHub API error {exc.code}: {error_body}")
    except urllib.error.URLError as exc:
        return fail(f"GitHub API request failed: {exc.reason}")

    return ok(
        {
            "mode": "github",
            "repo": repo_full_name,
            "number": payload.get("number"),
            "url": payload.get("html_url"),
            "base": base,
            "head": head_branch,
        }
    )


def _parse_github_repo(remote_url: str) -> str | None:
    patterns = [
        r"^git@github\.com:(?P<repo>[^/]+/[^.]+)(?:\.git)?$",
        r"^https://github\.com/(?P<repo>[^/]+/[^.]+)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.match(pattern, remote_url)
        if match:
            return match.group("repo")
    return None


def _git_commit_env() -> dict[str, str]:
    env = os.environ.copy()
    author_name = os.getenv("GIT_AUTHOR_NAME")
    author_email = os.getenv("GIT_AUTHOR_EMAIL")
    committer_name = os.getenv("GIT_COMMITTER_NAME") or author_name
    committer_email = os.getenv("GIT_COMMITTER_EMAIL") or author_email

    if author_name:
        env["GIT_AUTHOR_NAME"] = author_name
    if author_email:
        env["GIT_AUTHOR_EMAIL"] = author_email
    if committer_name:
        env["GIT_COMMITTER_NAME"] = committer_name
    if committer_email:
        env["GIT_COMMITTER_EMAIL"] = committer_email

    return env


def load_local_env(path: str = ".env") -> None:
    """Load simple KEY=VALUE pairs from a local .env file if it exists."""
    global ENV_LOADED
    if ENV_LOADED:
        return

    ENV_LOADED = True

    if not os.path.exists(path):
        return

    with open(path, encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key and key not in os.environ:
                os.environ[key] = value
