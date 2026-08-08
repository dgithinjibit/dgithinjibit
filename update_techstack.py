import requests
import re
import time
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Configuration
GITHUB_USERNAME = "dgithinjibit"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
# Realistic exclusion list to keep the tech stack clean and professional
EXCLUDE_LANGUAGES = ["Jupyter Notebook", "HTML", "CSS", "Dart", "PLpgSQL", "PowerShell", "SCSS", "Dockerfile", "Makefile"]
MAX_LANGUAGES = 10
CACHE_DIR = ".cache"
CACHE_TTL_HOURS = 24
MAX_REPOS_LIMIT = 500
REQUEST_TIMEOUT = 10

# Badge colors and logos
BADGE_CONFIG = {
    "Go": {"color": "00ADD8", "logo": "go"},
    "Rust": {"color": "000000", "logo": "rust"},
    "Python": {"color": "3776AB", "logo": "python"},
    "TypeScript": {"color": "3178C6", "logo": "typescript"},
    "C++": {"color": "00599C", "logo": "c%2B%2B"},
    "JavaScript": {"color": "F7DF1E", "logo": "javascript", "logoColor": "black"},
    "Shell": {"color": "4EAA25", "logo": "gnu-bash"},
    "Solidity": {"color": "363636", "logo": "solidity"},
    "Java": {"color": "ED8B00", "logo": "openjdk"},
}

class GitHubAPIClient:
    def __init__(self, username: str, token: Optional[str] = None):
        self.username = username
        self.token = token
        self.session = requests.Session()
        if token:
            self.session.headers.update({"Authorization": f"token {token}"})
    
    def get_repos(self) -> List[Dict]:
        repos = []
        page = 1
        while True:
            url = f"https://api.github.com/users/{self.username}/repos?per_page=100&page={page}"
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                break
            data = response.json()
            if not data:
                break
            repos.extend(data)
            if len(data) < 100:
                break
            page += 1
        return repos

    def get_languages(self, repo_name: str) -> Dict[str, int]:
        url = f"https://api.github.com/repos/{self.username}/{repo_name}/languages"
        response = self.session.get(url, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            return response.json()
        return {}

def main():
    print("🚀 Starting realistic tech stack update...")
    client = GitHubAPIClient(GITHUB_USERNAME, GITHUB_TOKEN)
    
    repos = client.get_repos()
    print(f"Found {len(repos)} repositories.")
    
    language_stats = defaultdict(lambda: {"bytes": 0, "repos": 0})
    from collections import defaultdict
    language_stats = defaultdict(lambda: {"bytes": 0, "repos": 0})
    
    for repo in repos:
        langs = client.get_languages(repo["name"])
        for lang, b in langs.items():
            if lang not in EXCLUDE_LANGUAGES:
                language_stats[lang]["bytes"] += b
                language_stats[lang]["repos"] += 1
                
    sorted_langs = sorted(language_stats.items(), key=lambda x: x[1]["bytes"], reverse=True)
    top_langs = sorted_langs[:MAX_LANGUAGES]
    
    badges = []
    for lang, stats in top_langs:
        config = BADGE_CONFIG.get(lang, {"color": "grey", "logo": lang.lower()})
        color = config["color"]
        logo = config["logo"]
        logo_color = config.get("logoColor", "white")
        badge_url = f"https://img.shields.io/badge/{lang.replace(' ', '%20')}-{color}?style=for-the-badge&logo={logo}&logoColor={logo_color}"
        badges.append(f'  <img src="{badge_url}" />')
    
    techstack_content = "\n".join(badges)
    
    with open("README.md", "r") as f:
        readme = f.read()
    
    start_marker = "<!-- TECHSTACK:START -->"
    end_marker = "<!-- TECHSTACK:END -->"
    
    pattern = f"{re.escape(start_marker)}.*?{re.escape(end_marker)}"
    new_readme = re.sub(
        pattern,
        f"{start_marker}\n<div align=\"center\">\n{techstack_content}\n</div>\n{end_marker}",
        readme,
        flags=re.DOTALL
    )
    
    # Robust URL update for top-langs stats card
    clean_stats_url = 'https://github-readme-stats-eight-theta.vercel.app/api/top-langs/?username=dgithinjibit&hide=Jupyter%20Notebook,HTML,CSS,Dart,PLpgSQL,PowerShell,SCSS&layout=compact&theme=tokyonight&hide_border=true&border_radius=10&title_color=8E4585&icon_color=8E4585'
    
    new_readme = re.sub(
        r'https://github-readme-stats-eight-theta\.vercel\.app/api/top-langs/\?[^\s"]+',
        clean_stats_url,
        new_readme
    )
    
    with open("README.md", "w") as f:
        f.write(new_readme)
    
    print("✅ Realistic README.md and tech stack updated!")

if __name__ == "__main__":
    main()
