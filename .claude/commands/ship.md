---
description: Stage, commit (conventional), and push the current branch.
argument-hint: <type>: <message>
allowed-tools: Bash
---

You are shipping the current changes. Arguments come in as `$ARGUMENTS` in the form `<type>: <message>`.

Steps:

1. **Parse and validate**:
   - Split `$ARGUMENTS` on the first `:`. Left side trimmed = type. Right side trimmed = message.
   - Type **must** be one of: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`.
   - If type is missing/invalid or message is empty — stop and tell the user the expected format: `/ship feat: добавил слот role`.

2. **Show what will be committed** before committing:
   ```bash
   git status --short
   git diff --stat
   ```
   If `git status --short` is empty — say "nothing to ship" and stop.

3. **Sanity-check the working tree**. If you see any of these in `git status`, stop and ask the user before proceeding:
   - files under `models/` (should be gitignored — if visible, gitignore is broken)
   - any `*.tar.gz`, `*.env`, `*.pem`, `credentials*`, secrets-looking files
   - changes to `01_hello_bot/` or `02_phones_bot/` (those are protected examples)

4. **Commit**:
   ```bash
   git add -A
   git commit -m "<type>: <message>"
   ```
   Use the message verbatim from `$ARGUMENTS` (do not paraphrase). Do **not** add Co-Authored-By or any other trailer unless the user has set one up.
   If a pre-commit hook fails — do **not** use `--no-verify`. Report the failure and stop.

5. **Push**:
   - Detect the current branch with `git rev-parse --abbrev-ref HEAD`.
   - If the branch has no upstream (`git rev-parse --abbrev-ref @{u}` fails), push with `-u`:
     ```bash
     git push -u origin <branch>
     ```
   - Otherwise plain `git push`.
   - If there is no `origin` remote at all — stop and tell the user to set one (do not invent one).

6. **Report**:
   ```
   /ship <type>: <message>
   commit: <short-sha>
   pushed: <branch> → origin/<branch>
   ```

Never force-push. Never push to `main` or `master` from this command — if the current branch is main/master, stop and tell the user to switch to a feature branch first.
