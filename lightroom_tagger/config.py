from dataclasses import dataclass, field
from pathlib import Path
import os
import re
import yaml


@dataclass
class Config:
    catalog_path: str
    db_path: str
    mount_point: str = "/mnt/nas"
    workers: int = 4
    ai_model: str = "claude-3-5-sonnet-20241022"
    skip_ai: bool = False
    verbose: bool = False

    def __post_init__(self):
        self.catalog_path = self._resolve_path(self.catalog_path)
        self.db_path = self._resolve_path(self.db_path)

    def _resolve_path(self, path: str) -> str:
        path = str(Path(path).expanduser())
        path = self._resolve_nas_path(path)
        return path

    def _resolve_nas_path(self, path: str) -> str:
        nas_pattern = re.compile(r"^//nas/|\\\\nas\\")
        if nas_pattern.match(path):
            path = nas_pattern.sub(self.mount_point + "/", path)
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
    }

    for env_var, config_key in env_mappings.items():
        if env_var in os.environ:
            value = os.environ[env_var]
            if config_key == "workers":
                value = int(value)
            elif config_key in ("skip_ai", "verbose"):
                value = value.lower() in ("true", "1", "yes")
            data[config_key] = value

    return data
