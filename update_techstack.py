import os
import requests
import re
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Configuration
GITHUB_USERNAME = "dgithinjibit"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
EXCLUDE_LANGUAGES = ["Jupyter Notebook"]
MAX_LANGUAGES = 12
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
    "HTML": {"color": "E34F26", "logo": "html5"},
    "C++": {"color": "00599C", "logo": "c%2B%2B"},
    "JavaScript": {"color": "F7DF1E", "logo": "javascript", "logoColor": "black"},
    "Shell": {"color": "4EAA25", "logo": "gnu-bash"},
    "Solidity": {"color": "363636", "logo": "solidity"},
    "Java": {"color": "ED8B00", "logo": "openjdk"},
    "CSS": {"color": "1572B6", "logo": "css3"},
    "Dockerfile": {"color": "2496ED", "logo": "docker"},
}


class CacheManager:
    """Manages file-based caching with TTL support."""
    
    def __init__(self, cache_dir: str = CACHE_DIR, ttl_hours: int = CACHE_TTL_HOURS):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)
    
    def _get_cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"
    
    def get(self, key: str) -> Optional[Dict]:
        """Retrieve cached data if valid and not expired."""
        cache_path = self._get_cache_path(key)
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, "r") as f:
                data = json.load(f)
            
            timestamp = datetime.fromisoformat(data.get("timestamp", ""))
            if datetime.now() - timestamp < self.ttl:
                return data.get("data")
            else:
                cache_path.unlink()  # Delete expired cache
                return None
        except (json.JSONDecodeError, ValueError, KeyError):
            cache_path.unlink()  # Delete corrupted cache
            return None
    
    def set(self, key: str, data: Dict) -> None:
        """Store data with timestamp."""
        cache_path = self._get_cache_path(key)
        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        with open(cache_path, "w") as f:
            json.dump(cache_data, f)


class GitHubAPIClient:
    """Handles GitHub API requests with rate limiting, retries, and caching."""
    
    def __init__(self, username: str, token: Optional[str] = None):
        self.username = username
        self.token = token
        self.session = requests.Session()
        self.headers = {"Authorization": f"token {token}"} if token else {}
        self.cache = CacheManager()
        self.rate_limit_remaining = None
        self.rate_limit_reset = None
    
    def _extract_rate_limit_info(self, response: requests.Response) -> None:
        """Extract and store rate limit information from response headers."""
        self.rate_limit_remaining = int(response.headers.get("X-RateLimit-Remaining", -1))
        self.rate_limit_reset = int(response.headers.get("X-RateLimit-Reset", 0))
    
    def _wait_for_rate_limit(self) -> None:
        """Wait if approaching rate limit."""
        if self.rate_limit_remaining is not None and self.rate_limit_remaining < 10:
            if self.rate_limit_reset:
                wait_time = self.rate_limit_reset - time.time()
                if wait_time > 0:
                    print(f"⚠️  Rate limit approaching. Waiting {wait_time:.0f} seconds...")
                    time.sleep(wait_time + 1)
    
    def _exponential_backoff_request(self, url: str, max_retries: int = 3) -> Optional[requests.Response]:
        """Make request with exponential backoff retry logic."""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, headers=self.headers, timeout=REQUEST_TIMEOUT)
                self._extract_rate_limit_info(response)
                
                if response.status_code == 429:  # Rate limited
                    retry_after = int(response.headers.get("Retry-After", 2 ** attempt))
                    print(f"⏱️  Rate limited. Retrying in {retry_after} seconds (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(retry_after)
                    continue
                
                if response.status_code == 200:
                    return response
                
                if response.status_code >= 500:  # Server error, retry
                    wait_time = 2 ** attempt
                    print(f"⚠️  Server error {response.status_code}. Retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                
                # Client error, don't retry
                print(f"❌ HTTP {response.status_code}: {response.reason}")
                return None
            
            except requests.exceptions.Timeout:
                wait_time = 2 ** attempt
                print(f"⏱️  Request timeout. Retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
            except requests.exceptions.RequestException as e:
                print(f"❌ Request error: {e}")
                return None
        
        print(f"❌ Failed after {max_retries} attempts")
        return None
    
    def fetch_repos(self) -> List[Dict]:
        """Fetch all repositories for the user with caching."""
        cache_key = f"repos_{self.username}"
        cached_repos = self.cache.get(cache_key)
        
        if cached_repos:
            print(f"✅ Loaded {len(cached_repos)} repos from cache")
            return cached_repos
        
        repos = []
        page = 1
        print(f"📦 Fetching repositories for {self.username}...")
        
        while len(repos) < MAX_REPOS_LIMIT:
            self._wait_for_rate_limit()
            
            url = f"https://api.github.com/users/{self.username}/repos?page={page}&per_page=100"
            response = self._exponential_backoff_request(url)
            
            if not response:
                print("❌ Failed to fetch repos, using empty list")
                break
            
            data = response.json()
            if not data:
                break
            
            repos.extend(data)
            print(f"  Fetched page {page} ({len(data)} repos)")
            page += 1
        
        if repos:
            self.cache.set(cache_key, repos)
            print(f"✅ Cached {len(repos)} repos")
        
        return repos[:MAX_REPOS_LIMIT]
    
    def fetch_languages(self, repo_full_name: str) -> Dict:
        """Fetch languages for a repository with caching."""
        cache_key = f"lang_{repo_full_name.replace('/', '_')}"
        cached_langs = self.cache.get(cache_key)
        
        if cached_langs:
            return cached_langs
        
        self._wait_for_rate_limit()
        
        url = f"https://api.github.com/repos/{repo_full_name}/languages"
        response = self._exponential_backoff_request(url)
        
        if not response:
            return {}
        
        langs = response.json()
        
        if langs:
            self.cache.set(cache_key, langs)
        
        return langs


def main():
    """Main function to update tech stack."""
    print("\n" + "="*60)
    print("🚀 Tech Stack Updater")
    print("="*60 + "\n")
    
    # Initialize API client
    api_client = GitHubAPIClient(GITHUB_USERNAME, GITHUB_TOKEN)
    
    # Fetch repos
    repos = api_client.fetch_repos()
    
    if not repos:
        print("❌ No repositories found")
        return
    
    print(f"\n📊 Processing {len(repos)} repositories...\n")
    
    language_stats = {}
    processed = 0
    skipped = 0
    
    for idx, repo in enumerate(repos, 1):
        # Skip forks
        if repo["fork"]:
            skipped += 1
            continue
        
        # Fetch languages
        langs = api_client.fetch_languages(repo["full_name"])
        
        for lang, bytes_count in langs.items():
            if lang in EXCLUDE_LANGUAGES:
                continue
            
            if lang not in language_stats:
                language_stats[lang] = {"bytes": 0, "repos": 0}
            
            language_stats[lang]["bytes"] += bytes_count
            language_stats[lang]["repos"] += 1
        
        processed += 1
        if idx % 10 == 0:
            print(f"  Progress: {idx}/{len(repos)} repos processed")
    
    print(f"\n✅ Processed {processed} repos (skipped {skipped} forks)")
    
    # Sort by bytes
    sorted_langs = sorted(language_stats.items(), key=lambda x: x[1]["bytes"], reverse=True)
    top_langs = sorted_langs[:MAX_LANGUAGES]
    
    print(f"\n🏆 Top {len(top_langs)} languages:")
    for lang, stats in top_langs:
        print(f"  • {lang}: {stats['bytes']:,} bytes across {stats['repos']} repos")
    
    # Generate badges
    badges = []
    for lang, stats in top_langs:
        config = BADGE_CONFIG.get(lang, {"color": "grey", "logo": lang.lower()})
        color = config["color"]
        logo = config["logo"]
        logo_color = config.get("logoColor", "white")
        badge_url = f"https://img.shields.io/badge/{lang.replace(' ', '%20')}-{color}?style=for-the-badge&logo={logo}&logoColor={logo_color}"
        badges.append(f'  <img src="{badge_url}" />')
    
    techstack_content = "\n".join(badges)
    
    # Update README
    print("\n📝 Updating README.md...")
    
    try:
        with open("README.md", "r") as f:
            readme = f.read()
        
        start_marker = "<!-- TECHSTACK:START -->"
        end_marker = "<!-- TECHSTACK:END -->"
        
        # Use simple string operations instead of regex for better performance
        start_idx = readme.find(start_marker)
        end_idx = readme.find(end_marker)
        
        if start_idx != -1 and end_idx != -1:
            new_readme = (
                readme[:start_idx + len(start_marker)] +
                f"\n<div align=\"center\">\n{techstack_content}\n</div>\n" +
                readme[end_idx:]
            )
        else:
            print("⚠️  Markers not found, using regex fallback")
            pattern = f"{re.escape(start_marker)}.*?{re.escape(end_marker)}"
            new_readme = re.sub(
                pattern,
                f"{start_marker}\n<div align=\"center\">\n{techstack_content}\n</div>\n{end_marker}",
                readme,
                flags=re.DOTALL
            )
        
        # Ensure top-langs uses a clean URL with exactly one hide parameter
        if "api/top-langs/?username=dgithinjibit" in new_readme:
            # Replace any variant of top-langs URL with the clean version
            import re
            new_readme = re.sub(
                r'https://github-readme-stats-eight-theta\.vercel\.app/api/top-langs/\?[^\s"]+',
                'https://github-readme-stats-eight-theta.vercel.app/api/top-langs/?username=dgithinjibit&hide=Jupyter%20Notebook&layout=compact&theme=tokyonight&hide_border=true&border_radius=10&title_color=8E4585&icon_color=8E4585',
                new_readme
            )
        
        with open("README.md", "w") as f:
            f.write(new_readme)
        
        print("✅ README.md updated successfully!")
        
        if api_client.rate_limit_remaining is not None:
            print(f"\n📊 GitHub API Rate Limit: {api_client.rate_limit_remaining} requests remaining")
    
    except IOError as e:
        print(f"❌ Error updating README.md: {e}")
    
    print("\n" + "="*60)
    print("✨ Update complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
