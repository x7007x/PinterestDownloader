# pinterest-downloader v3

Pinterest data extractor. No API key required. No dependencies.

## Install

```bash
pip install pinterest-downloader
```

## Quick Start

```python
from pinterest_downloader import Pinterest

p = Pinterest()

# Auto-detect URL type
result = p.get("https://pin.it/xxxxx")
# {"type": "pin", "data": {...}}

# Get pin data (image / video / gif)
pin = p.get_pin("https://www.pinterest.com/pin/123456/")

# Get user profile + boards
user = p.get_user("https://www.pinterest.com/username/")

# Get board info
board = p.get_board("https://www.pinterest.com/username/board-name/")

# Search
results = p.search("cute cats")
```

## Pin Types

| Type | Fields |
|------|--------|
| `image` | `default_image`, `images` |
| `video` | `default_video`, `default_image`, `videos`, `images` |
| `gif` | `gif_url`, `default_image`, `images` |

## Pin Response

```python
{
    "pin_id": "123456",
    "type": "video",
    "title": "...",
    "description": "...",
    "created_at": "...",
    "domain": "...",
    "dominant_color": "#hex",
    "repin_count": 100,
    "total_saves": 500,
    "categories": ["Art"],
    "visual_annotations": ["..."],
    "creator": {"name": "...", "username": "...", "entity_id": "...", "image": "..."},
    "pinner": {"name": "...", "username": "...", "entity_id": "...", "image": "..."},
    "board": {"name": "...", "url": "...", "entity_id": "..."},
    "default_image": "https://...",
    "default_video": "https://...",
    "gif_url": "https://...",
    "images": {"236x": "...", "474x": "...", "736x": "...", "orig": "..."},
    "videos": [{"quality": "v720P", "url": "...", "width": 720, "height": 720, "duration_ms": 9000}],
}
```

## User Response

```python
{
    "user_id": "...",
    "username": "...",
    "full_name": "...",
    "about": "...",
    "follower_count": 100,
    "following_count": 50,
    "pin_count": 200,
    "board_count": 5,
    "created_at": "...",
    "profile_images": {"small": "...", "medium": "...", "large": "..."},
    "profile_cover": {"originals": "...", "736x": "..."},
    "boards": [{"name": "...", "pin_count": 10, "url": "..."}],
}
```

## Board Response

```python
{
    "board_id": "...",
    "name": "...",
    "url": "...",
    "pin_count": 23,
    "follower_count": 100,
    "cover_images": {"200x150": "..."},
    "preview_images": ["...", "..."],
    "owner": {"name": "...", "username": "..."},
}
```

## Exceptions

```python
from pinterest_downloader import (
    PinterestError,
    PinNotFoundError,
    UserNotFoundError,
    BoardNotFoundError,
    SearchError,
    InvalidURLError,
)
```

## Supported URLs

- `https://pin.it/xxxxx`
- `https://www.pinterest.com/pin/123456/`
- `https://www.pinterest.com/username/`
- `https://www.pinterest.com/username/board-name/`
- `https://www.pinterest.com/search/pins/?q=query`

## License

MIT — Ahmed Nagm
