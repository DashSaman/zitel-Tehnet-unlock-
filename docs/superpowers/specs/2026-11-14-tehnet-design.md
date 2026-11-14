# Tehran Network P19H design

Owner specification: the 2026-11-14 MASTER MISSION supplied in chat. Build a
lightweight local management companion, secure account workflow, Windows
installer, Persian documentation and reviewable open-source distribution.

## Evidence and approach

The tested device is ZLT P19H, hardware TZ7.821.183, firmware3.2.27,
configuration YLM19H v9.10, Sequans S16. Native authentication is a salted
SHA256 challenge over the firmware's MD5 credential representation. Four stored
credential slots exist: PRIMARY, TEST, SUPPORT and SUPER. Tested SUPER has
userType1; the other observed logins have userType2 and lack the protected admin
read. No third independent admin role is invented. Command98 with username/
newUsername is verified for PRIMARY, rejected for SUPER. Command102 is verified
for PRIMARY and SUPER password changes; factory slots remain untouched.

Direct WebUI replacement was considered, but no verified filesystem write and
recovery method exists for this board. The owner's explicitly authorized fallback
is a companion served by Python on the owner's computer. It preserves native
menus through an authenticated same-origin proxy. It is not flashed firmware.
React/Tailwind runtime was considered; plain HTML/CSS/JS and standard-library
Python keep installation small and offline-capable. Lucide, shadcn and Tailwind
are reviewed design references only; no third-party icon/framework code is bundled.

## Boundaries

- Bind only127.0.0.1, exact Host checks, same-origin mutation checks, CSRF token,
  HttpOnly SameSiteStrict session cookie; no arbitrary proxy destinations.
- User types the current device password into a local form or protected console.
  Do not bundle any owner secret, hash, PAC, original WebUI, or hardware ID.
- Backend retains the modem session; frontend receives only normalized status,
  genuine role, and native-menu access. Escape all device-provided strings.
- Allowlist P19H/TZ7.821.183/3.2.27 for account writes. Unsupported hardware fails
  closed. Read-only checks never import, reboot, scan bands or change radio state.
- Native account transactions preserve per-step recovery information and verify
  fresh login. Shared usernames are treated as unknown until tested; revert the
  conflicting final rename if either account is inaccessible.
- Save private backups outside the checkout, protected by Windows DPAPI. Verify
  PAC checksums and exact decode/re-encode before considering account writes.
- Installer defaults to no device mutation. Optional native account edits are
  explicit. Rollback restores only account slots changed by its own transaction,
  rather than overwriting unrelated later configuration.
- No firmware update, calibration, identity, band, ACS or bootloader changes.
- Reboot persistence test is a separately visible installer step; a reboot briefly
  interrupts connectivity. Physical second-device testing is not claimed.

## Product behavior

Real TehNet logo and palette are extracted from tehnet.ir source. Dark/light,
Persian RTL/English, responsive navigation, telemetry cards, accessible SVG
history charts, polling pause and unavailable-data states. Login reveals on
hover, focus, click or touch; reduced-motion removes transitions. Native menus
remain available. Branding is replaceable by an owner-supplied local image.

## Delivery

Source, tests, licenses, threat boundaries, Persian install/role/recovery/compatibility
docs and CI. Package deterministic ZIP with SHA256 and test it from a clean
unpack. GitHub source publication is authorized by the repository supplied for
publication. Final release publication follows owner review as the mission asks;
do not invent a live release URL or one-line installer before that release exists.
