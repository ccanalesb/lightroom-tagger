import requests
import time
import json
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

from lightroom_tagger.config import load_config


@dataclass
class InstagramPost:
    post_url: str
    image_url: str
    timestamp: datetime
    index: int = 0
    caption: str = ""


def get_session_headers(config) -> dict:
    """Get headers with session cookie."""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Cookie": f"sessionid={config.instagram_session_id}",
    }


def get_user_id(config) -> Optional[str]:
    """Get Instagram user ID from username."""
    url = f"https://www.instagram.com/{config.instagram_url.split('/')[-2]}/?__a=1"
    
    try:
        response = requests.get(url, headers=get_session_headers(config), timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get('logging_page_id', '').replace('PagePostFragment', '')
    except Exception as e:
        print(f"Error getting user ID: {e}")
    return None


def fetch_user_posts(config, user_id: str = None, limit: int = 50) -> list:
    """Fetch user posts using GraphQL."""
    username = config.instagram_url.split('/')[-2]
    if not username or 'instagram' in username:
        raise ValueError("Could not extract username from instagram_url in config")
    
    if not user_id:
        url = f"https://www.instagram.com/{username}/?__a=1"
        response = requests.get(url, headers=get_session_headers(config), timeout=30)
        if response.status_code != 200:
            print(f"Error: Got status {response.status_code}")
            return []
        
        try:
            data = response.json()
        except:
            print("Error: Could not parse JSON response")
            return []
        
        if 'graphql' not in data:
            print("Error: No graphql data in response")
            return []
        
        user_data = data['graphql']['user']
    else:
        user_data = {'id': user_id}
    
    variables = {
        "id": user_data.get('id', username),
        "first": limit
    }
    
    url = "https://www.instagram.com/graphql/query/"
    params = {
        "query_hash": "8cBox6C53OzVKDGz8FgFw5LbsoeO",
        "variables": json.dumps(variables)
    }
    
    posts = []
    try:
        response = requests.get(url, headers=get_session_headers(config), params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            edges = data.get('data', {}).get('user', {}).get('edge_owner_to_timeline_media', {}).get('edges', [])
            
            for edge in edges:
                node = edge.get('node', {})
                posts.append({
                    'id': node.get('id'),
                    'shortcode': node.get('shortcode'),
                    'timestamp': node.get('taken_at_timestamp'),
                    'display_url': node.get('display_url'),
                    'thumbnail_url': node.get('thumbnail_src'),
                    'is_video': node.get('is_video'),
                    'caption': node.get('edge_media_to_caption', {}).get('edges', [{}])[0].get('node', {}).get('text', ''),
                })
    except Exception as e:
        print(f"Error fetching posts: {e}")
    
    return posts


def get_post_images(config, shortcode: str) -> list[dict]:
    """Get all images from a post (including carousels)."""
    url = f"https://www.instagram.com/p/{shortcode}/?__a=1"
    images = []
    
    try:
        response = requests.get(url, headers=get_session_headers(config), timeout=30)
        if response.status_code == 200:
            data = response.json()
            
            if 'graphql' in data:
                node = data['graphql']['shortcode_media']
                
                if node.get('__typename') == 'GraphSidecar':
                    for edge in node.get('edge_sidecar_to_children', {}).get('edges', []):
                        img_node = edge.get('node', {})
                        if not img_node.get('is_video'):
                            images.append({
                                'url': img_node.get('display_url'),
                                'type': 'image'
                            })
                elif not node.get('is_video'):
                    images.append({
                        'url': node.get('display_url'),
                        'type': 'image'
                    })
    except Exception as e:
        print(f"Error getting post images: {e}")
    
    return images


def download_images(posts: list, output_dir: str) -> dict:
    """Download Instagram images and return mapping."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    url_to_path = {}
    
    for i, post in enumerate(posts):
        try:
            img_url = post.get('display_url') or post.get('thumbnail_url')
            if not img_url:
                continue
            
            response = requests.get(img_url, timeout=30)
            response.raise_for_status()
            
            ext = '.jpg'
            if 'video' in response.headers.get('Content-Type', ''):
                ext = '.mp4'
            
            filename = f"instagram_{post.get('shortcode', i)}{ext}"
            filepath = output_path / filename
            
            with open(filepath, "wb") as f:
                f.write(response.content)
            
            url_to_path[img_url] = str(filepath)
            
        except Exception as e:
            print(f"  Error downloading: {e}")
            continue
    
    return url_to_path


def crawl_instagram(config=None, output_dir: str = "/tmp/instagram_images", limit: int = 50) -> tuple:
    """Main function to crawl Instagram and download images."""
    if config is None:
        config = load_config()
    
    if not config.instagram_session_id:
        print("Error: No Instagram session ID configured")
        return [], {}
    
    username = config.instagram_url.split('/')[-2]
    if not username or 'instagram' in username:
        raise ValueError("Could not extract username from instagram_url in config")
    print(f"Crawling Instagram: {username}")
    
    print("Fetching posts...")
    posts = fetch_user_posts(config, limit=limit)
    print(f"Found {len(posts)} posts")
    
    if not posts:
        return [], {}
    
    print("Downloading images...")
    url_to_path = download_images(posts, output_dir)
    print(f"Downloaded {len(url_to_path)} images")
    
    instagram_posts = []
    for i, post in enumerate(posts):
        img_url = post.get('display_url') or post.get('thumbnail_url')
        local_path = url_to_path.get(img_url)
        
        timestamp = datetime.fromtimestamp(post['timestamp']) if post.get('timestamp') else datetime.now()
        
        instagram_posts.append(InstagramPost(
            post_url=f"https://www.instagram.com/p/{post.get('shortcode')}/",
            image_url=img_url or "",
            timestamp=timestamp,
            index=0,
            caption=post.get('caption', '')[:100]
        ))
    
    return instagram_posts, url_to_path


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape Instagram posts")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--output", default="/tmp/instagram_images", help="Output directory")
    parser.add_argument("--limit", type=int, default=10, help="Limit number of posts")
    
    args = parser.parse_args()
    
    config = load_config(args.config)
    posts, url_to_path = crawl_instagram(config, args.output, args.limit)
    
    print(f"\nTotal: {len(posts)} posts, {len(url_to_path)} images downloaded")
