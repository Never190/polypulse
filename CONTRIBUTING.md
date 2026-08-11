# Contributing to PolyPulse

First off — thanks for taking the time to contribute! 🎉

PolyPulse is in **open beta**, and community feedback is what will make it stable enough for a 1.0 release. Whether you're reporting a bug, requesting a feature, or submitting a pull request — you're helping the project.

> 💡 **New here?** The easiest way to start is by [reporting a bug](https://github.com/DevWinstor/polypulse/issues/new?template=bug_report.md) you found while using PolyPulse. Even small UX papercuts count.

---

## 🐛 Reporting Bugs

Before opening a bug report:

1. **Search existing issues** to avoid duplicates
2. **Reproduce on a fresh scene** (File → New) — this rules out project-specific issues
3. **Check the [Blender version compatibility table](README.md#-compatibility)** — your Blender version may be in the "best-effort" tier

When you open the report (use the **Bug Report** template), include:

- **Blender version** (Help → About Blender)
- **Operating system**
- **PolyPulse version** (visible in addon preferences)
- **Steps to reproduce** (1, 2, 3, …)
- **Expected vs. actual behavior**
- **Console output** (Window → Toggle System Console) — copy-paste any traceback
- **Minimal `.blend` file** (only if it contains no private assets — strip textures if needed)

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