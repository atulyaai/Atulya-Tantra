"""
Application Action Handler
Handles application-specific actions and integrations
"""

import os
import subprocess
import webbrowser
from typing import Dict, Any, List
from datetime import datetime
from ..assistant_core import ActionRequest, ConversationContext

class ApplicationActionHandler:
    """
    Handles application-specific actions and integrations
    """
    
    def __init__(self):
        self.supported_actions = {
            'open_application': self._handle_open_application,
            'close_application': self._handle_close_application,
            'launch_website': self._handle_launch_website,
            'play_media': self._handle_play_media,
            'search_media': self._handle_search_media
        }
        
        # Application mappings
        self.application_mappings = {
            'chrome': self._open_chrome,
            'firefox': self._open_firefox,
            'edge': self._open_edge,
            'notepad': self._open_notepad,
            'calculator': self._open_calculator,
            'explorer': self._open_explorer,
            'word': self._open_word,
            'excel': self._open_excel,
            'powerpoint': self._open_powerpoint,
            'youtube': self._open_youtube,
            'spotify': self._open_spotify,
            'vscode': self._open_vscode,
            'sublime': self._open_sublime,
            'photoshop': self._open_photoshop,
            'illustrator': self._open_illustrator
        }
        
        # Website mappings
        self.website_mappings = {
            'youtube': 'https://www.youtube.com',
            'google': 'https://www.google.com',
            'facebook': 'https://www.facebook.com',
            'twitter': 'https://www.twitter.com',
            'linkedin': 'https://www.linkedin.com',
            'github': 'https://www.github.com',
            'stackoverflow': 'https://www.stackoverflow.com',
            'wikipedia': 'https://www.wikipedia.org',
            'amazon': 'https://www.amazon.com',
            'netflix': 'https://www.netflix.com',
            'gmail': 'https://www.gmail.com',
            'outlook': 'https://www.outlook.com'
        }
    
    def execute(self, action_request: ActionRequest, context: ConversationContext) -> Dict[str, Any]:
        """
        Execute application action
        """
        action_type = action_request.command
        parameters = action_request.parameters
        
        if action_type in self.supported_actions:
            try:
                result = self.supported_actions[action_type](parameters)
                return {
                    "success": True,
                    "action": action_type,
                    "result": result,
                    "message": f"Successfully executed {action_type}"
                }
            except Exception as e:
                return {
                    "success": False,
                    "action": action_type,
                    "error": str(e),
                    "message": f"Failed to execute {action_type}: {str(e)}"
                }
        else:
            return {
                "success": False,
                "action": action_type,
                "error": f"Unsupported action: {action_type}",
                "message": f"Action {action_type} is not supported"
            }
    
    def _handle_open_application(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle opening applications
        """
        application = parameters.get('application', '').lower()
        arguments = parameters.get('arguments', [])
        
        if not application:
            raise ValueError("Application name is required")
        
        if application in self.application_mappings:
            result = self.application_mappings[application](arguments)
            return {
                "action": "open_application",
                "application": application,
                "status": "Application opened",
                "result": result
            }
        else:
            raise ValueError(f"Unsupported application: {application}")
    
    def _handle_close_application(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle closing applications
        """
        application = parameters.get('application', '').lower()
        
        if not application:
            raise ValueError("Application name is required")
        
        try:
            # This is a simplified version - in production, you'd use proper process management
            if application == 'chrome':
                os.system('taskkill /f /im chrome.exe')
            elif application == 'firefox':
                os.system('taskkill /f /im firefox.exe')
            elif application == 'notepad':
                os.system('taskkill /f /im notepad.exe')
            else:
                return {
                    "action": "close_application",
                    "application": application,
                    "status": "Close command sent (simulation mode)",
                    "result": f"Close command for {application} sent"
                }
            
            return {
                "action": "close_application",
                "application": application,
                "status": "Application closed",
                "result": f"{application} closed successfully"
            }
        except Exception as e:
            raise Exception(f"Failed to close {application}: {str(e)}")
    
    def _handle_launch_website(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle launching websites
        """
        website = parameters.get('website', '').lower()
        url = parameters.get('url', '')
        
        if url:
            webbrowser.open(url)
            return {
                "action": "launch_website",
                "url": url,
                "status": "Website opened"
            }
        elif website in self.website_mappings:
            url = self.website_mappings[website]
            webbrowser.open(url)
            return {
                "action": "launch_website",
                "website": website,
                "url": url,
                "status": "Website opened"
            }
        else:
            raise ValueError(f"Unsupported website: {website}")
    
    def _handle_play_media(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle media playback
        """
        media_type = parameters.get('type', '')
        query = parameters.get('query', '')
        platform = parameters.get('platform', 'youtube')
        
        if not query:
            raise ValueError("Media query is required")
        
        if media_type == 'music' or platform == 'spotify':
            # Open Spotify with search
            spotify_url = f"https://open.spotify.com/search/{query}"
            webbrowser.open(spotify_url)
            return {
                "action": "play_media",
                "type": "music",
                "platform": "spotify",
                "query": query,
                "status": "Music search opened in Spotify"
            }
        elif media_type == 'video' or platform == 'youtube':
            # Open YouTube with search
            youtube_url = f"https://www.youtube.com/results?search_query={query}"
            webbrowser.open(youtube_url)
            return {
                "action": "play_media",
                "type": "video",
                "platform": "youtube",
                "query": query,
                "status": "Video search opened in YouTube"
            }
        else:
            # Default to YouTube
            youtube_url = f"https://www.youtube.com/results?search_query={query}"
            webbrowser.open(youtube_url)
            return {
                "action": "play_media",
                "type": "video",
                "platform": "youtube",
                "query": query,
                "status": "Media search opened in YouTube"
            }
    
    def _handle_search_media(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle media search
        """
        query = parameters.get('query', '')
        media_type = parameters.get('type', 'all')
        
        if not query:
            raise ValueError("Search query is required")
        
        results = []
        
        if media_type in ['all', 'music']:
            # Search Spotify
            spotify_url = f"https://open.spotify.com/search/{query}"
            results.append({
                "platform": "spotify",
                "type": "music",
                "url": spotify_url
            })
        
        if media_type in ['all', 'video']:
            # Search YouTube
            youtube_url = f"https://www.youtube.com/results?search_query={query}"
            results.append({
                "platform": "youtube",
                "type": "video",
                "url": youtube_url
            })
        
        return {
            "action": "search_media",
            "query": query,
            "type": media_type,
            "results": results,
            "status": "Media search completed"
        }
    
    # Application opening methods
    def _open_chrome(self, arguments: List[str] = None) -> str:
        """Open Chrome browser"""
        try:
            if arguments:
                subprocess.Popen(['chrome'] + arguments)
            else:
                os.startfile('chrome')
            return "Chrome browser opened"
        except:
            try:
                subprocess.Popen(['chrome'])
                return "Chrome browser opened via subprocess"
            except:
                webbrowser.open('https://www.google.com')
                return "Default browser opened with Google"
    
    def _open_firefox(self, arguments: List[str] = None) -> str:
        """Open Firefox browser"""
        try:
            if arguments:
                subprocess.Popen(['firefox'] + arguments)
            else:
                os.startfile('firefox')
            return "Firefox browser opened"
        except:
            webbrowser.open('https://www.google.com')
            return "Default browser opened with Google"
    
    def _open_edge(self, arguments: List[str] = None) -> str:
        """Open Microsoft Edge browser"""
        try:
            if arguments:
                subprocess.Popen(['msedge'] + arguments)
            else:
                os.startfile('msedge')
            return "Microsoft Edge browser opened"
        except:
            webbrowser.open('https://www.google.com')
            return "Default browser opened with Google"
    
    def _open_notepad(self, arguments: List[str] = None) -> str:
        """Open Notepad"""
        try:
            subprocess.Popen('notepad.exe')
            return "Notepad opened"
        except Exception as e:
            raise Exception(f"Failed to open Notepad: {str(e)}")
    
    def _open_calculator(self, arguments: List[str] = None) -> str:
        """Open Calculator"""
        try:
            subprocess.Popen('calc.exe')
            return "Calculator opened"
        except Exception as e:
            raise Exception(f"Failed to open Calculator: {str(e)}")
    
    def _open_explorer(self, arguments: List[str] = None) -> str:
        """Open File Explorer"""
        try:
            subprocess.Popen('explorer.exe')
            return "File Explorer opened"
        except Exception as e:
            raise Exception(f"Failed to open File Explorer: {str(e)}")
    
    def _open_word(self, arguments: List[str] = None) -> str:
        """Open Microsoft Word"""
        try:
            os.startfile('winword')
            return "Microsoft Word opened"
        except:
            return "Microsoft Word not found or failed to open"
    
    def _open_excel(self, arguments: List[str] = None) -> str:
        """Open Microsoft Excel"""
        try:
            os.startfile('excel')
            return "Microsoft Excel opened"
        except:
            return "Microsoft Excel not found or failed to open"
    
    def _open_powerpoint(self, arguments: List[str] = None) -> str:
        """Open Microsoft PowerPoint"""
        try:
            os.startfile('powerpnt')
            return "Microsoft PowerPoint opened"
        except:
            return "Microsoft PowerPoint not found or failed to open"
    
    def _open_youtube(self, arguments: List[str] = None) -> str:
        """Open YouTube"""
        webbrowser.open('https://www.youtube.com')
        return "YouTube opened in browser"
    
    def _open_spotify(self, arguments: List[str] = None) -> str:
        """Open Spotify"""
        try:
            os.startfile('spotify')
            return "Spotify app opened"
        except:
            webbrowser.open('https://open.spotify.com')
            return "Spotify web opened in browser"
    
    def _open_vscode(self, arguments: List[str] = None) -> str:
        """Open Visual Studio Code"""
        try:
            if arguments:
                subprocess.Popen(['code'] + arguments)
            else:
                subprocess.Popen(['code'])
            return "Visual Studio Code opened"
        except:
            return "Visual Studio Code not found or failed to open"
    
    def _open_sublime(self, arguments: List[str] = None) -> str:
        """Open Sublime Text"""
        try:
            if arguments:
                subprocess.Popen(['subl'] + arguments)
            else:
                subprocess.Popen(['subl'])
            return "Sublime Text opened"
        except:
            return "Sublime Text not found or failed to open"
    
    def _open_photoshop(self, arguments: List[str] = None) -> str:
        """Open Adobe Photoshop"""
        try:
            os.startfile('photoshop')
            return "Adobe Photoshop opened"
        except:
            return "Adobe Photoshop not found or failed to open"
    
    def _open_illustrator(self, arguments: List[str] = None) -> str:
        """Open Adobe Illustrator"""
        try:
            os.startfile('illustrator')
            return "Adobe Illustrator opened"
        except:
            return "Adobe Illustrator not found or failed to open"
