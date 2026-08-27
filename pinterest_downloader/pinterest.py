import os
import re
import json
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup

REACTION_LABELS = {
    "1": "like",
    "2": "love",
    "3": "applause",
    "4": "surprised",
    "5": "good_idea",
    "6": "wow",
    "7": "funny",
    "8": "thanks",
}


def _slugify(name):
    return str(name).lower().replace(" ", "-").replace("_", "-").strip("-")


class Pinterest:
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Upgrade-Insecure-Requests": "1",
    }
    BASE_URL = "https://www.pinterest.com"
    RESOURCE_URL = f"{BASE_URL}/resource"

    def __init__(self, headers=None, timeout=30, proxies=None):
        self.timeout = timeout
        self.proxies = proxies
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)
        if headers:
            self.session.headers.update(headers)

    def _clean(self, data):
        if isinstance(data, dict):
            cleaned = {k: self._clean(v) for k, v in data.items() if v is not None and v != "" and v != " "}
            return {k: v for k, v in cleaned.items() if not (isinstance(v, (dict, list)) and len(v) == 0)}
        if isinstance(data, list):
            filtered = [self._clean(x) for x in data if x is not None and x != "" and x != " "]
            return [x for x in filtered if not (isinstance(x, (dict, list)) and len(x) == 0)]
        if isinstance(data, str) and not data.strip():
            return None
        return data

    def _val(self, v, is_url=False):
        t = str(v).strip() if v is not None else None
        if not t or t in {"\u200c", "\u200f", "\ufeff", ""}:
            return None
        if is_url and t.startswith("//"):
            return f"https:{t}"
        return t

    def _text(self, value):
        """Normalize a value Pinterest may return as a plain string or a dict
        (e.g. {\"args\": [...], \"text\": \"...\"})."""
        if isinstance(value, dict):
            text = value.get("text")
            if text:
                return self._val(text)
            args = value.get("args") or []
            joined = " ".join(str(a) for a in args if a)
            return self._val(joined)
        return self._val(value)

    def _extract_username(self, identifier):
        if not identifier:
            return None
        if identifier.startswith("http://") or identifier.startswith("https://"):
            path = urlparse(identifier).path.strip("/")
            parts = [p for p in path.split("/") if p]
            if parts:
                return parts[0]
            return None
        m = re.search(r"^/?([a-zA-Z0-9._-]+)/?$", identifier.strip("/"))
        if m:
            return m.group(1)
        return identifier

    def _parse_reactions(self, reaction_counts):
        if not isinstance(reaction_counts, dict):
            return {}
        result = {}
        total = 0
        for key, count in reaction_counts.items():
            if isinstance(count, (int, float)):
                label = REACTION_LABELS.get(key, f"type_{key}")
                result[label] = count
                total += count
        result["total"] = total
        return result

    def _api(self, endpoint, options, source_url, handler):
        """Call a Pinterest resource API endpoint.

        Returns (True, resource_response) on success or (False, error_message)
        on failure. The resource response contains the payload under "data"
        plus metadata such as the search "bookmark".
        """
        url = f"{self.RESOURCE_URL}/{endpoint}/"
        params = {
            "source_url": source_url,
            "data": json.dumps({"options": options, "context": {}}),
        }
        headers = {
            "X-Pinterest-PWS-Handler": handler,
            "User-Agent": self.DEFAULT_HEADERS["User-Agent"],
        }
        try:
            resp = self.session.get(url, params=params, headers=headers, timeout=self.timeout, proxies=self.proxies)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            return False, f"HTTP {status}"
        except Exception as e:
            return False, str(e)

        resource_response = data.get("resource_response", {})
        if not resource_response.get("status") == "success":
            error = resource_response.get("message")
            if not error:
                error = (resource_response.get("error") or {}).get("message")
            return False, error or "Unknown error"
        return True, resource_response

    # ------------------------------------------------------------------
    # Pin parsing (shared by search() and get_pin())
    # ------------------------------------------------------------------
    def _parse_pin(self, pin_data, source_url=None):
        if not isinstance(pin_data, dict):
            return None

        pin_id = self._val(pin_data.get("id"))
        if not pin_id:
            return None

        title = self._text(pin_data.get("title") or pin_data.get("grid_title"))
        description = self._text(pin_data.get("description") or pin_data.get("closeup_description"))
        created_at = self._val(pin_data.get("created_at"))
        external_link = self._val(pin_data.get("link"))
        is_uploaded = pin_data.get("is_uploaded")
        domain = self._val(pin_data.get("domain"))
        dominant_color = self._val(pin_data.get("dominant_color"))
        comment_count = pin_data.get("comment_count", 0)

        images = {}
        raw_images = pin_data.get("images", {})
        if isinstance(raw_images, dict):
            for size_key, img_obj in raw_images.items():
                if isinstance(img_obj, dict):
                    img_url = self._val(img_obj.get("url"), True)
                    if img_url:
                        images[size_key] = {
                            "url": img_url,
                            "width": img_obj.get("width"),
                            "height": img_obj.get("height")
                        }

        orig = images.get("orig", {})
        original_url = orig.get("url") if orig else None
        if not original_url:
            for size_key in ["736x", "474x", "236x", "170x"]:
                u = images.get(size_key, {}).get("url")
                if u:
                    original_url = u
                    break
        if not original_url and images:
            original_url = list(images.values())[-1].get("url")

        media_type = "image"
        video_formats = []
        video_poster = None

        story = pin_data.get("story_pin_data", {})
        if isinstance(story, dict):
            pages = story.get("pages", [])
            for page in pages:
                for block in page.get("blocks", []):
                    if block.get("block_type") == 3:
                        video = block.get("video", {})
                        vlist = video.get("video_list", {})
                        for vkey, vobj in vlist.items():
                            if isinstance(vobj, dict):
                                vurl = self._val(vobj.get("url"), True)
                                if vurl:
                                    video_formats.append({
                                        "quality": vkey,
                                        "url": vurl,
                                        "width": vobj.get("width"),
                                        "height": vobj.get("height"),
                                        "duration": vobj.get("duration"),
                                        "thumbnail": self._val(vobj.get("thumbnail"), True)
                                    })
                                    if not video_poster:
                                        video_poster = self._val(vobj.get("thumbnail"), True)
            if video_formats:
                media_type = "video"

        if not video_formats:
            videos = pin_data.get("videos", {})
            if isinstance(videos, dict):
                vlist = videos.get("video_list") or videos.get("videoUrls") or {}
                for vkey, vobj in vlist.items():
                    if isinstance(vobj, dict):
                        vurl = self._val(vobj.get("url"), True)
                        if vurl:
                            video_formats.append({
                                "quality": vkey,
                                "url": vurl,
                                "width": vobj.get("width"),
                                "height": vobj.get("height"),
                                "duration": vobj.get("duration"),
                                "thumbnail": self._val(vobj.get("thumbnail"), True)
                            })
                            if not video_poster:
                                video_poster = self._val(vobj.get("thumbnail"), True)
            if video_formats:
                media_type = "video"

        if media_type == "image" and original_url and original_url.lower().endswith(".gif"):
            media_type = "gif"

        pinner = pin_data.get("pinner", {})
        author = {
            "id": self._val(pinner.get("id")),
            "username": self._val(pinner.get("username")),
            "full_name": self._val(pinner.get("full_name")),
            "image_url": self._val(pinner.get("image_medium_url") or pinner.get("image_large_url"), True)
        }

        board_data = pin_data.get("board", {})
        board = {
            "id": self._val(board_data.get("id")),
            "name": self._val(board_data.get("name")),
            "url": f"{self.BASE_URL}{board_data.get('url')}" if board_data.get("url") else None
        }

        reactions = self._parse_reactions(pin_data.get("reaction_counts", {}))
        engagement = {
            "reactions": reactions.get("total", 0),
            "reactions_detail": reactions,
            "comment_count": comment_count
        }

        embed = None
        raw_embed = pin_data.get("embed")
        if isinstance(raw_embed, dict):
            embed = {
                "src": self._val(raw_embed.get("src"), True),
                "width": raw_embed.get("width"),
                "height": raw_embed.get("height"),
                "type": raw_embed.get("type")
            }

        attribution = None
        raw_att = pin_data.get("attribution")
        if isinstance(raw_att, dict):
            attribution = {
                "title": self._text(raw_att.get("title")),
                "author_name": self._text(raw_att.get("author_name")),
                "author_url": self._val(raw_att.get("author_url")),
                "provider_name": self._text(raw_att.get("provider_name")),
                "provider_icon_url": self._val(raw_att.get("provider_icon_url"), True)
            }

        source = None
        rich = pin_data.get("rich_summary") or pin_data.get("rich_metadata")
        if isinstance(rich, dict):
            source = {
                "url": self._val(rich.get("url")),
                "site_name": self._text(rich.get("site_name")),
                "display_name": self._text(rich.get("display_name")),
                "type_name": self._text(rich.get("type_name"))
            }

        pin_obj = {
            "id": pin_id,
            "title": title,
            "description": description,
            "url": f"{self.BASE_URL}/pin/{pin_id}/",
            "external_link": external_link,
            "media_type": media_type,
            "images": images,
            "created_at": created_at,
            "author": author,
            "board": board,
            "engagement": engagement,
            "is_uploaded": is_uploaded,
            "domain": domain,
            "dominant_color": dominant_color
        }
        if source_url:
            pin_obj["source_url"] = source_url

        if video_formats:
            mp4_formats = [f for f in video_formats if f.get("url", "").endswith(".mp4")]
            pin_obj["video"] = {
                "formats": video_formats,
                "mp4_available": bool(mp4_formats),
                "poster": video_poster or original_url
            }
        if embed:
            pin_obj["embed"] = embed
        if attribution:
            pin_obj["attribution"] = attribution
        if source:
            pin_obj["source"] = source

        return pin_obj

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def search(self, query, page_size=25, bookmark=None, scope="pins"):
        """Search for pins (scope="pins") or videos (scope="videos")."""
        if scope == "boards":
            return self.search_boards(query, page_size=page_size, bookmark=bookmark)
        source_url = f"/search/{scope}/?q={query}" if scope != "pins" else f"/search/pins/?q={query}"
        options = {
            "query": query,
            "scope": scope,
            "page_size": page_size,
            "bookmarks": [bookmark] if bookmark else []
        }
        ok, resource_response = self._api(
            "BaseSearchResource/get",
            options,
            source_url,
            "www/[username]/search/pins.js",
        )
        if not ok:
            return {"ok": False, "error": {"message": resource_response}}

        data = resource_response.get("data", {}) if isinstance(resource_response, dict) else {}
        results = data.get("results", []) if isinstance(data, dict) else []
        next_bookmark = resource_response.get("bookmark") if isinstance(resource_response, dict) else None

        pins = []
        for pin_data in results:
            pin_obj = self._parse_pin(pin_data)
            if pin_obj:
                pins.append(pin_obj)

        return self._clean({
            "ok": True,
            "query": query,
            "bookmark": next_bookmark,
            "pins": pins
        })

    def search_all(self, query, max_pages=5):
        all_pins = []
        bookmark = None
        for _ in range(max_pages):
            result = self.search(query, bookmark=bookmark)
            if not result.get("ok"):
                break
            all_pins.extend(result.get("pins", []))
            bookmark = result.get("bookmark")
            if not bookmark:
                break
        return {"ok": True, "query": query, "total": len(all_pins), "pins": all_pins}

    # ------------------------------------------------------------------
    # Profiles & boards (HTML profile page + resource API fallbacks)
    # ------------------------------------------------------------------
    def _fetch_profile_page(self, username):
        """Fetch a profile page and pull the embedded user + boards data.

        Returns (user_data, raw_boards, resolved_url, error).
        """
        try:
            resp = self.session.get(f"{self.BASE_URL}/{username}/", timeout=self.timeout, proxies=self.proxies)
            resp.raise_for_status()
        except requests.RequestException as e:
            return None, {}, None, {"message": str(e)}

        soup = BeautifulSoup(resp.text, "html.parser")
        tag = soup.find("script", id="__PWS_INITIAL_PROPS__")
        redux = json.loads(tag.get_text().strip()).get("initialReduxState", {}) if tag else {}

        users = redux.get("users", {}) or {}
        user_data = next((v for v in users.values() if isinstance(v, dict) and v.get("username") == username), None)
        if not user_data:
            user_data = next((v for v in users.values() if isinstance(v, dict) and v.get("type") == "user"), None)

        raw_boards = redux.get("boards", {}) or {}
        return user_data, raw_boards, resp.url, None

    def _format_board_simple(self, bid, bdata, username):
        b_url = bdata.get("url")
        return {
            "id": str(bid),
            "name": bdata.get("name"),
            "board_url": f"{self.BASE_URL}{b_url}" if b_url else f"{self.BASE_URL}/{username}/{_slugify(bdata['name'])}/",
            "cover_url": self._val(bdata.get("image_cover_url") or bdata.get("image_cover_hd_url"), True)
        }

    def _format_board_detailed(self, bid, bdata, username):
        b_url = bdata.get("url")
        owner = bdata.get("owner", {}) or {}
        return {
            "id": str(bid),
            "name": bdata.get("name"),
            "description": bdata.get("description"),
            "category": bdata.get("category"),
            "privacy": bdata.get("privacy"),
            "pin_count": bdata.get("pin_count"),
            "follower_count": bdata.get("follower_count"),
            "cover_url": self._val(bdata.get("image_cover_url") or bdata.get("image_cover_hd_url"), True),
            "board_url": f"{self.BASE_URL}{b_url}" if b_url else f"{self.BASE_URL}/{username}/{_slugify(bdata['name'])}/",
            "owner": {
                "id": str(owner.get("id")) if owner.get("id") else None,
                "username": owner.get("username")
            }
        }

    def get_profile(self, identifier):
        username = self._extract_username(identifier)
        if not username:
            return {"ok": False, "error": {"message": "Invalid identifier"}}

        user_data, raw_boards, resolved_url, page_error = self._fetch_profile_page(username)

        if not user_data:
            ok, resource_response = self._api(
                "UserResource/get",
                {"username": username, "field_set_key": "profile"},
                f"/{username}/",
                "www/[username].js",
            )
            if not ok:
                if page_error:
                    return {"ok": False, "error": page_error}
                return {"ok": False, "error": {"message": "User not found"}}
            user_data = resource_response.get("data") or {}
            if not resolved_url:
                resolved_url = f"{self.BASE_URL}/{username}/"

        boards = [
            self._format_board_simple(bid, bdata, username)
            for bid, bdata in raw_boards.items()
            if isinstance(bdata, dict) and bdata.get("name")
        ]

        profile = {
            "username": username,
            "profile_url": f"{self.BASE_URL}/{username}/",
            "full_name": user_data.get("full_name"),
            "follower_count": user_data.get("follower_count"),
            "following_count": user_data.get("following_count"),
            "pin_count": user_data.get("pin_count"),
            "about": user_data.get("about"),
            "id": str(user_data.get("id")) if user_data.get("id") else None,
            "image_url": self._val(user_data.get("image_medium_url") or user_data.get("image_large_url"), True),
            "website_url": self._val(user_data.get("website_url") or user_data.get("domain_url"))
        }

        return self._clean({
            "ok": True,
            "resolved_url": resolved_url,
            "profile": profile,
            "boards": boards
        })

    def get_boards(self, identifier):
        username = self._extract_username(identifier)
        if not username:
            return {"ok": False, "error": {"message": "Invalid identifier"}}

        user_data, raw_boards, resolved_url, page_error = self._fetch_profile_page(username)

        if not user_data and not raw_boards:
            ok, _ = self._api(
                "UserResource/get",
                {"username": username, "field_set_key": "profile"},
                f"/{username}/",
                "www/[username].js",
            )
            if not ok:
                if page_error:
                    return {"ok": False, "error": page_error}
                return {"ok": False, "error": {"message": "User not found"}}

        boards = [
            self._format_board_detailed(bid, bdata, username)
            for bid, bdata in raw_boards.items()
            if isinstance(bdata, dict) and bdata.get("name")
        ]

        return self._clean({
            "ok": True,
            "resolved_url": resolved_url or f"{self.BASE_URL}/{username}/",
            "username": username,
            "boards": boards
        })

    def get_board(self, url):
        if not isinstance(url, str) or not url.startswith("http://") and not url.startswith("https://"):
            return {"ok": False, "error": {"message": "Invalid URL"}}

        path_parts = [p for p in urlparse(url).path.strip("/").split("/") if p]
        if len(path_parts) < 2:
            return {"ok": False, "error": {"message": "Invalid URL"}}
        username = path_parts[0]
        board_slug = path_parts[1]

        user_data, raw_boards, resolved_url, page_error = self._fetch_profile_page(username)

        boards = []
        board = None
        for bid, bdata in raw_boards.items():
            if not isinstance(bdata, dict) or not bdata.get("name"):
                continue
            entry = self._format_board_detailed(bid, bdata, username)
            boards.append(entry)
            b_url = bdata.get("url") or ""
            b_slug = _slugify(bdata["name"])
            if (b_url and b_url.rstrip("/").endswith(f"/{board_slug}")) or b_slug == board_slug.lower() or str(bid) == board_slug:
                board = entry

        if not user_data and not boards:
            ok, _ = self._api(
                "UserResource/get",
                {"username": username, "field_set_key": "profile"},
                f"/{username}/",
                "www/[username].js",
            )
            if not ok:
                if page_error:
                    return {"ok": False, "error": page_error}
                return {"ok": False, "error": {"message": "User not found"}}

        if not board:
            # Board wasn't in the profile page's embedded list (large accounts).
            # Try resolving it directly by owner slug.
            ok, resource_response = self._api(
                "BoardResource/get",
                {"slug": board_slug, "username": username, "field_set_key": "board"},
                f"/{username}/{board_slug}/",
                "www/[username]/[board_slug].js",
            )
            data = resource_response.get("data") if isinstance(resource_response, dict) else None
            if not ok or not isinstance(data, dict):
                return {"ok": False, "error": {"message": "Board not found"}}
            owner = data.get("owner", {}) or {}
            board = {
                "id": str(data.get("id")) if data.get("id") else None,
                "name": data.get("name"),
                "description": data.get("description"),
                "category": data.get("category"),
                "privacy": data.get("privacy"),
                "pin_count": data.get("pin_count"),
                "follower_count": data.get("follower_count"),
                "cover_url": self._val(data.get("image_cover_url") or data.get("image_cover_hd_url"), True),
                "board_url": f"{self.BASE_URL}{data.get('url')}" if data.get("url") else url.rstrip("/") + "/",
                "owner": {
                    "id": str(owner.get("id")) if owner.get("id") else None,
                    "username": owner.get("username")
                }
            }

        user_profile = {
            "username": username,
            "id": str(user_data.get("id")) if user_data and user_data.get("id") else None,
            "full_name": user_data.get("full_name") if user_data else None
        }

        return self._clean({
            "ok": True,
            "resolved_url": resolved_url or url,
            "user": user_profile,
            "board_slug": board_slug,
            "board": board,
            "boards": boards
        })

    # ------------------------------------------------------------------
    # Board search & feeds
    # ------------------------------------------------------------------
    def _parse_board(self, board_data):
        """Parse a board dict (e.g. from search results) into a clean board."""
        if not isinstance(board_data, dict):
            return None
        board_id = self._val(board_data.get("id"))
        if not board_id:
            return None
        owner = board_data.get("owner", {}) or {}
        b_url = board_data.get("url")
        cover = self._val(board_data.get("image_cover_url") or board_data.get("image_cover_hd_url"), True)
        if not cover:
            images = board_data.get("images", {})
            if isinstance(images, dict):
                for size_key in ["orig", "736x", "474x", "236x"]:
                    img = images.get(size_key)
                    if isinstance(img, list) and img:
                        cover = self._val(img[0].get("url"), True)
                    elif isinstance(img, dict) and img.get("url"):
                        cover = self._val(img["url"], True)
                    if cover:
                        break
        return {
            "id": board_id,
            "name": self._text(board_data.get("name")),
            "description": self._text(board_data.get("description")),
            "url": f"{self.BASE_URL}{b_url}" if b_url else None,
            "pin_count": board_data.get("pin_count"),
            "follower_count": board_data.get("follower_count"),
            "cover_url": cover,
            "owner": {
                "id": self._val(owner.get("id")),
                "username": self._val(owner.get("username")),
                "full_name": self._val(owner.get("full_name"))
            }
        }

    def search_boards(self, query, page_size=25, bookmark=None):
        """Search for boards instead of pins."""
        options = {
            "query": query,
            "scope": "boards",
            "page_size": page_size,
            "bookmarks": [bookmark] if bookmark else []
        }
        ok, resource_response = self._api(
            "BaseSearchResource/get",
            options,
            f"/search/boards/?q={query}",
            "www/[username]/search/boards.js",
        )
        if not ok:
            return {"ok": False, "error": {"message": resource_response}}

        data = resource_response.get("data", {}) if isinstance(resource_response, dict) else {}
        results = data.get("results", []) if isinstance(data, dict) else []
        next_bookmark = resource_response.get("bookmark") if isinstance(resource_response, dict) else None

        boards = []
        for board_data in results:
            board = self._parse_board(board_data)
            if board:
                boards.append(board)

        return self._clean({
            "ok": True,
            "query": query,
            "bookmark": next_bookmark,
            "boards": boards
        })

    def _resolve_board_meta(self, url_or_id):
        """Resolve a board URL or numeric board ID.

        Returns (board_id, board_meta, source_url, error).
        """
        if str(url_or_id).isdigit():
            board_id = str(url_or_id)
            ok, resource_response = self._api(
                "BoardResource/get",
                {"board_id": board_id, "field_set_key": "board"},
                f"/{board_id}/",
                "www/[username]/[board_slug].js",
            )
            data = resource_response.get("data") if isinstance(resource_response, dict) else None
            if not ok or not isinstance(data, dict):
                return None, None, None, "Board not found"
            b_url = data.get("url") or ""
            parts = [p for p in b_url.strip("/").split("/") if p]
            board_meta = {
                "id": str(data.get("id")) if data.get("id") else board_id,
                "name": data.get("name"),
                "url": f"{self.BASE_URL}{b_url}" if b_url else None,
            }
            return board_id, board_meta, b_url or f"/{board_id}/", None

        if not isinstance(url_or_id, str) or not (url_or_id.startswith("http://") or url_or_id.startswith("https://")):
            return None, None, None, "Invalid URL"
        path_parts = [p for p in urlparse(url_or_id).path.strip("/").split("/") if p]
        if len(path_parts) < 2:
            return None, None, None, "Invalid URL"
        username, board_slug = path_parts[0], path_parts[1]

        user_data, raw_boards, resolved_url, page_error = self._fetch_profile_page(username)
        for bid, bdata in raw_boards.items():
            if not isinstance(bdata, dict) or not bdata.get("name"):
                continue
            b_url = bdata.get("url") or ""
            b_slug = _slugify(bdata["name"])
            if (b_url and b_url.rstrip("/").endswith(f"/{board_slug}")) or b_slug == board_slug.lower() or str(bid) == board_slug:
                return str(bid), self._format_board_detailed(bid, bdata, username), f"/{username}/{board_slug}/", None

        ok, resource_response = self._api(
            "BoardResource/get",
            {"slug": board_slug, "username": username, "field_set_key": "board"},
            f"/{username}/{board_slug}/",
            "www/[username]/[board_slug].js",
        )
        data = resource_response.get("data") if isinstance(resource_response, dict) else None
        if not ok or not isinstance(data, dict):
            return None, None, None, "Board not found"
        b_url = data.get("url") or f"/{username}/{board_slug}/"
        board_meta = {
            "id": str(data.get("id")) if data.get("id") else None,
            "name": data.get("name"),
            "url": f"{self.BASE_URL}{b_url}" if data.get("url") else url_or_id,
        }
        return board_meta["id"], board_meta, b_url, None

    def get_board_pins(self, url_or_id, page_size=25, bookmark=None):
        """Retrieve the pins saved to a board (paginated with a bookmark).

        Accepts a board URL (https://www.pinterest.com/username/board-name/)
        or a numeric board ID.
        """
        board_id, board, source_url, error = self._resolve_board_meta(url_or_id)
        if error:
            return {"ok": False, "error": {"message": error}}

        ok, resource_response = self._api(
            "BoardFeedResource/get",
            {
                "board_id": board_id,
                "page_size": page_size,
                "bookmarks": [bookmark] if bookmark else [],
            },
            source_url,
            "www/[username]/[board_slug].js",
        )
        if not ok:
            return {"ok": False, "error": {"message": resource_response}}

        data = resource_response.get("data", []) if isinstance(resource_response, dict) else []
        results = data if isinstance(data, list) else []
        pins = []
        for pin_data in results:
            pin_obj = self._parse_pin(pin_data)
            if pin_obj:
                pins.append(pin_obj)
        next_bookmark = resource_response.get("bookmark") if isinstance(resource_response, dict) else None

        return self._clean({
            "ok": True,
            "board": board,
            "bookmark": next_bookmark,
            "pins": pins
        })

    def get_user_pins(self, username, page_size=25, bookmark=None):
        """Retrieve the pins created by a user (paginated with a bookmark)."""
        username = self._extract_username(username)
        if not username:
            return {"ok": False, "error": {"message": "Invalid identifier"}}

        ok, resource_response = self._api(
            "UserPinsResource/get",
            {
                "username": username,
                "page_size": page_size,
                "bookmarks": [bookmark] if bookmark else [],
            },
            f"/{username}/",
            "www/[username].js",
        )
        if not ok:
            if "404" in str(resource_response):
                return {"ok": False, "error": {"message": "User not found"}}
            return {"ok": False, "error": {"message": resource_response}}

        data = resource_response.get("data", []) if isinstance(resource_response, dict) else []
        results = data if isinstance(data, list) else []
        pins = []
        for pin_data in results:
            pin_obj = self._parse_pin(pin_data)
            if pin_obj:
                pins.append(pin_obj)
        next_bookmark = resource_response.get("bookmark") if isinstance(resource_response, dict) else None

        return self._clean({
            "ok": True,
            "username": username,
            "bookmark": next_bookmark,
            "pins": pins
        })

    # ------------------------------------------------------------------
    # Media downloads
    # ------------------------------------------------------------------
    def _download_file(self, url, dest_dir, filename):
        try:
            os.makedirs(dest_dir, exist_ok=True)
            resp = self.session.get(url, stream=True, timeout=self.timeout, proxies=self.proxies)
            resp.raise_for_status()
            filepath = os.path.join(dest_dir, filename)
            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
            return True, filepath
        except Exception as e:
            return False, str(e)

    def download_pin(self, url_or_id, path="."):
        """Download a pin's media (original image, GIF, or MP4 video) to disk.

        Saves the file as <pin_id>.<ext> inside `path`.
        """
        result = self.get_pin(url_or_id)
        if not result.get("ok"):
            return result
        pin = result["pin"]

        media_url = None
        media_type = pin.get("media_type")
        if media_type == "video":
            formats = (pin.get("video") or {}).get("formats") or []
            mp4s = [f for f in formats if f.get("url", "").lower().endswith(".mp4")]
            if mp4s:
                media_url = mp4s[0]["url"]
            else:
                media_url = (pin.get("video") or {}).get("poster")
        else:
            images = pin.get("images", {})
            for size_key in ["orig", "736x", "474x", "236x"]:
                media_url = images.get(size_key, {}).get("url")
                if media_url:
                    break

        if not media_url:
            return {"ok": False, "error": {"message": "No downloadable media for this pin"}}

        ext = os.path.splitext(urlparse(media_url).path)[1]
        if not ext:
            ext = ".mp4" if media_type == "video" else ".jpg"
        filename = f"{pin['id']}{ext}"
        ok, filepath_or_error = self._download_file(media_url, path, filename)
        if not ok:
            return {"ok": False, "error": {"message": filepath_or_error}}

        return {
            "ok": True,
            "path": filepath_or_error,
            "filename": filename,
            "url": media_url,
            "media_type": media_type
        }

    def download_board(self, url_or_id, path=".", limit=None):
        """Download the media of every pin in a board.

        Iterates all pages of the board feed; `limit` caps the number of
        pins downloaded.
        """
        board_id, board, source_url, error = self._resolve_board_meta(url_or_id)
        if error:
            return {"ok": False, "error": {"message": error}}

        downloaded = []
        failed = []
        files = []
        bookmark = None
        while True:
            page = self.get_board_pins(board_id, bookmark=bookmark)
            if not page.get("ok"):
                break
            for pin in page.get("pins", []):
                if limit is not None and len(downloaded) >= limit:
                    break
                dl = self.download_pin(pin["id"], path)
                if dl.get("ok"):
                    downloaded.append(pin["id"])
                    files.append(dl.get("path"))
                else:
                    failed.append(pin["id"])
            bookmark = page.get("bookmark")
            if not bookmark or (limit is not None and len(downloaded) >= limit):
                break

        return self._clean({
            "ok": True,
            "board": board,
            "downloaded": len(downloaded),
            "failed": len(failed),
            "total_pins": len(downloaded) + len(failed),
            "files": files
        })

    # ------------------------------------------------------------------
    # Single pin
    # ------------------------------------------------------------------
    def get_pin(self, url):
        pin_id = None
        m = re.search(r"/pin/(\d+)", str(url))
        if m:
            pin_id = m.group(1)
        elif re.fullmatch(r"\d+", str(url).strip()):
            pin_id = str(url).strip()
        else:
            # Resolve short links (pin.it) and other redirects.
            # Prefer HEAD; fall back to GET when HEAD does not yield a pin path
            # (some pin.it responses behave differently on HEAD vs GET).
            for method in ("head", "get"):
                try:
                    resp = getattr(self.session, method)(
                        url, allow_redirects=True, timeout=self.timeout, proxies=self.proxies
                    )
                    m = re.search(r"/pin/(\d+)", resp.url)
                    if m:
                        pin_id = m.group(1)
                        break
                except Exception:
                    continue
        if not pin_id:
            return {"ok": False, "error": {"message": "Cannot extract pin ID from URL"}}

        ok, resource_response = self._api(
            "PinResource/get",
            {"id": pin_id, "field_set_key": "detailed"},
            f"/pin/{pin_id}/",
            "www/[username]/pin.js",
        )
        if not ok:
            return {"ok": False, "error": {"message": resource_response}}

        pin_obj = self._parse_pin(resource_response.get("data"))
        if not pin_obj:
            return {"ok": False, "error": {"message": "Pin not found in page data"}}

        original_url = pin_obj.get("images", {}).get("orig", {}).get("url")
        if not original_url:
            for size_key in ["736x", "474x", "236x"]:
                original_url = pin_obj.get("images", {}).get(size_key, {}).get("url")
                if original_url:
                    break
        video_formats = (pin_obj.get("video") or {}).get("formats") if pin_obj.get("video") else None

        return self._clean({
            "ok": True,
            "pin": pin_obj,
            "author": pin_obj.get("author"),
            "board": pin_obj.get("board"),
            "media": {
                "type": pin_obj.get("media_type"),
                "url": original_url,
                "video_formats": video_formats,
                "poster": (pin_obj.get("video") or {}).get("poster")
            },
            "engagement": pin_obj.get("engagement")
        })
