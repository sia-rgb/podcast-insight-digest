from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


RSS_URL = "https://feed.xyzfm.space/dk4yh3pkpjp3"
TARGET_TITLE = "128. Manus决定出售前最后的访谈"
OUTPUT_DIR = Path("data")
AUDIO_DIR = OUTPUT_DIR / "audio"
EPISODES_JSON = OUTPUT_DIR / "episodes.json"


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_text(item: ET.Element, name: str) -> str:
    for child in item:
        if local_name(child.tag) == name:
            return (child.text or "").strip()
    return ""


def enclosure_url(item: ET.Element) -> str:
    for child in item:
        if local_name(child.tag) == "enclosure":
            return (child.attrib.get("url") or "").strip()
    return ""


def safe_filename(title: str, audio_url: str) -> str:
    parsed_path = urlparse(audio_url).path
    suffix = Path(parsed_path).suffix or ".m4a"
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).strip(" .")
    return f"{cleaned}{suffix}"


def fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "podcast-insight-digest/0.1"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def download_file(url: str, output_path: Path) -> None:
    request = Request(url, headers={"User-Agent": "podcast-insight-digest/0.1"})
    part_path = output_path.with_suffix(output_path.suffix + ".part")

    with urlopen(request, timeout=60) as response:
        with part_path.open("wb") as file:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                file.write(chunk)

    part_path.replace(output_path)


def parse_episodes(rss_bytes: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(rss_bytes)
    episodes: list[dict[str, str]] = []

    for item in root.iter():
        if local_name(item.tag) != "item":
            continue

        episodes.append(
            {
                "title": child_text(item, "title"),
                "pub_date": child_text(item, "pubDate"),
                "audio_url": enclosure_url(item),
            }
        )

    return episodes


def find_target_episode(episodes: list[dict[str, str]]) -> dict[str, str] | None:
    for episode in episodes:
        if TARGET_TITLE in episode["title"]:
            return episode
    return None


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    rss_bytes = fetch_bytes(RSS_URL)
    episodes = parse_episodes(rss_bytes)

    with EPISODES_JSON.open("w", encoding="utf-8") as file:
        json.dump(episodes, file, ensure_ascii=False, indent=2)

    if len(episodes) < 3:
        print(f"ERROR: only parsed {len(episodes)} episodes")
        return 1

    target = find_target_episode(episodes)
    if target is None:
        print(f"ERROR: target episode not found: {TARGET_TITLE}")
        return 1

    if not target["audio_url"]:
        print(f"ERROR: target episode has no audio_url: {target['title']}")
        return 1

    audio_path = AUDIO_DIR / safe_filename(target["title"], target["audio_url"])
    if not audio_path.exists():
        download_file(target["audio_url"], audio_path)

    print(f"episodes: {len(episodes)}")
    print(f"metadata: {EPISODES_JSON}")
    print(f"downloaded: {audio_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
