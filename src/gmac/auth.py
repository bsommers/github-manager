"""Credential resolution. GMAC never invents its own login; it reuses what you already have.

Order per provider: env var -> stored token (OS keychain) -> `gh`/`glab` CLI session.
`gmac auth login` delegates the browser/OAuth flow to gh/glab, or stores a pasted token.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

import keyring
import keyring.errors

SERVICE = "gmac"
ENV = {
    "github": ("GMAC_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"),
    "gitlab": ("GMAC_GITLAB_TOKEN", "GITLAB_TOKEN", "GLAB_TOKEN"),
}
CLI = {"github": "gh", "gitlab": "glab"}


@dataclass
class Credential:
    token: str
    origin: str  # "env:NAME" | "keychain" | "gh" | "glab"


def _cli_token(provider: str, host: str) -> str | None:
    exe = CLI[provider]
    if not shutil.which(exe):
        return None
    try:
        r = subprocess.run(
            [exe, "auth", "token", "--hostname", host],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() or None if r.returncode == 0 else None


def _stored(provider: str, host: str) -> str | None:
    try:
        return keyring.get_password(SERVICE, f"{provider}:{host}")
    except keyring.errors.KeyringError:
        return None


def default_host(provider: str) -> str:
    return "github.com" if provider == "github" else "gitlab.com"


def find_credential(provider: str, host: str | None = None) -> Credential | None:
    host = host or default_host(provider)
    for var in ENV[provider]:
        if os.environ.get(var):
            return Credential(os.environ[var], f"env:{var}")
    if t := _stored(provider, host):
        return Credential(t, "keychain")
    if t := _cli_token(provider, host):
        return Credential(t, CLI[provider])
    return None


def resolve_token(provider: str, host: str | None = None) -> str | None:
    c = find_credential(provider, host)
    return c.token if c else None


def store_token(provider: str, token: str, host: str | None = None) -> None:
    keyring.set_password(SERVICE, f"{provider}:{host or default_host(provider)}", token)


def forget_token(provider: str, host: str | None = None) -> bool:
    try:
        keyring.delete_password(SERVICE, f"{provider}:{host or default_host(provider)}")
        return True
    except keyring.errors.KeyringError:
        return False


def cli_login(provider: str, host: str | None = None) -> int:
    """Hand the terminal to `gh auth login` / `glab auth login` (browser OAuth device flow)."""
    exe = CLI[provider]
    if not shutil.which(exe):
        raise RuntimeError(f"`{exe}` not installed; install it or use --token")
    cmd = [exe, "auth", "login"] + (["--hostname", host] if host else [])
    return subprocess.call(cmd)
