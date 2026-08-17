# Contributing to CHRONOS

Thank you for helping improve CHRONOS.

## Current repository phase

This repository is the clean public lineage. Implementation contributions will open after the certified source snapshot is published. Documentation, governance, and release-safety corrections are welcome in the meantime.

## Contribution principles

- Keep changes focused and reviewable.
- Add or update tests for behavioral changes.
- Preserve fail-closed behavior at security boundaries.
- Do not add secrets, personal data, private datasets, customer/employer material, local repositories, database files, model weights, identity material, or generated runtime state.
- Do not weaken authentication, integrity verification, path containment, resource limits, or release gates to make a test pass.
- Clearly label experimental or simulation-only behavior; do not present it as a production guarantee.
- Prefer evidence-backed performance claims with reproducible benchmarks.

## Change workflow

- Never commit implementation changes directly to `main`; use a focused branch and pull request.
- Review the staged diff before every public commit, including filenames, generated files, logs, fixtures, and examples.
- Use synthetic data in tests, documentation, issues, pull requests, and security reproductions.
- Treat dependency manifests, lockfiles, GitHub Actions, release automation, and documentation claims as security-relevant changes.
- Do not merge when a required check is unavailable, skipped unexpectedly, or failing.

## Pull requests

A strong pull request should explain:

1. the problem;
2. the minimal change made;
3. security/privacy implications;
4. tests or verification performed;
5. compatibility or migration impact.

All automated checks must pass before merge. Reviewers may request additional threat-model, performance, or compatibility evidence for security-sensitive changes.

## Security issues

Do not file vulnerabilities publicly. Follow [SECURITY.md](SECURITY.md).

## Commit hygiene

Use a GitHub noreply email or another intentionally public identity. Never put secrets, tokens, personal email addresses, customer names, local user-home paths, private incident details, exploit details, or unsanitized logs in commit subjects or bodies.

Use concise Conventional Commit-style subjects, for example `fix: reject unsafe import paths` or `docs: clarify security reporting`. Keep messages factual and avoid security, performance, compatibility, or readiness claims that are not supported by evidence in the change.
