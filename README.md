# pinterest-downloader

**Unofficial Python library** to download and interact with Pinterest content — pins, videos, GIFs, profiles, and boards — **without an API key**.

[![PyPI](https://img.shields.io/pypi/v/pinterest-downloader.svg)](https://pypi.org/project/pinterest-downloader/)
[![Python](https://img.shields.io/pypi/pyversions/pinterest-downloader.svg)](https://pypi.org/project/pinterest-downloader/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Features

| Feature | Methods |
|---------|---------|
| 🔎 Search pins & videos (paginated + bookmark) | `search`, `search_all` |
| 📁 Search boards by keyword | `search_boards` |
| 📌 Fetch single pin (image / video / GIF) with full metadata | `get_pin` |
| 🗂️ Board feeds (all pins on a board) | `get_board_pins` |
| 👤 User pins | `get_user_pins` |
| 👤 User profiles (followers, bio, counts, …) | `get_profile` |
| 📁 Board metadata + list of user boards | `get_board`, `get_boards` |
| ⬇️ Download pin media or entire board to disk | `download_pin`, `download_board` |
| 🛡️ Graceful errors — every method returns `{"ok": …}` (no exceptions raised by the library) | — |
| 🚀 No API key required — works with public Pinterest data | — |

**Supported URL formats for pins:**
- Full URL: `https://www.pinterest.com/pin/123456789012345678/`
- With or without trailing slash / query parameters
- Short links: `https://pin.it/xxxxx`
- Numeric pin ID only: `"123456789012345678"`

**Supported media types:** image, video (MP4 + HLS), GIF.

---

## Requirements

- Python **≥ 3.8**
- Dependencies (installed automatically):
  - `requests >= 2.25.0`
  - `beautifulsoup4 >= 4.10.0`

---

## Installation

```bash
pip install pinterest-downloader
```

Or from source:

```bash
git clone https://github.com/x7007x/PinterestDownloader.git
cd PinterestDownloader
pip install -e .
```

---

## Quick Start

```python
from pinterest_downloader import Pinterest

p = Pinterest()

# --- Get a pin (image / video / GIF) ---
result = p.get_pin("https://www.pinterest.com/pin/1098174690415756357/")
# also works with: "https://pin.it/xxxxx"  or  "1098174690415756357"

if result["ok"]:
    pin = result["pin"]
    print(pin["id"], pin["media_type"])          # e.g. "image", "video", "gif"
    print(pin["images"]["orig"]["url"])          # original image URL
    if pin.get("video"):
        print(pin["video"]["formats"])           # list of MP4 / HLS variants

# --- Download media to disk ---
dl = p.download_pin("1098174690415756357", path="./downloads")
if dl["ok"]:
    print("Saved:", dl["path"], dl["media_type"])

# --- Search ---
search = p.search("cute cats", page_size=10)
if search["ok"]:
    for pin in search["pins"]:
        print(pin["id"], pin["media_type"], pin.get("title"))

# --- Profile & boards ---
profile = p.get_profile("pinterest")
board   = p.get_board("https://www.pinterest.com/pinterest/dream-dorm-room-inspo/")
```

All methods return a **dictionary** with an `"ok"` key:

- `"ok": True` → success payload
- `"ok": False` → `"error": {"message": "…"}`  

The library **never raises exceptions** for expected failures (invalid URL, missing pin, HTTP errors, etc.).

---

## API Reference

### Constructor

```python
Pinterest(headers=None, timeout=30, proxies=None)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `headers` | `dict` | `None` | Extra HTTP headers merged into the session |
| `timeout` | `int/float` | `30` | Request timeout in seconds |
| `proxies` | `dict` | `None` | Proxies passed to `requests` (e.g. `{"https": "http://…"}`) |

A modern Chrome User-Agent is used by default.

---

### `get_pin(url_or_id)`

Fetch full metadata for a single pin.

**Accepts:** full pin URL, `pin.it` short link, or numeric pin ID.

**Success response (simplified):**

```python
{
    "ok": True,
    "pin": {
        "id": "1098174690415756357",
        "title": "...",
        "description": "...",
        "url": "https://www.pinterest.com/pin/1098174690415756357/",
        "external_link": "https://...",
        "media_type": "image" | "video" | "gif",
        "images": {
            "orig":  {"url": "https://i.pinimg.com/originals/...", "width": 1080, "height": 1920},
            "736x":  {"url": "...", "width": 736, "height": 1308},
            "474x":  {"url": "...", "width": 474, "height": 842},
            # ... other sizes (236x, 170x, 60x60, …)
        },
        "video": {                          # only when media_type == "video"
            "formats": [
                {"url": "https://v1.pinimg.com/..._720w.mp4", "quality": "V_720P", ...},
                {"url": "https://...m3u8", "quality": "V_HLSV4", ...},
            ],
            "mp4_available": True,
            "poster": "https://i.pinimg.com/..."
        },
        "created_at": "Mon, 17 Aug 2026 17:47:49 +0000",
        "author": {
            "id": "...",
            "username": "...",
            "full_name": "...",
            "image_url": "..."
        },
        "board": {
            "id": "...",
            "name": "...",
            "url": "https://www.pinterest.com/user/board/"
        },
        "engagement": {...},
        "source": {...},                    # when available
        "attribution": {...},               # when available
        "embed": {...}                      # when available
    },
    "media": {
        "type": "image",
        "url": "https://i.pinimg.com/originals/...",
        "video_formats": [...],             # when video
        "poster": "..."
    },
    "author": {...},
    "board": {...},
    "engagement": {...}
}
```

**Error example:**

```python
{"ok": False, "error": {"message": "Cannot extract pin ID from URL"}}
# or
{"ok": False, "error": {"message": "HTTP 404"}}
```

---

### `download_pin(url_or_id, path=".")`

Download the highest-quality media of a pin to disk.

- **Images / GIFs** → original resolution
- **Videos** → highest-quality MP4 when available, otherwise poster image
- File is named `<pin_id>.<ext>`

**Success response:**

```python
{
    "ok": True,
    "path": "./1098174690415756357.jpg",
    "filename": "1098174690415756357.jpg",
    "url": "https://i.pinimg.com/originals/...",
    "media_type": "image"
}
```

---

### `download_board(url_or_id, path=".", limit=None)`

Download media for every pin on a board (walks all pages).  
Pass `limit` to stop after N successful downloads.

**Success response:**

```python
{
    "ok": True,
    "board": {"id": "...", "name": "..."},
    "downloaded": 25,
    "failed": 0,
    "total_pins": 25,
    "files": ["./123.jpg", "./456.mp4", ...]
}
```

---

### `search(query, page_size=25, bookmark=None, scope="pins")`

Paginated keyword search.

```python
result = p.search("cute cats", page_size=10)
# result["pins"]  → list of pin objects (same shape as get_pin["pin"])
# result["bookmark"] → pass to the next call for page 2
```

---

### `search_all(query, max_pages=5)`

Convenience wrapper that walks up to `max_pages` pages and returns all pins.

```python
result = p.search_all("mountain landscape", max_pages=2)
# result["pins"] → combined list
```

---

### `search_boards(query, page_size=25, bookmark=None)`

Search public boards by keyword.

```python
result = p.search_boards("interior design", page_size=10)
# result["boards"] → list of board summaries
```

---

### `get_profile(identifier)`

**Accepts:** username, profile URL, or user ID.

```python
{
    "ok": True,
    "profile": {
        "id": "...",
        "username": "pinterest",
        "full_name": "...",
        "bio": "...",
        "follower_count": 6259592,
        "following_count": ...,
        "pin_count": ...,
        "board_count": ...,
        "image_url": "...",
        ...
    },
    "boards": [ ... ]   # summary list of the user’s boards
}
```

---

### `get_boards(identifier)`

Full detailed list of boards belonging to a user.

```python
{
    "ok": True,
    "username": "pinterest",
    "boards": [
        {
            "id": "...",
            "name": "...",
            "description": "...",
            "privacy": "public",
            "pin_count": 463,
            "cover_url": "...",
            "board_url": "https://www.pinterest.com/username/board-name/",
            "owner": {"id": "...", "username": "..."}
        },
        ...
    ]
}
```

---

### `get_board(url)`

Retrieve a specific board (URL required) plus the owner’s full board list.

```python
{
    "ok": True,
    "board": {
        "id": "...",
        "name": "Dream dorm room inspo",
        "pin_count": 84,
        "follower_count": ...,
        "cover_url": "...",
        "board_url": "...",
        ...
    },
    "user": {"username": "...", "id": "...", "full_name": "..."},
    "boards": [ ... ]   # all boards of the same user
}
```

---

### `get_board_pins(url_or_id, page_size=25, bookmark=None)`

Paginated list of pins belonging to a board.

```python
result = p.get_board_pins("https://www.pinterest.com/pinterest/dream-dorm-room-inspo/", page_size=25)
# result["pins"], result["bookmark"]
```

---

### `get_user_pins(username, page_size=25, bookmark=None)`

Paginated list of pins created by a user.

```python
result = p.get_user_pins("pinterest", page_size=10)
```

---

## Error Handling

Every public method returns a dict. Always check `"ok"`:

```python
result = p.get_pin("https://example.com/not-a-pin")
if not result["ok"]:
    print(result["error"]["message"])
    # → "Cannot extract pin ID from URL"
```

Common error messages:

| Situation | Typical message |
|-----------|-----------------|
| Non-pin / malformed URL | `Cannot extract pin ID from URL` |
| Pin / resource not found | `HTTP 404` |
| Network / timeout | underlying requests message |
| No downloadable media | `No downloadable media for this pin` |

The library itself does **not** raise exceptions for these cases.

---

## Examples

### Download every image from a search

```python
from pinterest_downloader import Pinterest
import os

p = Pinterest(timeout=40)
os.makedirs("cats", exist_ok=True)

result = p.search("cute cats", page_size=15)
if result["ok"]:
    for pin in result["pins"]:
        if pin.get("media_type") == "image":
            p.download_pin(pin["id"], path="cats")
```

### Download a whole board (first 20 pins)

```python
p.download_board(
    "https://www.pinterest.com/pinterest/dream-dorm-room-inspo/",
    path="./board_downloads",
    limit=20
)
```

### Resolve short links and videos

```python
r = p.get_pin("https://pin.it/s5n05C0UK")
if r["ok"] and r["pin"]["media_type"] == "video":
    for fmt in r["pin"]["video"]["formats"]:
        print(fmt.get("quality"), fmt.get("url"))
```

---

## Notes & Limitations

- Works with **public** Pinterest content only.
- Relies on Pinterest’s public resource endpoints; future site changes may require updates.
- Media URLs (especially videos) may have limited lifetime — download promptly if you need the files offline.
- Rate limiting / anti-bot behaviour is not aggressively handled; use reasonable delays for large scrapes.
- Concurrent use of a single `Pinterest` instance is generally fine for moderate workloads, but creating separate instances is safer for heavy parallelism.

---

## Development

```bash
git clone https://github.com/x7007x/PinterestDownloader.git
cd PinterestDownloader
pip install -e .
python3 test_live.py   # live smoke tests (requires network)
```

---

## License

MIT © Ahmed Negm

---

## Links

- **PyPI:** https://pypi.org/project/pinterest-downloader/
- **Repository:** https://github.com/x7007x/PinterestDownloader
- **Issues:** https://github.com/x7007x/PinterestDownloader/issues
