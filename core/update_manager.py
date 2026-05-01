import json
import logging
import urllib.request
from packaging import version
from .version import VERSION, REPO_OWNER, REPO_NAME

def check_for_updates():
    """
    Checks the GitHub API for the latest release.
    Returns (has_update, latest_version, download_url) or (False, None, None) on error.
    """
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Sales-Assistant-App')
        
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode())
                latest_tag = data.get("tag_name", "").strip("v")
                
                if version.parse(latest_tag) > version.parse(VERSION):
                    # Find the asset that matches Windows (usually .zip or .exe)
                    assets = data.get("assets", [])
                    download_url = data.get("html_url") # Fallback to the release page
                    
                    for asset in assets:
                        if "Windows" in asset.get("name", "") or asset.get("name", "").endswith(".zip"):
                            download_url = asset.get("browser_download_url")
                            break
                            
                    return True, latest_tag, download_url
                    
    except Exception as e:
        logging.error(f"Update check failed: {e}")
        
    return False, None, None
