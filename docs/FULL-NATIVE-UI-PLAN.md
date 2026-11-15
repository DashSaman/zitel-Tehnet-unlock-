# Native workspace and alignment guide

The owner requests three outcomes: recover the reinserted Mobinnet360 SIM,
present every menu of this P19H through the Tehran Network design with no old
panel frame/entry, and help a non-specialist compare antenna directions.

The chosen implementation keeps the installed design and native backend ACL.
It renders the device's authorized settings fragments inside a styled workspace,
using the existing firmware's field validation/serialization controllers. It
does not embed the old home page or copy vendor sources into the repository.
Reimplementing every field conversion would add avoidable configuration risk;
retaining the old framed panel does not meet the owner's explicit requirement.

Core elements use a separate DOM namespace so native form IDs cannot collide.
One settings sidebar covers all 27 observed administrator menus; backend
authorization and the current user's native privilege flags remain authoritative.
Opening settings cannot automatically mutate configuration. User-requested
actions retain their normal validation and confirmations. Unknown firmware,
calibration and unsupported RF writes remain unavailable under the owner's
earlier explicit constraints. No network/reset/flash action is used as a UI test.

SIM and home-operator state are refreshed rather than cached from login. Missing
SIM, PIN required, registration search, WAN assignment and radio quality are
distinct states. Automatic APN recovery uses the owner's previous empty/default
selection, preserving the saved MCI profile and all unrelated settings.

The alignment guide explains SIM readiness first, then coarse/fine rotation,
settling time and several real samples per position. Comparisons use median
SINR, then RSRQ and RSRP, report band/cell changes, and never claim more Mbps
from signal bars or MHz alone. No location, calibration or unknown band is set.

Validation: regressions for stale operator and no old frame, API crypto/roles,
all menu/subtab loads with mutations blocked, real admin/ordinary sign-in,
responsive/RTL/themes/keyboard, fresh modem-side Internet checks, served hashes,
configuration comparisons and encrypted pre-update UI/config backups.
