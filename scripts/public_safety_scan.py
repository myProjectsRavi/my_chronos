#!/usr/bin/env python3
"""Fail-closed secret/privacy scan for every reachable Git object.

This scanner intentionally favors a small set of high-confidence credential patterns,
strict historical filename rules, and public-identity hygiene. It is dependency-free
so it can run before the project toolchain is installed.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import PurePosixPath

MAX_BLOB_BYTES = 5 * 1024 * 1024
ALLOWED_EMAIL_DOMAINS = {"users.noreply.github.com", "example.com", "example.org", "example.net"}
ALLOWED_HOME_PREFIXES = {"/home/chronos/"}

SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b"),
    "Anthropic key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "Stripe live key": re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b"),
    "PyPI token": re.compile(r"\bpypi-[A-Za-z0-9_-]{20,}\b"),
    "npm token": re.compile(r"\bnpm_[A-Za-z0-9]{20,}\b"),
    "generic secret assignment": re.compile(
        r"(?im)^\s*(?:api[_-]?key|secret|token|password|passwd|client[_-]?secret)\s*[:=]\s*[\"']?([^\s\"'#]{12,})"
    ),
}

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b", re.IGNORECASE)
HOME_PATTERNS = [
    re.compile("/" + "Users" + r"/[^/\s]+/"),
    re.compile("/" + "home" + r"/[^/\s]+/"),
    re.compile(r"[A-Za-z]:\\" + "Users" + r"\\[^\\\s]+\\"),
]

SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".sqlite", ".sqlite3", ".snapshot"}
SENSITIVE_NAMES = {".env", "identity.json"}


def git(*args: str, text: bool = True) -> str | bytes:
    result = subprocess.run(["git", *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout.decode("utf-8", errors="replace") if text else result.stdout


def fail(message: str) -> None:
    print(f"PUBLIC-SAFETY FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def check_complete_history() -> None:
    if git("rev-parse", "--is-shallow-repository").strip() != "false":
        fail("shallow repository; complete history is required")
    refs = git("for-each-ref", "--format=%(refname)").splitlines()
    if not refs:
        fail("no refs found")


def check_commit_metadata() -> None:
    raw = git("log", "--all", "--format=%H%x00%ae%x00%ce%x00%B%x00")
    fields = raw.split("\x00")
    for i in range(0, len(fields) - 3, 4):
        sha, author_email, committer_email, message = fields[i : i + 4]
        for role, email in (("author", author_email), ("committer", committer_email)):
            if not email:
                fail(f"{sha}: missing {role} email metadata")
            domain = email.rsplit("@", 1)[-1].lower()
            if domain not in ALLOWED_EMAIL_DOMAINS:
                fail(f"{sha}: non-public {role} email domain: {domain}")
        scan_text(message, f"commit {sha} message")


def scan_text(text: str, where: str) -> None:
    for label, pattern in SECRET_PATTERNS.items():
        if pattern.search(text):
            fail(f"{where}: matched {label}")
    for match in EMAIL_RE.finditer(text):
        domain = match.group(1).lower()
        if domain not in ALLOWED_EMAIL_DOMAINS:
            fail(f"{where}: non-example email domain {domain}")
    for pattern in HOME_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(0)
            if any(value.startswith(prefix) for prefix in ALLOWED_HOME_PREFIXES):
                continue
            fail(f"{where}: local user-home path {value}")


def check_paths_and_blobs() -> None:
    object_lines = git("rev-list", "--objects", "--all").splitlines()
    seen: set[str] = set()
    for line in object_lines:
        if not line:
            continue
        oid, *path_parts = line.split(" ", 1)
        path = path_parts[0] if path_parts else ""
        if path:
            p = PurePosixPath(path)
            lowered = p.name.lower()
            if lowered in SENSITIVE_NAMES and lowered != ".env.example":
                fail(f"historical sensitive filename: {path}")
            if p.suffix.lower() in SENSITIVE_SUFFIXES:
                fail(f"historical sensitive file type: {path}")
        if oid in seen:
            continue
        seen.add(oid)
        if git("cat-file", "-t", oid).strip() != "blob":
            continue
        size = int(git("cat-file", "-s", oid).strip())
        if size > MAX_BLOB_BYTES:
            fail(f"oversized historical blob requires explicit review: {oid} ({size} bytes)")
        data = git("cat-file", "-p", oid, text=False)
        if b"\x00" in data:
            continue
        scan_text(data.decode("utf-8", errors="replace"), f"blob {oid} ({path or 'path unknown'})")


def main() -> None:
    check_complete_history()
    check_commit_metadata()
    check_paths_and_blobs()
    print("PUBLIC-SAFETY PASS: reachable history, metadata, paths, and text blobs are clean")


if __name__ == "__main__":
    main()
