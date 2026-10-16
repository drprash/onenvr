# OneNVR - One Network Video Recorder

[![Repo](https://img.shields.io/badge/Docker-Repo-007EC6?labelColor-555555&color-007EC6&logo=docker&logoColor=fff&style=flat-square)](https://hub.docker.com/r/drprash/onenvr)
[![Version](https://img.shields.io/docker/v/drprash/onenvr/latest?labelColor-555555&color-007EC6&style=flat-square)](https://hub.docker.com/r/drprash/onenvr)
[![Size](https://img.shields.io/docker/image-size/drprash/onenvr/latest?sort=semver&labelColor-555555&color-007EC6&style=flat-square)](https://hub.docker.com/r/drprash/onenvr)
[![Pulls](https://img.shields.io/docker/pulls/drprash/onenvr?labelColor-555555&color-007EC6&style=flat-square)](https://hub.docker.com/r/drprash/onenvr)

A lightweight, self-hosted Network Video Recorder (NVR) designed to run on modest hardware such as a Raspberry Pi with an attached drive. Records 24/7 RTSP streams from network cameras into segmented files with a built-in web interface for browsing, playback, and management.

![Web Interface](/images/web-interface.png)

## Features

- **Multi-camera recording** — any number of RTSP cameras, each in its own storage directory
- **Segmented recording** — streams are saved in configurable-length segments (default 5 min) to limit data loss from file corruption
- **Auto-restart** — recording resumes automatically after unexpected interruptions
- **Manual start/stop** — per-camera controls in the dashboard; manual stop suppresses auto-restart until the camera is manually started again
- **Hot-reload config** — camera and settings changes apply within seconds without restarting the container
- **Daily concatenation** — optional job merges previous-day segments into a single file and removes the originals
- **Retention cleanup** — old recordings are deleted automatically based on configured retention days
- **Dark web UI** — dashboard, recordings browser with inline video player, camera management, and settings
- **Login with password reset** — credentials persist across container rebuilds; locked-out reset is file-based (admin access only for security reasons)

## Deployment

### docker-compose (recommended)

```yaml
services:
  onenvr:
    container_name: onenvr
    hostname: onenvr
    image: drprash/onenvr:latest
    ports:
      - "80:5000"
    volumes:
      - /path/to/onenvr/config:/config
      - /path/to/onenvr/storage:/storage
    environment:
      - TZ=America/New_York
      - DEBUG=false
    restart: unless-stopped
```

### docker run

```bash
docker run -d --name onenvr \
  -p 80:5000 \
  -v /path/to/onenvr/config:/config \
  -v /path/to/onenvr/storage:/storage \
  -e TZ=America/New_York \
  drprash/onenvr:latest
```

### Volumes

| Mount | Purpose |
|-------|---------|
| `/config` | `config.yaml`, credentials, and reset key |
| `/storage` | Recorded video files |

## Configuration

Camera and system settings are managed through the web interface or by editing `/config/config.yaml` directly. Changes are picked up automatically within a few seconds — no container restart needed.

### config.yaml structure

```yaml
cameras:
  - name: frontdoor
    rtsp_url: rtsp://user:password@192.168.1.10:554/stream1
    codec: copy
    interval: 300

  - name: backyard
    rtsp_url: rtsp://192.168.1.11:554/live
    codec: copy
    interval: 300

retention_days: 7
concatenation: true
concatenation_time: "02:00"
deletion_time: "01:00"
```

### Options

| Setting | Default | Description |
|---------|---------|-------------|
| `cameras[].name` | — | Unique camera identifier (alphanumeric, `-`, `_`). Used as the storage folder name. |
| `cameras[].rtsp_url` | — | Full RTSP URL including credentials if required. |
| `cameras[].codec` | `copy` | FFmpeg codec. `copy` (recommended) passes through the stream without re-encoding. Any FFmpeg-supported codec works. |
| `cameras[].interval` | `300` | Segment length in seconds (minimum 60). |
| `retention_days` | `7` | Recordings older than this are deleted by the daily cleanup job. |
| `concatenation` | `true` | Merge previous-day segments into a single file at `concatenation_time`. |
| `concatenation_time` | `02:00` | Time to run daily concatenation (24-hour HH:MM, local timezone). |
| `deletion_time` | `01:00` | Time to run daily cleanup (24-hour HH:MM, local timezone). |

Set the `TZ` environment variable to run scheduled jobs in your local timezone (e.g. `TZ=America/New_York`).

## Web Interface

Access the UI at `http://<host>:80` (or whichever port you mapped).

| Page | Path | Description |
|------|------|-------------|
| Dashboard | `/` | Camera health, disk usage, per-camera start/stop |
| Recordings | `/recordings` | Browse footage by camera → date → file; inline video player |
| Cameras | `/cameras` | Add, edit, and delete camera configurations |
| Settings | `/settings` | Retention, concatenation schedule, change password |

The dashboard polls for live status every 8 seconds and updates camera badges and buttons without a page reload.

## Authentication

On first access, create a username and password through the web interface. Credentials are stored in `/config/auth.dat` and persist across container rebuilds as long as the `/config` volume is preserved.

### Change password

Go to **Settings → Change Password** while logged in.

### Locked out / forgot password

1. Visit `/forgot_password` — a reset key is written to `/config/password_reset.key`.
2. Retrieve the key from the host (requires filesystem access):
   ```bash
   docker exec <container_name> cat /config/password_reset.key
   ```
3. Visit `/reset_password`, enter the key, and set a new password.

This flow is intentionally file-based so that only a server administrator can reset a lost password.

## Building from source

```bash
git clone https://github.com/drprash/onenvr.git
cd onenvr

TIMESTAMP="$(date '+%Y%m%d-%H%M')"
docker build -t "${USER}/onenvr:${TIMESTAMP}" .

docker run -d --name onenvr \
  -p 80:5000 \
  -v /path/to/config:/config \
  -v /path/to/storage:/storage \
  "${USER}/onenvr:${TIMESTAMP}"
```

## Logs

```bash
docker logs onenvr
```

For verbose output, set `DEBUG=true` in your environment variables.
