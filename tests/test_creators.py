"""creators.py: video addresses that may be embedded, and what of data/creators.json is let through."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import creators

E = creators.embed
assert E("https://www.youtube.com/watch?v=_KbrQ0PTjlg")["src"] == "https://www.youtube-nocookie.com/embed/_KbrQ0PTjlg?autoplay=1&rel=0"
assert E("https://youtu.be/_KbrQ0PTjlg?si=x")["id"] == "_KbrQ0PTjlg" and not E("https://youtu.be/_KbrQ0PTjlg")["tall"]
assert E("https://www.youtube.com/shorts/3g_UNj5KyS8")["tall"] and E("https://m.youtube.com/shorts/3g_UNj5KyS8")["kind"] == "youtube"
i = E("https://www.instagram.com/reel/DZE-pBygPIr/?igsh=abc")
assert i == {"kind": "instagram", "id": "DZE-pBygPIr", "tall": True, "src": "https://www.instagram.com/reel/DZE-pBygPIr/embed/",
             "watch": "https://www.instagram.com/reel/DZE-pBygPIr/"}, i
assert E("https://instagram.com/p/DZE-pBygPIr/")["src"].endswith("/p/DZE-pBygPIr/embed/")
assert E("https://www.instagram.com/some.user/reel/DZE-pBygPIr/")["id"] == "DZE-pBygPIr"
t = E("https://www.tiktok.com/@nail.artist_1/video/7301234567890123456?is_from_webapp=1")
assert t["src"] == "https://www.tiktok.com/player/v1/7301234567890123456?autoplay=1&rel=0" and t["watch"].startswith("https://www.tiktok.com/@nail.artist_1/video/")
for bad in ("", "not a url", "http://www.youtube.com/watch?v=_KbrQ0PTjlg", "https://www.youtube.com/watch?v=short",
            "https://www.youtube.com/watch?v=_KbrQ0PTjlg\"onload=x", "https://evil.com/watch?v=_KbrQ0PTjlg",
            "https://youtube.com.evil.com/watch?v=_KbrQ0PTjlg", "https://www.instagram.com/someuser/", "https://vm.tiktok.com/ZMabc123/",
            "https://www.tiktok.com/@u/video/12", "https://www.instagram.com/reel/<script>/", "javascript:alert(1)"):
    assert E(bad) is None, bad
for bad in ("https://www.instagram.com/share/reel/BAbcdEFgh1/", "https://www.instagram.com/reels/audio/123456789/",
            "https://www.instagram.com/explore/tags/p/nails/", "https://user@www.youtube.com/watch?v=_KbrQ0PTjlg"):
    assert E(bad) is None, bad
assert E("https://www.youtube.com/watch?v=_KbrQ0PTjlg&t=10s")["id"] == "_KbrQ0PTjlg"
assert not creators.social("youtube", "https://evil.com\\@youtube.com/x") and not creators.social("youtube", "https://youtube.com@evil.com/x")
assert creators.a_date("2026-11-10") == "2026-11-10" and not creators.a_date("0000-00-00") and not creators.a_date("2099-01-01") \
    and not creators.a_date("2026-11-10\n") and not creators.a_date(None)
assert creators.social("instagram", "https://www.instagram.com/nails_by_x/") and not creators.social("instagram", "https://evil.com/x")
assert not creators.social("tiktok", 'https://www.tiktok.com/@x"><script>')

with tempfile.TemporaryDirectory() as d:
    d = Path(d); assets = d / "assets"; (assets / "creators").mkdir(parents=True); (assets / "creators" / "dana.jpg").write_bytes(b"x")
    ok_product = {"slug": "uv-lamp", "id": "1005001234567890", "name": "מנורת UV", "video": "https://www.instagram.com/reel/DZE-pBygPIr/",
                  "text": ["פסקה ראשונה", " "], "text_ok": "2026-11-11", "quote": "המנורה שעל השולחן שלי"}
    data = {"topics": [{"slug": "nails", "name": "ציפורניים"}, {"slug": "guides", "name": "שמור"}, {"slug": "Bad Slug", "name": "x"}],
            "creators": [
                {"slug": "dana", "topic": "nails", "name": "דנה", "tracking": "nails_dana", "videos_ok": "2026-11-10", "photo": "creators/dana.jpg",
                 "instagram": "https://www.instagram.com/dana/", "tiktok": "https://evil.com/dana",
                 "products": [ok_product,
                              {"slug": "gel", "id": "1005001234567891", "name": "לק ג'ל", "text": ["לא אושר"], "quote": "לא אושר"},
                              {"slug": "drill", "id": "1005001234567892", "name": "מקדחה", "video": "https://vm.tiktok.com/ZMabc/"},
                              {"slug": "uv-lamp", "id": "1005001234567893", "name": "כפול"}, {"slug": "x", "id": "abc", "name": "לא מספר"},
                              {"slug": "again", "id": "1005001234567890", "name": "אותו מוצר"}]},
                {"slug": "noa", "topic": "nails", "name": "נועה", "tracking": "nails_noa"},                       # no consent date
                {"slug": "maya", "topic": "nails", "name": "מאיה", "tracking": "nails_dana", "videos_ok": "2026-11-10"},   # another's ID
                {"slug": "tal", "topic": "hair", "name": "טל", "tracking": "hair_tal", "videos_ok": "2026-11-10"},      # no such topic
                {"slug": "shir", "topic": "nails", "name": "שיר", "tracking": "bad id!", "videos_ok": "2026-11-10"}]}
    (d / "creators.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    log = []
    out = creators.load(d / "creators.json", assets, log.append)
    assert [t["slug"] for t in out["topics"]] == ["nails"], out["topics"]
    cs = out["topics"][0]["creators"]
    assert [c["slug"] for c in cs] == ["dana"], [c["slug"] for c in cs]
    c = cs[0]
    assert c["about"] == "" and c["demo"] is False and c["since"] == "2026-11-10"      # no about_ok: the line about her is not shown
    assert c["photo"] == "creators/dana.jpg" and c["links"] == {"instagram": "https://www.instagram.com/dana/"} and c["tracking"] == "nails_dana"
    assert [p["slug"] for p in c["products"]] == ["uv-lamp", "gel", "drill"], [p["slug"] for p in c["products"]]
    lamp, gel, drill = c["products"]
    assert lamp["video"]["kind"] == "instagram" and lamp["text"] == ["פסקה ראשונה"] and lamp["quote"]
    assert gel["text"] == [] and gel["quote"] == "" and gel["video"] is None            # her words only after she approved them
    assert drill["video"] is None                                                        # a short link cannot be embedded
    assert len(log) >= 8, log
    # reserved top-level paths, a newline after a slug, a date that is not one
    data2 = {"topics": [{"slug": s, "name": "x"} for s in ("og", "404", "nails\n", "nails")],
             "creators": [{"slug": "a", "topic": "nails", "name": "א", "tracking": "t_a", "videos_ok": "0000-00-00"},
                          {"slug": "b", "topic": "nails", "name": "ב", "tracking": "t_b", "videos_ok": "2099-01-01"},
                          {"slug": "c", "topic": "nails", "name": "ג", "tracking": "t_c", "videos_ok": "2026-11-10", "about": "מאושר", "about_ok": "2026-11-10",
                           "products": [{"slug": "p", "id": "1005001234567890", "name": "מ", "text": "מחרוזת ולא רשימה", "text_ok": "2026-11-10"}]},
                          {"slug": "d", "topic": "nails", "name": "ד", "tracking": "T_C", "videos_ok": "2026-11-10"},          # same ID in another case
                          {"slug": "demo", "topic": "nails", "demo": True, "name": "דוגמה", "tracking": "nicebuy", "about": "בלי אישור",
                           "products": [{"slug": "p", "id": "1005001234567891", "name": "מ", "text": ["ממלא מקום"], "quote": "ציטוט"}]}]}
    (d / "c2.json").write_text(json.dumps(data2, ensure_ascii=False), encoding="utf-8")
    out2 = creators.load(d / "c2.json", assets, log.append)
    assert [t["slug"] for t in out2["topics"]] == ["nails"]
    cs2 = {c["slug"]: c for c in out2["topics"][0]["creators"]}
    assert set(cs2) == {"c", "demo"}, set(cs2)
    assert cs2["c"]["about"] == "מאושר" and cs2["c"]["products"][0]["text"] == []
    assert cs2["demo"]["demo"] and cs2["demo"]["about"] == "בלי אישור" and cs2["demo"]["products"][0]["text"] == ["ממלא מקום"] and cs2["demo"]["since"] == ""
    for shape in ("[]", "null", '{"topics": ["nails"], "creators": ["x"]}', '{"topics": [{"slug": "nails", "name": "x"}], "creators": [{"slug": "a", "topic": "nails", "name": "x", "tracking": "t_a", "videos_ok": "2026-11-10", "products": {"a": 1}}]}'):
        (d / "shape.json").write_text(shape, encoding="utf-8")
        creators.load(d / "shape.json", assets, log.append)             # must not raise
    assert creators.load(d / "missing.json", assets, log.append) == {"topics": []}
    (d / "broken.json").write_text("{", encoding="utf-8")
    assert creators.load(d / "broken.json", assets, log.append) == {"topics": []}
print("OK")
