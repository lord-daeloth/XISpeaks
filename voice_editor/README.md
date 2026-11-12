# Pocket Voice Catalog Editor

Run START-Voice-Catalog.cmd beside the installed addon. The bundled Windows EXE needs no Python or Hugging Face login. Save catalog updates the companion on its next request; NPC overrides remain intact except references to removed voices.

Select one voice to edit its label, gender (m/f/a/u), accent, automatic assignment flags, NPC types, speed and volume. Ctrl/Shift-select to bulk-edit gender, accent and eligibility. Search and gender/accent/NPC filters remain available.

Preview uses unsaved edits and the companion's public English 18M model. It reports peak, RMS dBFS and duration. Fixed seed mode is recommended for comparison; New seed changes the reference. Zero noise uses temperature zero, which can produce unnatural pacing or generation-limit warnings in Pocket. Model loading is cached between previews.

Add voice imports a .safetensors state exported specifically for english_18m_2026-10. Architecture is validated, but matching export provenance is still required. One file represents one voice; Pocket has no Piper-style speaker selector. Newly added voices are manual-only until enabled. Remove affects the catalog, not shared state files. Save makes timestamped catalog backups and rejects concurrent edits.

Source checkout: START-Voice-Catalog.cmd targets the installed CatsEyeXI Pocket catalog if present, otherwise the source pocket_voices/catalog.json. You can also run voice_editor/app.py --catalog PATH to target another Pocket catalog. The catalog path is shown at startup.

Both Halver volunteer test states have been retired; Halver uses normal automatic assignment until a new profile is created.

On opening or reloading, entries whose .safetensors files are missing are removed automatically. The original catalog is backed up in catalog-backups and the editor reports the removal count. Invalid paths and corrupt existing voice files still report errors.
