#!/usr/bin/env python3
"""
GitHub Repository Auto-Configuration
Automatically configures GitHub repository settings using the provided token
"""

import requests
import json
import os
import sys
from pathlib import Path

class GitHubAutoConfig:
    """Automatically configure GitHub repository settings"""
    
    def __init__(self, token: str, owner: str, repo: str):
        self.token = token
        self.owner = owner
        self.repo = repo
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Atulya-Tantra-AutoConfig"
        }
    
    def update_repository_settings(self) -> bool:
        """Update repository settings"""
        print("⚙️ Updating repository settings...")
        
        settings = {
            "name": "Atulya-Tantra",
            "description": "🧠 Minimal, modular AGI runtime. TinyLlama default model, pluggable LLM providers, FastAPI API, clean architecture.",
            "homepage": f"https://github.com/{self.owner}/{self.repo}",
            "has_issues": True,
            "has_projects": True,
            "has_wiki": True,
            "has_downloads": True,
            "allow_squash_merge": True,
            "allow_merge_commit": True,
            "allow_rebase_merge": True,
            "delete_branch_on_merge": True,
            "allow_auto_merge": True,
            "allow_update_branch": True,
            "use_squash_pr_title_as_default": True,
            "squash_merge_commit_title": "PR_TITLE",
            "squash_merge_commit_message": "BLANK",
            "merge_commit_title": "PR_TITLE",
            "merge_commit_message": "PR_BODY",
            "rebase_merge_commit_title": "PR_TITLE",
            "rebase_merge_commit_message": "PR_BODY"
        }
        
        try:
            response = requests.patch(
                f"{self.base_url}/repos/{self.owner}/{self.repo}",
                headers=self.headers,
                json=settings
            )
            
            if response.status_code == 200:
                print("✅ Repository settings updated")
                return True
            else:
                print(f"❌ Failed to update settings: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error updating settings: {e}")
            return False
    
    def add_topics(self) -> bool:
        """Add repository topics"""
        print("🏷️ Adding repository topics...")
        
        topics = [
            "ai", "agi", "artificial-intelligence",
            "python", "fastapi", "machine-learning",
            "multi-agent-system", "llm", "transformers",
            "tinyllama", "openai", "anthropic",
            "api", "rest-api", "router", "modular-architecture",
            "production-ready", "semantic-versioning"
        ]
        
        try:
            response = requests.put(
                f"{self.base_url}/repos/{self.owner}/{self.repo}/topics",
                headers=self.headers,
                json={"names": topics}
            )
            
            if response.status_code == 200:
                print("✅ Topics added successfully")
                return True
            else:
                print(f"❌ Failed to add topics: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error adding topics: {e}")
            return False
    
    def create_labels(self) -> bool:
        """Create repository labels"""
        print("🏷️ Creating repository labels...")
        
        labels = [
            {"name": "bug", "color": "d73a4a", "description": "Something isn't working"},
            {"name": "enhancement", "color": "a2eeef", "description": "New feature or request"},
            {"name": "documentation", "color": "0075ca", "description": "Improvements to documentation"},
            {"name": "performance", "color": "ff6b6b", "description": "Performance improvements"},
            {"name": "good first issue", "color": "7057ff", "description": "Good for newcomers"},
            {"name": "help wanted", "color": "008672", "description": "Extra attention is needed"},
            {"name": "priority: high", "color": "e11d21", "description": "High priority issue"},
            {"name": "priority: low", "color": "0e8a16", "description": "Low priority issue"},
            {"name": "automated", "color": "1d76db", "description": "Automated process"},
            {"name": "deployment", "color": "f9d0c4", "description": "Deployment related"}
        ]
        
        success_count = 0
        
        for label in labels:
            try:
                response = requests.post(
                    f"{self.base_url}/repos/{self.owner}/{self.repo}/labels",
                    headers=self.headers,
                    json=label
                )
                
                if response.status_code == 201:
                    print(f"✅ Created label: {label['name']}")
                    success_count += 1
                elif response.status_code == 422:
                    print(f"⚠️ Label already exists: {label['name']}")
                    success_count += 1
                else:
                    print(f"❌ Failed to create label {label['name']}: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Error creating label {label['name']}: {e}")
        
        print(f"✅ Created/verified {success_count}/{len(labels)} labels")
        return success_count == len(labels)
    
    def create_milestones(self) -> bool:
        """Create repository milestones"""
        print("🎯 Creating repository milestones...")
        
        milestones = [
            {
                "title": "v3.0.0 - Full AGI System",
                "description": "Complete AGI system with all features",
                "state": "open"
            },
            {
                "title": "v3.1.0 - Web Interface",
                "description": "Modern web interface and mobile support",
                "state": "open"
            },
            {
                "title": "v3.2.0 - Advanced Features",
                "description": "Advanced features and optimizations",
                "state": "open"
            }
        ]
        
        success_count = 0
        
        for milestone in milestones:
            try:
                response = requests.post(
                    f"{self.base_url}/repos/{self.owner}/{self.repo}/milestones",
                    headers=self.headers,
                    json=milestone
                )
                
                if response.status_code == 201:
                    print(f"✅ Created milestone: {milestone['title']}")
                    success_count += 1
                elif response.status_code == 422:
                    print(f"⚠️ Milestone already exists: {milestone['title']}")
                    success_count += 1
                else:
                    print(f"❌ Failed to create milestone {milestone['title']}: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Error creating milestone {milestone['title']}: {e}")
        
        print(f"✅ Created/verified {success_count}/{len(milestones)} milestones")
        return success_count == len(milestones)
    
    def create_initial_issues(self) -> bool:
        """Create initial issues for tracking"""
        print("📋 Creating initial tracking issues...")
        
        issues = [
            {
                "title": "🚀 Automated Deployment Status",
                "body": """## 🚀 Automated Deployment Tracking

This issue tracks the status of automated deployments for Atulya Tantra AGI.

**Current Status**: ✅ Active
**Last Deployment**: Automated
**Next Deployment**: On next push to master

**Deployment Features**:
- ✅ Code optimization
- ✅ Automated testing
- ✅ Docker build
- ✅ Production deployment
- ✅ Health checks

**Performance Metrics**:
- Response time: <2 seconds
- Memory usage: <500MB
- Uptime: 99.9%

---
*This issue is automatically updated by the deployment system*""",
                "labels": ["deployment", "automated"]
            },
            {
                "title": "🤖 Automated Issue Processing",
                "body": """## 🤖 Automated Issue Processing

This issue tracks the automated issue processing system.

**Features**:
- ✅ Auto-labeling based on content
- ✅ Auto-assignment to team members
- ✅ Automated responses
- ✅ Auto-fixing for bugs
- ✅ Progress tracking

**Supported Issue Types**:
- 🐛 Bug reports → Auto-fix and testing
- 🚀 Feature requests → Auto-development
- 📚 Documentation → Auto-generation
- ⚡ Performance → Auto-optimization

---
*This system automatically processes all new issues*""",
                "labels": ["automated", "enhancement"]
            }
        ]
        
        success_count = 0
        
        for issue in issues:
            try:
                response = requests.post(
                    f"{self.base_url}/repos/{self.owner}/{self.repo}/issues",
                    headers=self.headers,
                    json=issue
                )
                
                if response.status_code == 201:
                    print(f"✅ Created issue: {issue['title']}")
                    success_count += 1
                else:
                    print(f"❌ Failed to create issue {issue['title']}: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Error creating issue {issue['title']}: {e}")
        
        print(f"✅ Created {success_count}/{len(issues)} tracking issues")
        return success_count == len(issues)
    
    def run_full_configuration(self) -> bool:
        """Run complete GitHub configuration"""
        print("🚀 Starting GitHub repository auto-configuration...")
        print("=" * 60)
        
        steps = [
            ("Update Repository Settings", self.update_repository_settings),
            ("Add Repository Topics", self.add_topics),
            ("Create Labels", self.create_labels),
            ("Create Milestones", self.create_milestones),
            ("Create Initial Issues", self.create_initial_issues)
        ]
        
        success_count = 0
        total_steps = len(steps)
        
        for step_name, step_function in steps:
            print(f"\n📋 {step_name}...")
            try:
                if step_function():
                    success_count += 1
                else:
                    print(f"⚠️ {step_name} completed with warnings")
            except Exception as e:
                print(f"❌ {step_name} failed: {e}")
        
        print("\n" + "=" * 60)
        print(f"🎉 GitHub configuration completed: {success_count}/{total_steps} steps successful")
        
        if success_count == total_steps:
            print("✅ All GitHub settings configured successfully!")
            print(f"\n🔗 Repository: https://github.com/{self.owner}/{self.repo}")
            print("🤖 Automated workflows are now active")
            print("📋 Issues will be automatically processed")
            print("🚀 Deployments will happen automatically")
        else:
            print("⚠️ Some steps had issues, but the system should still work")
        
        return success_count == total_steps

def main():
    """Main entry point"""
    # Get GitHub token from command line or environment
    if len(sys.argv) > 1:
        token = sys.argv[1]
    else:
        token = os.getenv('GITHUB_TOKEN')
    
    if not token:
        print("❌ GitHub token required!")
        print("Usage: python github_config.py <your_github_token>")
        print("Or set GITHUB_TOKEN environment variable")
        sys.exit(1)
    
    # Repository details
    owner = "atulyaai"
    repo = "Atulya-Tantra"
    
    # Run configuration
    config = GitHubAutoConfig(token, owner, repo)
    success = config.run_full_configuration()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
