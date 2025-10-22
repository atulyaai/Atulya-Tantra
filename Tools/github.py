"""
GitHub utilities for Atulya Tantra AGI
GitHub API integration and file fetching
"""

import requests
from typing import Dict, Any, Optional


def fetch_github_file(repo: str, file_path: str, branch: str = "main") -> Dict[str, Any]:
    """Fetch a file from GitHub repository"""
    try:
        # GitHub API URL for raw file content
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/{file_path}"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            return {
                "success": True,
                "content": response.text,
                "url": url,
                "size": len(response.text)
            }
        elif response.status_code == 404:
            return {"error": f"File not found: {file_path}"}
        else:
            return {"error": f"GitHub API error: {response.status_code}"}
            
    except Exception as e:
        return {"error": f"Error fetching file: {str(e)}"}


def get_github_repo_info(repo: str) -> Dict[str, Any]:
    """Get information about a GitHub repository"""
    try:
        url = f"https://api.github.com/repos/{repo}"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "name": data.get("name"),
                "full_name": data.get("full_name"),
                "description": data.get("description"),
                "language": data.get("language"),
                "stars": data.get("stargazers_count"),
                "forks": data.get("forks_count"),
                "url": data.get("html_url"),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at")
            }
        elif response.status_code == 404:
            return {"error": f"Repository not found: {repo}"}
        else:
            return {"error": f"GitHub API error: {response.status_code}"}
            
    except Exception as e:
        return {"error": f"Error fetching repo info: {str(e)}"}


def search_github_repos(query: str, limit: int = 10) -> Dict[str, Any]:
    """Search GitHub repositories"""
    try:
        url = "https://api.github.com/search/repositories"
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": limit
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            repos = []
            
            for item in data.get("items", []):
                repos.append({
                    "name": item.get("name"),
                    "full_name": item.get("full_name"),
                    "description": item.get("description"),
                    "language": item.get("language"),
                    "stars": item.get("stargazers_count"),
                    "forks": item.get("forks_count"),
                    "url": item.get("html_url")
                })
            
            return {
                "success": True,
                "repos": repos,
                "total_count": data.get("total_count", 0)
            }
        else:
            return {"error": f"GitHub API error: {response.status_code}"}
            
    except Exception as e:
        return {"error": f"Error searching repos: {str(e)}"}


def get_github_file_tree(repo: str, path: str = "", branch: str = "main") -> Dict[str, Any]:
    """Get file tree from GitHub repository"""
    try:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        params = {"ref": branch}
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            files = []
            for item in data:
                files.append({
                    "name": item.get("name"),
                    "path": item.get("path"),
                    "type": item.get("type"),
                    "size": item.get("size"),
                    "download_url": item.get("download_url")
                })
            
            return {
                "success": True,
                "files": files,
                "count": len(files)
            }
        elif response.status_code == 404:
            return {"error": f"Path not found: {path}"}
        else:
            return {"error": f"GitHub API error: {response.status_code}"}
            
    except Exception as e:
        return {"error": f"Error fetching file tree: {str(e)}"}


# Export public API
__all__ = [
    "fetch_github_file",
    "get_github_repo_info",
    "search_github_repos",
    "get_github_file_tree"
]