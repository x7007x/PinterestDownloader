import re
import json
import urllib.request
import urllib.error
import urllib.parse
import http.cookiejar
from .exceptions import (
    PinNotFoundError,
    UserNotFoundError,
    BoardNotFoundError,
    SearchError,
    InvalidURLError,
)


class Pinterest:

    def __init__(self, user_agent=None, timeout=30):
        self._ua = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self._timeout = timeout
        self._cj = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._cj))

    def _fetch(self, url):
        req = urllib.request.Request(url, headers={
            "User-Agent": self._ua,
            "Accept-Language": "en-US,en;q=0.9",
        })
        try:
            resp = self._opener.open(req, timeout=self._timeout)
            return resp.url, resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.status in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                return self._fetch(e.headers["Location"])
            raise

    def _clean(self, data):
        if isinstance(data, dict):
            cleaned = {}
            for k, v in data.items():
                v = self._clean(v)
                if v is not None:
                    cleaned[k] = v
            return cleaned if cleaned else None
        elif isinstance(data, list):
            cleaned = [self._clean(i) for i in data if self._clean(i) is not None]
            return cleaned if cleaned else None
        elif isinstance(data, str):
            return data.strip() if data.strip() else None
        else:
            return data

    def _resolve(self, url):
        if "pin.it" in url:
            url, _ = self._fetch(url)
        return url

    def _get_relay_pin(self, html):
        for match in re.finditer(r'window\.__PWS_RELAY_REGISTER_COMPLETED_REQUEST__\("[^"]*",\s*(\{.*?\})\)', html):
            try:
                block = json.loads(match.group(1))
                query = block.get("data", {}).get("v3GetPinQuery")
                if query:
                    return query.get("data", query)
            except json.JSONDecodeError:
                continue
        return None

    def _get_redux_state(self, html):
        for m in re.finditer(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.DOTALL):
            try:
                d = json.loads(m.group(1))
                if "initialReduxState" in d:
                    return d["initialReduxState"]
            except json.JSONDecodeError:
                continue
        return None

    def _extract_images(self, data):
        images = {}
        for key, val in data.items():
            if key.startswith("images_") and isinstance(val, dict) and val.get("url"):
                images[key.replace("images_", "")] = val["url"]
        if data.get("imageLargeUrl"):
            images["1200x"] = data["imageLargeUrl"]
        return images if images else None

    def _extract_videos(self, data):
        story = data.get("storyPinData") or {}
        videos = []
        for page in story.get("pages") or []:
            for block in page.get("blocks") or []:
                if block.get("__typename") != "StoryPinVideoBlock":
                    continue
                for list_val in (block.get("videoDataV2") or {}).values():
                    if not isinstance(list_val, dict):
                        continue
                    for qk, qv in list_val.items():
                        if not isinstance(qv, dict) or not qv.get("url"):
                            continue
                        videos.append({
                            "quality": qk,
                            "url": qv["url"],
                            "thumbnail": qv.get("thumbnail"),
                            "width": qv.get("width"),
                            "height": qv.get("height"),
                            "duration_ms": qv.get("duration"),
                        })
        return videos if videos else None

    def _extract_embed(self, data):
        embed = data.get("embed")
        if not embed or not embed.get("src"):
            return None
        return {"type": embed.get("type"), "url": embed.get("src")}

    def _format_user_short(self, data):
        if not data:
            return None
        return {
            "name": data.get("fullName") or data.get("full_name") or data.get("firstName") or data.get("first_name"),
            "username": data.get("username"),
            "entity_id": data.get("entityId") or data.get("id"),
            "image": data.get("imageLargeUrl") or data.get("imageMediumUrl") or data.get("image_medium_url"),
        }

    def _detect_type(self, url):
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.rstrip("/")
        parts = [p for p in path.split("/") if p]
        if re.search(r"/pin/\d+", url):
            return "pin"
        elif re.search(r"/search/", url):
            return "search"
        elif len(parts) == 1 and parts[0] not in ("search", "pin", "settings", "password"):
            return "user"
        elif len(parts) >= 2 and parts[0] not in ("search", "pin", "settings", "password") and not parts[1].startswith("_"):
            return "board"
        return None

    def get(self, url):
        url = self._resolve(url)
        url_type = self._detect_type(url)
        if url_type == "pin":
            return {"type": "pin", "data": self.get_pin(url)}
        elif url_type == "search":
            m = re.search(r"[?&]q=([^&]+)", url)
            query = urllib.parse.unquote_plus(m.group(1)) if m else ""
            return {"type": "search", "data": self.search(query)}
        elif url_type == "user":
            return {"type": "user", "data": self.get_user(url)}
        elif url_type == "board":
            return {"type": "board", "data": self.get_board(url)}
        raise InvalidURLError(f"Unknown URL type: {url}")

    def get_pin(self, url):
        url = self._resolve(url)
        m = re.search(r"/pin/(\d+)", url)
        if not m:
            raise InvalidURLError(f"Could not extract pin ID from: {url}")
        _, html = self._fetch(f"https://www.pinterest.com/pin/{m.group(1)}/")
        pin = self._get_relay_pin(html)
        if not pin:
            raise PinNotFoundError(f"Pin not found: {m.group(1)}")

        images = self._extract_images(pin)
        videos = self._extract_videos(pin)
        embed = self._extract_embed(pin)
        creator = pin.get("nativeCreator") or pin.get("closeupAttribution") or {}
        origin = pin.get("originPinner") or {}
        pinner = pin.get("pinner") or {}
        board = pin.get("board") or {}
        agg = (pin.get("aggregatedPinData") or {}).get("aggregatedStats") or {}
        pin_join = pin.get("pinJoin") or {}

        is_gif = embed and embed.get("type") == "gif"
        orig_url = (pin.get("images_orig") or {}).get("url")

        default_video = None
        if videos:
            mp4s = [v for v in videos if v["url"].endswith(".mp4")]
            default_video = mp4s[0]["url"] if mp4s else videos[0]["url"]

        result = {
            "pin_id": pin.get("entityId"),
            "created_at": pin.get("createdAt"),
            "title": pin.get("title") or pin.get("gridTitle"),
            "description": (pin.get("description") or "").strip(),
            "domain": pin.get("domain"),
            "link": pin.get("link"),
            "dominant_color": pin.get("dominantColor"),
            "repin_count": pin.get("repinCount"),
            "total_saves": agg.get("saves"),
            "categories": [b.get("name") for b in (pin_join.get("seoBreadcrumbs") or [])],
            "visual_annotations": pin_join.get("visualAnnotation"),
            "creator": self._clean(self._format_user_short(creator) or self._format_user_short(origin)),
            "pinner": self._clean(self._format_user_short(pinner)),
            "board": {
                "name": board.get("name"),
                "url": board.get("url"),
                "entity_id": board.get("entityId"),
                "is_collaborative": board.get("isCollaborative"),
            },
            "type": "gif" if is_gif else ("video" if videos else "image"),
            "default_image": orig_url or (images or {}).get("originals") or (images or {}).get("736x"),
            "default_video": default_video,
            "gif_url": embed.get("url") if is_gif else None,
            "images": images,
            "videos": videos,
            "image_signature": pin.get("imageSignature"),
        }
        return self._clean(result)

    def get_user(self, url):
        url = self._resolve(url)
        if not re.search(r"pinterest\.com/[^/]+/?$", url):
            m = re.search(r"pinterest\.com/([^/?]+)", url)
            if m:
                url = f"https://www.pinterest.com/{m.group(1)}/"
        _, html = self._fetch(url)
        state = self._get_redux_state(html)
        if not state:
            raise UserNotFoundError("Could not find user data.")

        user_data = None
        for uid, u in state.get("users", {}).items():
            if u.get("username"):
                user_data = u
                break
        if not user_data:
            raise UserNotFoundError("Could not find user data.")

        boards = []
        for bid, b in state.get("boards", {}).items():
            if not b.get("name"):
                continue
            boards.append({
                "id": b.get("id"),
                "name": b.get("name"),
                "url": b.get("url"),
                "description": (b.get("description") or "").strip(),
                "pin_count": b.get("pin_count"),
                "follower_count": b.get("follower_count"),
                "section_count": b.get("section_count"),
                "privacy": b.get("privacy"),
                "is_collaborative": b.get("is_collaborative"),
                "cover_image": (b.get("cover_images") or {}).get("200x150", {}).get("url"),
                "created_at": b.get("created_at"),
            })

        cover = user_data.get("profile_cover") or {}
        cover_images = {k: v.get("url") for k, v in (cover.get("images") or {}).items() if isinstance(v, dict) and v.get("url")}

        result = {
            "user_id": user_data.get("id"),
            "username": user_data.get("username"),
            "full_name": user_data.get("full_name"),
            "first_name": user_data.get("first_name"),
            "about": (user_data.get("about") or "").strip(),
            "website_url": user_data.get("website_url"),
            "domain_url": user_data.get("domain_url"),
            "domain_verified": user_data.get("domain_verified"),
            "is_verified_merchant": user_data.get("is_verified_merchant"),
            "is_partner": user_data.get("is_partner"),
            "is_private_profile": user_data.get("is_private_profile"),
            "created_at": user_data.get("created_at"),
            "follower_count": user_data.get("follower_count"),
            "following_count": user_data.get("following_count"),
            "pin_count": user_data.get("pin_count"),
            "board_count": user_data.get("board_count"),
            "last_pin_save_time": user_data.get("last_pin_save_time"),
            "profile_images": {
                "small": user_data.get("image_small_url"),
                "medium": user_data.get("image_medium_url"),
                "large": user_data.get("image_xlarge_url"),
            },
            "profile_cover": cover_images,
            "eligible_profile_tabs": [t.get("name") for t in (user_data.get("eligible_profile_tabs") or [])],
            "boards": boards,
        }
        return self._clean(result)

    def get_board(self, url):
        url = self._resolve(url)
        _, html = self._fetch(url)
        state = self._get_redux_state(html)
        if not state:
            raise BoardNotFoundError("Could not find board data.")

        board_data = None
        for bid, b in state.get("boards", {}).items():
            if b.get("name"):
                board_data = b
                break
        if not board_data:
            raise BoardNotFoundError("Could not find board data.")

        owner = board_data.get("owner") or {}
        cover = board_data.get("cover_images") or {}

        result = {
            "board_id": board_data.get("id"),
            "name": board_data.get("name"),
            "url": board_data.get("url"),
            "description": (board_data.get("description") or "").strip(),
            "privacy": board_data.get("privacy"),
            "layout": board_data.get("layout"),
            "created_at": board_data.get("created_at"),
            "pin_count": board_data.get("pin_count"),
            "follower_count": board_data.get("follower_count"),
            "collaborator_count": board_data.get("collaborator_count"),
            "section_count": board_data.get("section_count"),
            "is_collaborative": board_data.get("is_collaborative"),
            "has_custom_cover": board_data.get("has_custom_cover"),
            "cover_images": {k: v.get("url") for k, v in cover.items() if isinstance(v, dict) and v.get("url")},
            "cover_hd": board_data.get("image_cover_hd_url"),
            "preview_images": [img.get("url") for img in (board_data.get("images", {}).get("170x") or []) if img.get("url")],
            "owner": self._clean(self._format_user_short(owner)),
        }
        return self._clean(result)

    def search(self, query, limit=25):
        self._fetch("https://www.pinterest.com/")
        csrf = ""
        for c in self._cj:
            if c.name == "csrftoken":
                csrf = c.value
        cookies = "; ".join(f"{c.name}={c.value}" for c in self._cj)
        options = {"options": {"query": query, "scope": "pins", "page_size": limit, "bookmarks": []}, "context": {}}
        encoded = urllib.parse.quote(json.dumps(options))
        url = f"https://www.pinterest.com/resource/BaseSearchResource/get/?source_url=%2Fsearch%2Fpins%2F%3Fq%3D{urllib.parse.quote(query)}&data={encoded}"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", self._ua)
        req.add_header("Accept", "application/json, text/javascript, */*, q=0.01")
        req.add_header("X-Requested-With", "XMLHttpRequest")
        req.add_header("X-CSRFToken", csrf)
        req.add_header("X-Pinterest-AppState", "active")
        req.add_header("Cookie", cookies)
        req.add_header("Referer", f"https://www.pinterest.com/search/pins/?q={urllib.parse.quote(query)}")
        try:
            resp = self._opener.open(req, timeout=self._timeout)
            result = json.loads(resp.read().decode())
            data = result.get("resource_response", {}).get("data", {})
            results = data if isinstance(data, list) else data.get("results", [])
            pins = []
            for r in results:
                if not isinstance(r, dict) or not r.get("id"):
                    continue
                pins.append({
                    "pin_id": r.get("id"),
                    "title": r.get("title") or r.get("grid_title"),
                    "description": (r.get("description") or "").strip(),
                    "link": f"https://www.pinterest.com/pin/{r.get('id')}/",
                })
            return self._clean(pins) or []
        except urllib.error.HTTPError:
            raise SearchError(f"Search failed for: {query}")
