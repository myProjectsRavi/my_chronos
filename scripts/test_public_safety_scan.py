#!/usr/bin/env python3
"""Regression tests for the dependency-free public safety scanner."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).with_name("public_safety_scan.py")
SPEC = importlib.util.spec_from_file_location("public_safety_scan", SCRIPT)
assert SPEC and SPEC.loader
scanner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scanner)


class PublicSafetyScannerTests(unittest.TestCase):
    def test_sensitive_environment_paths(self) -> None:
        self.assertEqual(scanner.sensitive_path_reason(".env"), "environment file")
        self.assertEqual(scanner.sensitive_path_reason(".env.local"), "environment file")
        self.assertEqual(scanner.sensitive_path_reason("config/.env.production"), "environment file")
        self.assertIsNone(scanner.sensitive_path_reason(".env.example"))

    def test_extensionless_private_key_names(self) -> None:
        for name in ("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"):
            with self.subTest(name=name):
                self.assertEqual(scanner.sensitive_path_reason(name), "sensitive filename")

    def test_sensitive_file_types(self) -> None:
        for path in ("certs/client.p12", "keys/private.pem", "vault/local.gpg", "state/cache.sqlite"):
            with self.subTest(path=path):
                self.assertEqual(scanner.sensitive_path_reason(path), "sensitive file type")

    def test_normal_source_paths_are_allowed(self) -> None:
        for path in ("README.md", "src/chronos/auth.py", "tests/test_auth.py"):
            with self.subTest(path=path):
                self.assertIsNone(scanner.sensitive_path_reason(path))

    def test_only_exact_github_system_identity_is_special_cased(self) -> None:
        system_email = "noreply@" + "github.com"
        other_email = "person@" + "github.com"
        self.assertTrue(scanner.allowed_identity("GitHub", system_email))
        self.assertFalse(scanner.allowed_identity("Someone Else", system_email))
        self.assertFalse(scanner.allowed_identity("GitHub", other_email))

    def test_github_noreply_user_identity_is_allowed(self) -> None:
        self.assertTrue(
            scanner.allowed_identity(
                "myProjectsRavi",
                "95069115+myProjectsRavi@users.noreply.github.com",
            )
        )

    def test_pgp_private_key_signature_is_detected(self) -> None:
        marker = "-----BEGIN " + "PGP PRIVATE KEY BLOCK-----"
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                scanner.scan_text(marker, "test fixture")


if __name__ == "__main__":
    unittest.main()
