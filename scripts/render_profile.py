#!/usr/bin/env python3
"""根据 scripts/cards.json 一键渲染个人主页横幅与全部开源项目双色卡片（1200x244 @2x）。

用法：
  python3 scripts/render_profile.py                 # 渲染横幅 + 全部项目卡片，并打印 README 卡片片段
  python3 scripts/render_profile.py --only fh5      # 仅渲染 slug 包含 fh5 的项目卡片
"""
from __future__ import annotations

import argparse
import base64
import html
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "scripts" / "cards.json"
ASSETS_DIR = REPO_ROOT / "assets"
CARDS_DIR = ASSETS_DIR / "cards"
IP_DIR = ASSETS_DIR / "ip"

ACCOUNT = "dylanma8232-art"
CANVAS_W = 1200
CANVAS_H = 244
SCALE = 2

THEMES = {
    "light": {
        "bg": "#FAF8F4",
        "border": "rgba(28, 25, 23, 0.09)",
        "dot": "rgba(28, 25, 23, 0.075)",
        "eyebrow": "#78716C",
        "title": "#18181B",
        "desc": "#27272A",
        "badge_bg": "rgba(194, 65, 12, 0.08)",
        "badge_border": "rgba(194, 65, 12, 0.28)",
        "badge_text": "#C2410C",
        "cta_bg": "#C2410C",
        "cta_text": "#FFFFFF",
        "glow": "radial-gradient(circle at 88% 55%, rgba(234, 88, 12, 0.045) 0%, rgba(234, 88, 12, 0) 42%)",
        "cat_shadow": "drop-shadow(0 12px 18px rgba(24, 24, 27, 0.13))",
    },
    "dark": {
        "bg": "#141417",
        "border": "rgba(255, 255, 255, 0.10)",
        "dot": "rgba(255, 255, 255, 0.065)",
        "eyebrow": "#A1A1AA",
        "title": "#FAFAFA",
        "desc": "#E4E4E7",
        "badge_bg": "rgba(249, 115, 22, 0.14)",
        "badge_border": "rgba(249, 115, 22, 0.36)",
        "badge_text": "#FB923C",
        "cta_bg": "#EA580C",
        "cta_text": "#FFFFFF",
        "glow": "radial-gradient(circle at 88% 55%, rgba(249, 115, 22, 0.06) 0%, rgba(249, 115, 22, 0) 42%)",
        "cat_shadow": "drop-shadow(0 14px 22px rgba(0, 0, 0, 0.55))",
    },
}

BASE_CSS = f"""
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{
  width: {CANVAS_W}px;
  height: {CANVAS_H}px;
  background: transparent;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", "Helvetica Neue", sans-serif;
  -webkit-font-smoothing: antialiased;
}}
.canvas {{
  position: relative;
  width: {CANVAS_W}px;
  height: {CANVAS_H}px;
  border-radius: 22px;
  overflow: hidden;
  background-color: var(--bg);
  background-image:
    var(--glow),
    radial-gradient(var(--dot) 1.25px, transparent 1.25px);
  background-size: 100% 100%, 22px 22px;
  background-position: 0 0, 11px 11px;
  border: 1.5px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 56px 0 60px;
}}
.left {{
  max-width: 890px;
  display: flex;
  flex-direction: column;
  z-index: 2;
}}
.eyebrow {{
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--eyebrow);
  margin-bottom: 10px;
}}
.title-row {{
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}}
.title {{
  font-size: 38px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.18;
  color: var(--title);
}}
.hero-title {{
  font-size: 48px;
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.1;
  color: var(--title);
}}
.role-pill {{
  display: inline-flex;
  align-items: center;
  padding: 5px 14px;
  border-radius: 999px;
  font-size: 15px;
  font-weight: 700;
  background: var(--badge_bg);
  border: 1px solid var(--badge_border);
  color: var(--badge_text);
}}
.desc {{
  margin-top: 16px;
  font-size: 20px;
  font-weight: 500;
  line-height: 1.55;
  color: var(--desc);
}}
.cta-row {{
  margin-top: 22px;
  display: flex;
  align-items: center;
}}
.cta {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 18px;
  border-radius: 999px;
  background: var(--cta_bg);
  color: var(--cta_text);
  font-size: 13.5px;
  font-weight: 600;
  letter-spacing: 0.01em;
}}
.cat-wrap {{
  position: relative;
  height: 100%;
  width: 210px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding-bottom: 12px;
  z-index: 2;
  flex-shrink: 0;
}}
.cat-wrap img {{
  max-height: 92%;
  width: auto;
  object-fit: contain;
  filter: var(--cat_shadow);
}}
"""


def data_uri(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def build_page_html(theme_key: str, inner_html: str) -> str:
    t = THEMES[theme_key]
    vars_css = ":root {\n" + "\n".join(f"  --{k}: {v};" for k, v in t.items()) + "\n}"
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{vars_css}\n{BASE_CSS}</style></head><body><div class='canvas'>{inner_html}</div></body></html>"


def readme_snippet(card: dict) -> str:
    slug = card["slug"]
    repo = card["repo"]
    alt = f"{card['title']}（{card['pill']}）— {card['desc']}"
    return (
        "<p>\n"
        f'  <a href="https://github.com/{ACCOUNT}/{repo}#gh-light-mode-only"><img alt="{alt}" src="assets/cards/card-{slug}-light.png#gh-light-mode-only" width="100%"></a>\n'
        f'  <a href="https://github.com/{ACCOUNT}/{repo}#gh-dark-mode-only"><img alt="{alt}" src="assets/cards/card-{slug}-dark.png#gh-dark-mode-only" width="100%"></a>\n'
        "</p>"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="渲染个人主页横幅与开源项目卡片")
    parser.add_argument("--only", help="仅渲染匹配的卡片 slug（跳过横幅）")
    args = parser.parse_args()

    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    CARDS_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome")
        except Exception:
            browser = p.chromium.launch()

        if not args.only:
            b = cfg["banner"]
            b_ip = data_uri(IP_DIR / b["ip"])
            banner_inner = f"""
              <div class="left">
                <div class="title-row">
                  <div class="hero-title">{html.escape(b['title'])}</div>
                  <span class="role-pill">{html.escape(b['pill'])}</span>
                </div>
                <div class="desc">{html.escape(b['desc'])}</div>
              </div>
              <div class="cat-wrap"><img src="{b_ip}" alt="{html.escape(b['title'])}"></div>
            """
            for mode in ("light", "dark"):
                page = browser.new_page(viewport={"width": CANVAS_W, "height": CANVAS_H}, device_scale_factor=SCALE)
                page.set_content(build_page_html(mode, banner_inner), wait_until="load")
                out = ASSETS_DIR / f"banner-{mode}.png"
                page.screenshot(path=str(out), omit_background=True)
                page.close()
                print(f"[OK] {out.relative_to(REPO_ROOT)}")
            (ASSETS_DIR / "banner.png").write_bytes((ASSETS_DIR / "banner-light.png").read_bytes())

        snippets = []
        for card in cfg["cards"]:
            if args.only and args.only not in card["slug"]:
                continue
            c_ip = data_uri(IP_DIR / card["ip"])
            eyebrow = f"{ACCOUNT} / {card['repo']}"
            card_inner = f"""
              <div class="left">
                <div class="eyebrow">{html.escape(eyebrow)}</div>
                <div class="title-row">
                  <div class="title">{html.escape(card['title'])}</div>
                  <span class="role-pill">{html.escape(card['pill'])}</span>
                </div>
                <div class="desc">{html.escape(card['desc'])}</div>
                <div class="cta-row"><span class="cta">点此查看项目 →</span></div>
              </div>
              <div class="cat-wrap"><img src="{c_ip}" alt="{html.escape(card['title'])}"></div>
            """
            for mode in ("light", "dark"):
                page = browser.new_page(viewport={"width": CANVAS_W, "height": CANVAS_H}, device_scale_factor=SCALE)
                page.set_content(build_page_html(mode, card_inner), wait_until="load")
                out = CARDS_DIR / f"card-{card['slug']}-{mode}.png"
                page.screenshot(path=str(out), omit_background=True)
                page.close()
                print(f"[OK] {out.relative_to(REPO_ROOT)}")
            snippets.append(readme_snippet(card))

        browser.close()

    print("\n--- README.md 项目卡片嵌入片段 ---")
    print("\n\n".join(snippets))


if __name__ == "__main__":
    main()
