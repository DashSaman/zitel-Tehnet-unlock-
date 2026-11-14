# Assets and design references

Software written for this project is MIT licensed. No original modem WebUI,
firmware, decoded backup or vendor script is redistributed. Original native menus
are retrieved live from the owner's own modem.

The Tehran Network name/logo are brand assets, not covered by the software MIT
license. The logo is reused at the brand owner's request from
https://tehnet.ir/wp-content/themes/tehnet/assets/img/tehnet-logo.jpg . Brand and
palette provenance is recorded in `webui/assets/brand-provenance.json`. Replace
the local image file with your authorized logo when appropriate. No external
asset requests are needed at runtime.

The following primary-source licenses were checked on2026-11-14:

- shadcn/ui: MIT, https://github.com/shadcn-ui/ui/blob/main/LICENSE.md
- Tailwind CSS: MIT, https://github.com/tailwindlabs/tailwindcss/blob/main/LICENSE
- Lucide: ISC plus identified Feather-derived icons/MIT notices,
  https://github.com/lucide-icons/lucide/blob/main/LICENSE

These were design-system references. No source component, CSS framework runtime,
icon path or package from these projects is bundled. UI shapes/navigation glyphs
are authored here or standard text glyphs. Runtime dependencies are empty. Optional
browser QA uses Playwright Python1.65.2 (Apache2.0); it is not distributed in the
runtime package. Python's standard library is provided by the owner's installation.
