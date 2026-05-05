```markdown
# pinterest-downloader v3

Unofficial library to download and interact with Pinterest content. No API key required.

## Install

```bash
pip install pinterest-downloader
```

Dependencies: requests, beautifulsoup4 (automatically installed).

Quick Start

```python
from pinterest_downloader import Pinterest

p = Pinterest()

# Get a pin (image / video / gif)
pin = p.get_pin("https://pin.it/xxxxx")
if pin["ok"]:
    print(pin["pin"]["media_type"])  # "image", "video", or "gif"

# Get user profile
profile = p.get_profile("username_or_url_or_id")

# Get board info
board = p.get_board("https://www.pinterest.com/username/board-name/")

# Search for pins
result = p.search("cute cats")
for pin in result["pins"]:
    print(pin["id"], pin["media_type"])
```

All functions return a dictionary with an "ok" key (True on success, False on error). If "ok" is False, an "error" key contains a message.

Available Methods

get_pin(url_or_id)

Retrieves all available data for a single pin.

Accepts: full pin URL, short pin.it link, or numeric pin ID.

Returns:

```python
{
    "ok": True,
    "pin": {
        "id": "123456789",
        "title": "...",
        "description": "...",
        "url": "https://www.pinterest.com/pin/123456789/",
        "source_url": "https://...",
        "external_link": "https://...",
        "media_type": "image" | "video" | "gif",
        "images": {
            "170x": {"url": "...", "width": 236, "height": 132},
            "236x": {"url": "...", "width": 236, "height": 132},
            "474x": {"url": "...", "width": 474, "height": 266},
            "736x": {"url": "...", "width": 736, "height": 414},
            "orig": {"url": "...", "width": 1200, "height": 675}
        },
        "created_at": "Thu, 30 Oct 2025 04:39:43 +0000",
        "is_uploaded": False,
        "domain": "...",
        "dominant_color": "#615c67",
        "video": {                        # only for videos
            "formats": [
                {
                    "quality": "V_HLSV3_MOBILE",
                    "url": "https://...",
                    "width": 1920,
                    "height": 1080,
                    "duration": 11378,
                    "thumbnail": "https://..."
                }
            ],
            "mp4_available": False,
            "poster": "https://..."
        },
        "embed": {                        # if available
            "src": "...",
            "width": 290,
            "height": 374,
            "type": "gif"
        },
        "attribution": { ... },           # if available
        "source": {                       # if available
            "url": "...",
            "site_name": "Cheezburger",
            "display_name": "...",
            "type_name": "article"
        }
    },
    "author": {
        "id": "...",
        "username": "...",
        "full_name": "...",
        "image_url": "..."
    },
    "board": {
        "id": "...",
        "name": "...",
        "url": "..."
    },
    "media": {                            # legacy flat media info
        "type": "video",
        "url": "...",
        "video_formats": [...],
        "poster": "..."
    },
    "engagement": {
        "reactions": 96,
        "reactions_detail": {"like": 96},
        "comment_count": 0
    }
}
```

· Reaction labels are descriptive: like, love, wow, funny, etc. (if the API reports them).
· Videos include both HLS (.m3u8) and direct MP4 links when available (mp4_available flag).

search(query, page_size=25, bookmark=None)

Searches for pins and returns a page of results.

Parameters:

· query – search keywords.
· page_size – number of results per page (max 25).
· bookmark – used for pagination; pass the "bookmark" value from a previous response to get the next page.

Returns:

```python
{
    "ok": True,
    "query": "cute cats",
    "bookmark": "Y2JVS...",    # for the next page
    "pins": [
        { ... },               # each pin has the same structure as get_pin() minus the full wrapper
        ...
    ]
}
```

search_all(query, max_pages=5)

Convenience method that fetches multiple pages of search results automatically.

Returns:

```python
{
    "ok": True,
    "query": "cute cats",
    "total": 42,
    "pins": [ ... ]
}
```

get_profile(identifier)

Retrieves a user's public profile and their boards.

Accepts: username, pinterest.com/username URL, or user ID.

Returns:

```python
{
    "ok": True,
    "resolved_url": "https://www.pinterest.com/username/",
    "profile": {
        "username": "...",
        "profile_url": "...",
        "full_name": "...",
        "follower_count": 1193,
        "following_count": 101,
        "pin_count": 480,
        "about": "...",
        "id": "123456789",
        "image_url": "...",
        "website_url": "..."
    },
    "boards": [
        {
            "id": "...",
            "name": "Cute Animals",
            "board_url": "https://www.pinterest.com/username/cute-animals/",
            "cover_url": "..."
        },
        ...
    ]
}
```

get_boards(identifier)

Returns a detailed list of all boards for a user.

Accepts: same as get_profile.

Returns:

```python
{
    "ok": True,
    "resolved_url": "...",
    "username": "...",
    "boards": [
        {
            "id": "...",
            "name": "...",
            "description": "...",
            "category": "...",
            "privacy": "public",
            "pin_count": 463,
            "cover_url": "...",
            "board_url": "https://www.pinterest.com/username/board-name/",
            "owner": {"id": "...", "username": "..."}
        }
    ]
}
```

get_board(url)

Retrieves a specific board and also returns the user's full board list.

Accepts: board URL (required).

Returns:

```python
{
    "ok": True,
    "resolved_url": "...",
    "user": {"username": "...", "id": "...", "full_name": "..."},
    "board_slug": "board-name",
    "board": {
        "id": "...",
        "name": "Board Name",
        "description": "...",
        "category": "...",
        "privacy": "public",
        "pin_count": 25,
        "follower_count": 100,
        "board_url": "...",
        "cover_url": "...",
        "owner": {"username": "...", "id": "..."}
    },
    "boards": [ ... ]   # all user boards
}
```

Error Handling

When something goes wrong, the function returns:

```python
{"ok": False, "error": {"message": "description of the problem"}}
```

No exceptions are raised by the library itself. Always check the "ok" key.

License

MIT — Ahmed Negm

```