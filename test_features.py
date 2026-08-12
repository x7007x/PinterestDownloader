"""Live tests for the new library features."""
import json
import os
import sys
import tempfile

from pinterest_downloader import Pinterest

p = Pinterest(timeout=40)
results = {}


def report(name, result, expect_ok=True):
    ok = result.get("ok", False)
    status = "PASS" if ok == expect_ok else "FAIL"
    print(f"\n=== {name}: ok={ok} [{status}] ===")
    if not ok:
        print("ERROR:", json.dumps(result.get("error"), indent=2)[:300])
    else:
        for k, v in result.items():
            if k == "pins":
                print(f"  pins: {len(v)}")
                for pin in v[:2]:
                    print("    pin:", pin.get("id"), "|", pin.get("media_type"), "|", (pin.get("title") or "")[:40])
            elif k == "boards":
                print(f"  boards: {len(v)}")
                for b in v[:3]:
                    print("    board:", b.get("id"), "|", b.get("name"), "| pins:", b.get("pin_count"), "| owner:", (b.get("owner") or {}).get("username"))
            elif k == "board":
                print("  board:", v.get("id"), "|", v.get("name"))
            elif k == "files":
                print(f"  files ({len(v)}):")
                for f in v[:3]:
                    print("    ", f, "|", os.path.getsize(f) if f and os.path.exists(f) else "MISSING")
            elif k == "path":
                print(f"  saved: {v} ({os.path.getsize(v) if v and os.path.exists(v) else 0} bytes)")
            elif k not in ("ok",):
                print(f"  {k}: {v}")
    results[name] = (ok == expect_ok)


# 1) Board search
report("search_boards('cute cats')", p.search_boards("cute cats", page_size=5))

# 2) Board search pagination
r = p.search_boards("cute cats", page_size=5)
if r.get("ok") and r.get("bookmark"):
    report("search_boards page 2", p.search_boards("cute cats", page_size=5, bookmark=r["bookmark"]))
else:
    print("\n=== search_boards page 2: no bookmark ===")
    results["search_boards page 2"] = False

# 3) Video scope search
report("search('funny cats', scope='videos')", p.search("funny cats", scope="videos", page_size=5))

# 4) Board pins via URL (board owned by homedecor)
report("get_board_pins('https://www.pinterest.com/homedecor/dream-dorm-room-inspo/')",
       p.get_board_pins("https://www.pinterest.com/homedecor/dream-dorm-room-inspo/", page_size=5))

# 5) Board pins via numeric id
report("get_board_pins(887842582730086661)", p.get_board_pins("887842582730086661", page_size=5))

# 6) Board pins pagination
r = p.get_board_pins("887842582730086661", page_size=5)
if r.get("ok") and r.get("bookmark"):
    report("get_board_pins page 2", p.get_board_pins("887842582730086661", page_size=5, bookmark=r["bookmark"]))
else:
    print("\n=== get_board_pins page 2: no bookmark ===")
    results["get_board_pins page 2"] = False

# 7) User pins
report("get_user_pins('pinterest')", p.get_user_pins("pinterest", page_size=5))

# 8) User pins pagination
r = p.get_user_pins("pinterest", page_size=5)
if r.get("ok") and r.get("bookmark"):
    report("get_user_pins page 2", p.get_user_pins("pinterest", page_size=5, bookmark=r["bookmark"]))
else:
    print("\n=== get_user_pins page 2: no bookmark ===")
    results["get_user_pins page 2"] = False

# 9) download_pin (image)
tmp = tempfile.mkdtemp(prefix="pinterest_test_")
report("download_pin(image)", p.download_pin("900438519285436133", path=tmp))

# 10) download_pin (video)
sv = p.search("cute dog video", page_size=10)
video_pin = next((x for x in sv.get("pins", []) if x.get("media_type") == "video"), None)
if video_pin:
    report("download_pin(video)", p.download_pin(video_pin["id"], path=tmp))
else:
    print("\n=== download_pin(video): no video pin found ===")
    results["download_pin(video)"] = False

# 11) download_board (small board, limit 2)
report("download_board(limit=2)", p.download_board("https://www.pinterest.com/homedecor/dream-dorm-room-inspo/", path=tmp, limit=2))

# 12) error path: nonexistent board for feed
report("get_board_pins(bad board) -> error", p.get_board_pins("https://www.pinterest.com/pinterest/this-board-does-not-exist-zzz/"), expect_ok=False)
report("get_user_pins(bad user) -> error", p.get_user_pins("this-user-should-not-exist-xyz"), expect_ok=False)

print("\n\n===== SUMMARY =====")
fails = []
for k, v in results.items():
    print(("PASS" if v else "FAIL"), "-", k)
    if not v:
        fails.append(k)
print("\nFAILURES:", fails if fails else "none")
sys.exit(1 if fails else 0)
