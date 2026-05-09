import os
import requests
import re

# Configuration
GITHUB_USERNAME = "dgithinjibit"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
EXCLUDE_LANGUAGES = ["Jupyter Notebook"]
MAX_LANGUAGES = 12

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

def fetch_repos(username, token):
    repos = []
    page = 1
    headers = {"Authorization": f"token {token}"} if token else {}
    while True:
        url = f"https://api.github.com/users/{username}/repos?page={page}&per_page=100"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            break
        data = response.json()
        if not data:
            break
        repos.extend(data)
        page += 1
    return repos

def fetch_languages(repo_full_name, token):
    headers = {"Authorization": f"token {token}"} if token else {}
    url = f"https://api.github.com/repos/{repo_full_name}/languages"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return {}
    return response.json()

def main():
    print(f"Fetching data for {GITHUB_USERNAME}...")
    repos = fetch_repos(GITHUB_USERNAME, GITHUB_TOKEN)
    
    language_stats = {}
    
    for repo in repos:
        if repo["fork"]:
            continue
        langs = fetch_languages(repo["full_name"], GITHUB_TOKEN)
        for lang, bytes_count in langs.items():
            if lang in EXCLUDE_LANGUAGES:
                continue
            if lang not in language_stats:
                language_stats[lang] = {"bytes": 0, "repos": 0}
            language_stats[lang]["bytes"] += bytes_count
            language_stats[lang]["repos"] += 1
            
    # Sort by bytes
    sorted_langs = sorted(language_stats.items(), key=lambda x: x[1]["bytes"], reverse=True)
    top_langs = sorted_langs[:MAX_LANGUAGES]
    
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
    with open("README.md", "r") as f:
        readme = f.read()
        
    start_marker = "<!-- TECHSTACK:START -->"
    end_marker = "<!-- TECHSTACK:END -->"
    
    pattern = f"{start_marker}.*?{end_marker}"
    replacement = f"{start_marker}\n<div align=\"center\">\n{techstack_content}\n</div>\n{end_marker}"
    
    new_readme = re.sub(pattern, replacement, readme, flags=re.DOTALL)
    
    # Update top-langs card URL to exclude Jupyter Notebook
    new_readme = new_readme.replace(
        "api/top-langs/?username=dgithinjibit",
        "api/top-langs/?username=dgithinjibit&hide=Jupyter%20Notebook"
    )
    
    with open("README.md", "w") as f:
        f.write(new_readme)
        
    print("README.md updated successfully!")

if __name__ == "__main__":
    main()
