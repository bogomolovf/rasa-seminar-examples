---
description: Validate RASA data and run a quick training for a bot directory, summarize errors.
argument-hint: [bot_dir]
allowed-tools: Bash
---

You are validating a RASA bot. Steps:

0. **Use the absolute rasa path** — `.venv` is a conda prefix env (no `bin/activate` script):
   ```
   /Users/fedorbogomolov/Desktop/examples/.venv/bin/rasa <subcommand>
   ```
   (Or `conda activate /Users/fedorbogomolov/Desktop/examples/.venv` for an interactive shell — but Bash tool calls each spawn a fresh shell, so activation won't persist; prefer the direct path.)

1. Determine the target bot directory:
   - If `$ARGUMENTS` is non-empty, use it (e.g. `03_hr_bot`).
   - Otherwise default to `03_hr_bot`.
   - Verify the directory exists and contains `domain.yml`, `config.yml`, `data/`. If not — stop and report what's missing.

2. From inside the bot directory, run:
   ```bash
   rasa data validate
   ```
   Capture stdout+stderr. Note any `ERROR`/`WARNING` lines.

3. If `rasa data validate` exited 0 (or only warnings), run:
   ```bash
   rasa train --quiet
   ```
   Capture stdout+stderr.

4. Produce a **compact** report in this exact shape:

   ```
   /rasa-check <bot_dir>
   validate: ✅  (or ❌ — first 1–3 error lines)
   train:    ✅  (or ❌ — first 1–3 error lines, or "skipped" if validate failed)
   ```

   No verbose logs. Strip RASA's progress bars, training loss tables, and INFO chatter. Keep only the failure cause if any.

5. If anything failed, do **not** attempt fixes — just report. The user (or another agent) will fix.

Be fast and quiet. The whole report should fit in ~10 lines.
