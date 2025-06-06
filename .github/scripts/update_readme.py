#!/usr/bin/env python3
"""
Automatically update README.md with commit changes using AI API
"""

import os
import re
import requests
from datetime import datetime, timezone, timedelta
from git import Repo, GitCommandError
from typing import List, Optional
from dataclasses import dataclass
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
GIT_REMOTE = "origin"
GIT_BRANCH = "main"

@dataclass
class FileChange:
    filename: str
    change_type: str
    diff: str
    description: Optional[str] = None

class ReadmeUpdater:
    def __init__(self):
        self.repo = Repo('.')
        self.api_key = os.getenv('MY_DEEPSEEK_API')
        if not self.api_key:
            raise ValueError("MY_DEEPSEEK_API environment variable not set")
        self._setup_git()
        self._sync_repository()

    def _setup_git(self):
        """Configure git user for automated commits"""
        self.repo.git.config('--global', 'user.name', 'GitHub Actions')
        self.repo.git.config('--global', 'user.email', 'actions@github.com')

    def _sync_repository(self):
        """Pull latest changes before making updates"""
        try:
            print("Syncing repository...")
            self.repo.git.pull(GIT_REMOTE)
            self.repo.git.reset('--hard', f'{GIT_REMOTE}/{GIT_BRANCH}')
            print("Repository synced successfully")
        except GitCommandError as e:
            print(f"Error syncing repository: {e}")
            raise

    def _get_current_time(self):
        """Get current time in Moscow timezone (UTC+3)"""
        tz = timezone(timedelta(hours=3))
        return datetime.now(tz).strftime('%d.%m.%Y %H:%M')

    def should_skip_commit(self, commit) -> bool:
        """Check if commit should be skipped"""
        commit_msg = commit.message.lower()
        return any(pattern in commit_msg for pattern in COMMIT_SKIP_PATTERNS)

    def is_ignored_path(self, path: str) -> bool:
        """Check if path should be ignored"""
        return any(ignored in path.replace('\\', '/') for ignored in IGNORE_PATHS)

    def get_changes(self, commit) -> List[FileChange]:
        """Get list of changed files with diffs"""
        changes = []
        
        if not commit.parents:
            for item in commit.tree.traverse():
                if item.type == 'blob' and not self.is_ignored_path(item.path):
                    changes.append(FileChange(
                        filename=item.path,
                        change_type='added',
                        diff=f"Initial commit: {item.path}"
                    ))
            return changes

        parent = commit.parents[0]
        diffs = parent.diff(commit, create_patch=True)
        
        for diff in diffs:
            filename = diff.b_path if diff.b_path else diff.a_path
            if not filename or self.is_ignored_path(filename):
                continue
                
            change_type = self._determine_change_type(diff)
            try:
                diff_text = diff.diff.decode('utf-8', errors='replace')[:MAX_DIFF_LENGTH]
            except UnicodeDecodeError:
                diff_text = "Binary file changes"
            
            changes.append(FileChange(
                filename=filename,
                change_type=change_type,
                diff=diff_text
            ))
        
        return changes

    def _determine_change_type(self, diff) -> str:
        """Determine change type"""
        if diff.new_file: return 'added'
        if diff.deleted_file: return 'deleted'
        if diff.renamed_file: return 'renamed'
        return 'modified'

    def generate_change_description(self, diff: str) -> str:
        """Get AI-generated description of changes"""
        prompt = f"""
        Проанализируй изменения в коде и предоставь краткое описание на русском языке.
        Формат ответа (только список, без вводных слов):
        - Основное изменение 1
        - Основное изменение 2
        
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
            content = response.json()['choices'][0]['message']['content']
            return self._clean_ai_response(content)
        except Exception as e:
            print(f"API Error: {e}")
            return "- Не удалось получить описание изменений"

    def _clean_ai_response(self, text: str) -> str:
        """Clean and format AI response"""
        lines = []
        for line in text.split('\n'):
            line = re.sub(r'^[\d\-•*]+\.?\s*', '- ', line.strip())
            if line and not line.startswith(('```', 'Изменения:', 'Анализ:')):
                lines.append(line)
        return '\n'.join(lines)

    def format_change_entry(self, change: FileChange) -> str:
        """Format file change entry for README with proper Markdown"""
        symbols = {'added': '++', 'modified': '~~', 'deleted': '--', 'renamed': '->'}
        entry = f"**{symbols.get(change.change_type, '~~')} {change.filename}**  \n"
        
        if change.description:
            entry += "```\n"
            entry += change.description.replace('\n', '\n') + "\n"
            entry += "```\n"
        
        return entry + "\n"

    def update_readme(self):
        """Main function to update README with proper Markdown formatting"""
        self._sync_repository()
        
        commit = self.repo.head.commit
        if self.should_skip_commit(commit):
            print("Skipping automated commit")
            return
        
        changes = [c for c in self.get_changes(commit) if c.change_type != 'deleted']
        if not changes:
            print("No relevant changes detected")
            return
        
        # Generate descriptions
        for change in changes:
            change.description = self.generate_change_description(change.diff)
        
        # Build entry with proper Markdown and Moscow time
        timestamp = self._get_current_time()
        new_entry = f"## Изменения от {timestamp} ({len(changes)} файлов)\n\n"
        new_entry += "".join(self.format_change_entry(c) for c in changes)
        new_entry += "---\n\n"
        
        # Update README with proper line breaks
        if Path(README_PATH).exists():
            with open(README_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            content = "# История изменений\n\n"
        
        # Insert new entry after header
        header = "# История изменений"
        if header in content:
            updated_content = content.replace(
                f"{header}\n", 
                f"{header}\n\n{new_entry}"
            )
        else:
            updated_content = f"{header}\n\n{new_entry}{content}"
        
        # Write with explicit newlines
        with open(README_PATH, 'w', encoding='utf-8', newline='\n') as f:
            f.write(updated_content)
        
        # Commit and push changes
        self.repo.git.add(README_PATH)
        if not self.repo.index.diff('HEAD'):
            print("No changes to commit")
            return
            
        self.repo.git.commit('-m', 'Auto-update README with changes [skip ci]')
        self.repo.git.push(GIT_REMOTE, GIT_BRANCH)
        print(f"Updated README with {len(changes)} changes and pushed")

if __name__ == "__main__":
    try:
        updater = ReadmeUpdater()
        updater.update_readme()
    except Exception as e:
        print(f"Error: {e}")
        exit(1)