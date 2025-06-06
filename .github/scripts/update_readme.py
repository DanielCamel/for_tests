#!/usr/bin/env python3
"""
Генерирует детальную историю изменений в README.md
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
MAX_DIFF_LENGTH = 4000
IGNORE_FILES = [
    ".github/scripts/update_readme.py",
    ".github/workflows/update_readme.yml"
]

class DetailedHistoryGenerator:
    def __init__(self):
        self.repo = Repo('.')
        self.api_key = os.getenv('MY_DEEPSEEK_API')
        if not self.api_key:
            raise ValueError("MY_DEEPSEEK_API environment variable not set")
        self.tz = timezone(timedelta(hours=3))

    def get_new_commits(self) -> List[Commit]:
        """Получает новые коммиты, которых нет в README"""
        if not Path(README_PATH).exists():
            return list(self.repo.iter_commits('HEAD', max_count=20))
        
        with open(README_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        last_hash_match = re.search(r'\d{2}:\d{2} \(([a-f0-9]{7})\)', content)
        if last_hash_match:
            return list(self.repo.iter_commits(f'{last_hash_match.group(1)}..HEAD'))
        
        return list(self.repo.iter_commits('HEAD', max_count=5))

    def format_time(self, timestamp: int) -> str:
        """Форматирует время в UTC+3"""
        return datetime.fromtimestamp(timestamp, self.tz).strftime('%H:%M')

    def get_changes(self, commit: Commit) -> List[Dict]:
        """Возвращает список изменений с диффами"""
        changes = []
        
        if not commit.parents:
            return [{
                'filename': item.path,
                'type': 'added',
                'diff': f"Initial commit: {item.path}"
            } for item in commit.tree.traverse() 
               if item.type == 'blob' and not self.is_ignored(item.path)]

        parent = commit.parents[0]
        diffs = parent.diff(commit, create_patch=True)
        
        for diff in diffs:
            filename = diff.b_path if diff.b_path else diff.a_path
            if not filename or self.is_ignored(filename):
                continue
                
            change_type = self.determine_change_type(diff)
            try:
                diff_text = diff.diff.decode('utf-8', errors='replace')[:MAX_DIFF_LENGTH]
            except (AttributeError, UnicodeDecodeError):
                diff_text = str(diff)[:MAX_DIFF_LENGTH]
            
            changes.append({
                'filename': filename,
                'type': change_type,
                'diff': diff_text
            })
        
        return changes

    def determine_change_type(self, diff) -> str:
        """Определяет тип изменения"""
        if diff.new_file: return 'added'
        if diff.deleted_file: return 'deleted'
        if diff.renamed_file: return 'renamed'
        return 'modified'

    def is_ignored(self, path: str) -> bool:
        """Проверяет, нужно ли игнорировать файл"""
        path = path.replace('\\', '/')
        return any(ignored in path for ignored in IGNORE_FILES)

    def generate_detailed_description(self, diff: str) -> str:
        """Генерирует детальное описание изменений"""
        prompt = f"""
        Детально проанализируй эти изменения кода и предоставь развернутое описание на русском языке.
        Формат ответа (только по пунктам, без вводных слов):
        Изменение 1: [подробное описание первого изменения]
        Изменение 2: [подробное описание второго изменения]
        
        Изменения:
        {diff}
        """
        
        try:
            response = requests.post(
                API_URL,
                json={
                    "model": "Qwen/Qwen2.5-VL-72B-Instruct",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.5,
                    "max_tokens": 500
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=15
            )
            response.raise_for_status()
            content = response.json()['choices'][0]['message']['content']
            return self.clean_description(content)
        except Exception as e:
            print(f"API Error: {e}")
            return "Не удалось получить описание изменений"

    def clean_description(self, text: str) -> str:
        """Очищает описание от лишнего"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        cleaned = []
        for line in lines:
            if line.startswith(('Изменение', 'Change')) or re.match(r'^\d+\.', line):
                cleaned.append(line)
            elif not line.startswith(('```', 'Анализ', 'Analysis')):
                cleaned.append(f"Изменение {len(cleaned)+1}: {line}")
        return '\n'.join(cleaned[:5])  # Ограничиваем 5 изменениями

    def format_commit_entry(self, commit: Commit) -> str:
        """Форматирует запись коммита"""
        time_str = self.format_time(commit.committed_date)
        changes = self.get_changes(commit)
        
        if not changes:
            return ""
        
        entry = f"{time_str} ({commit.hexsha[:7]}) Сообщение: {commit.message.strip()}\n\n"
        
        for change in changes:
            symbol = {'added': '++', 'modified': '~~', 'deleted': '--', 'renamed': '->'}.get(change['type'], '~~')
            entry += f"{symbol} {change['filename']}\n\n"
            
            description = self.generate_detailed_description(change['diff'])
            entry += f"{description}\n\n"
        
        return entry

    def update_readme(self):
        """Обновляет README новыми коммитами"""
        new_commits = self.get_new_commits()
        if not new_commits:
            print("Нет новых коммитов для добавления")
            return
        
        # Формируем новые записи
        current_date = datetime.now(self.tz).strftime('%d.%m.%Y')
        new_entries = f"{current_date}\n\n"
        
        for commit in reversed(new_commits):  # Новые коммиты сверху
            formatted = self.format_commit_entry(commit)
            if formatted:
                new_entries += formatted
        
        # Читаем существующее содержимое
        old_content = ""
        if Path(README_PATH).exists():
            with open(README_PATH, 'r', encoding='utf-8') as f:
                old_content = f.read()
        
        # Объединяем содержимое
        if "## История изменений" in old_content:
            updated_content = old_content.replace("## История изменений\n", f"## История изменений\n\n{new_entries}")
        else:
            updated_content = f"## История изменений\n\n{new_entries}{old_content}"
        
        # Записываем обратно
        with open(README_PATH, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print(f"Добавлено {len(new_commits)} новых коммитов")

if __name__ == "__main__":
    try:
        generator = DetailedHistoryGenerator()
        generator.update_readme()
    except Exception as e:
        print(f"Ошибка: {e}")
        exit(1)