import pathlib
import shutil

_FX = pathlib.Path(__file__).resolve().parent
SEED_LIBRARY_DB: pathlib.Path = _FX / "library_seed.db"


def ensure_writable_fixture_library(dest_path: pathlib.Path) -> pathlib.Path:
    if not SEED_LIBRARY_DB.is_file():
        raise RuntimeError("library_seed.db missing")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SEED_LIBRARY_DB, dest_path)
    return dest_path.resolve()
