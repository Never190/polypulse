# Changelog

All notable changes to PolyPulse are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(with a `beta` pre-release tag during the open beta phase).

## [0.5.8] — 2026-08-10 — Open Beta

### 🎉 Open Beta Release

PolyPulse is now **open beta** under the **GNU GPL v3.0** license. All features are unlocked and free for personal and commercial use. Bug reports and contributions are welcome via [GitHub Issues](https://github.com/polypulse/polypulse/issues).

### Changed

- **License switched from MIT (interim) to GNU GPL v3.0** for stronger copyleft protection — derivative works must also be GPL-3.0. This aligns PolyPulse with Blender's own license and prevents closed-source commercial forks.
- Removed all license/tier enforcement code — every feature is now available without activation.
- Removed dead code: `_LICENSE_MODULE_LOADED` flag, `_tier_badge_text` / `_tier_button_icon` no-op helpers, `wrap_operator_tier_check` call in `register()`.
- Removed 27 `lic_*` translation strings from all 5 language files (EN/RU/DE/ES/JP) — they were leftover UI strings for the disabled license panel.
- Updated `bl_info.wiki_url` to point to the GitHub wiki, and `bl_info.tracker_url` to point to GitHub Issues (was previously `blendermarket.com` and `support@polypulse.dev`).
- Updated docstrings in `__init__.py`, `modules/__init__.py`, `modules/collider.py`, `modules/visual_overlay.py` to reflect GPL-3.0 license and v0.5.8 version.

### Added

- [`SECURITY.md`](SECURITY.md) — vulnerability disclosure policy with private email reporting and 90-day coordinated disclosure timeline.
- [`SECURITY_AUDIT.md`](SECURITY_AUDIT.md) — Community / Pro tier architecture, dual-licensing strategy, code-protection plan for future paid features.

### Fixed

- **CRITICAL FIX (Capsule Collider)**: clicking Capsule on a flat-ish object produced a spiky "starburst" mesh (sea urchin) instead of a proper capsule. Root cause: `_create_cylinder_mesh` used `cap_tris=True`, which made each cylinder cap a triangle fan with a center vertex and 24 spokes. The bevel operation then caught both perimeter edges AND fan spokes with `offset=radius`, producing the starburst. Fix: `cap_tris=False` — caps are now flat n-gons with only a single perimeter edge loop at top/bottom. Bevel rounds those edges cleanly into hemispheres.
- Added bevel integrity check: after bevel, if vertex count is suspiciously low (`< 96`, expected ~144 for 24-seg cylinder + 8-seg bevel), the operator falls back to a UV-sphere with uniform scale `(radius, radius, Z/2)`. This is a valid capsule approximation that works in UE5/Unity/Godot physics engines and prevents silent failures.
- **Bake Atlas quality warning**: when baking many objects (e.g. 88 cabinets) at small atlas size (e.g. 2048px), each UV island gets only ~10-20 pixels, producing blurry textures. New code estimates UV island count (~4 per object) and recommends an ideal atlas size (`sqrt(islands) * 64`, rounded to next power of 2, capped at 8192). If user's atlas is smaller than ideal, popup shows a warning like: *"Atlas size 2048px is small for 88 objects (~352 UV islands). Recommended: 8192px to avoid blurry textures."*
- Multi-selection support for UV Atlas: when Shift-selecting 8 cabinets in a row, all their shelves and contents are processed as a single batch.
- Updated `bl_info` warning to "Public beta. Use for evaluation and report reproducible issues."

## [0.5.7] — 2026-08-08

### Fixed

- **CRITICAL FIX (Create UV Atlas / Bake Texture Atlas)**: textures turned completely black after baking. Root cause: `scene.render.bake.use_selected_to_active` was never set to `True`, so Blender baked each selected object into ITS OWN image node instead of projecting source materials onto the active target's atlas image. Sources had no image node → nothing written. Target sampled its own black image → wrote black. Atlas image stayed black.
  - Fix: explicitly set `use_selected_to_active=True` on both `scene.render.bake` AND pass it as kwarg to `bpy.ops.object.bake()` (defense in depth for Blender 4.x/5.x API differences).
- Added `max_ray_distance = 0.005` (5mm) to prevent raycaster from sampling far-away surfaces through the model.
- Added source-object visibility enforcement: temporarily sets `hide_viewport = False` and `hide_render = False` on every source before bake, then restores original state after. (Bake raycaster skips hidden objects, which previously caused silent failures.)
- Changed atlas image `generated_color` from black `(0,0,0,1)` to magenta `(1,0,1,1)` as a debug fallback. If bake fails for any reason, the user now sees a pink image instead of pure black — making the failure obvious. Successful bake overwrites every island with the source material colors.

## [0.5.6] — 2026-08-05

### Added

- Blender-compatible exporter keyword filtering for FBX and glTF.
- Blender smoke tests for all operators and exporters.

### Fixed

- UV Smart Project angle handling for legacy Blender and added island packing.
- Duplicate-vertex distance comparison and UV winding false positives.
- Auto Fix loose-geometry deletion ordering.

### Changed

- Made score and validation displays read-only.
- Improved extension-style preference lookup and viewport overlay cache invalidation.

## [0.5.5] — 2026-07-30

### Added

- Visual Overlay module: viewport highlight for ngons, broken UVs, and duplicate vertices.
- Draw handler lifecycle management to prevent leaks on addon reload.

### Fixed

- Overlay draw handler not removed when disabling the addon.
- Overlay cache invalidation when geometry changes mid-session.

## [0.5.4] — 2026-07-22

### Added

- Collider Generator module (`modules/collider.py`) with Box, Sphere, Capsule, and Convex Hull colliders.
- Colliders properly positioned at the source mesh origin and named with `_COLLISION_*` suffix.

### Fixed

- Convex hull calculation producing degenerate faces on low-poly inputs.

## [0.5.3] — 2026-07-15

### Added

- UV Atlas Generator (`modules/uv_atlas.py`) with Smart Project and optional material merge.
- Bake Texture Atlas operator for projecting source materials onto a single shared atlas image.

### Fixed

- Material slot merge dropping the active material slot when source had only one material.

## [0.5.2] — 2026-07-08

### Added

- LOD Chain Generator: one-click production of LOD0 / LOD1 / LOD2 / LOD3 with progressive decimation.
- LOD objects properly named with `_LOD0` / `_LOD1` / `_LOD2` / `_LOD3` suffix.
- Original mesh preserved (LOD objects are duplicates).

### Fixed

- Decimate modifier not applied correctly when object had shape keys.

## [0.5.1] — 2026-07-01

### Added

- UI helpers for collapsible N-panel sections (disclosure triangle open/close).
- Sub-section grouping: Mesh Repair, LOD Chain, Engine Presets, Textures, Reports.

### Fixed

- N-panel layout breaking on Blender 5.x when section header used `emboss=False`.

## [0.5.0] — 2026-06-20

### 🎉 Initial Public Beta Candidate

First feature-complete beta candidate. Includes:

### Added

- **Scene Analysis**: Analyze Scene, Advanced Scan, Draw Calls Estimator, Game Ready Score.
- **Mesh Repair**: Auto Fix Mesh, Remove Doubles, Recalculate Normals, Remove Loose Geometry, Clean Material Slots.
- **Optimization**: Smart Decimate, LOD Chain Generator.
- **Asset Preparation**: UV Atlas Generator, Bake Texture Atlas, Collider Generator (Box/Sphere/Capsule/Convex), Visual Overlay.
- **Export**: UE5 / Unity / Godot presets (FBX / FBX / GLB).
- **Validation**: Game Ready Check, Validation Score, category breakdowns.
- **Reports**: Export Report, Batch Optimize.
- **i18n**: English, Russian, German, Spanish, Japanese.
- **Compatibility**: Blender 2.83 LTS, 2.93 LTS, 3.6 LTS, 4.3+, 5.x.

---

## Versioning Policy

PolyPulse uses `MAJOR.MINOR.PATCH` versioning during the open beta:

- **PATCH** (`0.5.8 → 0.5.9`): bug fixes, no behavior changes
- **MINOR** (`0.5.x → 0.6.0`): new features, backwards-compatible
- **MAJOR** (`0.x → 1.0.0`): public API changes, stable release

The `beta` suffix is dropped when version `1.0.0` is reached.
