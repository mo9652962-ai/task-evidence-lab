# Security Policy for Task Evidence Lab

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Security Model & Boundaries

Task Evidence Lab enforces strict local execution boundaries:
- **Zero Command Execution:** Imported scripts, commands, and file paths are displayed as text records and never evaluated or executed.
- **SSRF Prevention:** Link verification endpoints reject internal, loopback, and RFC 1918 private IP addresses.
- **Data Protection:** Local database files and JSON exports contain parameterized SQL statements.

## Reporting a Vulnerability

Please report security issues privately via GitHub Security Advisories or contact `mo9652962-ai@users.noreply.github.com`.
