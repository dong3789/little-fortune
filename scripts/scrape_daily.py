#!/usr/bin/env python3
"""Daily collector for little-fortune (momyment/little-fortune).

What it collects, every day (KST), without anyone's computer turned on:

1. 띠별 운세 (zodiac-by-birth-year) image from Instagram @sinbi_saju.
   Source: the public profile embed page
   (https://www.instagram.com/sinbi_saju/embed/), which needs no login.
   It lists the latest posts with shortcode, caption and image URL.
   The matching post's image is saved as ``fortunes/YYYY-MM-DD.jpg``
   and its shortcode is recorded in ``fortune-index.json``.
2. 별자리 운세 (12-sign horoscope) from the official Asahi Broadcasting
   (ABC, おはよう朝日です) JSON feed
   (https://www.asahi.co.jp/data/ohaasa2020/horoscope.json),
   translated from Japanese to Korean and appended to
   ``horoscope-editions.json``.

Why this works without rebuilding the site: both pages fetch their data
in the browser (``fetch(..., {cache: "no-store"})``), so updating the
three data files is enough. The committed ``index.html`` /
``horoscope/index.html`` are only the first paint; the client JS
replaces them with the fresh data on load.

No third-party dependencies: standard library only, so the GitHub
Actions runner needs nothing installed.

Translation notes (read scripts/README.md for the full story):
- Lucky items (``lucky``) come from ``glossary.json`` first. It was
  built by aligning the 12 existing human-translated editions with the
  original Japanese, so recurring items keep the site's own wording.
  Unknown items fall back to Google Translate (direct ja -> ko).
- Summaries are also translated with Google Translate, direct ja -> ko
  (one request per sign, not via English). It is still machine
  translation: the Japanese original is kept in ``ja_summary`` /
  ``ja_lucky`` so any awkward line can be traced and fixed by hand.

Exit codes: 0 = collected (or already up to date), 1 = hard error,
2 = today's data not published yet (after waiting).
"""

from __future__ import annotations

import argparse
import datetime as dt
import html as htmlmod
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

KST = dt.timezone(dt.timedelta(hours=9))
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
# Instagram serves different embed markup per User-Agent. The plain
# "Mozilla/5.0" UA returns the server-rendered page that lists recent
# posts (graphql_media); a full Chrome UA returns a JS-heavy page
# without them. Try in order.
IG_UAS = [
    "Mozilla/5.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    UA,
]

IG_USERNAME = "sinbi_saju"
IG_EMBED_URL = f"https://www.instagram.com/{IG_USERNAME}/embed/"
ABC_URL = "https://www.asahi.co.jp/data/ohaasa2020/horoscope.json"

# ABC horoscope_st code -> Korean sign name (verified against the
# 2026-11-24 edition: 04 = かに座 = 게자리 at rank 1, etc.)
SIGN_BY_CODE = {
    "01": "양자리",   # おひつじ座
    "02": "황소자리",  # おうし座
    "03": "쌍둥이자리",  # ふたご座
    "04": "게자리",   # かに座
    "05": "사자자리",  # しし座
    "06": "처녀자리",  # おとめ座
    "07": "천칭자리",  # てんびん座
    "08": "전갈자리",  # さそり座
    "09": "사수자리",  # いて座
    "10": "염소자리",  # やぎ座
    "11": "물병자리",  # みずがめ座
    "12": "물고기자리",  # うお座
}

FORTUNE_INDEX = "fortune-index.json"
HOROSCOPE_EDITIONS = "horoscope-editions.json"
FORTUNES_DIR = "fortunes"


def log(msg: str) -> None:
    print(f"[scrape] {msg}", flush=True)


def http_get(url: str, timeout: int = 25, user_agent: str | None = None) -> bytes:
    """GET with a browser UA, retried a few times on transient errors."""
    last: Exception | None = None
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": user_agent or UA}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            log(f"GET {url[:80]}... failed (attempt {attempt}/3): {exc}")
            time.sleep(5 * attempt)
    raise RuntimeError(f"GET failed after 3 attempts: {url}") from last


# --------------------------------------------------------------------------
# Translation (Google Translate web endpoint, no key needed)
# --------------------------------------------------------------------------

def google_translate(text: str, src: str, tgt: str) -> str:
    query = urllib.parse.urlencode(
        {"client": "gtx", "sl": src, "tl": tgt, "dt": "t", "q": text}
    )
    url = "https://translate.googleapis.com/translate_a/single?" + query
    last: Exception | None = None
    delays = (2, 5, 10, 20)
    for attempt in range(1, 6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.load(resp)
            return "".join(part[0] for part in data[0] if part[0]).strip()
        except Exception as exc:  # noqa: BLE001 - retry, then surface
            last = exc
            if attempt >= 5:
                break
            code = getattr(exc, "code", None)
            if code == 429 or (isinstance(code, int) and 500 <= code < 600):
                delay = delays[min(attempt - 1, len(delays) - 1)]
                delay += random.uniform(0, 1)
                log(
                    f"translate {src}->{tgt} HTTP {code}, "
                    f"retry in {delay:.1f}s ({attempt}/5)"
                )
                time.sleep(delay)
            else:
                time.sleep(3 * attempt)
    raise RuntimeError(f"translate {src}->{tgt} failed: {text!r}") from last


def translate_summary(ja_text: str) -> str:
    """Japanese horoscope summary -> Korean, direct ja -> ko."""
    return google_translate(ja_text, "ja", "ko")


def load_glossary(root: str) -> dict:
    path = os.path.join(root, "scripts", "glossary.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("lucky", {})
    except FileNotFoundError:
        log("glossary.json not found, lucky items will use machine translation")
        return {}


# --------------------------------------------------------------------------
# Instagram: @sinbi_saju daily fortune image
# --------------------------------------------------------------------------

def _unescape_embed(raw: str) -> str:
    """Undo the JSON string escaping used inside the embed page."""
    text = raw.replace('\\"', '"').replace("\\/", "/").replace("\\\\", "\\")
    return text


def parse_embed_posts(page: str) -> list[dict]:
    """Extract the recent posts listed in the embed page.

    Each entry: shortcode, is_video, caption (decoded when possible),
    taken_at_timestamp (KST date derived from it), display_url (1080px).
    """
    text = _unescape_embed(page)
    posts: list[dict] = []
    # One shortcode_media object per post; fields appear in this order:
    # shortcode, is_video, dimensions, display_url, ..., caption, ..., taken_at_timestamp
    pattern = re.compile(
        r'"shortcode":"([A-Za-z0-9_\-]+)".{0,4000}?'
        r'"display_url":"([^"]+)".{0,6000}?'
        r'"text":"((?:[^"\\]|\\.)*)".{0,1500}?'
        r'"taken_at_timestamp":(\d+)',
        re.S,
    )
    for m in pattern.finditer(text):
        shortcode, url, caption_raw, ts = m.groups()
        is_video = '"is_video":true' in text[m.start():m.start() + 400]
        caption = caption_raw
        try:
            caption = caption_raw.encode("utf-8").decode("unicode_escape")
        except Exception:  # noqa: BLE001 - keep the raw caption
            pass
        posted = dt.datetime.fromtimestamp(int(ts), tz=KST).date()
        posts.append(
            {
                "shortcode": shortcode,
                "is_video": is_video,
                "caption": caption,
                "posted_date": posted,
                "display_url": url.replace("\\", ""),
            }
        )
    return posts


def caption_date(caption: str) -> dt.date | None:
    """'11월 24일 오늘의 띠별 운세입니다.' -> date (year taken from context)."""
    m = re.search(r"(\d+)\s*월\s*(\d+)\s*일", caption)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)))


def fetch_instagram_post(target: dt.date, shortcode_override: str | None) -> dict:
    """Find today's fortune post. Returns {shortcode, image_url}."""
    if shortcode_override:
        # Single-post embed page contains the 1080px CDN URL directly.
        url = f"https://www.instagram.com/p/{shortcode_override}/embed/"
        log(f"shortcode override given, fetching {url}")
        page = http_get(url, user_agent=IG_UAS[0]).decode("utf-8", errors="ignore")
        m = re.search(
            r"https://[^\s\"\\]*cdninstagram[^\s\"\\]*?s1080x1080[^\s\"\\]*",
            page,
        )
        if m:
            image_url = htmlmod.unescape(m.group(0)).replace("\\", "")
            return {"shortcode": shortcode_override, "image_url": image_url}
        m = re.search(
            r'<meta property="og:image" content="([^"]+)"',
            htmlmod.unescape(page),
        )
        if m:
            log("warning: only the 640px og:image was found for the override")
            return {"shortcode": shortcode_override, "image_url": m.group(1)}
        raise RuntimeError(
            f"could not find an image for shortcode {shortcode_override}"
        )

    log(f"fetching Instagram embed page for @{IG_USERNAME}")
    posts: list[dict] = []
    for ua in IG_UAS:
        try:
            page = http_get(IG_EMBED_URL, user_agent=ua).decode("utf-8", errors="ignore")
        except Exception as exc:  # noqa: BLE001 - try the next UA
            log(f"embed fetch failed with UA {ua[:30]!r}: {exc}")
            continue
        posts = parse_embed_posts(page)
        log(f"embed page lists {len(posts)} recent posts (UA {ua[:30]!r})")
        if posts:
            break
    if not posts:
        raise LookupError(
            f"embed page for @{IG_USERNAME} lists no posts "
            "(Instagram may have changed its markup or blocked the request)"
        )
    for post in posts:
        if post["is_video"]:
            continue
        cap = caption_date(post["caption"])
        month_day = (target.month, target.day)
        # Posts go up at 00:00 KST on the fortune date itself.
        if post["posted_date"] == target or cap == month_day:
            if cap is not None and cap != month_day:
                log(f"skipping {post['shortcode']}: caption date mismatch")
                continue
            log(
                f"matched {post['shortcode']} for {target} "
                f"(posted {post['posted_date']}, caption: {post['caption'][:40]!r})"
            )
            return {"shortcode": post["shortcode"], "image_url": post["display_url"]}
    raise LookupError(
        f"no @{IG_USERNAME} post found for {target} "
        f"(saw: {[(p['shortcode'], str(p['posted_date'])) for p in posts]})"
    )


def download_image(url: str, dest: str) -> None:
    data = http_get(url)
    if not data.startswith(b"\xff\xd8\xff"):
        raise RuntimeError(f"downloaded file is not a JPEG: {url[:100]}")
    if len(data) < 50_000:
        raise RuntimeError(f"downloaded image suspiciously small ({len(data)} bytes)")
    with open(dest, "wb") as f:
        f.write(data)
    log(f"saved {dest} ({len(data)} bytes)")


# --------------------------------------------------------------------------
# ABC horoscope
# --------------------------------------------------------------------------

def fetch_abc(target: dt.date) -> list[dict] | None:
    """Fetch the official ABC JSON; return today's entries or None."""
    raw = http_get(ABC_URL)
    feed = json.loads(raw.decode("utf-8"))
    if not feed:
        raise RuntimeError("ABC horoscope feed is empty")
    edition = feed[0]
    onair = edition.get("onair_date", "")
    try:
        aired = dt.datetime.strptime(onair, "%Y%m%d").date()
    except ValueError:
        raise RuntimeError(f"unexpected ABC onair_date: {onair!r}") from None
    log(f"ABC feed onair_date is {aired} (target {target})")
    if aired != target:
        return None
    entries: list[dict] = []
    for detail in edition.get("detail", []):
        parts = [p.strip() for p in detail.get("horoscope_text", "").split("\t")]
        parts = [p for p in parts if p]
        if len(parts) < 2:
            raise RuntimeError(f"unexpected ABC text format: {detail!r}")
        lucky_ja, summary_ja = parts[-1], " ".join(parts[:-1])
        entries.append(
            {
                "rank": int(detail["ranking_no"]),
                "sign": SIGN_BY_CODE[detail["horoscope_st"]],
                "ja_summary": summary_ja,
                "ja_lucky": lucky_ja,
            }
        )
    entries.sort(key=lambda e: e["rank"])
    if len(entries) != 12 or {e["rank"] for e in entries} != set(range(1, 13)):
        raise RuntimeError(f"ABC edition has {len(entries)} entries, expected 12")
    return entries


def translate_entries(entries: list[dict], glossary: dict) -> list[dict]:
    out: list[dict] = []
    for entry in entries:
        lucky_ja = entry["ja_lucky"]
        lucky = glossary.get(lucky_ja)
        if lucky:
            log(f"lucky {lucky_ja!r} -> glossary {lucky!r}")
        else:
            lucky = google_translate(lucky_ja, "ja", "ko")
            log(f"lucky {lucky_ja!r} -> translated {lucky!r}")
        summary = translate_summary(entry["ja_summary"])
        out.append(
            {
                "rank": entry["rank"],
                "sign": entry["sign"],
                "summary": summary,
                "lucky": lucky,
                "ja_summary": entry["ja_summary"],
                "ja_lucky": lucky_ja,
            }
        )
        time.sleep(0.4)  # be gentle with the translate endpoint
    return out


# --------------------------------------------------------------------------
# File updates (idempotent)
# --------------------------------------------------------------------------

def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def update_fortune(root: str, target: dt.date, post: dict) -> bool:
    """Download + record the fortune. Returns True if the date is now present."""
    index_path = os.path.join(root, FORTUNE_INDEX)
    index = load_json(index_path, {})
    key = target.isoformat()
    img_path = os.path.join(root, FORTUNES_DIR, f"{key}.jpg")
    if index.get(key) == post["shortcode"] and os.path.exists(img_path):
        log(f"fortune for {key} already collected ({post['shortcode']})")
        return True
    os.makedirs(os.path.join(root, FORTUNES_DIR), exist_ok=True)
    download_image(post["image_url"], img_path)
    index[key] = post["shortcode"]
    dump_json(index_path, index)
    log(f"fortune-index.json: {key} -> {post['shortcode']}")
    return True


def update_horoscope(root: str, target: dt.date, entries: list[dict]) -> bool:
    path = os.path.join(root, HOROSCOPE_EDITIONS)
    editions = load_json(path, [])
    key = target.isoformat()
    if any(e.get("date") == key for e in editions):
        log(f"horoscope for {key} already collected")
        return True
    editions.append({"date": key, "entries": entries})
    editions.sort(key=lambda e: e.get("date", ""))
    dump_json(path, editions)
    log(f"horoscope-editions.json: added {key} ({len(entries)} signs)")
    return True


# --------------------------------------------------------------------------

def collect_once(root: str, target: dt.date, shortcode_override: str | None,
                 glossary: dict) -> tuple[bool, bool]:
    """One attempt. Returns (fortune_satisfied, horoscope_satisfied):
    True when that side's data for the date is present (newly collected
    or already there), False when it still needs to be waited for."""
    fortune_done = horoscope_done = False
    try:
        post = fetch_instagram_post(target, shortcode_override)
        fortune_done = update_fortune(root, target, post)
    except LookupError as exc:
        log(f"fortune not published yet: {exc}")
    except Exception as exc:  # noqa: BLE001 - reported, retried by caller
        log(f"fortune collection failed: {exc}")

    # ABC airs on weekdays (Mon-Fri) only: the existing editions skip
    # Sat/Sun (e.g. no 2026-11-14/15), so a missing weekend edition is
    # normal, not an error.
    if target.weekday() >= 5:
        log(f"{target} is a weekend, skipping horoscope (ABC is Mon-Fri)")
        horoscope_done = True
    elif any(
        e.get("date") == target.isoformat()
        for e in load_json(os.path.join(root, HOROSCOPE_EDITIONS), [])
    ):
        log(f"horoscope for {target} already collected")
        horoscope_done = True
    else:
        try:
            entries = fetch_abc(target)
        except Exception as exc:  # noqa: BLE001 - reported, retried by caller
            log(f"horoscope collection failed: {exc}")
            entries = None
        if entries is None:
            log("horoscope not published yet")
        else:
            translated = translate_entries(entries, glossary)
            horoscope_done = update_horoscope(root, target, translated)
    return fortune_done, horoscope_done


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect today's little-fortune data")
    parser.add_argument("--date", default="",
                        help="Target date YYYY-MM-DD in KST (default: today)")
    parser.add_argument("--wait-minutes", type=int, default=120,
                        help="Keep retrying until today's posts appear (default: 120)")
    parser.add_argument("--poll-seconds", type=int, default=600,
                        help="Seconds between retries (default: 600)")
    parser.add_argument("--fortune-shortcode", default="",
                        help="Instagram shortcode override for the fortune image")
    parser.add_argument("--root", default="",
                        help="Repo root (default: parent of scripts/)")
    args = parser.parse_args(argv)

    root = args.root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if args.date:
        target = dt.date.fromisoformat(args.date)
    else:
        target = dt.datetime.now(KST).date()
    glossary = load_glossary(root)
    log(f"target date: {target} ({target.strftime('%A')}), root: {root}")

    deadline = time.monotonic() + max(0, args.wait_minutes) * 60
    attempt = 0
    while True:
        attempt += 1
        log(f"attempt {attempt}")
        fortune_done, horoscope_done = collect_once(
            root, target, args.fortune_shortcode or None, glossary
        )
        if fortune_done and horoscope_done:
            # Both sides done. But "done" also means "already collected":
            # verify today's data is actually present before finishing.
            index = load_json(os.path.join(root, FORTUNE_INDEX), {})
            editions = load_json(os.path.join(root, HOROSCOPE_EDITIONS), [])
            has_fortune = target.isoformat() in index
            has_horoscope = target.weekday() >= 5 or any(
                e.get("date") == target.isoformat() for e in editions
            )
            if has_fortune and has_horoscope:
                log(f"all done for {target}")
                return 0
        if time.monotonic() >= deadline:
            log(f"gave up after {args.wait_minutes} min: {target} not fully published")
            return 2
        sleep_for = min(args.poll_seconds, max(0, deadline - time.monotonic()))
        log(f"waiting {sleep_for:.0f}s for publication...")
        time.sleep(sleep_for)


if __name__ == "__main__":
    sys.exit(main())
