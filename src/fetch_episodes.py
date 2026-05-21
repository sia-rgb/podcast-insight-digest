from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


RSS_URL = "https://feed.xyzfm.space/dk4yh3pkpjp3"
OUTPUT_DIR = Path("data")
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


def fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "podcast-insight-digest/0.1"})
    with urlopen(request, timeout=60) as response:
        return response.read()


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


def write_episodes(episodes: list[dict[str, str]], output_path: Path = EPISODES_JSON) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(episodes, file, ensure_ascii=False, indent=2)


def main() -> int:
    episodes = parse_episodes(fetch_bytes(RSS_URL))
    write_episodes(episodes)

    if len(episodes) < 3:
        print(f"ERROR: only parsed {len(episodes)} episodes")
        return 1

    print(f"episodes: {len(episodes)}")
    print(f"metadata: {EPISODES_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
