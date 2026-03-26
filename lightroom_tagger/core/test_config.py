import unittest
from unittest.mock import mock_open, patch

from lightroom_tagger.core.config import Config, load_config


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
        self.assertEqual(config.mount_point, "/mnt/nas")
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


if __name__ == "__main__":
    unittest.main()
