# Tehran Network · ZLT P19H Companion

A lightweight, bilingual local management workspace for the **verified ZLT P19H
3.2.27**. Real LTE signal history, dark/light themes, accessible mobile layouts,
native-menu access, protected account changes and Windows-encrypted recovery.

**This is a companion on your computer, not replacement firmware.** It does not
add FDD bands, unlock unknown RF hardware or flash the modem. Only the owner's
physical P19H has been tested; second-device installation is unverified.

[راهنمای کامل فارسی](README.fa.md) · [Compatibility](docs/COMPATIBILITY-FA.md) ·
[Recovery](docs/RECOVERY-FA.md) · [Security](SECURITY.md)

![Actual modem dashboard, identifiers sanitized](screenshots/dashboard-dark-fa.png)

## Start from a checkout

Install Python3.10+ and keep the Ethernet connection to the modem. No runtime
packages, Node build or elevated Windows privileges are needed.

```powershell
.\installer\install.ps1 -Mode check
.\installer\install.ps1 -Mode install
```

For everyday browser-only sign-in, double-click `OPEN-PANEL.cmd`. For the initial
backup/installer wizard, double-click `installer/install.cmd`. Current credentials are requested in a
protected console prompt; the local browser panel uses the modem's real login.
Passwords are never CLI arguments or repository defaults. Keep the console open
while using the panel. Close it with Ctrl+C. Native modem IP access still works.

Optional account wizard: `installer\install.cmd --install --apply-accounts`.
Backup is mandatory before privileged account changes. Read the role limitations:
ordinary primary username/password and SUPER password changes are verified;
**SUPER username change is not supported by the verified native method**.

## Release status

Source and a tested candidate package are prepared for owner review. A final
release installer URL/one-line download command is not claimed until the release
actually exists. The package builder writes SHA256 alongside the candidate ZIP.

## Development

```text
python -X utf8 -m unittest discover -s tests -v
python tools/audit_public.py
python tools/package.py
```

Runtime dependencies: Python standard library only. Source: MIT; brand image has
separate terms. shadcn/ui, Tailwind CSS and Lucide were reviewed as design
references; no framework runtime or third-party icon code is bundled. See
[asset/license notes](docs/ASSET-NOTICES.md).
