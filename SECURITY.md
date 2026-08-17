# Security Policy

Security reports must be handled privately.

## Current pre-release state

The implementation source has not yet been published in this clean public lineage. GitHub **Private vulnerability reporting must be enabled before implementation publication** and is part of the mandatory public-release gate.

Until that setting is enabled, do **not** disclose suspected vulnerabilities in a public issue, pull request, discussion, or commit message. The repository does not yet contain the implementation intended for public security review.

## Reporting after source publication

Once GitHub Private vulnerability reporting is enabled, use:

**Security → Advisories → Report a vulnerability**

Include, where possible:

- the affected component and version or commit;
- a minimal synthetic reproduction or proof of concept;
- expected versus observed behavior;
- realistic impact and prerequisites;
- any suggested remediation.

Never include real credentials, personal data, private customer data, employer-confidential material, or third-party confidential information in a report.

## Scope

Supported/stable surfaces will be identified explicitly with the source release. Beta, experimental, research, and simulation-only modules do not inherit production-security claims merely by existing in the repository.

## Disclosure

Please allow reasonable time for validation and remediation before public disclosure. Good-faith security research that avoids privacy violations, destructive activity, service disruption, and unauthorized access is appreciated.
