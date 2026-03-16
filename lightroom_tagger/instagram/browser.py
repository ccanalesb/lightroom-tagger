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
        """Check if session is logged in.
        
        Checks both URL and DOM for logged-in state.
        """
        try:
            # Navigate to Instagram homepage
            self.open_url("https://www.instagram.com/")
            self.wait(3)
            
            # Check snapshot for login page (not logged in)
            snapshot = self.snapshot()
            
            # If we see login form elements, we're not logged in
            if 'textbox "Mobile number' in snapshot or 'button "Log In"' in snapshot:
                return False
            
            # Also check for "Create new account" which appears on login page
            if 'link "Create new account"' in snapshot:
                return False
            
            # Check DOM for logged-in elements
            js_check = """(function() {
                // If we can find the stories bar or home feed, we're logged in
                const hasStories = document.querySelector('header') !== null || 
                                   document.querySelector('main') !== null;
                const hasHomeLink = document.querySelector('a[href*="/"] svg[aria-label="Home"]') !== null ||
                                   document.querySelector('svg[aria-label="Home"]') !== null;
                // Check for username in URL or profile elements
                const url = window.location.href;
                const hasUsername = url.includes('/im.canales') || url === 'https://www.instagram.com/';
                return hasStories || hasHomeLink;
            })()"""
            
            returncode, result, stderr = self._run_command(["eval", js_check])
            if returncode == 0 and "true" in result.lower():
                return True
            
            return False
        except Exception as e:
            print(f"Session check error: {e}")
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
    """Convenience function to crawl Instagram using browser to extract image URLs.
    
    Uses pre-saved post URLs and extracts image URLs via JS, then downloads with curl.
    """
    import json
    import re
    import time
    import subprocess
    
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
    
    # JS to extract post images by clicking through carousel
    js_extract = '''(function() {
        const results = [];
        const seen = new Set();
        
        // Get images at current position
        const getImages = () => {
            const imgs = Array.from(document.querySelectorAll('img')).filter(i => 
                i.naturalWidth >= 1000 && i.src.includes('instagram')
            );
            for (const img of imgs) {
                const url = img.src.split('?')[0];
                if (!seen.has(url)) {
                    seen.add(url);
                    results.push({src: img.src, width: img.naturalWidth, height: img.naturalHeight});
                }
            }
        };
        
        // Get initial images
        getImages();
        
        // Try to navigate through carousel using arrow key
        let maxClicks = 10;
        while (maxClicks > 0) {
            // Simulate arrow right key press
            document.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight', keyCode: 39}));
            // Wait a bit for images to load
            const start = Date.now();
            while (Date.now() - start < 500) {}
            
            const beforeCount = results.length;
            getImages();
            
            // If no new images, we've reached the end
            if (results.length >= beforeCount && maxClicks < 10) break;
            maxClicks--;
        }
        
        return results.slice(0, 10);
    })()'''
    
    for i, url in enumerate(post_urls):
        post_id = url.split("/p/")[-1].split("/")[0]
        filename = f"insta_{i}_{post_id}.jpg"
        local_path = os.path.join(output_dir, filename)
        
        print(f"Processing {i+1}/{len(post_urls)}: {post_id}")
        
        # Navigate to post
        subprocess.run(["agent-browser", "--session-name", session_name, "open", url], 
                      capture_output=True, timeout=30)
        
        # Wait for images to load
        subprocess.run(["agent-browser", "--session-name", session_name, "wait", "3"], 
                      capture_output=True, timeout=30)
        
        # Extract image URLs via JS
        result = subprocess.run(
            ["agent-browser", "--session-name", session_name, "eval", js_extract],
            capture_output=True, text=True, timeout=30
        )
        
        # Parse image URLs from JS result
        images = []
        if result.returncode == 0 and result.stdout.strip():
            try:
                images = json.loads(result.stdout.strip())
                if images:
                    print(f"  Found {len(images)} image(s)")
            except Exception as e:
                print(f"  Parse error: {e}")
        
        downloaded_paths = []
        if images and len(images) > 0:
            for j, img_data in enumerate(images):
                image_url = img_data['src']
                if not image_url or "cdn" not in image_url:
                    continue
                    
                # Use sub-index for carousel images
                sub_idx = f"{i}_{j}" if len(images) > 1 else str(i)
                filename = f"insta_{sub_idx}_{post_id}.jpg"
                local_path = os.path.join(output_dir, filename)
                
                curl_cmd = [
                    "curl", "-sL", "--max-time", "30",
                    "-o", local_path, image_url
                ]
                curl_result = subprocess.run(curl_cmd, capture_output=True, timeout=35)
                
                if os.path.exists(local_path):
                    file_size = os.path.getsize(local_path)
                    if file_size > 100:
                        downloaded_paths.append(local_path)
                        print(f"  Downloaded[{j}]: {img_data['width']}x{img_data['height']} ({file_size} bytes)")
                    else:
                        os.remove(local_path)
                
                # Delay between images to avoid rate limiting
                if j < len(images) - 1:
                    time.sleep(2)
        
        # If no images downloaded, try screenshot fallback
        if not downloaded_paths:
            png_path = os.path.join(output_dir, f"insta_{i}_{post_id}.png")
            subprocess.run(
                ["agent-browser", "--session-name", session_name, "screenshot", png_path],
                capture_output=True, timeout=30
            )
            if os.path.exists(png_path) and os.path.getsize(png_path) > 1000:
                downloaded_paths.append(png_path)
                print(f"  Screenshot fallback: {png_path}")
        
        # Store first image path in url_to_local for compatibility
        if downloaded_paths:
            url_to_local[url] = downloaded_paths[0]
        
        # Add post with image URL (use first downloaded image or the JS result)
        post_image_url = downloaded_paths[0] if downloaded_paths else (images[0]['src'] if images and images[0].get('src') else "")
        posts.append(BrowserPost(
            post_url=url,
            image_url=post_image_url,
            index=i
        ))
        
        # Delay between posts to avoid rate limiting
        if i < len(post_urls) - 1:
            time.sleep(3)
    
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
