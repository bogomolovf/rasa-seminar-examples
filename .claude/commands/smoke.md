---
description: Start action server + RASA REST API, send a few curl probes, then shut everything down.
argument-hint: [bot_dir]
allowed-tools: Bash
---

You are running an end-to-end smoke test for a RASA bot. Steps:

0. **Activate venv** (or use absolute paths) in every Bash invocation that runs rasa:
   ```bash
   source /Users/fedorbogomolov/Desktop/examples/.venv/bin/activate
   ```
   Each Bash call is a fresh shell — activation does not persist.

1. Determine target bot directory:
   - Use `$ARGUMENTS` if non-empty, else `03_hr_bot`.
   - Verify it has a trained model under `models/`. If not — tell the user to run `/rasa-check` first and stop.

2. Pick free ports: default `5005` (REST) and `5055` (actions). If `lsof -i :5005` or `lsof -i :5055` shows them busy, stop and tell the user which port is taken.

3. From inside the bot directory, start the action server **in the background** and capture its PID:
   ```bash
   rasa run actions --port 5055 > /tmp/rasa_actions.log 2>&1 &
   ACTIONS_PID=$!
   ```
   Then start the REST API in the background:
   ```bash
   rasa run --enable-api --cors "*" --port 5005 > /tmp/rasa_api.log 2>&1 &
   API_PID=$!
   ```

4. **Wait for readiness**, don't just sleep blindly. Poll with curl up to ~30s:
   ```bash
   for i in {1..30}; do
     curl -fs http://localhost:5005/status > /dev/null && break
     sleep 1
   done
   ```
   If never ready — print the last 20 lines of each log and skip to cleanup.

5. Send **2–3 curl probes** to `http://localhost:5005/webhooks/rest/webhook`. Default probes (override if user asked for specific scenarios):
   ```bash
   curl -s -H 'Content-Type: application/json' \
     -d '{"sender":"smoke","message":"привет"}' \
     http://localhost:5005/webhooks/rest/webhook
   ```
   Pick messages relevant to the bot's current intents (peek at `data/nlu.yml`).

6. **Always clean up**, even on failure:
   ```bash
   kill $API_PID $ACTIONS_PID 2>/dev/null
   wait $API_PID $ACTIONS_PID 2>/dev/null
   ```
   Verify with `lsof -i :5005 -i :5055` that nothing is left listening.

7. Report compactly:
   ```
   /smoke <bot_dir>
   probe 1 "<msg>" → <bot reply summary>  ✅/❌
   probe 2 ...
   probe 3 ...
   cleanup: ✅
   ```

Never leave servers running. If you hit Ctrl-C territory, still kill the PIDs.
