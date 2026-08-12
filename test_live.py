"""Live smoke-test of every public method in the library."""
import json
import sys

from pinterest_downloader import Pinterest

p = Pinterest(timeout=40)
results = {}


def report(name, result, expect_ok=True):
    ok = result.get("ok", False)
    status = "PASS" if ok == expect_ok else "FAIL"
    print(f"\n=== {name}: ok={ok} [{status}] ===")
    if not ok:
        print("ERROR:", json.dumps(result.get("error"), indent=2)[:400])
    else:
        summary = {k: v for k, v in result.items() if k not in ("pins", "boards")}
        print("KEYS:", sorted(summary.keys()))
        if "pins" in result:
            pins = result["pins"]
            print("PIN COUNT:", len(pins))
            for pin in pins[:3]:
                print("  pin:", pin.get("id"), "|", pin.get("media_type"), "|", (pin.get("title") or "")[:60])
                print("    images sizes:", sorted(pin.get("images", {}).keys())[:8])
                if pin.get("video"):
                    v = pin["video"]
                    print("    video:", [f.get("quality") for f in v.get("formats", [])][:6], "| mp4:", v.get("mp4_available"))
        if "profile" in result:
            prof = result["profile"]
            print("PROFILE:", prof.get("username"), "| id:", prof.get("id"), "| followers:", prof.get("follower_count"), "| pins:", prof.get("pin_count"))
            print("  boards:", len(result.get("boards", [])))
        if "boards" in result:
            print("BOARD COUNT:", len(result["boards"]))
            for b in result["boards"][:3]:
                print("  board:", b.get("id"), "|", b.get("name"), "| pins:", b.get("pin_count"))
        if "board" in result and result.get("board"):
            b = result["board"]
            print("BOARD:", b.get("id"), "|", b.get("name"), "| pins:", b.get("pin_count"), "| followers:", b.get("follower_count"), "| url:", b.get("board_url"))
            print("  other boards in profile:", len(result.get("boards", [])))
        if "pin" in result:
            pin = result["pin"]
            print("PIN:", pin.get("id"), "|", pin.get("media_type"), "|", (pin.get("title") or "")[:60])
            print("  images sizes:", sorted(pin.get("images", {}).keys())[:8])
            print("  author:", pin.get("author", {}).get("username"))
            print("  board:", pin.get("board", {}).get("name"))
            if pin.get("video"):
                v = pin["video"]
                print("  video:", [f.get("quality") for f in v.get("formats", [])][:6], "| mp4:", v.get("mp4_available"))
            if pin.get("source"):
                print("  source:", pin["source"].get("site_name"))
    results[name] = (ok == expect_ok)


# --- happy paths ---
report("search('cute cats')", p.search("cute cats", page_size=10))

r = p.search("cute cats", page_size=10)
if r.get("ok") and r.get("bookmark"):
    report("search page 2 (bookmark)", p.search("cute cats", page_size=10, bookmark=r["bookmark"]))
else:
    print("\n=== search page 2: no bookmark returned ===")
    results["search page 2 (bookmark)"] = False

report("search_all('mountain landscape', max_pages=2)", p.search_all("mountain landscape", max_pages=2))

report("get_profile('pinterest')", p.get_profile("pinterest"))
report("get_boards('pinterest')", p.get_boards("pinterest"))
report("get_board('https://www.pinterest.com/pinterest/dream-dorm-room-inspo/')", p.get_board("https://www.pinterest.com/pinterest/dream-dorm-room-inspo/"))

# image pin from search results
pin = None
s = p.search("cute cats", page_size=5)
if s.get("ok") and s.get("pins"):
    pin = s["pins"][0]
if pin:
    report(f"get_pin(image) {pin.get('url')}", p.get_pin(pin.get("url")))
    report(f"get_pin(numeric id) {pin.get('id')}", p.get_pin(pin.get("id")))
else:
    print("\n=== get_pin: no search pin available ===")
    results["get_pin(image)"] = False
    results["get_pin(numeric id)"] = False

# video pin via search
video_pin = None
sv = p.search("cute dog video", page_size=10)
if sv.get("ok"):
    video_pin = next((x for x in sv["pins"] if x.get("media_type") == "video"), None)
if video_pin:
    report(f"get_pin(video) {video_pin.get('url')}", p.get_pin(video_pin.get("url")))
else:
    print("\n=== get_pin(video): no video pin found ===")
    results["get_pin(video)"] = False

# --- expected failure paths ---
report("get_profile(nonexistent user) -> error", p.get_profile("this-user-should-not-exist-xyz"), expect_ok=False)
report("get_board(nonexistent board) -> error", p.get_board("https://www.pinterest.com/pinterest/this-board-does-not-exist-zzz/"), expect_ok=False)
report("get_pin(bad url) -> error", p.get_pin("https://example.com/not-a-pin"), expect_ok=False)

print("\n\n===== SUMMARY =====")
fails = []
for k, v in results.items():
    print(("PASS" if v else "FAIL"), "-", k)
    if not v:
        fails.append(k)
print("\nFAILURES:", fails if fails else "none")
sys.exit(1 if fails else 0)
