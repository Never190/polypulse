# PolyPulse public beta test plan

Use a copy of a `.blend` file. The smoke script runs automatically in background mode; the manual checks below verify the visible result.

## Run the automated robot

From the extracted project folder:

```bash
blender --background --factory-startup --python tests/polypulse_smoke_tests.py