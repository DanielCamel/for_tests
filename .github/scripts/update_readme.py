#!/usr/bin/env python3
"""
Логирует новые коммиты в README.md с группировкой по датам
Формат вывода полностью соответствует примеру
"""

import os
import re
import requests
from datetime import datetime, timezone, timedelta
from git import Repo, Commit, Diff
from typing import List, Dict, Optional
from pathlib import Path

# Конфигурация
API_URL = "https://api.siliconflow.cn/v1/chat/completions"
README_PATH = "README.md"
MAX_DIFF_LENGTH = 4000
IGNORE_PATHS = [
    ".github/scripts/update_readme.py",
    ".github/workflows/update_readme.yml"
]
SKIP_PATTERNS = ["skip ci", "auto-update", "update readme"]  # Добавлено определение

class CommitHistory:
    def __init__(self):
        self.repo = Repo('.')
        self.api_key = os.getenv('MY_DEEPSEEK_API')
        if not self.api_key:
            raise ValueError("MY_DEEPSEEK_API environment variable not set")
        self.tz = timezone(timedelta(hours=3))  # UTC+3

    def get_new_commits(self) -> List[Commit]:
        """Возвращает новые коммиты, которых нет в README"""
        if not Path(README_PATH).exists():
            return list(self.repo.iter_commits(max_count=20))
        
        with open(README_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        last_hash_match = re.search(r'\d{2}:\d{2} \(([a-f0-9]{7})\)', content)
        if last_hash_match:
            return list(self.repo.iter_commits(f'{last_hash_match.group(1)}..HEAD'))
        
        return list(self.repo.iter_commits(max_count=5))

    def format_time(self, timestamp: int) -> str:
        """Форматирует время в UTC+3 (ЧЧ:ММ)"""
        return datetime.fromtimestamp(timestamp, self.tz).strftime('%H:%M')

    def get_changes(self, commit: Commit) -> List[Dict]:
        """Возвращает изменения для коммита"""
        changes = []
        
        if not commit.parents:  # Первый коммит
            for item in commit.tree.traverse():
                if item.type == 'blob' and not self.is_ignored(item.path):
                    changes.append({
                        'filename': item.path,
                        'type': 'added',
                        'diff': f"Initial commit: {item.path}"
                    })
            return changes

        parent = commit.parents[0]
        diffs = parent.diff(commit, create_patch=True)
        
        for diff in diffs:
            filename = diff.b_path if diff.b_path else diff.a_path
            if filename and not self.is_ignored(filename):
                try:
                    diff_text = diff.diff.decode('utf-8', errors='replace')[:MAX_DIFF_LENGTH]
                except (AttributeError, UnicodeDecodeError):
                    diff_text = str(diff)[:MAX_DIFF_LENGTH]
                
                changes.append({
                    'filename': filename,
                    'type': self.get_change_type(diff),
                    'diff': diff_text
                })
        
        return changes

    def get_change_type(self, diff) -> str:
        """Определяет тип изменения"""
        if diff.new_file: return 'added'
        if diff.deleted_file: return 'deleted'
        if diff.renamed_file: return 'renamed'
        return 'modified'

    def is_ignored(self, path: str) -> bool:
        """Проверяет, нужно ли игнорировать файл"""
        path = path.replace('\\', '/')
        return any(ignored in path for ignored in IGNORE_PATHS)

    def generate_description(self, diff: str) -> str:
        """Генерирует подробное описание изменений"""
        prompt = f"""
        Детально проанализируй эти изменения кода и сгенерируй развернутое описание на русском языке.
        Формат строго следующий:
        Изменение 1: [детальное описание первого изменения]
        Изменение 2: [детальное описание второго изменения]
        
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
            return self.clean_response(response.json()['choices'][0]['message']['content'])
        except Exception as e:
            print(f"API Error: {e}")
            return "Не удалось получить описание изменений"

    def clean_response(self, text: str) -> str:
        """Очищает ответ API до нужного формата"""
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith(('Изменение', 'Change')) or re.match(r'^\d+[\.:]', line):
                lines.append(re.sub(r'^\d+[\.:\s]*', '', line).strip())
            elif line and not lines:
                lines.append(line)
        
        return '\n'.join(f"Изменение {i+1}: {line}" for i, line in enumerate(lines[:2]))

    def format_commit(self, commit: Commit) -> Optional[Dict]:
        """Форматирует коммит для вывода"""
        if any(p in commit.message.lower() for p in SKIP_PATTERNS):  # Исправлено на SKIP_PATTERNS
            return None
            
        changes = self.get_changes(commit)
        if not changes:
            return None
            
        return {
            'time': self.format_time(commit.committed_date),
            'hash': commit.hexsha[:7],
            'message': commit.message.strip(),
            'changes': [
                {
                    'symbol': {'added': '++', 'modified': '~~', 'deleted': '--', 'renamed': '->'}.get(c['type'], '~~'),
                    'filename': c['filename'],
                    'description': self.generate_description(c['diff'])
                }
                for c in changes
            ]
        }

    def update_readme(self):
        """Обновляет README новыми коммитами"""
        new_commits = self.get_new_commits()
        if not new_commits:
            print("Нет новых коммитов для добавления")
            return
        
        # Группируем коммиты по датам
        commits_by_date = {}
        for commit in new_commits:
            date_str = datetime.fromtimestamp(commit.committed_date, self.tz).strftime('%d.%m.%Y')
            formatted = self.format_commit(commit)
            if formatted:
                if date_str not in commits_by_date:
                    commits_by_date[date_str] = []
                commits_by_date[date_str].append(formatted)
        
        if not commits_by_date:
            return
        
        # Формируем новые записи
        new_content = ""
        for date in sorted(commits_by_date.keys(), reverse=True):
            new_content += f"{date}\n\n"
            for commit in commits_by_date[date]:
                new_content += f"{commit['time']} ({commit['hash']}) Сообщение: {commit['message']}\n\n"
                for change in commit['changes']:
                    new_content += f"{change['symbol']} {change['filename']}\n\n"
                    new_content += f"{change['description']}\n\n"
        
        # Читаем существующее содержимое
        old_content = ""
        if Path(README_PATH).exists():
            with open(README_PATH, 'r', encoding='utf-8') as f:
                old_content = f.read()
        
        # Объединяем содержимое
        if "## История изменений" in old_content:
            updated_content = old_content.replace("## История изменений\n", f"## История изменений\n\n{new_content}")
        else:
            updated_content = f"## История изменений\n\n{new_content}{old_content}"
        
        # Записываем обратно
        with open(README_PATH, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print(f"Добавлено {len(new_commits)} новых коммитов")

if __name__ == "__main__":
    try:
        logger = CommitHistory()
        logger.update_readme()
    except Exception as e:
        print(f"Ошибка: {e}")
        exit(1)