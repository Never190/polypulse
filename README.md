<div align="center">

# ⚡ PolyPulse

**Game-ready 3D asset toolkit for Blender**

*Mesh repair · LOD generation · UV atlas · Collider generation · Engine export — all in one N-panel*

[![Blender](https://img.shields.io/badge/Blender-2.83%20LTS%20%E2%80%93%205.x-blue?logo=blender&logoColor=white)](https://www.blender.org/)
[![Version](https://img.shields.io/badge/version-0.5.8%20beta-orange)](https://github.com/polypulse/polypulse/releases)
[![License: GPL v3](https://img.shields.io/badge/license-GPL%20v3-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-open%20beta-purple.svg)](#-open-beta)
[![CI](https://github.com/polypulse/polypulse/actions/workflows/ci.yml/badge.svg)](https://github.com/polypulse/polypulse/actions)
[![Languages](https://img.shields.io/badge/i18n-EN%20%C2%B7%20RU%20%C2%B7%20DE%20%C2%B7%20ES%20%C2%B7%20JP-teal.svg)](#-languages)

[Features](#-features) · [Install](#-install) · [Quick Start](#-quick-start) · [Screenshots](#-screenshots) · [Roadmap](#-roadmap) · [FAQ](#-faq) · [Contributing](#-contributing)

📚 **English version** · **[Русская версия](docs/README.ru.md)**

</div>

---

## 📋 Overview

**PolyPulse** is a Blender addon that consolidates the most common asset-pipeline operations into a single N-panel: mesh repair, automatic LOD generation, UV atlas creation, collider generation, and engine-specific FBX/GLB export for **Unreal Engine 5**, **Unity**, and **Godot**.

Built for technical artists, prop modelers, and indie game devs who want a fast, deterministic path from Blender to a game engine — without leaving the viewport.

> ⚠️ **Open Beta**: This is a public beta release. All features are free and unlocked. Please report bugs and feedback via [GitHub Issues](https://github.com/polypulse/polypulse/issues/new/choose).

> **What comes next:** PolyPulse Community Beta remains free and fully unlocked. The next-generation Blender asset pipeline is now being developed as **VORVEXON**. Follow development updates and early-access news on [Telegram](https://t.me/vorvexon).

---

## ✨ Features

### 🔍 Scene Analysis
- **Scene Analyze** — object/mesh/material statistics at a glance
- **Advanced Scan** — deep mesh diagnostics: ngons, tris, non-manifold edges, UV islands, duplicate verts (via KDTree, O(N log N))
- **Draw Calls Estimator** — estimate engine draw calls before export
- **Game Ready Score** — weighted readiness score across geometry, UV, textures, materials

### 🛠 Mesh Repair
- **Auto Fix Mesh** — one-click cleanup: remove doubles, recalc normals, remove loose geometry, clean material slots
- **Remove Doubles** — configurable merge distance
- **Recalculate Normals** — outside/front-facing
- **Remove Loose Geometry** — zero-area faces and stray verts
- **Clean Material Slots** — drop unused material slots
- **Visual Overlay** — viewport highlight of problem areas (ngons, bad UVs, dup verts)

### 📉 Optimization
- **Smart Decimate** — context-aware polygon reduction preserving silhouette
- **LOD Chain Generator** — automatically produce LOD1 / LOD2 / LOD3 with progressive decimation and proper naming (`_LOD0`, `_LOD1`, `_LOD2`, `_LOD3`)

### 🎯 Asset Preparation
- **UV Atlas Generator** — Smart Project + island packing + optional material merge
- **Bake Texture Atlas** — bake multiple objects onto a single shared atlas image
- **Collider Generator** — Box / Sphere / Capsule / Convex Hull, properly positioned and named (`_COLLISION_*`)
- **Visual Overlay** — viewport diagnostics for ngons, broken UVs, duplicate vertices

### 🚀 Engine Export
- **UE5 preset** — FBX with proper forward/up axis and Y-forward
- **Unity preset** — FBX with Z-forward, Y-up
- **Godot preset** — GLB with embedded materials and textures
- **Export Report** — full audit of what was exported (geometry, materials, textures, file size)

### 🌍 Languages
Built-in internationalization with full translations for:
- 🇬🇧 English · 🇷🇺 Russian · 🇩🇪 German · 🇪🇸 Spanish · 🇯🇵 Japanese

Switch language from the addon preferences — UI updates instantly.

---

## 📥 Install

### From GitHub Releases (recommended)

1. Go to [Releases](https://github.com/polypulse/polypulse/releases)
2. Download `polypulse_v0.5.8_beta.zip`
3. In Blender: **Edit → Preferences → Add-ons → Install…**
4. Select the downloaded ZIP file
5. Enable **PolyPulse** checkbox
6. Open 3D Viewport, press `N` to open sidebar
7. Switch to **PolyPulse** tab

### From source (developers)

```bash
git clone https://github.com/polypulse/polypulse.git
cd polypulse
python build_release.py --tag beta
# Output: dist/polypulse_v0.5.8_beta.zip
```

Then install the ZIP from `dist/` as described above.

> 💡 The ZIP **must** contain a top-level `polypulse/` folder. If you see "ZIP packaged incorrectly" in Blender, you downloaded the source code ZIP, not a Release build — download from the [Releases page](https://github.com/polypulse/polypulse/releases) instead.

---

## 🚀 Quick Start

1. **Open a scene** with at least one mesh object
2. Press `N` in the 3D Viewport → switch to **PolyPulse** tab
3. **Select one or more objects** (Shift-click for multi-select — works great on cabinets/shelves/etc.)
4. Click **Analyze Scene** to see statistics
5. Click **Advanced Scan** for deep diagnostics
6. Click **Auto Fix Mesh** to clean up common issues
7. Click **Generate LOD Chain** to create LOD0–LOD3
8. Click **Create UV Atlas** to pack UVs
9. Pick an export preset (**UE5 / Unity / Godot**) to export the asset

**Multi-selection works on full hierarchies** — selecting a cabinet also selects its shelves and contents. The UV atlas operator processes all selected objects as a batch.

---

## 📸 Screenshots

> 🎨 Screenshots coming soon. Want to contribute? See [`CONTRIBUTING.md`](CONTRIBUTING.md) and open a PR adding images to `docs/screenshots/`.

Placeholder preview:

```
┌─────────────────────────────────────────────────────────┐
│  PolyPulse                                              │
│  ─────────                                              │
│  ▼ Game Ready Score                                     │
│    [████████░░] 82/100 — Game Ready                    │
│                                                         │
│  ▼ Analysis                                             │
│    [Analyze Scene]  [Advanced Scan]                    │
│    Objects: 24  Meshes: 18  Verts: 12.4k               │
│                                                         │
│  ▼ Optimization                                         │
│    [Auto Fix Mesh]  [Remove Doubles]                   │
│    [Smart Decimate] [Generate LOD Chain]               │
│                                                         │
│  ▼ Asset Preparation                                    │
│    [Box] [Sphere] [Capsule] [Convex]                   │
│    [Create UV Atlas]  [Visual Scan]                    │
│                                                         │
│  ▼ Export                                               │
│    [Unreal Engine 5]  [Unity]  [Godot]                 │
└─────────────────────────────────────────────────────────┘
```

---

## 🧪 Testing

### Automated smoke tests

Run the full operator/exporter/collider/LOD/UV test suite:

```bash
blender --background --factory-startup --python tests/polypulse_smoke_tests.py
```

Expected: Blender exits with code `0`, console ends with `SUMMARY passed=... failed=0`, and a JSON report is written next to the test file.

### Manual QA checklist

See [`BETA_TEST_PLAN.md`](BETA_TEST_PLAN.md) for the full manual test workflow.

---

## 🐛 Bug Reports

Found a bug? Please [open an issue](https://github.com/polypulse/polypulse/issues/new?template=bug_report.md) and include:

- **Blender version** (Help → About Blender)
- **Operating system** (Windows / macOS / Linux + version)
- **PolyPulse version** (visible in addon preferences)
- **Steps to reproduce** (step-by-step, starting from a fresh Blender file if possible)
- **Expected vs. actual behavior**
- **Console output** (Window → Toggle System Console) — copy-paste any traceback
- **Minimal `.blend` file** (only if it contains no private/commercial assets — strip textures if needed)

💡 **Tip**: Before reporting, try **File → New** to confirm the bug reproduces on a fresh scene. This rules out project-specific issues.

---

## 💡 Feature Requests

Have an idea? [Open a feature request](https://github.com/polypulse/polypulse/issues/new?template=feature_request.md). Please describe your use case and workflow — knowing *why* you want a feature is more useful than knowing *what* you want.

---

## 🤝 Contributing

Pull requests are welcome! Before opening one:

1. **Open an issue first** to discuss large changes
2. Keep PRs focused — one feature or fix per PR
3. Test on **Blender 3.6 LTS** and **Blender 4.3+**
4. Run smoke tests: `blender --background --factory-startup --python tests/polypulse_smoke_tests.py`
5. Compile-check: `python -m compileall -q .`
6. Never commit `.blend` files containing private work, `__pycache__`, or generated ZIP archives

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for full guidelines.

---

## 🗺 Roadmap

PolyPulse is in **open beta**. All features are currently free and unlocked.

**Planned for future releases:**

- 🔲 **Pro tier** ($15/month) — Advanced batch processing, automation scripts, custom export profiles
- 🔲 **Premium tier** ($45/month) — Team workflows, cloud asset validation, priority support
- 🔲 **Blender 5.x compatibility** tests on official release
- 🔲 **More languages** — French, Portuguese, Korean, Chinese
- 🔲 **GPU-accelerated** mesh analysis for large scenes
- 🔲 **Plugin API** — let third parties extend PolyPulse

> ℹ️ The current open beta will remain free for personal and commercial use. Future paid tiers will add *new* features, not lock existing ones behind a paywall.

See [`SECURITY_AUDIT.md`](SECURITY_AUDIT.md) for the full Community / Pro architecture and licensing strategy.

---

## ❓ FAQ

### Is PolyPulse really free?

**Yes.** PolyPulse v0.5.x is licensed under **GNU GPL v3.0** and is free for both personal and commercial use. You can modify it, distribute it, and use it in production. The only requirement is that derivative works must also be GPL-3.0.

### Will the addon stay free?

**The Community edition will always be free.** Future Pro/Premium features ($15/$45/month) will be **new** code, not existing features locked behind a paywall. See [`SECURITY_AUDIT.md`](SECURITY_AUDIT.md) for the dual-licensing strategy.

### Can I use PolyPulse in a commercial game project?

**Yes.** Your game project is separate from PolyPulse — GPL-3.0 only applies to PolyPulse itself, not to the assets or games you create using it. This is the same model as Blender itself.

### Can I modify PolyPulse and sell my modified version?

**Yes, but** you must:
1. Keep the GPL-3.0 license
2. Publish your modified source code
3. Include the original copyright notice

This is the standard copyleft requirement of GPL-3.0.

### Which Blender versions are supported?

| Version           | Status          | Notes                                  |
|-------------------|-----------------|----------------------------------------|
| 5.x (current)     | ✅ Supported    | Primary test target                    |
| 4.3+              | ✅ Supported    | Primary test target                    |
| 3.6 LTS           | ✅ Supported    | Primary test target                    |
| 2.93 LTS          | ⚠️ Best-effort | Code paths retained, not actively tested |
| 2.83 LTS          | ⚠️ Best-effort | Code paths retained, not actively tested |

**Operating systems**: Windows 10/11, macOS 12+, Ubuntu 22.04+

### The ZIP won't install — "No blender_manifest.toml" error

This error appears on **Blender 4.2+** when installing via the Extensions Manager. PolyPulse v0.5.8 ships as a **legacy addon** (not an extension), so:

1. Use **Edit → Preferences → Add-ons** (not Extensions) → **Install…**
2. Select the ZIP file
3. Enable the addon in the list

We plan to ship a proper extension manifest in a future release.

### UV Atlas bake produces a black texture — what should I do?

This was fixed in **v0.5.7**. If you still see a black atlas:
- Make sure you're on PolyPulse v0.5.7 or later (check addon preferences)
- Make sure Cycles is available (the addon sets it automatically, but custom Blender builds without Cycles will fail)
- If bake fails, the atlas image will be **magenta** `(1, 0, 1, 1)` as a debug indicator — this means "no pixels were written". Open the System Console to see the error.

### Capsule collider produces a spiky "sea urchin" mesh

This was fixed in **v0.5.8**. The bug was caused by `cap_tris=True` on cylinder caps, which created triangle fans that bevel caught as edges. Update to v0.5.8 or later.

### Multi-selection doesn't work as expected

PolyPulse respects Blender's selection hierarchy:
- If you select a parent object, child objects are NOT automatically selected
- Use Shift+click to multi-select
- If a cabinet + its shelves + its contents are all selected, the UV Atlas operator processes all of them as a batch

For large groups (e.g. 8 cabinets in a row), Shift-click each one — works fine up to 128 unique meshes per UV Atlas bake.

### Where can I see what changed between versions?

See [`CHANGELOG.md`](CHANGELOG.md) — it follows the [Keep a Changelog](https://keepachangelog.com/) format.

### I found a security vulnerability — where do I report it?

**Please do NOT open a public GitHub issue.** See [`SECURITY.md`](SECURITY.md) for private disclosure instructions.

---

## ⚙️ Compatibility

| Blender version | Status | Notes |
|---|---|---|
| 5.x (current) | ✅ Supported | Primary test target |
| 4.3+ | ✅ Supported | Primary test target |
| 3.6 LTS | ✅ Supported | Primary test target |
| 2.93 LTS | ⚠️ Best-effort | Code paths retained, not actively tested |
| 2.83 LTS | ⚠️ Best-effort | Code paths retained, not actively tested |

**Operating systems**: Windows 10/11, macOS 12+, Ubuntu 22.04+

---

## 📦 Repository Structure

```
polypulse/
├── __init__.py              # Addon entry point (bl_info, registration, panels)
├── modules/
│   ├── __init__.py          # Shared UI helpers (section_header)
│   ├── collider.py          # Collider Generator (Box/Sphere/Capsule/Convex)
│   ├── uv_atlas.py          # UV Atlas + Bake Texture Atlas
│   └── visual_overlay.py    # Viewport diagnostics overlay
├── translations/
│   ├── en.json  ru.json  de.json  es.json  jp.json
├── tests/
│   ├── polypulse_smoke_tests.py
│   └── README.md
├── docs/
│   └── README.ru.md          # Russian documentation
├── .github/
│   ├── workflows/ci.yml    # CI: compile check + structure check + ZIP build
│   ├── ISSUE_TEMPLATE/      # bug_report.md, feature_request.md, config.yml
│   └── PULL_REQUEST_TEMPLATE.md
├── build_release.py         # ZIP packaging script
├── CHANGELOG.md             # Keep a Changelog format
├── CONTRIBUTING.md          # Contributor guide
├── CODE_OF_CONDUCT.md       # Contributor Covenant v2.1
├── SECURITY.md              # Vulnerability disclosure policy
├── SECURITY_AUDIT.md        # Community/Pro architecture & IP strategy
├── BETA_TEST_PLAN.md        # Manual QA checklist
├── RELEASE_CHECKLIST.md     # Maintainer release workflow
├── LICENSE                  # GNU GPL v3.0
├── .gitignore
└── README.md
```

---

## 📜 License

PolyPulse is released under the **GNU General Public License v3.0** — see [`LICENSE`](LICENSE).

You are free to:
- ✅ Use the addon for personal and commercial projects
- ✅ Modify the source code
- ✅ Distribute the addon (with attribution)
- ✅ Submit pull requests and contribute

**Copyleft requirement**: If you distribute a modified version, you must publish the source code under the same GPL-3.0 license. This protects the project from being forked into closed-source commercial products.

The copyright notice and license text must be included in all copies or substantial portions of the software.

---

## 🌟 Acknowledgements

PolyPulse is built on top of [Blender](https://www.blender.org/)'s excellent Python API and BMesh library. Thanks to the Blender Foundation and the entire Blender community for making tools like this possible.

Special thanks to early beta testers who provided invaluable feedback on collider generation, UV atlas baking, and exporter compatibility.

---

<div align="center">

**[⬆ Back to top](#-polypulse)** · **[Report a bug](https://github.com/polypulse/polypulse/issues/new?template=bug_report.md)** · **[Request a feature](https://github.com/polypulse/polypulse/issues/new?template=feature_request.md)** · **[Security disclosure](SECURITY.md)**

Made with ⚡ for the Blender community

</div>
