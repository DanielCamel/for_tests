#!/usr/bin/env python3
"""
Обновляет README.md, исключая собственные изменения
"""

import os
import re
import requests
from datetime import datetime, timezone, timedelta
from git import Repo, Commit, Diff
from typing import List, Dict
from pathlib import Path

# Настройки
API_URL = "https://api.siliconflow.cn/v1/chat/completions"
README_PATH = "README.md"
MAX_DIFF_LENGTH = 2000
IGNORE_FILES = [
    ".github/scripts/update_readme.py",
    ".github/workflows/update_readme.yml",
    "README.md"  # Исключаем сам README.md
]

class ReadmeUpdater:
    def __init__(self):
        self.repo = Repo('.')
        self.api_key = os.getenv('MY_DEEPSEEK_API')
        if not self.api_key:
            raise ValueError("API ключ не установлен")
        self.tz = timezone(timedelta(hours=3))

    def get_new_commits(self) -> List[Commit]:
        """Получает новые коммиты, исключая служебные"""
        if not Path(README_PATH).exists():
            return list(self.repo.iter_commits('HEAD', max_count=10))
        
        with open(README_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        last_hash_match = re.search(r'\d{2}:\d{2} \(([a-f0-9]{7})\)', content)
        if last_hash_match:
            return list(self.repo.iter_commits(f'{last_hash_match.group(1)}..HEAD'))
        return []

    def format_time(self, timestamp: int) -> str:
        """Форматирует время в UTC+3"""
        return datetime.fromtimestamp(timestamp, self.tz).strftime('%H:%M')

    def get_changes(self, commit: Commit) -> List[Dict]:
        """Возвращает изменения, исключая игнорируемые файлы"""
        if not commit.parents:
            return []
            
        changes = []
        for diff in commit.parents[0].diff(commit, create_patch=True):
            filename = diff.b_path or diff.a_path
            if filename and not self.is_ignored(filename):
                changes.append({
                    'file': filename,
                    'diff': diff.diff.decode('utf-8', errors='replace')[:MAX_DIFF_LENGTH]
                })
        return changes

    def is_ignored(self, path: str) -> bool:
        """Проверяет, нужно ли игнорировать файл"""
        path = path.replace('\\', '/')
        return any(ignored in path for ignored in IGNORE_FILES)

    def generate_comment(self, diff: str) -> str:
        """Генерирует краткое описание изменений"""
        try:
            response = requests.post(
                API_URL,
                json={
                    "model": "Qwen/Qwen2.5-VL-72B-Instruct",
                    "messages": [{
                        "role": "user",
                        "content": f"Опиши изменения кратко (2-3 пункта):\n{diff}"
                    }],
                    "max_tokens": 150,
                    "temperature": 0.3
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5
            )
            content = response.json()['choices'][0]['message']['content']
            return '\n'.join(f"- {line.strip()}" for line in content.split('\n') if line.strip())
        except Exception:
            return "- Изменения"

    def update_readme(self):
        """Обновляет README, добавляя новые коммиты сверху"""
        new_commits = self.get_new_commits()
        if not new_commits:
            return
            
        current_date = datetime.now(self.tz).strftime('%d.%m.%Y')
        new_content = [f"## {current_date}\n"]
        
        for commit in reversed(new_commits):
            changes = self.get_changes(commit)
            if changes:
                new_content.append(f"{self.format_time(commit.committed_date)} ({commit.hexsha[:7]})")
                new_content.append(f"Сообщение: {commit.message.split('[skip ci]')[0].strip()}")
                
                for change in changes:
                    new_content.append(f"++ {change['file']}")
                    new_content.append(self.generate_comment(change['diff']))
                
                new_content.append("")
        
        if Path(README_PATH).exists():
            with open(README_PATH, 'r', encoding='utf-8') as f:
                new_content.append(f.read())
        
        with open(README_PATH, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_content))

if __name__ == "__main__":
    try:
        ReadmeUpdater().update_readme()
    except Exception as e:
        print(f"Ошибка: {e}")
        exit(1)