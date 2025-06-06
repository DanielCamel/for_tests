#!/usr/bin/env python3
"""
Generate change history for the last month in README.md
"""

import os
import re
import requests
from datetime import datetime, timezone, timedelta
from git import Repo, Commit
from typing import List
from pathlib import Path

# Configuration
API_URL = "https://api.siliconflow.cn/v1/chat/completions"
README_PATH = "README.md"
MAX_DIFF_LENGTH = 4000
COMMIT_SKIP_PATTERNS = ["skip ci", "auto-update", "update readme"]
IGNORE_PATHS = [
    ".github/scripts/update_readme.py",
    ".github/workflows/update_readme.yml"
]
HISTORY_MONTHS = 1  # Количество месяцев истории

class ChangeHistoryGenerator:
    def __init__(self):
        self.repo = Repo('.')
        self.api_key = os.getenv('MY_DEEPSEEK_API')
        if not self.api_key:
            raise ValueError("MY_DEEPSEEK_API environment variable not set")
        self.tz = timezone(timedelta(hours=3))  # UTC+3

    def _get_commits_since(self, months: int) -> List[Commit]:
        """Get all commits for the specified number of months"""
        since_date = datetime.now() - timedelta(days=30*months)
        return list(self.repo.iter_commits(since=since_date.isoformat()))

    def _format_datetime(self, timestamp: int) -> str:
        """Format timestamp to string in UTC+3"""
        dt = datetime.fromtimestamp(timestamp, self.tz)
        return dt.strftime('%d.%m.%Y %H:%M')

    def _is_ignored_path(self, path: str) -> bool:
        """Check if path should be ignored"""
        path = path.replace('\\', '/')
        return any(ignored in path for ignored in IGNORE_PATHS)

    def _get_changes(self, commit: Commit) -> List[dict]:
        """Get list of changed files with diffs for a commit"""
        changes = []
        
        if not commit.parents:  # Initial commit
            for item in commit.tree.traverse():
                if item.type == 'blob' and not self._is_ignored_path(item.path):
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
            if not filename or self._is_ignored_path(filename):
                continue
                
            change_type = self._determine_change_type(diff)
            try:
                diff_text = diff.diff.decode('utf-8', errors='replace')[:MAX_DIFF_LENGTH]
            except UnicodeDecodeError:
                diff_text = "Binary file changes"
            
            changes.append({
                'filename': filename,
                'type': change_type,
                'diff': diff_text
            })
        
        return changes

    def _determine_change_type(self, diff) -> str:
        """Determine change type"""
        if diff.new_file: return 'added'
        if diff.deleted_file: return 'deleted'
        if diff.renamed_file: return 'renamed'
        return 'modified'

    def _generate_change_description(self, diff: str) -> str:
        """Get AI-generated description of changes"""
        prompt = f"""
        Проанализируй изменения в коде и предоставь краткое описание на русском языке.
        Формат ответа (только список, без вводных слов):
        - Изменение 1
        - Изменение 2
        
        Изменения:
        {diff}
        """
        
        payload = {
            "model": "Qwen/Qwen2.5-VL-72B-Instruct",
            "temperature": 0.7,
            "max_tokens": 512,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(API_URL, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return self._clean_ai_response(response.json()['choices'][0]['message']['content'])
        except Exception as e:
            print(f"API Error: {e}")
            return "- Не удалось получить описание изменений"

    def _clean_ai_response(self, text: str) -> str:
        """Clean and format AI response"""
        lines = [re.sub(r'^[\d\-•*]+\.?\s*', '- ', line.strip()) 
                for line in text.split('\n') if line.strip()]
        return '\n'.join(lines)

    def _should_skip_commit(self, commit: Commit) -> bool:
        """Check if commit should be skipped"""
        commit_msg = commit.message.lower()
        return any(pattern in commit_msg for pattern in COMMIT_SKIP_PATTERNS)

    def generate_readme(self):
        """Generate README with change history"""
        commits = self._get_commits_since(HISTORY_MONTHS)
        if not commits:
            print("No commits found for the specified period")
            return
        
        # Начинаем с заголовка
        content = "# Изменения\n\n"
        content += f"Последнее обновление: {self._format_datetime(datetime.now().timestamp())}\n\n"
        
        # Добавляем коммиты в обратном порядке (новые сверху)
        for commit in commits:
            if self._should_skip_commit(commit):
                continue
                
            changes = self._get_changes(commit)
            if not changes:
                continue
                
            # Форматируем запись коммита
            commit_time = self._format_datetime(commit.committed_date)
            content += f"## {commit_time} ({commit.hexsha[:7]})\n\n"
            content += f"**Сообщение:** {commit.message.strip()}\n\n"
            
            # Добавляем изменения
            for change in changes:
                description = self._generate_change_description(change['diff'])
                symbol = {'added': '++', 'modified': '~~', 'deleted': '--', 'renamed': '->'}.get(change['type'], '~~')
                content += f"**{symbol} {change['filename']}**  \n"
                content += "```\n"
                content += description + "\n"
                content += "```\n\n"
            
            content += "---\n\n"
        
        # Записываем в файл
        with open(README_PATH, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)
        
        print(f"Generated change history for {len(commits)} commits")

if __name__ == "__main__":
    try:
        generator = ChangeHistoryGenerator()
        generator.generate_readme()
    except Exception as e:
        print(f"Error: {e}")
        exit(1)