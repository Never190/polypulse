<div align="center">

# ⚡ PolyPulse

**Game-ready 3D asset toolkit for Blender**

*Mesh repair · LOD generation · UV atlas · Collider generation · Engine export — all in one N-panel*

[![Blender](https://img.shields.io/badge/Blender-2.83%20LTS%20%E2%80%93%205.x-blue?logo=blender&logoColor=white)](https://www.blender.org)
[![Version](https://img.shields.io/badge/version-0.5.8%20beta-orange)](https://github.com/DevWinstor/polypulse/releases)
[![License: GPL v3](https://img.shields.io/badge/license-GPL%20v3-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-open%20beta-purple.svg)](#-open-beta)
[![Languages](https://img.shields.io/badge/i18n-EN%20%C2%B7%20RU%20%C2%B7%20DE%20%C2%B7%20ES%20%C2%B7%20JP-teal.svg)](#-languages)

[Features](#-features) · [Install](#-install) · [Quick Start](#-quick-start) · [Screenshots](#-screenshots) · [Roadmap](#-roadmap) · [FAQ](#-faq) · [Contributing](#-contributing)

**English version** · **[Русская версия](docs/README.ru.md)**

</div>

---

## 📋 Overview

**PolyPulse** is a Blender addon that consolidates the most common asset-pipeline operations into a single N-panel: mesh repair, automatic LOD generation, UV atlas creation, collider generation, and engine-specific FBX/GLB export for Unreal Engine 5, Unity, and Godot.

Built for technical artists, prop modelers, and indie game devs who want a fast, deterministic path from Blender to a game engine — without leaving the viewport.

> ⚠️ **Open Beta**: This is a public beta release. All features are free and unlocked. Please report bugs and feedback via [GitHub Issues](https://github.com/DevWinstor/polypulse/issues/new/choose).

---

## 🚀 PolyPulse Pro is Coming

PolyPulse is in **open beta**, and we're building the next evolution. Here's what's on the horizon:

| Feature | Community (this beta) | Pro (coming soon) |
|---------|:---:|:---:|
| Mesh repair · LOD · colliders · UV atlas | ✅ Free | ✅ Included |
| C++ core (20x faster UV unwrap) | — | ✅ |
| Batch automation (100+ assets) | — | ✅ |
| Cloud validation & team workflows | — | ✅ |
| Priority support | — | ✅ |

### 🎁 Beta Testers Get Rewarded

If you're testing this open beta, you'll get:

- 🔔 **First access** to PolyPulse Pro
- 💸 **Exclusive launch discount** (up to 50% off)
- 🗳 **Your feedback shapes** the Pro roadmap

**→ Join the dev channel: [t.me/Dev_PolyPulse](https://t.me/Dev_PolyPulse)**

> The Community edition (this beta) stays **free forever** under GPL-3.0. Pro adds *new* features on top — it never removes or paywalls what's already free.

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

1. Go to [Releases](https://github.com/DevWinstor/polypulse/releases)
2. Download `polypulse_v0.5.8_beta.zip`
3. In Blender: **Edit → Preferences → Add-ons → Install…**
4. Select the downloaded ZIP file
5. Enable **PolyPulse** checkbox
6. Open 3D Viewport, press `N` to open sidebar
7. Switch to **PolyPulse** tab

### From source (developers)

```bash
git clone https://github.com/DevWinstor/polypulse.git
cd polypulse
python build_release.py --tag beta
# Output: dist/polypulse_v0.5.8_beta.zip