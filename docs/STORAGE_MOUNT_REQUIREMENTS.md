# Storage and mount requirements

The visualizer backend runs on a **host machine** (your server, VM, or dev box). Lightroom catalogs and image files often live on a NAS or network share. For path-dependent jobs—embed, cache build, matching, description, scoring—the backend must be able to **read those paths on disk**.

If the share is not mounted (or mounted at the wrong path), jobs may appear to run but process almost nothing.

## How paths are resolved

The library database stores file paths as Lightroom recorded them—often UNC-style network paths:

```
//tnas/ccanales/Photos/2024/IMG_1234.jpg
```

At runtime, `resolve_filepath()` in `lightroom_tagger/core/database/catalog.py` maps UNC paths to a **local mount point** on the backend host:

| Platform | Typical mount |
|----------|----------------|
| macOS (SMB) | `/Volumes/<share>/...` (auto-detected under `/Volumes/`) |
| Linux / WSL | `/mnt/nas/...`, `/mnt/tnas/...`, or your configured path |

Example:

```
//tnas/ccanales/Photos/2024/IMG_1234.jpg  →  /Volumes/ccanales/Photos/2024/IMG_1234.jpg
```

The resolved path must exist and be readable (`os.path.isfile`) before an image can be embedded, cached, or scored.

### Configuration

Set the mount point in `config.yaml` or via environment variable:

```yaml
mount_point: "/mnt/nas"   # or /Volumes/ccanales on macOS
```

```bash
export LIGHTRoom_MOUNT=/mnt/nas
```

When the visualizer backend starts, it copies `mount_point` into `NAS_MOUNT_POINT` and may auto-detect `NAS_PATH_PREFIX` from a sample UNC path in `library.db`.

You can also set these explicitly:

```bash
export NAS_PATH_PREFIX=//tnas/ccanales
export NAS_MOUNT_POINT=/mnt/tnas
```

See also [Catalog read vs write](CATALOG_READ_WRITE.md) for how the backend opens `.lrcat` files on network storage.

## Symptoms

| What you see | Likely cause |
|--------------|--------------|
| Embed (or cache build) **finishes quickly** with `embedded: 0` and high `skipped` | Most file paths do not resolve to readable files |
| Job Queue shows **Embed diagnostics** with large counts for **Missing file** or **Empty path** | UNC paths not mapped to an existing mount |
| Embed job **fails immediately** with a message like *"sampled paths unreachable — this usually means your network share is not mounted"* | Preflight sampled images and found >50% inaccessible |
| Matching or description jobs skip most images | Same root cause: backend cannot open source files |

The embed job runs a **preflight check** on a random sample of pending images. If more than half have missing or inaccessible paths, it aborts with an actionable error instead of silently skipping thousands of rows.

## Fix steps

### 1. Verify the mount on the backend host

SSH or log in to the machine running the visualizer backend (not your Lightroom workstation unless they are the same).

```bash
# Linux — is the share mounted?
mount | grep -E 'nas|tnas|cifs|smb'

# macOS — is the volume present?
ls /Volumes/

# Can you read a known file?
test -r /mnt/nas/Photos/some-known-file.jpg && echo OK || echo MISSING
```

If the mount is missing, mount the share before retrying jobs. On Linux this is often `/etc/fstab` or a manual `mount -t cifs ...`; on macOS, connect the share in Finder so it appears under `/Volumes/`.

### 2. Check path resolution

Pick a UNC path from your library (Processing → Catalog cache shows cache location; or query `images.filepath` in `library.db`):

```bash
python3 -c "
from lightroom_tagger.core.database import resolve_filepath
p = '//tnas/ccanales/Photos/example.jpg'  # replace with a real path
r = resolve_filepath(p)
print('resolved:', r)
import os
print('exists:', os.path.isfile(r))
"
```

- If `resolved` still looks like `//...`, no mount mapping matched—set `mount_point` / `NAS_MOUNT_POINT`.
- If `resolved` is a local path but `exists: False`, the mount is wrong or the file moved.

Restart the visualizer backend after changing `config.yaml` or mount env vars so `NAS_MOUNT_POINT` is picked up.

### 3. Retry the job

1. Open **Processing → Catalog cache**.
2. Re-run **Embed catalog images** (or the full cache build).
3. Open **Job Queue** and confirm `embedded` counts increase and skip diagnostics shrink.

If preflight still aborts, read the job error and **Embed diagnostics** card for breakdown (`Missing file`, `Empty path`, `No DB row`).

## Jobs affected

Any job that reads original image bytes from disk:

- Embed catalog / catalog + Instagram
- Catalog cache build
- Prepare catalog (pre-compress)
- Vision matching, description, and scoring pipelines

The catalog SQLite file itself also must be readable on the backend; see the NAS section in the main [README](../README.md#catalog-on-network-storage-nassmb).
