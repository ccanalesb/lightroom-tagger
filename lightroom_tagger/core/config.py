import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    catalog_path: str = ""
    db_path: str = ""
    mount_point: str = "/mnt/nas"
    workers: int = 4
    ai_model: str = "claude-3-5-sonnet-20241022"
    skip_ai: bool = False
    verbose: bool = False
    instagram_url: str = "https://www.instagram.com/im.canales"
    instagram_keyword: str = "Posted"
    hash_threshold: int = 5
    small_catalog_path: str = ""
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = ""
    instagram_session_id: str = ""
    vision_model: str = "gemma3:27b"
    phash_weight: float = 0.4
    desc_weight: float = 0.3
    vision_weight: float = 0.3
    match_threshold: float = 0.7
    vision_cache_dir: str = field(default_factory=lambda: os.path.expanduser("~/.cache/lightroom_tagger/vision"))
    vision_cache_enabled: bool = True

    def __post_init__(self):
        self.catalog_path = self._resolve_path(self.catalog_path)
        self.db_path = self._resolve_path(self.db_path)

    def _resolve_path(self, path: str) -> str:
        if not path:
            return path
        path = str(Path(path).expanduser())
        path = self._resolve_nas_path(path)
        return path

    def _resolve_nas_path(self, path: str) -> str:
        if not path:
            return path
        # Handle common NAS patterns: //nas/, //tnas/, etc.
        # Match //nas/ or //tnas/ or any //<name>/
        # Handle both //tnas/ccanales/... and //tnas/... formats
        # Map //tnas/ccanales -> /mnt/tnas, //nas -> /mnt/nas, etc.
        if path.startswith('//tnas/ccanales'):
            path = path.replace('//tnas/ccanales', '/mnt/tnas', 1)
        elif path.startswith('//tnas/'):
            path = path.replace('//tnas/', '/mnt/tnas/', 1)
        elif path.startswith('//nas/'):
            path = path.replace('//nas/', '/mnt/nas/', 1)

        path = path.replace("\\", "/")
        return path


def load_config(config_path: str = "config.yaml") -> Config:
    config_file = Path(config_path)

    if config_file.exists():
        with open(config_file) as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    data = _load_from_env(data)

    defaults = {
        "mount_point": "/mnt/nas",
        "workers": 4,
        "ai_model": "claude-3-5-sonnet-20241022",
        "skip_ai": False,
        "verbose": False,
        "instagram_url": "https://www.instagram.com/im.canales",
        "instagram_keyword": "Posted",
        "hash_threshold": 5,
        "cloudflare_account_id": "",
        "cloudflare_api_token": "",
        "instagram_session_id": "",
        "vision_model": "gemma3:27b",
        "phash_weight": 0.4,
        "desc_weight": 0.3,
        "vision_weight": 0.3,
        "match_threshold": 0.7,
        "vision_cache_dir": os.path.expanduser("~/.cache/lightroom_tagger/vision"),
        "vision_cache_enabled": True,
    }

    for key, value in defaults.items():
        if key not in data:
            data[key] = value

    return Config(**data)


def _load_from_env(data: dict) -> dict:
    env_mappings = {
        "LIGHTRoom_CATALOG": "catalog_path",
        "LIGHTRoom_DB": "db_path",
        "LIGHTRoom_MOUNT": "mount_point",
        "LIGHTRoom_WORKERS": "workers",
        "LIGHTRoom_AI_MODEL": "ai_model",
        "LIGHTRoom_SKIP_AI": "skip_ai",
        "LIGHTRoom_VERBOSE": "verbose",
        "LIGHTRoom_INSTAGRAM_URL": "instagram_url",
        "LIGHTRoom_INSTAGRAM_KEYWORD": "instagram_keyword",
        "LIGHTRoom_HASH_THRESHOLD": "hash_threshold",
        "CLOUDFLARE_ACCOUNT_ID": "cloudflare_account_id",
        "CLOUDFLARE_API_TOKEN": "cloudflare_api_token",
        "INSTAGRAM_SESSION_ID": "instagram_session_id",
        "VISION_MODEL": "vision_model",
        "PHASH_WEIGHT": "phash_weight",
        "DESC_WEIGHT": "desc_weight",
        "VISION_WEIGHT": "vision_weight",
        "MATCH_THRESHOLD": "match_threshold",
        "VISION_CACHE_DIR": "vision_cache_dir",
        "VISION_CACHE_ENABLED": "vision_cache_enabled",
    }

    for env_var, config_key in env_mappings.items():
        if env_var in os.environ:
            value = os.environ[env_var]
            if config_key == "workers":
                value = int(value)
            elif config_key in ("skip_ai", "verbose", "vision_cache_enabled"):
                value = value.lower() in ("true", "1", "yes")
            elif config_key in ("hash_threshold", "match_threshold"):
                value = int(value)
            elif config_key in ("phash_weight", "desc_weight", "vision_weight"):
                value = float(value)
            data[config_key] = value

    return data
