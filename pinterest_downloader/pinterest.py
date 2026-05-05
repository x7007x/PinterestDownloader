import re
import json
import html
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

    def search(self, query, page_size=25, bookmark=None):
        url = f"{self.BASE_URL}/resource/BaseSearchResource/get/"
        payload = {
            "source_url": f"/search/pins/?q={query}",
            "data": json.dumps({
                "options": {
                    "query": query,
                    "scope": "pins",
                    "page_size": page_size,
                    "bookmarks": [bookmark] if bookmark else []
                },
                "context": {}
            })
        }
        headers = {
            "X-Pinterest-PWS-Handler": "www/[username]/search/pins.js",
            "User-Agent": self.DEFAULT_HEADERS["User-Agent"]
        }
        try:
            resp = self.session.get(url, params=payload, headers=headers, timeout=self.timeout, proxies=self.proxies)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return {"ok": False, "error": str(e)}

        resource_response = data.get("resource_response", {})
        if not resource_response.get("status") == "success":
            return {"ok": False, "error": resource_response.get("message", "Unknown error")}

        results = resource_response.get("data", {}).get("results", [])
        next_bookmark = resource_response.get("bookmark")

        pins = []
        for pin_data in results:
            if not isinstance(pin_data, dict):
                continue

            pin_id = self._val(pin_data.get("id"))
            if not pin_id:
                continue

            title = self._val(pin_data.get("title") or pin_data.get("grid_title"))
            description = self._val(pin_data.get("description"))
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
            if not original_url and images:
                last = list(images.values())[-1]
                original_url = last.get("url")

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
                top_videos = pin_data.get("videos", {})
                if isinstance(top_videos, dict):
                    vlist = top_videos.get("video_list") or top_videos.get("videoUrls") or {}
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
                    "title": self._val(raw_att.get("title")),
                    "author_name": self._val(raw_att.get("author_name")),
                    "author_url": self._val(raw_att.get("author_url")),
                    "provider_name": self._val(raw_att.get("provider_name")),
                    "provider_icon_url": self._val(raw_att.get("provider_icon_url"), True)
                }

            source = None
            rich = pin_data.get("rich_summary")
            if isinstance(rich, dict):
                source = {
                    "url": self._val(rich.get("url")),
                    "site_name": self._val(rich.get("site_name")),
                    "display_name": self._val(rich.get("display_name")),
                    "type_name": self._val(rich.get("type_name"))
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

            if video_formats:
                mp4_formats = [f for f in video_formats if f.get("url", "").endswith(".mp4")]
                hls_formats = [f for f in video_formats if not f.get("url", "").endswith(".mp4")]
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

    def get_profile(self, identifier):
        username = self._extract_username(identifier)
        if not username:
            return {"ok": False, "error": {"message": "Invalid identifier"}}
        try:
            resp = self.session.get(f"{self.BASE_URL}/{username}/", timeout=self.timeout, proxies=self.proxies)
            resp.raise_for_status()
        except requests.RequestException as e:
            return {"ok": False, "error": {"message": str(e)}}

        soup = BeautifulSoup(resp.text, "html.parser")
        tag = soup.find("script", id="__PWS_INITIAL_PROPS__")
        redux = json.loads(tag.get_text().strip()).get("initialReduxState", {}) if tag else {}

        profile = {"username": username, "profile_url": f"{self.BASE_URL}/{username}/"}
        users = redux.get("users", {}) or {}
        uid, udata = next(((k, v) for k, v in users.items() if isinstance(v, dict) and v.get("username") == username), (None, {}))
        if not udata:
            uid, udata = next(((k, v) for k, v in users.items() if isinstance(v, dict) and v.get("type") == "user"), (None, {}))

        if udata:
            for k in ["full_name", "follower_count", "following_count", "pin_count", "about", "website_url"]:
                profile[k] = udata.get(k)
            profile["id"] = str(uid) if uid else None
            profile["image_url"] = self._val(udata.get("image_medium_url"), True)

        if not profile.get("id"):
            ld_tag = soup.find("script", attrs={"data-test-id": "profile-snippet", "type": "application/ld+json"})
            if ld_tag:
                try:
                    ld = json.loads(ld_tag.get_text().strip()).get("mainEntity", {})
                    profile["full_name"] = ld.get("name", profile.get("full_name"))
                    img = ld.get("image", {})
                    if isinstance(img, dict):
                        profile["image_url"] = img.get("contentUrl")
                except Exception:
                    pass

        boards = []
        for bid, bdata in (redux.get("boards", {}) or {}).items():
            if isinstance(bdata, dict) and bdata.get("name"):
                b_url = bdata.get("url")
                boards.append({
                    "id": str(bid),
                    "name": bdata.get("name"),
                    "board_url": f"{self.BASE_URL}{b_url}" if b_url else f"{self.BASE_URL}/{username}/{bdata['name'].lower().replace(' ', '-')}/",
                    "cover_url": self._val(bdata.get("image_cover_url"), True)
                })

        return self._clean({
            "ok": True,
            "resolved_url": resp.url,
            "profile": profile,
            "boards": boards
        })

    def get_boards(self, identifier):
        username = self._extract_username(identifier)
        if not username:
            return {"ok": False, "error": {"message": "Invalid identifier"}}
        try:
            resp = self.session.get(f"{self.BASE_URL}/{username}/", timeout=self.timeout, proxies=self.proxies)
            resp.raise_for_status()
        except requests.RequestException as e:
            return {"ok": False, "error": {"message": str(e)}}

        soup = BeautifulSoup(resp.text, "html.parser")
        tag = soup.find("script", id="__PWS_INITIAL_PROPS__")
        redux = json.loads(tag.get_text().strip()).get("initialReduxState", {}) if tag else {}

        boards = []
        for bid, bdata in (redux.get("boards", {}) or {}).items():
            if not isinstance(bdata, dict) or not bdata.get("name"):
                continue
            b_url = bdata.get("url")
            board_url = f"{self.BASE_URL}{b_url}" if b_url else f"{self.BASE_URL}/{username}/{bdata['name'].lower().replace(' ', '-').replace('_', '-')}/"
            owner = bdata.get("owner", {})
            boards.append({
                "id": str(bid),
                "name": bdata.get("name"),
                "description": bdata.get("description"),
                "category": bdata.get("category"),
                "privacy": bdata.get("privacy"),
                "pin_count": bdata.get("pin_count"),
                "cover_url": self._val(bdata.get("image_cover_url") or bdata.get("image_cover_hd_url"), True),
                "board_url": board_url,
                "owner": {"id": str(owner.get("id")) if owner.get("id") else None, "username": owner.get("username")}
            })

        return self._clean({
            "ok": True,
            "resolved_url": resp.url,
            "username": username,
            "boards": boards
        })

    def get_board(self, url):
        try:
            resp = self.session.get(url, timeout=self.timeout, proxies=self.proxies)
            resp.raise_for_status()
        except requests.RequestException as e:
            return {"ok": False, "error": {"message": str(e)}}

        path_parts = [p for p in urlparse(resp.url).path.strip("/").split("/") if p]
        if not path_parts:
            return {"ok": False, "error": {"message": "Invalid URL"}}
        username = path_parts[0]
        board_slug = path_parts[1] if len(path_parts) >= 2 else None

        soup = BeautifulSoup(resp.text, "html.parser")
        tag = soup.find("script", id="__PWS_INITIAL_PROPS__")
        redux = json.loads(tag.get_text().strip()).get("initialReduxState", {}) if tag else {}

        users = redux.get("users", {}) or {}
        uid, udata = next(((k, v) for k, v in users.items() if isinstance(v, dict) and v.get("username") == username), (None, {}))
        user_profile = {"username": username, "id": str(uid) if uid else None, "full_name": udata.get("full_name") if udata else None}

        boards = []
        board = None
        for bid, bdata in (redux.get("boards", {}) or {}).items():
            if not isinstance(bdata, dict) or not bdata.get("name"):
                continue
            b_url = bdata.get("url")
            b_slug = bdata["name"].lower().replace(" ", "-").replace("_", "-")
            entry = {
                "id": str(bid),
                "name": bdata.get("name"),
                "description": bdata.get("description"),
                "category": bdata.get("category"),
                "privacy": bdata.get("privacy"),
                "pin_count": bdata.get("pin_count"),
                "follower_count": bdata.get("follower_count"),
                "board_url": f"{self.BASE_URL}{b_url}" if b_url else f"{self.BASE_URL}/{username}/{b_slug}/",
                "cover_url": self._val(bdata.get("image_cover_url"), True),
                "owner": {"username": username, "id": user_profile["id"]}
            }
            boards.append(entry)
            if board_slug and (b_slug == board_slug.lower() or str(bid) == board_slug):
                board = entry

        if not board and boards:
            board = boards[0]

        return self._clean({
            "ok": True,
            "resolved_url": resp.url,
            "user": user_profile,
            "board_slug": board_slug,
            "board": board,
            "boards": boards
        })

    def get_pin(self, url):
        pin_id = None
        m = re.search(r'/pin/(\d+)', url)
        if m:
            pin_id = m.group(1)
        else:
            try:
                resp = self.session.head(url, allow_redirects=True, timeout=self.timeout, proxies=self.proxies)
                m = re.search(r'/pin/(\d+)', resp.url)
                if m:
                    pin_id = m.group(1)
            except:
                pass
        if not pin_id:
            return {"ok": False, "error": {"message": "Cannot extract pin ID from URL"}}

        try:
            resp = self.session.get(url, timeout=self.timeout, proxies=self.proxies)
            resp.raise_for_status()
            final_url = resp.url
        except requests.RequestException as e:
            return {"ok": False, "error": {"message": str(e)}}

        soup = BeautifulSoup(resp.text, "html.parser")
        tag = soup.find("script", id="__PWS_INITIAL_PROPS__")
        if not tag:
            return {"ok": False, "error": {"message": "No data found"}}
        try:
            data = json.loads(tag.get_text().strip())
        except Exception:
            return {"ok": False, "error": {"message": "Failed to parse JSON"}}

        redux = data.get("initialReduxState", {})
        pins = redux.get("pins", {})
        pin_data = pins.get(pin_id)
        if not pin_data:
            for key, val in pins.items():
                if isinstance(val, dict) and str(val.get("id")) == pin_id:
                    pin_data = val
                    break
        if not pin_data:
            return {"ok": False, "error": {"message": "Pin not found in page data"}}

        title = self._val(pin_data.get("title") or pin_data.get("grid_title"))
        description = self._val(pin_data.get("description"))
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
        if not original_url and images:
            for size_key in ["736x", "474x", "236x"]:
                u = images.get(size_key, {}).get("url")
                if u:
                    original_url = u
                    break

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
                "title": self._val(raw_att.get("title")),
                "author_name": self._val(raw_att.get("author_name")),
                "author_url": self._val(raw_att.get("author_url")),
                "provider_name": self._val(raw_att.get("provider_name")),
                "provider_icon_url": self._val(raw_att.get("provider_icon_url"), True)
            }

        source = None
        rich = pin_data.get("rich_summary")
        if isinstance(rich, dict):
            source = {
                "url": self._val(rich.get("url")),
                "site_name": self._val(rich.get("site_name")),
                "display_name": self._val(rich.get("display_name")),
                "type_name": self._val(rich.get("type_name"))
            }

        pin_obj = {
            "id": pin_id,
            "title": title,
            "description": description,
            "url": f"{self.BASE_URL}/pin/{pin_id}/",
            "source_url": final_url,
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

        if video_formats:
            mp4_formats = [f for f in video_formats if f.get("url", "").endswith(".mp4")]
            hls_formats = [f for f in video_formats if not f.get("url", "").endswith(".mp4")]
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

        return self._clean({
            "ok": True,
            "pin": pin_obj,
            "author": author,
            "board": board,
            "media": {
                "type": media_type,
                "url": original_url,
                "video_formats": video_formats if video_formats else None,
                "poster": video_poster
            },
            "engagement": engagement
        })