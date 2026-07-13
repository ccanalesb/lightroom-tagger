import os
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

from lightroom_tagger.core.config import (
    Config,
    DEFAULT_CONFIG_PATH,
    REPO_ROOT,
    load_config,
)


class TestConfig(unittest.TestCase):
    """Tests for Config dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        config = Config(
            catalog_path="/test/catalog.lrcat",
            db_path="/test/db.json"
        )
        self.assertEqual(config.catalog_path, "/test/catalog.lrcat")
        self.assertEqual(config.db_path, "/test/db.json")
        self.assertEqual(config.mount_point, "")
        self.assertEqual(config.workers, 4)
        self.assertEqual(config.instagram_keyword, "Posted")
        self.assertEqual(config.hash_threshold, 5)

    def test_custom_values(self):
        """Test custom values override defaults."""
        config = Config(
            catalog_path="/test/catalog.lrcat",
            db_path="/test/db.json",
            mount_point="/mnt/custom",
            workers=8,
            instagram_keyword="Instagram",
            hash_threshold=10
        )
        self.assertEqual(config.mount_point, "/mnt/custom")
        self.assertEqual(config.workers, 8)
        self.assertEqual(config.instagram_keyword, "Instagram")
        self.assertEqual(config.hash_threshold, 10)


class TestLoadConfig(unittest.TestCase):
    """Tests for load_config function."""

    @patch("lightroom_tagger.core.config.open", new_callable=mock_open, read_data="")
    @patch("lightroom_tagger.core.config.Path.exists", return_value=False)
    @patch.dict("os.environ", {}, clear=True)
    def test_load_config_no_file(self, mock_exists, mock_file):
        """Test loading config when file doesn't exist."""
        config = load_config("nonexistent.yaml")
        self.assertEqual(config.catalog_path, "")
        self.assertEqual(config.db_path, "")

    @patch("lightroom_tagger.core.config.open", new_callable=mock_open, read_data="catalog_path: /test/catalog\ndb_path: /test/db\n")
    @patch("lightroom_tagger.core.config.Path.exists", return_value=True)
    @patch("lightroom_tagger.core.config.load_dotenv")
    @patch.dict("os.environ", {}, clear=True)
    def test_load_config_from_file(self, mock_dotenv, mock_exists, mock_file):
        """Test loading config from YAML file."""
        config = load_config("config.yaml")
        self.assertEqual(config.catalog_path, "/test/catalog")
        self.assertEqual(config.db_path, "/test/db")

    @patch("lightroom_tagger.core.config.open", new_callable=mock_open, read_data="catalog_path: /file/catalog\ndb_path: /file/db\n")
    @patch("lightroom_tagger.core.config.Path.exists", return_value=True)
    @patch("lightroom_tagger.core.config.load_dotenv")
    def test_load_config_from_file_without_clearing_environ(self, mock_dotenv, mock_exists, mock_file):
        """Test loading config from YAML when os.environ is not cleared."""
        config = load_config("config.yaml")
        self.assertEqual(config.catalog_path, "/file/catalog")
        self.assertEqual(config.db_path, "/file/db")

    @patch("lightroom_tagger.core.config.open", new_callable=mock_open, read_data="")
    @patch("lightroom_tagger.core.config.Path.exists", return_value=False)
    @patch.dict("os.environ", {"INSTAGRAM_DUMP_PATH": "/env/instagram-dump"}, clear=True)
    def test_load_config_instagram_dump_path_from_env(self, mock_exists, mock_file):
        """INSTAGRAM_DUMP_PATH in the environment is mapped to Config.instagram_dump_path."""
        config = load_config("nonexistent.yaml")
        self.assertEqual(config.instagram_dump_path, "/env/instagram-dump")

    def test_find_repo_root_has_pyproject(self):
        """REPO_ROOT must be the directory that contains pyproject.toml."""
        self.assertTrue((REPO_ROOT / "pyproject.toml").is_file())
        self.assertTrue((REPO_ROOT / "lightroom_tagger").is_dir())

    def test_load_config_default_ignores_cwd(self):
        """No-arg load_config() uses repo-root config.yaml, not CWD-relative path."""
        isolated_cwd = REPO_ROOT / "lightroom_tagger" / "core"
        previous_cwd = os.getcwd()
        try:
            os.chdir(isolated_cwd)
            self.assertFalse(Path("config.yaml").exists())

            with patch(
                "lightroom_tagger.core.config.DEFAULT_CONFIG_PATH",
                REPO_ROOT / "config.yaml",
            ), patch(
                "lightroom_tagger.core.config.open",
                mock_open(
                    read_data=(
                        "catalog_path: /repo/root/catalog.lrcat\n"
                        "db_path: /repo/root/library.db\n"
                    )
                ),
            ), patch(
                "lightroom_tagger.core.config.Path.exists",
                return_value=True,
            ):
                config = load_config()

            self.assertEqual(config.catalog_path, "/repo/root/catalog.lrcat")
            self.assertEqual(config.db_path, "/repo/root/library.db")
        finally:
            os.chdir(previous_cwd)


if __name__ == "__main__":
    unittest.main()
