#!/bin/bash

set -e

# --- 1. Настройки (ни один из этих токенов не хранится в GitHub!)
# Секреты удалить после тестов!
REPO_URL='https://github.com/DanielCamel/java_labs.git'
#SV_TOKEN="$SV_TOKEN"
PROJECT_NAME='Java_Labs'
GITHUB_OWNER='DanielCamel'
#GITHUB_TOKEN="$GITHUB_TOKEN"

REPO_ID=493 # Идентификатор свойства Ссылка на репозиторий
PROJECT_NAME_ID=3 # Идентификатор свойства Наименование проекта
BUILD_ID=537 # Идентификатор свойства Сведения о проекте
BUILD_STOP_ID=648 # Идентификатор свойства Остановить сборку
API_UPDATE_URL='http://localhost:8108/api/entity/update'
API_SEARCH_URL='http://localhost:8108/api/entity/search'


# Функция обработки ответа API
parse_response() {
    local response="$1"

    # Последняя строка — это http_code
    local http_code=$(echo "$response" | tail -n1)
    # Всё кроме последней строки — тело
    local content=$(echo "$response" | sed '$d')

    if [ "$http_code" -ne 200 ]; then
        echo "Ошибка API: HTTP $http_code"
        echo "Ответ: $content"
        exit 1
    fi

    # Возвращаем тело через echo
    echo "$content"
}


# --- 2. Проверка внешнего флага (пример)
echo "Checking build stop flag..."

# Формируем JSON фильтр. Id свойства объекта "Ссылка на репозиторий": Id=493
SEARCH_JSON_REPO_LINK="{\
\"skip\":0,\
\"top\":5,\
\"outputproperties\":[\
  {\"id\": \"$BUILD_STOP_ID\"},{\"id\": \"$REPO_ID\"},{\"id\": \"$PROJECT_NAME_ID\"}\
],\
\"filter\":{\
  \"type\": \"and\",\
  \"conditions\":[
    {\
      \"type\":\"property\",\
      \"id\": $REPO_ID,\
      \"operator\": \"like\",\
      \"value\": \"$REPO_URL\"\
     },\
     {\
      \"type\":\"property\",\
      \"id\": $PROJECT_NAME_ID,\
      \"operator\": \"like\",\
      \"value\": \"$PROJECT_NAME\"\
      }\
    ]\
  }
}"

# Выполняем запрос для получения информации о проекте
search_response=$(curl -s -w "\n%{http_code}" \
  -X POST "$API_SEARCH_URL" \
  -H "SV-Token: $SV_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$SEARCH_JSON_REPO_LINK")


search_content=$(parse_response "$search_response")

BUILD_STOP_VALUE="$(echo "$search_content" | jq -r '.result[0].properties[0].value')"

echo "Остановить сборку: $BUILD_STOP_VALUE"

# --- 3. Если true → пытаемся отменить активный workflow
if [[ "$BUILD_STOP_VALUE" == "true" ]]; then

  git commit --allow-empty -m "[WARNING] Установлен флаг остановки сборки!"

  echo "Build stop requested — checking active workflows..."

  echo "$BUILD_STOP_VALUE" > .github/scripts/build_stop.txt
  echo "Push aborted — build stop enforced."
else

  echo "$BUILD_STOP_VALUE" > .github/scripts/build_stop.txt
  echo "Build flag is false — proceeding with push."
fi
