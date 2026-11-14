# Tehran Network P19H Implementation Plan

> Native implementation in this session. The owner supplied the execution request;
> reviewed coding preferences limit assistance to one focused evidence search.

**Goal:** Deliver and test a secure reusable local P19H management companion.
**Architecture:** Standard-library Python device client, transaction/recovery layer,
loopback HTTP server and static bilingual UI; PowerShell/CMD wrappers.
**Tech Stack:** Python3.10+, HTML/CSS/JS, PowerShell5.1+, GitHub Actions.
**Spec:** ../specs/2026-11-14-tehnet-design.md

## Global Constraints

No firmware/radio/identity/ACS changes; no device secrets in repository. Exact
tested compatibility guard. Genuine backend roles. No credentials in arguments,
URLs or logs. Preserve all native menus. Final Release requires owner review.

## Review Focus

Wrong device/address, malformed status, session expiry, duplicate usernames,
partial account mutation and recovery, CSRF/DNS rebinding, hostile device text,
missing optional telemetry, mobile/reduced motion, clean package installation.

## Tasks

- [x] Device baseline and recovery: native config+assets private backup; strict
  PAC roundtrip; extract brand. Files client.py, recovery.py, tests/test_device.py.
- [x] Native account workflow: prove supported command98/102 payloads; fresh role verification;
  narrow rollback on failure. Files accounts.py, tests/test_accounts.py. Test fake
  backend collisions and partial failure before real owner changes.
- [x] Companion server: protected sessions, status normalization and native menu
  proxy. Files server.py, tests/test_server.py. Test unauthenticated/Host/Origin/
  cookie checks and session expiry without device writes.
- [x] UI: webui/index.html, app.js, styles.css, brand assets; real status, SVG
  history, English/RTL/dark/light/mobile/reduced-motion and all native menus.
  Browser-test both roles, charts, focus login, mobile and expired login.
- [x] Installer: CLI modes check,dry-run,install,backup,verify,rollback; secure wizard;
  PowerShell/CMD wrappers, DPAPI private state; tests/test_installer.py. Offline
  simulated rollback and clean-unpack smoke test; real backup and verification.
- [x] Distribution preparation: documentation, sample placeholders, LICENSE and asset notices,
  AGENTS, CI secret/license/test checks; clean ZIP+SHA256, sanitized screenshots.
  Run all tests; inspect complete staged diff; scan secrets; publish source and
  prepare reviewable release assets. Do not publish an unreviewed final release.

- [ ] Owner approval and final publication of the Draft Release. A public-release
  one-line download/install command follows only after the release actually exists.

Supported account scope is recorded in ADMIN-ROLES-FA.md; SUPER rename was
rejected and is intentionally not claimed. Physical second-device installation
is unverified. Operator selection and full restoration evidence are in
OPERATOR-TEST-FA.md; no universal-SIM or physical FDD claim is made.
