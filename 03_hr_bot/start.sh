#!/bin/bash
# Запускает HR-бота с Telegram-каналом одной командой:
#   ./start.sh
# Делает по шагам:
#   1. Гасит то, что висит на портах 5005/5055.
#   2. Поднимает cloudflared quick-tunnel, ждёт публичный HTTPS-URL.
#   3. Прописывает свежий URL в credentials.local.yml.
#   4. Запускает action server :5055 в фоне.
#   5. Запускает RASA :5005 с Telegram-каналом в foreground.
# Ctrl+C — глушит cloudflared + action server + RASA, очищает порты.

set -e
cd "$(dirname "$0")"

VENV=/Users/fedorbogomolov/Desktop/examples/.venv
LOG_DIR=/tmp
PIDS=()

cleanup() {
  echo
  echo "→ Останавливаю фоновые процессы..."
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
  lsof -ti:5005,5055 2>/dev/null | xargs kill 2>/dev/null || true
  pkill -f "cloudflared tunnel --url http://localhost:5005" 2>/dev/null || true
  echo "  done."
}
trap cleanup EXIT INT TERM

echo "→ Освобождаю порты 5005 / 5055..."
lsof -ti:5005,5055 2>/dev/null | xargs kill 2>/dev/null || true
pkill -f "cloudflared tunnel --url http://localhost:5005" 2>/dev/null || true
sleep 1

echo "→ Запускаю cloudflared quick-tunnel..."
: > "$LOG_DIR/cloudflared.log"
cloudflared tunnel --url http://localhost:5005 > "$LOG_DIR/cloudflared.log" 2>&1 &
PIDS+=($!)

echo "→ Жду публичный URL от cloudflared..."
URL=""
for i in {1..40}; do
  URL=$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG_DIR/cloudflared.log" 2>/dev/null | head -1 || true)
  [ -n "$URL" ] && break
  sleep 1
done
if [ -z "$URL" ]; then
  echo "✗ cloudflared не дал URL за 40s. Лог: $LOG_DIR/cloudflared.log"
  exit 1
fi
echo "  cloudflared URL: $URL"

echo "→ Прописываю webhook_url в credentials.local.yml..."
WEBHOOK="$URL/webhooks/telegram/webhook"
sed -i.bak "s|webhook_url:.*|webhook_url: \"$WEBHOOK\"|" credentials.local.yml
rm -f credentials.local.yml.bak

echo "→ Запускаю action server :5055..."
"$VENV/bin/rasa" run actions > "$LOG_DIR/rasa-actions.log" 2>&1 &
PIDS+=($!)
until curl -s http://localhost:5055/health > /dev/null 2>&1; do sleep 1; done
echo "  action server up"

echo "→ Запускаю RASA :5005 с Telegram..."
echo "  логи action-server: $LOG_DIR/rasa-actions.log"
echo "  логи cloudflared:   $LOG_DIR/cloudflared.log"
echo "  Ctrl+C — остановить всё"
echo
"$VENV/bin/rasa" run --enable-api --cors "*" --credentials credentials.local.yml
