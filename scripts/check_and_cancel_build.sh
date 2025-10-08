#!/usr/bin/env bash
set -e

# --- 1. Настройки (ни один из этих токенов не хранится в GitHub!)
# Секреты удалить после тестов!
REPO_URL='https://github.com/DanielCamel/java_labs.git'
SV_TOKEN=''
PROJECT_NAME='Java_Labs'
GITHUB_OWNER='DanielCamel'
GITHUB_TOKEN=''


REPO_ID=493 # Идентификатор свойства Ссылка на репозиторий
PROJECT_NAME_ID=3 # Идентификатор свойства Наименование проекта
BUILD_ID=537 # Идентификатор свойства Сведения о проекте
BUILD_STOP_ID=648 # Идентификатор свойства Остановить сборку
API_UPDATE_URL='http://localhost:8108/api/entity/update'
API_SEARCH_URL='http://localhost:8108/api/entity/search'

# --- 2. Проверка внешнего флага (пример)
echo "🔍 Checking build stop flag..."
BUILD_STOP_VALUE=$(curl -s -X POST "$API_SEARCH_URL" \
  -H "SV-Token: $SV_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"project":"Java_Labs"}' | jq -r '.result[0].properties[0].value')

echo "BUILD_STOP_VALUE=$BUILD_STOP_VALUE"

# --- 3. Если true → пытаемся отменить активный workflow
if [[ "$BUILD_STOP_VALUE" == "true" ]]; then
  echo "🛑 Build stop requested — checking active workflows..."

  # Получаем последние запущенные workflow runs
  RUNS=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$GITHUB_OWNER/$GITHUB_REPO/actions/runs?status=in_progress")

  RUN_ID=$(echo "$RUNS" | jq -r '.workflow_runs[0].id')

  if [[ "$RUN_ID" != "null" && -n "$RUN_ID" ]]; then
    echo "⚙️ Found active run: $RUN_ID"
    echo "⏹ Cancelling workflow..."
    curl -s -L \
      -X POST \
      -H "Accept: application/vnd.github+json" \
      -H "Authorization: Bearer $GITHUB_TOKEN" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "https://api.github.com/repos/$GITHUB_OWNER/$GITHUB_REPO/actions/runs/$RUN_ID/cancel"
    echo "✅ Workflow $RUN_ID cancelled."
  else
    echo "ℹ️ No active workflow found to cancel."
  fi

  echo "Push aborted — build stop enforced."
  exit 1
else
  echo "✅ Build flag is false — proceeding with push."
fi
