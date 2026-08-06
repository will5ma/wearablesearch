"""
웨어러블서치 카드 자동 업데이트 스크립트

rss.blog.naver.com/geekstarter.xml 에서 최신 글을 가져와
index.html 의 두 영역을 교체합니다.

  - IT 뉴스 카드   : 카테고리에 'IT'가 포함된 글 (크라우드펀딩 제외) → 매일 새벽 3시
  - 펀딩 인사이트 카드: 카테고리에 '크라우드'가 포함된 글           → 매일 아침 7시

사용법:
  python update_news.py                    # news + funding 모두 실행
  python update_news.py --target=news      # IT 뉴스 카드만 갱신
  python update_news.py --target=funding   # 펀딩 인사이트 카드만 갱신
  python update_news.py --dry-run          # HTML 파일 수정 없이 결과만 출력
"""

import urllib.request
import xml.etree.ElementTree as ET
import re
import html
import sys
from datetime import datetime
from pathlib import Path

# ── 설정 ──────────────────────────────────────────────
RSS_URL   = "https://rss.blog.naver.com/geekstarter.xml"
HTML_FILE = Path(__file__).parent / "index.html"
MAX_CARDS = 3
EXCERPT_LEN = 115

SECTIONS = {
    "news": {
        "category_keyword": "IT",
        "tag_label": "IT",
        "tag_class": "tag-market",
        "id_prefix": "card-title",
        "start_marker": "<!-- NEWS_CARDS_START -->",
        "end_marker":   "<!-- NEWS_CARDS_END -->",
    },
    "funding": {
        "category_keyword": "크라우드",
        "tag_label": "FUNDING",
        "tag_class": "tag-health",
        "id_prefix": "funding-title",
        "start_marker": "<!-- FUNDING_CARDS_START -->",
        "end_marker":   "<!-- FUNDING_CARDS_END -->",
    },
}
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


def parse_items(xml_bytes: bytes, category_keyword: str) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    matched = []
    for item in root.findall(".//item"):
        category = clean(item.findtext("category", "") or "")
        if category_keyword not in category:
            continue
        link = (item.findtext("guid", "") or item.findtext("link", "") or "").strip()
        link = link.split("?")[0]
        matched.append({
            "title":       clean(item.findtext("title", "")),
            "link":        link,
            "description": excerpt(item.findtext("description", "")),
            "category":    category,
        })
        if len(matched) >= MAX_CARDS:
            break
    return matched


def build_cards_html(items: list[dict], tag_label: str, tag_class: str, id_prefix: str) -> str:
    delays = ["", ' style="transition-delay:0.1s"', ' style="transition-delay:0.2s"']
    cards = []
    for i, item in enumerate(items):
        delay = delays[i] if i < len(delays) else ""
        cards.append(
            f'      <article class="glass-card insight-card fade-up" aria-labelledby="{id_prefix}-{i+1}"{delay}>\n'
            f'        <span class="card-tag {tag_class}">{tag_label}</span>\n'
            f'        <h3 class="card-title" id="{id_prefix}-{i+1}">{esc(item["title"])}</h3>\n'
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


def update_html(content: str, cards_html: str, start_marker: str, end_marker: str) -> tuple[str, bool]:
    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker),
        re.DOTALL,
    )
    if not pattern.search(content):
        raise RuntimeError(
            f"마커를 찾을 수 없습니다. index.html에 "
            f"'{start_marker}' 와 '{end_marker}' 가 있는지 확인하세요."
        )

    replacement = f"{start_marker}\n{cards_html}\n      {end_marker}"
    new_content = pattern.sub(replacement, content)
    return new_content, new_content != content


def run_section(name: str, content: str, xml_bytes: bytes, dry_run: bool) -> tuple[str, bool]:
    cfg = SECTIONS[name]
    items = parse_items(xml_bytes, cfg["category_keyword"])

    print(f"[{name}] 포스트 {len(items)}개 파싱 완료:")
    for item in items:
        print(f"  - [{item['category']}] {item['title']}")

    cards_html = build_cards_html(items, cfg["tag_label"], cfg["tag_class"], cfg["id_prefix"])
    new_content, changed = update_html(content, cards_html, cfg["start_marker"], cfg["end_marker"])

    if dry_run:
        print(f"[{name}] [DRY RUN] 변경될 카드 HTML:")
        print(cards_html)

    return new_content, changed


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    target = "all"
    for a in args:
        if a.startswith("--target="):
            target = a.split("=", 1)[1]

    targets = list(SECTIONS.keys()) if target == "all" else [target]
    for t in targets:
        if t not in SECTIONS:
            print(f"알 수 없는 --target 값: {t} (news, funding, all 중 선택)")
            return 1

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"[{now}] RSS 피드 가져오는 중... {RSS_URL} (target={target})")
    xml_bytes = fetch_rss()

    content = HTML_FILE.read_text(encoding="utf-8")
    any_changed = False
    for t in targets:
        content, changed = run_section(t, content, xml_bytes, dry_run)
        any_changed = any_changed or changed

    if not dry_run:
        if any_changed:
            HTML_FILE.write_text(content, encoding="utf-8")
            print(f"✓ {HTML_FILE.name} 업데이트 완료")
        else:
            print("변경 없음 — 콘텐츠가 동일합니다.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
