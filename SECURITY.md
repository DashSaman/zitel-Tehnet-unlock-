# Security boundaries

Only the tested owner's private P19H endpoint is supported. The companion binds
127.0.0.1, validates Host, rejects cross-origin requests, requires an HttpOnly
SameSiteStrict session cookie and CSRF token for API writes, and disables indexing.
It does not support external destinations or redirects in the modem client.
Firmware privilege checks remain authoritative; SUPER requires a protected read.

No credentials are CLI arguments, URL parameters, default passwords, logs, or
public repository content. The original native WebUI necessarily uses its modem
session in browser sessionStorage, as it does at the modem IP; the bridge injects
only that transient session, never the saved password/hash. Browser UI code uses
textContent for device strings. Identifier hiding is a presentation feature, not
an access-control mechanism.

Backup/account journals use user-bound Windows DPAPI and a private physical-device
binding. DPAPI is not protection from malware running as that Windows user.
The modem's native LAN link is HTTP; this project does not claim transport TLS
for the original device. Do not expose the loopback server or modem management
port publicly. No analytics or telemetry collector is installed.

No automatic firmware import, band activation, calibration, bootloader or identity
changes exist. Native menus retain real effects and their original backend ACL.
Do not run untrusted scripts in the authenticated native panel.

Report a vulnerability without device credentials, hashes, PACs, IMEI/IMSI/ICCID,
serials or session tokens. Use the repository's private reporting facility if
available; otherwise submit a minimal sanitized issue and arrange private evidence
with the owner. No automatic messages to third parties are sent by this project.
