"""
웨어러블서치 IT 뉴스 카드 자동 업데이트 스크립트

wearablesearch.tistory.com/rss 에서 최신 포스트 3개를 가져와
index.html 의 <!-- NEWS_CARDS_START --> ~ <!-- NEWS_CARDS_END --> 사이를 교체합니다.

사용법:
  python update_news.py              # 기본 실행
  python update_news.py --dry-run    # HTML 파일 수정 없이 결과만 출력
"""

import urllib.request
import xml.etree.ElementTree as ET
import re
import html
import sys
from datetime import datetime
from pathlib import Path

# ── 설정 ──────────────────────────────────────────────
RSS_URL   = "https://wearablesearch.tistory.com/rss"
HTML_FILE = Path(__file__).parent / "index.html"
MAX_CARDS = 3
EXCERPT_LEN = 115

CATEGORY_MAP = {
    "IT 소식":    ("IT",      "tag-market"),
    "크라우드펀딩": ("FUNDING", "tag-health"),
    "웨어러블":   ("WEARABLE","tag-trend"),
    "리뷰":       ("REVIEW",  "tag-trend"),
}
DEFAULT_TAG = ("TECH", "tag-trend")

START_MARKER = "<!-- NEWS_CARDS_START -->"
END_MARKER   = "<!-- NEWS_CARDS_END -->"
# ──────────────────────────────────────────────────────


def fetch_rss() -> bytes:
    req = urllib.request.Request(
        RSS_URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; WearableSearchBot/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def excerpt(text: str, max_len: int = EXCERPT_LEN) -> str:
    text = clean(text)
    return text[:max_len].rstrip() + "..." if len(text) > max_len else text


def esc(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


def parse_items(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.findall(".//item"):
        items.append({
            "title":       clean(item.findtext("title", "")),
            "link":        (item.findtext("link", "") or "").strip(),
            "description": excerpt(item.findtext("description", "")),
            "category":    (item.findtext("category", "IT 소식") or "").strip(),
        })
    return items[:MAX_CARDS]


def build_cards_html(items: list[dict]) -> str:
    delays = ["", ' style="transition-delay:0.1s"', ' style="transition-delay:0.2s"']
    cards = []
    for i, item in enumerate(items):
        tag_label, tag_class = CATEGORY_MAP.get(item["category"], DEFAULT_TAG)
        delay = delays[i] if i < len(delays) else ""
        cards.append(
            f'      <article class="glass-card insight-card fade-up" aria-labelledby="card-title-{i+1}"{delay}>\n'
            f'        <span class="card-tag {tag_class}">{tag_label}</span>\n'
            f'        <h3 class="card-title" id="card-title-{i+1}">{esc(item["title"])}</h3>\n'
            f'        <p class="card-excerpt">{esc(item["description"])}</p>\n'
            f'        <a href="{esc(item["link"])}" class="card-link" target="_blank"\n'
            f'           rel="noopener noreferrer" aria-label="{esc(item["title"])} 읽기">\n'
            f'          READ\n'
            f'          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">\n'
            f'            <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>\n'
            f'          </svg>\n'
            f'        </a>\n'
            f'      </article>'
        )
    return "\n".join(cards)


def update_html(cards_html: str, dry_run: bool = False) -> bool:
    content = HTML_FILE.read_text(encoding="utf-8")

    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )
    if not pattern.search(content):
        raise RuntimeError(
            f"마커를 찾을 수 없습니다. index.html에 "
            f"'{START_MARKER}' 와 '{END_MARKER}' 가 있는지 확인하세요."
        )

    replacement = f"{START_MARKER}\n{cards_html}\n      {END_MARKER}"
    new_content = pattern.sub(replacement, content)

    if new_content == content:
        print("변경 없음 — 콘텐츠가 동일합니다.")
        return False

    if not dry_run:
        HTML_FILE.write_text(new_content, encoding="utf-8")
        print(f"✓ {HTML_FILE.name} 업데이트 완료")
    else:
        print("[DRY RUN] 변경될 카드 HTML:")
        print(cards_html)
    return True


def main():
    dry_run = "--dry-run" in sys.argv
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"[{now}] RSS 피드 가져오는 중... {RSS_URL}")

    xml_bytes = fetch_rss()
    items = parse_items(xml_bytes)

    print(f"  포스트 {len(items)}개 파싱 완료:")
    for item in items:
        print(f"  - [{item['category']}] {item['title']}")

    cards_html = build_cards_html(items)
    changed = update_html(cards_html, dry_run=dry_run)
    return 0 if changed or dry_run else 0


if __name__ == "__main__":
    sys.exit(main())
