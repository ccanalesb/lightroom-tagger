import subprocess
import json
import os
import tempfile
import shutil
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class BrowserPost:
    post_url: str
    image_url: str
    index: int


class BrowserAgent:
    """Wrapper for agent-browser CLI to scrape Instagram."""

    def __init__(self, output_dir: str = "/tmp/instagram_images", session_name: str = "instagram", headed: bool = False):
        self.output_dir = output_dir
        self.session_name = session_name
        self.headed = headed
        self._ensure_output_dir()

    def _ensure_output_dir(self):
        """Create output directory if it doesn't exist."""
        os.makedirs(self.output_dir, exist_ok=True)

    def _run_command(self, args: list[str]) -> tuple[int, str, str]:
        """Run agent-browser command and return (returncode, stdout, stderr)."""
        cmd = ["agent-browser", "--session-name", self.session_name]
        if self.headed:
            cmd.append("--headed")
        cmd.extend(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )
        return result.returncode, result.stdout, result.stderr

    def open_url(self, url: str) -> bool:
        """Open a URL in the browser."""
        returncode, stdout, stderr = self._run_command(["open", url])
        return returncode == 0

    def snapshot(self) -> str:
        """Get current page snapshot."""
        returncode, stdout, stderr = self._run_command(["snapshot", "-i"])
        if returncode == 0:
            return stdout
        raise RuntimeError(f"snapshot failed: {stderr}")

    def click(self, ref: str) -> bool:
        """Click element by reference."""
        returncode, stdout, stderr = self._run_command(["click", ref])
        return returncode == 0

    def scroll(self, direction: str = "down") -> bool:
        """Scroll the page."""
        returncode, stdout, stderr = self._run_command(["scroll", direction])
        return returncode == 0

    def close(self) -> bool:
        """Close the browser."""
        returncode, stdout, stderr = self._run_command(["close"])
        return returncode == 0

    def wait(self, seconds: int = 2) -> bool:
        """Wait for specified seconds."""
        returncode, stdout, stderr = self._run_command(["wait", str(seconds)])
        return returncode == 0

    def login(self, url: str = "https://www.instagram.com") -> bool:
        """Open Instagram and wait for manual login.
        
        Returns True when browser is opened. User must log in manually.
        Session is persisted automatically by agent-browser.
        """
        return self.open_url(url)

    def is_logged_in(self) -> bool:
        """Check if session appears to be logged in.
        
        Takes snapshot and checks for presence of profile elements.
        """
        try:
            snapshot = self.snapshot()
            logged_in_indicators = ["profile", "settings", "logout"]
            return any(indicator in snapshot.lower() for indicator in logged_in_indicators)
        except Exception:
            return False

    def navigate_to_profile(self, username: str) -> bool:
        """Navigate to a user's profile page."""
        url = f"https://www.instagram.com/{username}/"
        return self.open_url(url)

    def scroll_feed(self, times: int = 3) -> bool:
        """Scroll the feed multiple times."""
        for _ in range(times):
            if not self.scroll("down"):
                return False
            self.wait(1)
        return True

    def extract_posts(self, limit: int = 20) -> list[BrowserPost]:
        """Extract post URLs from current page using JavaScript."""
        js = f"""
        (function() {{
            const links = Array.from(document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]'));
            const seen = new Set();
            const posts = [];
            for (const a of links) {{
                const url = a.href.split('?')[0];
                if (!seen.has(url) && posts.length < {limit}) {{
                    seen.add(url);
                    posts.push(url);
                }}
            }}
            return posts;
        }})()
        """
        returncode, stdout, stderr = self._run_command(["eval", js])
        if returncode != 0:
            return []
        
        import json
        try:
            urls = json.loads(stdout.strip())
            return [
                BrowserPost(post_url=url, image_url="", index=i)
                for i, url in enumerate(urls)
            ]
        except:
            return []

    def get_post_image_url(self) -> Optional[str]:
        """Get the main image URL from current post page."""
        js = """
        (function() {
            const img = document.querySelector('article img') || 
                        document.querySelector('article picture img') ||
                        document.querySelector('div[role="dialog"] img');
            return img ? img.src : null;
        })()
        """
        returncode, stdout, stderr = self._run_command(["eval", js])
        if returncode == 0 and stdout.strip() != "null":
            return stdout.strip()
        return None

    def download_image(self, url: str, filename: str) -> Optional[str]:
        """Download an image from URL to output directory.
        
        Returns local file path or None if failed.
        """
        import urllib.request
        
        local_path = os.path.join(self.output_dir, filename)
        try:
            urllib.request.urlretrieve(url, local_path)
            return local_path
        except Exception as e:
            print(f"Failed to download {url}: {e}")
            return None

    def fetch_posts(self, username: str, limit: int = 20) -> tuple[list[BrowserPost], dict[str, str]]:
        """Fetch posts from a user's profile using a single combined command."""
        import urllib.request
        
        # Use a single command to get posts
        js = f"""(function() {{const links = Array.from(document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]'));const seen = new Set();const posts = [];for (const a of links) {{const url = a.href.split('?')[0];if (!seen.has(url) && posts.length < {limit}) {{seen.add(url);posts.push(url);}}}}return posts;}})()"""
        
        # Single combined command: navigate, wait, scroll, get posts
        cmd = ["agent-browser", "--session-name", self.session_name, "open", f"https://www.instagram.com/{username}/"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        # Wait and scroll
        cmd = ["agent-browser", "--session-name", self.session_name, "wait", "3"]
        subprocess.run(cmd, capture_output=True, timeout=30)
        
        cmd = ["agent-browser", "--session-name", self.session_name, "scroll", "down"]
        subprocess.run(cmd, capture_output=True, timeout=30)
        
        cmd = ["agent-browser", "--session-name", self.session_name, "wait", "2"]
        subprocess.run(cmd, capture_output=True, timeout=30)
        
        # Get posts
        cmd = ["agent-browser", "--session-name", self.session_name, "eval", js]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            return [], {}
        
        import json
        try:
            urls = json.loads(result.stdout.strip())
        except:
            print(f"Failed to parse: {result.stdout}")
            return [], {}
        
        print(f"Found {len(urls)} post URLs")
        
        url_to_local = {}
        posts = []
        
        for i, url in enumerate(urls[:limit]):
            # Get image URL from post
            img_js = '(document.querySelector("article img") || document.querySelector("article picture img"))?.src || null'
            cmd = ["agent-browser", "--session-name", self.session_name, "open", url]
            subprocess.run(cmd, capture_output=True, timeout=30)
            
            cmd = ["agent-browser", "--session-name", self.session_name, "wait", "2"]
            subprocess.run(cmd, capture_output=True, timeout=30)
            
            cmd = ["agent-browser", "--session-name", self.session_name, "eval", img_js]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            image_url = result.stdout.strip() if result.returncode == 0 else ""
            if image_url and image_url != "null" and "cdn" in image_url:
                # Download image
                filename = f"insta_{i}.jpg"
                local_path = os.path.join(self.output_dir, filename)
                try:
                    urllib.request.urlretrieve(image_url, local_path)
                    url_to_local[url] = local_path
                    print(f"Downloaded: {filename}")
                except Exception as e:
                    print(f"Failed to download {image_url}: {e}")
            
            posts.append(BrowserPost(post_url=url, image_url=image_url, index=i))
        
        return posts, url_to_local


def crawl_instagram_browser(username: str, output_dir: str = "/tmp/instagram_images", 
                            limit: int = 50, session_name: str = "instagram") -> tuple[list, dict]:
    """Convenience function to crawl Instagram using browser screenshots.
    
    Uses pre-saved post URLs and browser screenshots to minimize API requests.
    """
    import json
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Load cached URLs if available
    cache_file = "/tmp/instagram_posts.json"
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            post_urls = json.load(f)[:limit]
    else:
        post_urls = []
    
    if not post_urls:
        return [], {}
    
    url_to_local = {}
    posts = []
    
    for i, url in enumerate(post_urls):
        post_id = url.split("/p/")[-1].split("/")[0]
        filename = f"insta_{i}_{post_id}.png"
        local_path = os.path.join(output_dir, filename)
        
        # Use browser to take screenshot - each command separately
        subprocess.run(["agent-browser", "--session-name", session_name, "open", url], 
                      capture_output=True, timeout=30)
        subprocess.run(["agent-browser", "--session-name", session_name, "wait", "2"], 
                      capture_output=True, timeout=30)
        result = subprocess.run(["agent-browser", "--session-name", session_name, "screenshot", local_path], 
                      capture_output=True, text=True, timeout=30)
        
        if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
            url_to_local[url] = local_path
            print(f"Screenshot: {filename}")
        else:
            print(f"Failed: {filename} - {result.stdout[:100] if result.stdout else result.stderr[:100]}")
        
        posts.append(BrowserPost(
            post_url=url,
            image_url=local_path,
            index=i
        ))
    
    return posts, url_to_local


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python browser.py <username> [limit]")
        sys.exit(1)
    
    username = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    
    print(f"Fetching posts for {username}...")
    posts, url_map = crawl_instagram_browser(username, limit=limit)
    
    print(f"Found {len(posts)} posts")
    for post in posts:
        print(f"  {post.post_url}")
