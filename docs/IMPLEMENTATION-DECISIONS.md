# Implementation decisions

- Companion was the owner's explicitly authorized fallback when direct native
  WebUI replacement lacked a verified write/recovery path. This requires the
  owner's computer to remain running and does not serve other LAN devices.
- Standard-library Python and authored static UI replace heavy build/runtime
  frameworks; reviewed libraries are design references only.
- Native PRIMARY and SUPER are distinct account slots. Other factory slots stay
  unchanged. SUPER password changes work; native SUPER rename is rejected. The
  product does not repeat an asynchronous PAC-import experiment to rename it.
- A native import experiment was rolled back and independently verified against
  all177 baseline values. It revealed that immediate export/login checks during
  the asynchronous loader are unreliable. No loader command exists in the product.
- Primary rename requires a known verified SUPER name, or the administrator
  wizard, so the application does not introduce an unverified shared username.
- Local journals use Windows DPAPI and physical-device binding. Unknown write
  outcomes stop automatic recovery instead of falsely claiming rollback success.
- One focused read-only helper mapped the captured account protocol. The author
  performed integration review and regression tests; no second assistant review
  was run under the owner's one-assistant preference.
- Final public release stays Draft for owner review. Source publication was
  authorized with the supplied repository. No fabricated download/install command
  or second-device success is presented.
