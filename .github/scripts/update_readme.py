#!/usr/bin/env python3
"""
Automatically update README.md with commit changes descriptions using Qwen API
"""

import os
import re
import requests
from datetime import datetime
from git import Repo, Diff
from typing import List, Optional
from dataclasses import dataclass
from pathlib import Path

# Configuration
API_URL = "https://api.siliconflow.cn/v1/chat/completions"
README_PATH = "README.md"
MAX_DIFF_LENGTH = 4000
COMMIT_SKIP_PATTERNS = ["skip ci", "auto-update", "update readme"]
IGNORE_FILES = [README_PATH, ".github/workflows/update_readme.yml"]

@dataclass
class FileChange:
    filename: str
    change_type: str  # 'added', 'modified', 'deleted', 'renamed'
    diff: str
    description: Optional[str] = None

class ReadmeUpdater:
    def __init__(self):
        self.repo = Repo('.')
        self.api_key = os.getenv('QWEN_API_KEY')
        if not self.api_key:
            raise ValueError("QWEN_API_KEY environment variable not set")

    def should_skip_commit(self, commit) -> bool:
        """Check if commit should be skipped"""
        commit_msg = commit.message.lower()
        return any(pattern in commit_msg for pattern in COMMIT_SKIP_PATTERNS) or \
               "actions" in commit.committer.email.lower()

    def get_changes(self, commit) -> List[FileChange]:
        """Get list of changed files with diffs"""
        changes = []
        
        if not commit.parents:  # Initial commit
            for item in commit.tree.traverse():
                if item.type == 'blob' and item.path not in IGNORE_FILES:
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
            if filename in IGNORE_FILES:
                continue
                
            change_type = self._determine_change_type(diff)
            diff_text = diff.diff.decode('utf-8', errors='replace')[:MAX_DIFF_LENGTH]
            
            changes.append(FileChange(
                filename=filename,
                change_type=change_type,
                diff=diff_text
            ))
        
        return changes

    def _determine_change_type(self, diff) -> str:
        """Determine the type of change"""
        if diff.new_file:
            return 'added'
        if diff.deleted_file:
            return 'deleted'
        if diff.renamed_file:
            return 'renamed'
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
            "stream": False,
            "max_tokens": 512,
            "temperature": 0.7,
            "top_p": 0.7,
            "top_k": 50,
            "frequency_penalty": 0.5,
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
            print(f"API Error: {str(e)}")
            return "Не удалось получить описание изменений"

    def _clean_ai_response(self, text: str) -> str:
        """Clean and standardize AI response"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        cleaned = []
        
        for line in lines:
            # Normalize bullet points and remove numbers
            line = re.sub(r'^(\d+\.\s*|[\-\*•]\s*)', '- ', line)
            cleaned.append(line)
        
        return '\n'.join(cleaned)

    def format_change_entry(self, change: FileChange) -> str:
        """Format single file change entry for README"""
        symbol = {'added': '🆕', 'modified': '✏️', 'deleted': '🗑️', 'renamed': '🔀'}.get(change.change_type, '✏️')
        
        entry = f"| {symbol} `{change.filename}`\n"
        
        if not change.description:
            change.description = self.generate_change_description(change.diff)
        
        if change.description:
            entry += "  |\n"
            for line in change.description.split('\n'):
                entry += f"  | {line}\n"
        
        return entry + "\n"

    def update_readme(self):
        """Main function to update README with changes"""
        commit = self.repo.head.commit
        
        if self.should_skip_commit(commit):
            print("Skipping automated commit")
            return
        
        commit_date = datetime.fromtimestamp(commit.committed_date).strftime('%d.%m.%Y %H:%M')
        changes = [c for c in self.get_changes(commit) if c.change_type != 'deleted']
        
        if not changes:
            print("No relevant changes detected")
            return
        
        # Generate descriptions in parallel (optional optimization)
        for change in changes:
            change.description = self.generate_change_description(change.diff)
        
        # Build the new entry
        new_entry = f"### {commit_date} ({len(changes)} changes)\n\n"
        for change in changes:
            new_entry += self.format_change_entry(change)
        
        # Update README content
        if Path(README_PATH).exists():
            with open(README_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            content = "# История изменений\n\n"
        
        # Insert new entry after header
        header = "## История изменений"
        if header in content:
            updated_content = content.replace(
                f"{header}\n", 
                f"{header}\n\n{new_entry}"
            )
        else:
            updated_content = f"{header}\n\n{new_entry}\n{content}"
        
        with open(README_PATH, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print(f"Updated README with {len(changes)} changes")

if __name__ == "__main__":
    try:
        updater = ReadmeUpdater()
        updater.update_readme()
    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)