# Contributing to PolyPulse

First off — thanks for taking the time to contribute! 🎉

PolyPulse is in **open beta**, and community feedback is what will make it stable enough for a 1.0 release. Whether you're reporting a bug, requesting a feature, or submitting a pull request — you're helping the project.

> 💡 **New here?** The easiest way to start is by [reporting a bug](https://github.com/polypulse/polypulse/issues/new?template=bug_report.md) you found while using PolyPulse. Even small UX papercuts count.

---

## 🐛 Reporting Bugs

Before opening a bug report:

1. **Search existing issues** to avoid duplicates
2. **Reproduce on a fresh scene** (File → New) — this rules out project-specific issues
3. **Check the [Blender version compatibility table](README.md#-compatibility)** — your Blender version may be in the "best-effort" tier

When you open the report (use the **Bug Report** template), include:

- Blender version (Help → About Blender)
- Operating system
- PolyPulse version (visible in addon preferences)
- Steps to reproduce (1, 2, 3, …)
- Expected vs. actual behavior
- Console output (Window → Toggle System Console) — copy-paste any traceback
- Minimal `.blend` file **only if it contains no private assets** — strip textures if needed

---

## 💡 Requesting Features

Open a feature request (use the **Feature Request** template) and describe:

- **Your workflow** — what are you trying to accomplish?
- **The problem** — what's painful or missing?
- **Your proposed solution** — but be open to alternative approaches
- **Alternatives you've considered** — what workarounds are you using today?

Knowing *why* you want a feature is more useful than knowing *what* you want.

---

## 🔧 Pull Requests

PRs are welcome! Before opening one:

### 1. Open an issue first

For anything bigger than a typo fix, **open an issue** to discuss the change. PRs that don't have a matching issue may be closed if they don't fit the project direction.

### 2. Keep PRs focused

One feature or fix per PR. If you have multiple unrelated changes, open multiple PRs — it makes review faster and safer.

### 3. Test before submitting

Run the following from the repository root:

```bash
# Compile-check (catches syntax errors)
python -m compileall -q .

# Smoke tests (requires Blender installed and on PATH)
blender --background --factory-startup --python tests/polypulse_smoke_tests.py
```

Expected: `compileall` exits `0` with no output; smoke tests end with `SUMMARY passed=... failed=0`.

Also test manually in Blender:

- Open a fresh `.blend` file
- Run the operator you changed (and 2-3 adjacent ones)
- Confirm undo restores the original state
- Check the console for warnings

### 4. Follow the code style

- **Indentation**: 4 spaces (Python standard)
- **Line length**: keep under ~100 chars where reasonable
- **Docstrings**: every public function gets one
- **Comments**: in English, explain *why*, not *what*
- **No `print()` calls** in production code — use Blender's `self.report({'INFO', 'WARNING', 'ERROR'}, message)` inside operators, or the `logging` module for module-level diagnostics

### 5. Don't commit any of the following

- `.blend` files containing private work
- `__pycache__/` directories
- `.pyc` / `.pyo` files
- Generated `dist/*.zip` archives
- License keys, customer data, or any proprietary content
- IDE-specific files (`.idea/`, `.vscode/` — they're in `.gitignore` but double-check)

### 6. Write a clear commit message

Use the [Conventional Commits](https://www.conventionalcommits.org/) format:

```
fix(capsule-collider): prevent starburst on flat inputs
feat(uv-atlas): add island count estimate and recommended atlas size
docs(readme): add Blender 5.x compatibility note
chore(ci): add Python compile check workflow
```

### 7. Update the CHANGELOG

If your PR adds a feature or fixes a bug visible to users, add an entry under `[Unreleased]` at the top of [`CHANGELOG.md`](CHANGELOG.md).

### 8. Open the PR

Use the **Pull Request** template and fill in all sections. Link the issue it closes (e.g. `Closes #123`).

---

## 🏗 Repository Structure

```
polypulse/
├── __init__.py              # Addon entry point — bl_info, panel registration, operators
├── modules/
│   ├── __init__.py          # Module loader
│   ├── collider.py          # Box/Sphere/Capsule/Convex collider generator
│   ├── uv_atlas.py          # Smart Project + Bake Texture Atlas
│   ├── visual_overlay.py    # Viewport diagnostics overlay
│   └── license.py           # License subsystem (disabled in open beta)
├── translations/
│   ├── en.json  ru.json  de.json  es.json  jp.json
├── tests/
│   ├── polypulse_smoke_tests.py
│   └── README.md
├── build_release.py         # ZIP packaging script
└── .github/
    ├── ISSUE_TEMPLATE/
    │   ├── bug_report.md
    │   ├── feature_request.md
    │   └── config.yml
    ├── PULL_REQUEST_TEMPLATE.md
    └── workflows/
        └── ci.yml
```

---

## 🌍 Translations

PolyPulse ships with 5 languages: English, Russian, German, Spanish, Japanese. To add a new language:

1. Copy `translations/en.json` to `translations/<lang>.json` (use [ISO 639-1](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes) code)
2. Translate all values (the keys must stay the same)
3. Add the language to the `LANGUAGES` list in `__init__.py` (search for `LANGUAGES =`)
4. Test by switching language in addon preferences

---

## 📦 Building a Release

```bash
python build_release.py --version 0.5.8 --tag beta
# Output: dist/polypulse_v0.5.8_beta.zip
```

The build script:
- Reads the version from `bl_info`
- Excludes `__pycache__`, `.git`, `.github`, `dist`, `build` directories
- Verifies every ZIP entry lives under `polypulse/` (Blender requirement)
- Reports file count and final archive size

Only maintainers should publish releases — contributors don't need to build ZIPs to submit PRs.

---

## 🧪 Testing Philosophy

PolyPulse has two test layers:

### 1. Smoke tests (`tests/polypulse_smoke_tests.py`)

Run in Blender's headless mode. Exercises every registered operator with an execute path, all collider types, all exporters, LOD, UV Atlas, viewport scan, reports, and batch analysis. Writes a JSON report and disposable output files.

Smoke tests catch regressions but **cannot** verify visual correctness — that requires manual QA on real `.blend` files.

### 2. Manual QA

See [`BETA_TEST_PLAN.md`](BETA_TEST_PLAN.md) for the manual test workflow. Before tagging a release, run through:

- Install/enable
- Advanced Scan
- Auto Fix
- LOD chain
- UV Atlas
- All collider types (Box / Sphere / Capsule / Convex)
- UE5 / Unity / Godot export
- Visual Scan
- Report / Batch generation
- Undo safety

---

## 🤔 Questions?

- **Usage questions** → [GitHub Discussions](https://github.com/polypulse/polypulse/discussions) (if enabled) or open a *Discussion*-type issue
- **Bug reports** → [Issue tracker](https://github.com/polypulse/polypulse/issues/new?template=bug_report.md)
- **Security-sensitive reports** (e.g. dangerous operator that could corrupt files) → email `security@polypulse.dev` (PGP key on request)

---

Thanks again for contributing! 🚀
