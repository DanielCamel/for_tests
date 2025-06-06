#!/usr/bin/env python3
"""
Automatically update README.md with commit changes using Qwen API
Includes automatic git pull to sync changes
"""

import os
import re
import requests
from datetime import datetime
from git import Repo, GitCommandError
from typing import List, Optional
from dataclasses import dataclass
from pathlib import Path

# Configuration
API_URL = "https://api.siliconflow.cn/v1/chat/completions"
README_PATH = "README.md"
MAX_DIFF_LENGTH = 4000
COMMIT_SKIP_PATTERNS = ["skip ci", "auto-update", "update readme"]
IGNORE_FILES = [README_PATH, ".github/workflows/update_readme.yml"]
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
        
        # Configure git
        self.git = self.repo.git
        self._setup_git()

    def _setup_git(self):
        """Configure git user for automated commits"""
        self.git.config('--global', 'user.name', 'GitHub Actions')
        self.git.config('--global', 'user.email', 'actions@github.com')

    def _sync_repository(self):
        """Pull latest changes before making updates"""
        try:
            print("Syncing repository...")
            self.git.fetch()
            self.git.checkout(GIT_BRANCH)
            self.git.pull(GIT_REMOTE, GIT_BRANCH)
            print("Repository synced successfully")
        except GitCommandError as e:
            print(f"Error syncing repository: {e}")
            raise

    def should_skip_commit(self, commit) -> bool:
        """Check if commit should be skipped"""
        commit_msg = commit.message.lower()
        return any(pattern in commit_msg for pattern in COMMIT_SKIP_PATTERNS)

    def get_changes(self, commit) -> List[FileChange]:
        """Get list of changed files with diffs"""
        changes = []
        
        if not commit.parents:
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
        """Determine change type with emoji"""
        if diff.new_file: return 'added'
        if diff.deleted_file: return 'deleted'
        if diff.renamed_file: return 'renamed'
        return 'modified'

    def generate_change_description(self, diff: str) -> str:
        """Get AI-generated description of changes"""
        prompt = f"""
        Analyze these code changes and provide a concise description in Russian.
        Return only bullet points:
        - Change 1
        - Change 2
        
        Changes:
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
            return "Не удалось получить описание изменений"

    def _clean_ai_response(self, text: str) -> str:
        """Clean and format AI response"""
        lines = [re.sub(r'^[\d\-•*]+\.?\s*', '- ', line.strip()) 
                for line in text.split('\n') if line.strip()]
        return '\n'.join(lines)

    def format_change_entry(self, change: FileChange) -> str:
        """Format file change entry for README"""
        icons = {'added': '🆕', 'modified': '✏️', 'deleted': '🗑️', 'renamed': '🔀'}
        entry = f"| {icons.get(change.change_type, '✏️')} `{change.filename}`\n"
        
        if change.description:
            entry += "  |\n"
            for line in change.description.split('\n'):
                entry += f"  | {line}\n"
        
        return entry + "\n"

    def update_readme(self):
        """Main function to update README"""
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
        
        # Build entry
        timestamp = datetime.now().strftime('%d.%m.%Y %H:%M')
        new_entry = f"### {timestamp} ({len(changes)} changes)\n\n"
        new_entry += "".join(self.format_change_entry(c) for c in changes)
        
        # Update README
        content = Path(README_PATH).read_text(encoding='utf-8') if Path(README_PATH).exists() else "# История изменений\n\n"
        
        header = "## История изменений"
        updated_content = content.replace(f"{header}\n", f"{header}\n\n{new_entry}") if header in content \
                        else f"{header}\n\n{new_entry}\n{content}"
        
        Path(README_PATH).write_text(updated_content, encoding='utf-8')
        
        # Commit changes
        self.git.add(README_PATH)
        if not self.repo.index.diff('HEAD'):
            print("No changes to commit")
            return
            
        self.git.commit('-m', 'Auto-update README with changes [skip ci]')
        self.git.push(GIT_REMOTE, GIT_BRANCH)
        print(f"Updated README with {len(changes)} changes and pushed")

if __name__ == "__main__":
    try:
        updater = ReadmeUpdater()
        updater.update_readme()
    except Exception as e:
        print(f"Error: {e}")
        exit(1)