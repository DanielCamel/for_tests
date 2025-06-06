#!/usr/bin/env python3
"""
Просто добавляет новые коммиты в начало README.md
"""

import os
import re
import requests
from datetime import datetime, timezone, timedelta
from git import Repo, Commit
from typing import List
from pathlib import Path

# Конфигурация
API_URL = "https://api.siliconflow.cn/v1/chat/completions"
README_PATH = "README.md"
MAX_DIFF_LENGTH = 4000
IGNORE_PATHS = [
    ".github/scripts/update_readme.py",
    ".github/workflows/update_readme.yml"
]

class SimpleReadmeUpdater:
    def __init__(self):
        self.repo = Repo('.')
        self.api_key = os.getenv('MY_DEEPSEEK_API')
        if not self.api_key:
            raise ValueError("MY_DEEPSEEK_API environment variable not set")
        self.tz = timezone(timedelta(hours=3))  # UTC+3

    def _get_new_commits(self) -> List[Commit]:
        """Получает только новые коммиты, которых ещё нет в README"""
        if not Path(README_PATH).exists():
            return list(self.repo.iter_commits('HEAD', max_count=20))
        
        with open(README_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Ищем последний обработанный коммит
        last_commit_match = re.search(r'\d{2}:\d{2} \(([a-f0-9]{7})\)', content)
        if last_commit_match:
            last_hash = last_commit_match.group(1)
            return list(self.repo.iter_commits(f'{last_hash}..HEAD'))
        
        return list(self.repo.iter_commits('HEAD', max_count=5))

    def _format_time(self, timestamp: int) -> str:
        """Форматирует время в UTC+3"""
        return datetime.fromtimestamp(timestamp, self.tz).strftime('%H:%M')

    def _get_changes(self, commit: Commit) -> List[str]:
        """Возвращает список изменённых файлов"""
        changes = []
        
        if not commit.parents:  # Первый коммит
            return [item.path for item in commit.tree.traverse() 
                   if item.type == 'blob' and not self._is_ignored(item.path)]

        parent = commit.parents[0]
        diffs = parent.diff(commit)
        
        for diff in diffs:
            filename = diff.b_path if diff.b_path else diff.a_path
            if filename and not self._is_ignored(filename):
                changes.append(filename)
        
        return changes

    def _is_ignored(self, path: str) -> bool:
        """Проверяет, нужно ли игнорировать файл"""
        path = path.replace('\\', '/')
        return any(ignored in path for ignored in IGNORE_PATHS)

    def _generate_description(self, diff: str) -> str:
        """Генерирует описание изменений через API"""
        prompt = f"Опиши эти изменения кратко на русском:\n{diff}"
        
        try:
            response = requests.post(
                API_URL,
                json={
                    "model": "Qwen/Qwen2.5-VL-72B-Instruct",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 300
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'].strip()
        except Exception:
            return "Описание изменений недоступно"

    def _format_commit(self, commit: Commit) -> str:
        """Форматирует коммит для README"""
        time_str = self._format_time(commit.committed_date)
        changes = self._get_changes(commit)
        
        if not changes:
            return ""
        
        # Получаем diff для описания
        diff = ""
        if commit.parents:
            diff = commit.parents[0].diff(commit, create_patch=True).decode(errors='replace')[:MAX_DIFF_LENGTH]
        
        description = self._generate_description(diff)
        
        # Формируем запись
        entry = f"{time_str} ({commit.hexsha[:7]})\n"
        entry += f"Сообщение: {commit.message.strip()}\n\n"
        
        for file in changes:
            entry += f"++ {file}\n\n"
        
        entry += f"{description}\n\n"
        return entry

    def update_readme(self):
        """Добавляет новые коммиты в начало файла"""
        new_commits = self._get_new_commits()
        if not new_commits:
            print("Нет новых коммитов для добавления")
            return
        
        # Читаем текущее содержимое
        old_content = ""
        if Path(README_PATH).exists():
            with open(README_PATH, 'r', encoding='utf-8') as f:
                old_content = f.read()
        
        # Формируем новые записи
        new_entries = ""
        current_date = datetime.now(self.tz).strftime('%d.%m.%Y')
        new_entries += f"## {current_date}\n\n"
        
        for commit in reversed(new_commits):  # Новые сверху
            formatted = self._format_commit(commit)
            if formatted:
                new_entries += formatted
        
        # Объединяем с существующим содержимым
        if old_content.startswith("## "):
            # Вставляем перед первой датой
            parts = old_content.split("\n", 2)
            updated_content = parts[0] + "\n\n" + new_entries + parts[2] if len(parts) > 2 else new_entries + old_content
        else:
            updated_content = new_entries + old_content
        
        # Записываем обратно
        with open(README_PATH, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        

if __name__ == "__main__":
    try:
        updater = SimpleReadmeUpdater()
        updater.update_readme()
    except Exception as e:
        print(f"Ошибка: {e}")
        exit(1)