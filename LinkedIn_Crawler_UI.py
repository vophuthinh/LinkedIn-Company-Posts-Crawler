# -*- coding: utf-8 -*-
"""
LinkedIn Company Posts Crawler — Professional Edition
------------------------------------------------------------------
Professional tool for automated LinkedIn company posts extraction.

Features:
- Modern UI with dark mode support and intuitive design
- Smart automation with retry mechanism and rate limiting
- Auto cookie management for seamless login
- Batch processing with resume/checkpoint functionality
- Advanced filtering (date range, strict mode)
- Real-time progress tracking with ETA
- Multi-format output (CSV, JSONL)
- Keyboard shortcuts for power users

Installation:
    pip install -r requirements.txt
    # Optional: pip install undetected-chromedriver
"""
import csv
import json
import queue
import random
import re
import threading
import time
import unicodedata
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from tkinter import font as tkfont

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

ACCEPT_LANG = "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

EXTRACT_JS = r"""
// ---- LinkedIn company posts extractor (robust) ----
const out = [];

const toAbs = (h) => {
  if (!h) return null;
  if (h.startsWith('http')) return h.split('?')[0];
  return location.origin + (h.startsWith('/') ? h : '/' + h);
};
const isNoise = (t) => /see more|xem thêm|copy link|sao chép liên kết/i.test(t);

// Build post nodes (activity/ugcPost + articles)
const nodes = Array.from(document.querySelectorAll(
  '[data-urn*="urn:li:activity:"], [data-entity-urn*="urn:li:activity:"], ' +
  '[data-urn*="urn:li:ugcPost:"], [data-entity-urn*="urn:li:ugcPost:"], ' +
  'article[role="article"], article'
));

for (const el of nodes) {
  const rec = {};

  // URN
  let urn = el.getAttribute('data-urn') || el.getAttribute('data-entity-urn') || '';
  if (!urn) {
    const html = el.outerHTML || '';
    const m = html.match(/urn:li:(activity|ugcPost):\d+/);
    if (m) urn = m[0];
  }
  rec.urn = urn || null;

  // Link
  let link = null;
  for (const a of el.querySelectorAll('a')) {
    const href = a.getAttribute('href') || '';
    if (href.includes('/feed/update/') || href.includes('/posts/')) { link = toAbs(href); break; }
  }
  rec.post_url = link || (rec.urn && rec.urn.startsWith('urn:li:activity:') ? ('https://www.linkedin.com/feed/update/' + rec.urn + '/') : null);

  // Time (robust)
  let timeEl = el.querySelector('time[datetime]');
  if (!timeEl) {
    const root = el.closest('article, li, div');
    if (root) timeEl = root.querySelector('time[datetime]');
  }
  if (!timeEl) {
    const a = el.querySelector('a[href*="/feed/update/"], a[href*="/posts/"]');
    if (a) {
      const r2 = a.closest('article, li, div');
      if (r2) timeEl = r2.querySelector('time[datetime]');
    }
  }
  rec.time_iso  = timeEl && timeEl.getAttribute('datetime') ? timeEl.getAttribute('datetime') : null;
  rec.time_text = timeEl ? (timeEl.innerText || timeEl.textContent || '') : null;
  if (!rec.time_text) {
    const meta = el.querySelector('.update-components-actor__sub-description, .feed-shared-actor__sub-description');
    if (meta) {
      const t = meta.innerText || meta.textContent || '';
      rec.time_text = t.split('•')[0].split('·')[0].split('|')[0].trim();
    }
  }

  // Text (keep newlines & bullets, drop UI noise)
  const cands = [
    '[data-test-id="main-feed-activity-card__commentary"]',
    '.update-components-text',
    '.feed-shared-update-v2__description',
    '.attributed-text-segment-list__container',
    '.break-words',
    'div[dir]', 'p[dir]'
  ];
  let best = '';
  for (const sel of cands) {
    const ns = el.querySelectorAll(sel);
    for (const n of ns) {
      const clone = n.cloneNode(true);
      clone.querySelectorAll('br').forEach(br => { const x = document.createTextNode('\n'); br.parentNode && br.parentNode.replaceChild(x, br); });
      clone.querySelectorAll('li').forEach(li => { li.insertBefore(document.createTextNode('• '), li.firstChild); li.parentNode && li.parentNode.insertBefore(document.createTextNode('\n'), li.nextSibling); });
      clone.querySelectorAll('button,script,style,svg,figcaption').forEach(x => x.remove());
      let tx = clone.innerText || '';
      tx = tx.replace(/\u00A0/g, ' ').replace(/\r/g, '');
      tx = tx.replace(/[ \t]+\n/g, '\n').replace(/\n[ \t]+/g, '\n');
      tx = tx.split('\n').map(l => l.replace(/[ \t]+$/,'')).filter(l => !isNoise(l)).join('\n');
      tx = tx.replace(/\n{3,}/g, '\n\n').trim();
      if (tx && tx.length > best.length) best = tx;
    }
  }
  if (!best) {
    const leaves = Array.from(el.querySelectorAll('div, p, span')).filter(x => x.childElementCount === 0 || x.tagName.toLowerCase()==='p');
    for (const n of leaves) {
      const t = (n.innerText || '').trim();
      if (t && !isNoise(t) && t.length > best.length) best = t;
    }
  }
  rec.text = best || null;

  if (rec.urn || rec.post_url || rec.text) out.push(rec);
}

// De-dup
const seen = new Set(); const uniq = [];
for (const r of out) {
  const key = r.post_url || r.urn || (r.text ? r.text.slice(0,120) : '');
  if (!seen.has(key)) { seen.add(key); uniq.push(r); }
}
return uniq;
"""


# ---------- helpers ----------
# Import shared utilities if available
try:
    from utils import (
        normalize_time, inside_date_range, normalize_time_for_output,
        url_to_slug, clean_text_keep_newlines
    )
    USE_SHARED_UTILS = True
except ImportError:
    USE_SHARED_UTILS = False

def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def fix_hashtag(text: str) -> str:
    return re.sub(r"(?i)\bhashtag#", "#", text)


def clean_text_keep_newlines(s: Optional[str], apply_hashtag_fix: bool = True) -> Optional[str]:
    if not s:
        return None
    s = unicodedata.normalize("NFC", s)
    if apply_hashtag_fix:
        s = fix_hashtag(s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = s.strip()
    return s or None


def parse_rel_time_to_dt(rel: str, now: Optional[datetime] = None) -> Optional[datetime]:
    if not rel:
        return None
    rel = rel.strip().lower()
    now = now or datetime.now(timezone.utc)

    m = re.match(r"^(\d+)\s*m(?:in)?$", rel)
    if m:
        return now - timedelta(minutes=int(m.group(1)))
    m = re.match(r"^(\d+)\s*h(?:our)?$", rel)
    if m:
        return now - timedelta(hours=int(m.group(1)))
    m = re.match(r"^(\d+)\s*d(?:ay)?$", rel)
    if m:
        return now - timedelta(days=int(m.group(1)))
    m = re.match(r"^(\d+)\s*w(?:eek)?$", rel)
    if m:
        return now - timedelta(weeks=int(m.group(1)))
    m = re.match(r"^(\d+)\s*mo(?:nth)?$", rel)
    if m:
        return now - timedelta(days=30 * int(m.group(1)))
    m = re.match(r"^(\d+)\s*y(?:ear)?$", rel)
    if m:
        return now - timedelta(days=365 * int(m.group(1)))

    VI = [
        (r"(\d+)\s*phút", "minutes"),
        (r"(\d+)\s*giờ", "hours"),
        (r"(\d+)\s*ngày", "days"),
        (r"(\d+)\s*tuần", "weeks"),
        (r"(\d+)\s*tháng", "months"),
        (r"(\d+)\s*năm", "years"),
    ]
    for pat, unit in VI:
        m = re.search(pat, rel)
        if m:
            v = int(m.group(1))
            if unit == "minutes":
                return now - timedelta(minutes=v)
            if unit == "hours":
                return now - timedelta(hours=v)
            if unit == "days":
                return now - timedelta(days=v)
            if unit == "weeks":
                return now - timedelta(weeks=v)
            if unit == "months":
                return now - timedelta(days=30 * v)
            if unit == "years":
                return now - timedelta(days=365 * v)
    return None


# NÂNG CẤP: normalize_time()
# Use shared function if available, otherwise use local implementation
if not USE_SHARED_UTILS:
    def normalize_time(time_iso: Optional[str], time_text: Optional[str]) -> Optional[str]:
        # 1. Prioritize time_iso
        if time_iso:
            s = time_iso.strip()
            # Clean up common timezone variations, e.g., +0000 -> +00:00
            s = re.sub(r"([+-]\d{4})$", r"\1", s.replace("+0000", "+00:00"))

            # Try to parse and normalize ISO time
            try:
                # If it already contains Z or a timezone, just clean it up
                if "Z" in s or re.search(r"[-+]\d{2}:\d{2}$", s):
                    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

                # If it's a date/time without timezone, assume it's UTC/server time for robustness
                try:
                    dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
                    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
                except ValueError:
                    pass  # Not a full datetime

                # If it's a date only, assume it's the start of the day in UTC
                try:
                    dt = datetime.strptime(s, "%Y-%m-%d")
                    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
                except ValueError:
                    pass  # Not a date only

            except Exception:
                # ISO format error - Fallback to relative time
                pass

        # 2. Fallback to relative time (time_text)
        if time_text:
            dt = parse_rel_time_to_dt(time_text)
            if dt:
                return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

        return None


# NÂNG CẤP: inside_date_range()
# Use shared function if available, otherwise use local implementation
if not USE_SHARED_UTILS:
    def inside_date_range(
            iso_str: Optional[str],
            start: Optional[datetime],
            end: Optional[datetime],
            strict: bool = True,  # Nâng cấp: Thêm tuỳ chọn strict
    ) -> bool:
        if not (start or end):
            return True

        if not iso_str:
            return not strict  # Nâng cấp: Nếu không strict, cho qua (giữ lại dữ liệu).

        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        except Exception:
            return not strict  # Nâng cấp: Nếu parse lỗi và không strict, cho qua.

        if start and dt < start:
            return False
        if end and dt > (end + timedelta(days=1) - timedelta(seconds=1)):
            return False
        return True


if not USE_SHARED_UTILS:
    def url_to_slug(u: str) -> str:
        try:
            p = urlparse(u)
            parts = [x for x in p.path.split("/") if x]
            for i, seg in enumerate(parts):
                if seg == "company" and i + 1 < len(parts):
                    return re.sub(r"[^a-z0-9\-]+", "-", parts[i + 1].lower())
            return re.sub(r"[^a-z0-9\-]+", "-", (parts[-1] if parts else "company"))
        except Exception:
            return "company"


def close_overlays(driver):
    xps = [
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'accept')]",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'đồng ý')]",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'chấp nhận')]",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'got it')]",
        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'ok')]",
        "//button[@aria-label='Dismiss' or contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'dismiss')]",
        "//button[contains(@class,'artdeco-modal__dismiss')]",
        "//button[contains(@class,'ember-view') and contains(.,'Close')]",
    ]
    for xp in xps:
        try:
            for b in driver.find_elements(By.XPATH, xp):
                try:
                    driver.execute_script("arguments[0].click();", b)
                    time.sleep(0.2)
                except Exception:
                    pass
        except Exception:
            pass


def init_driver(headless: bool, use_uc: bool, fast_mode: bool):
    if use_uc:
        try:
            import undetected_chromedriver as uc  # type: ignore
            print("INFO: Attempting to use undetected-chromedriver.")
            return uc.Chrome(headless=headless)
        except Exception as e:
            print("⚠ Không thể dùng undetected-chromedriver:", e, "Sử dụng Chrome thông thường.")

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument(f"--lang={ACCEPT_LANG}")
    opts.add_argument(f"user-agent={USER_AGENT}")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    try:
        opts.page_load_strategy = "eager"
    except Exception:
        pass
    prefs = {"intl.accept_languages": ACCEPT_LANG}
    if fast_mode:
        prefs["profile.managed_default_content_settings.images"] = 2
    try:
        opts.add_experimental_option("prefs", prefs)
    except Exception:
        pass
    driver = webdriver.Chrome(options=opts)
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"},
        )
    except Exception:
        pass
    return driver


def add_cookies_if_any(driver, cookie_path: Path) -> int:
    count = 0
    try:
        if cookie_path.exists():
            driver.get("https://www.linkedin.com/")
            time.sleep(1.0)
            cookies = json.loads(cookie_path.read_text(encoding="utf-8")) or []
            for c in cookies:
                if isinstance(c.get("expiry"), float):
                    c["expiry"] = int(c["expiry"])
                try:
                    driver.add_cookie(c)
                    count += 1
                except Exception:
                    pass
            driver.get("https://www.linkedin.com/feed/")
            time.sleep(1.0)
    except Exception as e:
        print("⚠ Không thể nạp cookies:", e)
    return count


def save_cookies(driver, cookie_path: Path) -> tuple[bool, int]:
    try:
        cookie_path.parent.mkdir(parents=True, exist_ok=True)
        cookies = driver.get_cookies() or []
        cookie_path.write_text(
            json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return True, len(cookies)
    except Exception as e:
        print("⚠ Không thể lưu cookies:", e)
        return False, 0


# NÂNG CẤP: Ngẫu nhiên hóa hành vi cuộn
def smart_scroll(driver, outer_rounds=2, base_step_px=1100):
    for _ in range(outer_rounds):
        scroll_amount = random.randint(base_step_px - 200, base_step_px + 200)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        time.sleep(random.uniform(0.6, 1.2))

        driver.execute_script(
            """
            const els = [...document.querySelectorAll('div')].filter(d =>
                (d.scrollHeight - d.clientHeight) > 200 && getComputedStyle(d).overflowY !== 'visible');
            els.slice(0, 12).forEach(e => { e.scrollTop = e.scrollHeight; });
            """
        )
        time.sleep(random.uniform(0.5, 1.0))


if not USE_SHARED_UTILS:
    def normalize_time_for_output(iso_str: Optional[str]) -> Optional[str]:
        try:
            if not iso_str:
                return None
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            vn = timezone(timedelta(hours=7))
            dt = dt.astimezone(vn)
            return dt.strftime("%d-%m-%Y")
        except Exception:
            return None


# ---- checkpoint helpers ----

def write_checkpoint(out_dir: Path, urls: List[str], next_index: int, filters: Dict[str, Optional[str]]):
    ck = {
        "urls": urls,
        "next_index": next_index,
        "filters": filters,
        "ts": datetime.now().isoformat(timespec="seconds"),
    }
    (out_dir / "checkpoint.json").write_text(json.dumps(ck, ensure_ascii=False, indent=2), encoding="utf-8")


def read_checkpoint(out_dir: Path) -> Optional[Dict]:
    p = out_dir / "checkpoint.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def remove_checkpoint(out_dir: Path):
    p = out_dir / "checkpoint.json"
    if p.exists():
        try:
            p.unlink()
        except Exception:
            pass


# ---- core scrape ----
# Import shared scraping functions
try:
    from scraper_core import scrape_url, close_overlays, smart_scroll, EXTRACT_JS
    USE_SHARED_SCRAPER = True
except ImportError:
    USE_SHARED_SCRAPER = False
    # Fallback to local implementation if shared module not available
    def scrape_url(
            driver,
            url: str,
            wait_sec: int,
            scroll_rounds: int,
            max_posts: int,
            start_dt: Optional[datetime],
            end_dt: Optional[datetime],
            apply_hashtag_fix: bool = True,
            strict_date_filter: bool = False,
            update_progress=None,
            stop_flag=lambda: False,
            app=None
    ) -> Tuple[Optional[List[Dict]], bool]:
        """Return (rows, stopped_by_time_lower_bound)."""
        driver.get(url)
        
        close_overlays(driver)
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except Exception:
            return [], False

        try:
            if "/posts" not in driver.current_url:
                links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/posts/"]')
                if links:
                    driver.execute_script("arguments[0].click();", links[0])
                    WebDriverWait(driver, wait_sec).until(lambda d: "/posts" in d.current_url)
            if "feedView=all" not in driver.current_url:
                base = driver.current_url.split("?")[0]
                driver.get(base + "?feedView=all")
        except Exception:
            pass

        try:
            WebDriverWait(driver, wait_sec).until(
                EC.presence_of_element_located((By.CSS_SELECTOR,
                                                '.organization-content-list__posts-list-item, .feed-shared-update-v2'
                                                ))
            )
            if app:
                app.log("  → Đã tìm thấy khu vực bài post. Bắt đầu cuộn.")
        except Exception as e:
            if app:
                app.log(f"  → ⚠ Timeout/Lỗi khi đợi khu vực bài post. Tiếp tục cuộn...")

        collected: Dict[str, Dict] = {}
        stable_rounds, prev_n = 0, -1
        stop_by_time_hit = False

        for i in range(scroll_rounds):
            if stop_flag():
                break
            try:
                raw = driver.execute_script(EXTRACT_JS) or []
            except Exception:
                raw = []

            for p in raw:
                key = p.get("post_url") or p.get("urn") or (p.get("text") or "")[:120]
                if key and key not in collected:
                    iso = normalize_time(p.get("time_iso"), p.get("time_text"))
                    p["time_iso"] = iso
                    p["text"] = clean_text_keep_newlines(p.get("text"), apply_hashtag_fix=apply_hashtag_fix)

                    if start_dt and iso:
                        try:
                            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
                            if dt < start_dt:
                                stop_by_time_hit = True
                        except Exception:
                            pass

                    if inside_date_range(iso, start_dt, end_dt, strict=strict_date_filter):
                        collected[key] = {
                            "post_url": p.get("post_url"),
                            "urn": p.get("urn"),
                            "time_iso": iso,
                            "text": p.get("text"),
                        }

            n = len(collected)
            if update_progress:
                update_progress(1)
            if n == prev_n:
                stable_rounds += 1
            else:
                stable_rounds = 0
            prev_n = n

            if n >= max_posts or stable_rounds >= 3 or stop_by_time_hit:
                break

            if i > 0 and i % random.randint(8, 15) == 0:
                long_pause = random.uniform(5, 12)
                if app:
                    app.log(f"  → Tạm nghỉ dài {long_pause:.1f} giây để mô phỏng người dùng...")
                time.sleep(long_pause)

            smart_scroll(driver, outer_rounds=2, base_step_px=1100)
        
        return list(collected.values()), stop_by_time_hit


def save_outputs(rows: List[Dict], out_dir: Path, url: str) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = url_to_slug(url)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    jsonl = out_dir / f"{slug}_posts_{ts}.jsonl"
    csv_path = out_dir / f"{slug}_posts_{ts}.csv"

    enriched = []
    for r in rows:
        rec = dict(r)
        rec["date_dmy"] = normalize_time_for_output(rec.get("time_iso"))
        enriched.append(rec)

    with jsonl.open("w", encoding="utf-8") as f:
        for r in enriched:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    pd.DataFrame(enriched).to_csv(
        csv_path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_ALL
    )
    return {"jsonl": str(jsonl), "csv": str(csv_path)}


# ---------- UI helpers (NEW) ----------
class Tooltip:
    """Tooltip đơn giản: Tooltip(widget, text="...")"""

    def __init__(self, widget, text: str, delay: int = 400):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tip = None
        self._after_id = None
        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)

    def _on_enter(self, _):
        self._after_id = self.widget.after(self.delay, self._show)

    def _on_leave(self, _):
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None
        self._hide()

    def _show(self):
        if self.tip or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert") if self.widget.winfo_class() != 'TButton' else (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 12
        y += self.widget.winfo_rooty() + 24
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        lbl = ttk.Label(self.tip, text=self.text, style="Tooltip.TLabel")
        lbl.pack(ipadx=8, ipady=5)

    def _hide(self):
        if self.tip:
            self.tip.destroy()
            self.tip = None


# ---------- GUI ----------
class ScrapeThread(threading.Thread):
    def __init__(self, app, urls: List[str], start_index: int = 0):
        super().__init__(daemon=True)
        self.app = app
        self.urls = urls
        self.start_index = start_index

    def run(self):
        app = self.app
        app.set_running(True)
        app.reset_progress()
        start_time = time.time()
        total_steps = len(self.urls[self.start_index:]) * int(app.var_rounds.get() or 1)
        app.progress_total = max(total_steps, 1)

        all_rows_agg: List[Dict] = []

        try:
            app.log("Khởi động Chrome...")
            driver = app.init_driver()
            app.driver = driver

            out_dir = Path(app.var_outdir.get().strip() or ".")
            cookie_path = out_dir / "cookies.json"
            is_headless = app.var_headless.get()
            
            # Load cookies if available
            if app.var_use_cookies.get() and cookie_path.exists():
                loaded = add_cookies_if_any(driver, cookie_path)
                app.log(f"Đã nạp {loaded} cookies từ: {cookie_path}")
                # Verify cookies by checking if we can access LinkedIn
                try:
                    driver.get("https://www.linkedin.com/feed/")
                    time.sleep(2)  # Wait for page to load
                except Exception:
                    pass

            # Check if logged in
            names = [c['name'] for c in (driver.get_cookies() or [])]
            if "li_at" not in names:
                if is_headless:
                    # Headless mode: Cannot login manually, need cookies
                    app.log("❌ Headless mode: Không có cookies hợp lệ!")
                    app.log("⚠ Vui lòng tắt Headless mode để đăng nhập lần đầu, hoặc đảm bảo có cookies.json hợp lệ.")
                    messagebox.showerror(
                        "Lỗi đăng nhập",
                        "Headless mode cần cookies hợp lệ để tự động đăng nhập.\n\n"
                        "Giải pháp:\n"
                        "1. Tắt Headless mode để đăng nhập lần đầu\n"
                        "2. Hoặc đảm bảo có file cookies.json hợp lệ trong thư mục output"
                    )
                    return
                else:
                    # Non-headless: Show browser and wait for user login
                    app.log("Mở trang đăng nhập LinkedIn...")
                    driver.get("https://www.linkedin.com/login")
                    app.log("Đăng nhập trong Chrome, rồi bấm 'Tôi đã đăng nhập'.")
                    app.wait_login_event.clear()
                    app.enable_continue(True)
                    app.wait_login_event.wait()
                    app.enable_continue(False)
                    if app.var_use_cookies.get():
                        ok, n = save_cookies(driver, cookie_path)
                        if ok:
                            app.log(f"Đã lưu {n} cookies → {cookie_path}")
                        else:
                            app.log("⚠ Không thể lưu cookies (xem log).")
            else:
                # Already logged in (cookies worked)
                if is_headless:
                    app.log("✅ Headless mode: Đã đăng nhập tự động bằng cookies")
                else:
                    app.log("✅ Đã đăng nhập (cookies hợp lệ)")

            urls = self.urls
            for idx in range(self.start_index, len(urls)):
                if app.stop_requested:
                    app.log("⏹ Đã nhận yêu cầu dừng. Kết thúc sớm.")
                    break
                url = urls[idx].strip()
                if not url:
                    continue
                app.log(f"[{idx + 1}/{len(urls)}] Đang lấy: {url}")

                start_dt, end_dt = app.get_date_range()
                write_checkpoint(
                    out_dir=out_dir,
                    urls=urls,
                    next_index=idx,
                    filters={
                        "start": app.var_start_date.get().strip(),
                        "end": app.var_end_date.get().strip(),
                    },
                )

                result, hit_time_stop = scrape_url(
                    driver=driver, url=url,
                    wait_sec=int(app.var_wait.get()), scroll_rounds=int(app.var_rounds.get()),
                    max_posts=int(app.var_max.get()), start_dt=start_dt, end_dt=end_dt,
                    apply_hashtag_fix=app.var_fix_hashtag.get(), update_progress=app.update_progress,
                    stop_flag=lambda: app.stop_requested,
                    strict_date_filter=app.var_strict_date.get(),
                    app=self.app
                )

                if result is None:
                    app.log(f"  → ⚠ URL không hợp lệ hoặc không tải được. Bỏ qua.")
                    write_checkpoint(out_dir, urls, idx + 1,
                                     {"start": app.var_start_date.get(), "end": app.var_end_date.get()})
                    continue

                rows = result
                all_rows_agg.extend(rows)
                app.log(
                    f"  → Thu được {len(rows)} bài (stop-by-time: {'YES' if hit_time_stop else 'no'})."
                )

                if app.var_preview.get():
                    app.preview_rows(rows[:5], title=f"Preview 5 — {url}")

                files = save_outputs(rows, out_dir, url)
                app.log(f"  → Đã lưu: {files['csv']}")

                write_checkpoint(
                    out_dir=out_dir,
                    urls=urls,
                    next_index=idx + 1,
                    filters={
                        "start": app.var_start_date.get().strip(),
                        "end": app.var_end_date.get().strip(),
                    },
                )

                if idx < len(urls) - 1:
                    delay = random.uniform(5, 10)
                    app.log(f"  → Tạm nghỉ ngẫu nhiên {delay:.1f} giây...")
                    time.sleep(delay)

                elapsed = time.time() - start_time
                done_steps = app.progress_done
                if done_steps:
                    rate = elapsed / done_steps
                    remain = max(0, app.progress_total - done_steps) * rate
                    app.set_eta(remain)

            next_idx = read_checkpoint(out_dir) or {}
            if next_idx and next_idx.get("next_index", 0) >= len(self.urls):
                remove_checkpoint(out_dir)

            app.enable_open_folder(True)
            app.show_analysis(all_rows_agg)
            app.log("Hoàn tất.")
        except Exception as e:
            app.log(f"❌ Lỗi: {e}")
            messagebox.showerror("Lỗi", str(e))
        finally:
            # Auto save cookies before closing driver
            try:
                if app.driver and app.var_use_cookies.get():
                    out_dir = Path(app.var_outdir.get().strip() or ".")
                    cookie_path = out_dir / "cookies.json"
                    ok, n = save_cookies(app.driver, cookie_path)
                    if ok:
                        app.log(f"💾 Đã tự động lưu {n} cookies → {cookie_path}")
                    else:
                        app.log("⚠ Không thể tự động lưu cookies (xem log)")
            except Exception as e:
                app.log(f"⚠ Lỗi khi tự động lưu cookies: {e}")
            
            # Close driver
            try:
                if app.driver:
                    app.driver.quit()
            except Exception:
                pass
            app.set_running(False)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LinkedIn Company Posts Crawler — Professional Edition")
        self.geometry("1040x760")
        self.driver = None
        self.last_output_list = None
        self.stop_requested = False

        # Vars (logic giữ nguyên)
        self.var_headless = tk.BooleanVar(value=True)
        self.var_use_uc = tk.BooleanVar(value=True)
        self.var_use_cookies = tk.BooleanVar(value=True)
        self.var_fix_hashtag = tk.BooleanVar(value=True)
        self.var_preview = tk.BooleanVar(value=True)
        self.var_strict_date = tk.BooleanVar(value=False)
        self.var_dark_mode = tk.BooleanVar(value=True)  # Dark mode on by default

        self.var_mode_batch = tk.BooleanVar(value=False)
        self.var_url = tk.StringVar(value="https://www.linkedin.com/company/viettel-cyber-security/posts/?feedView=all")
        self.var_outdir = tk.StringVar(value=str(Path.home() / "LinkedInOut"))
        self.var_wait = tk.StringVar(value="30")
        self.var_rounds = tk.StringVar(value="60")
        self.var_max = tk.StringVar(value="300")
        self.var_start_date = tk.StringVar(value="")  # DD-MM-YYYY
        self.var_end_date = tk.StringVar(value="")  # DD-MM-YYYY

        self.progress_done = 0
        self.progress_total = 1
        self.wait_login_event = threading.Event()

        # NEW: init style/theme first
        self._configure_styles()

        # UI
        self._build_ui()
        self.log_queue = queue.Queue()
        self.after(100, self._drain_log_queue)
        self.after(300, self._maybe_prompt_resume)

        # Shortcuts
        self.bind('<F5>', lambda e: self._on_start())
        self.bind('<Escape>', lambda e: self._on_stop())
        self.bind('<Control-s>', lambda e: self._save_cookies_now())
        self.bind('<Control-o>', lambda e: self._open_folder())

    # ---------- UI (Enhanced) ----------
    def _toggle_theme(self):
        self._configure_styles()

    def _configure_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except Exception:
            pass

        is_dark = self.var_dark_mode.get()

        # --- Color Palette ---
        if is_dark:
            BG, FG, WIDGET_BG, SELECT_BG, SELECT_FG, BORDER, HEADER_FG, SUB_FG, TT_BG, TT_FG = (
                '#2b2b2b', '#dcdcdc', '#3c3c3c', '#4a6984', '#ffffff', '#555555', '#e0e0e0', '#999999', '#111827',
                '#f9fafb'
            )
        else:  # Light mode
            BG, FG, WIDGET_BG, SELECT_BG, SELECT_FG, BORDER, HEADER_FG, SUB_FG, TT_BG, TT_FG = (
                '#f0f0f0', '#000000', '#ffffff', '#0078d7', '#ffffff', '#adadad', '#000000', '#6b7280', '#333333',
                '#f9fafb'
            )

        PRIMARY_BG, DANGER_BG, ACCENT_BG = '#0078d4', '#c53929', '#2d882d'

        self.config(bg=BG)

        # --- Fonts ---
        base = tkfont.nametofont('TkDefaultFont')
        base.configure(size=10)
        fixed = tkfont.nametofont('TkFixedFont')
        fixed.configure(size=10)
        self.option_add('*TCombobox*Listbox.font', base)

        # --- General Widget Styles ---
        style.configure('.', background=BG, foreground=FG, bordercolor=BORDER, lightcolor=WIDGET_BG,
                        darkcolor=WIDGET_BG)
        style.map('.', background=[('active', WIDGET_BG)])
        style.configure('TFrame', background=BG)
        style.configure('TLabel', background=BG, foreground=FG)
        style.configure('TCheckbutton', background=BG, foreground=FG)
        style.map('TCheckbutton', foreground=[('active', FG)], background=[('active', BG)])

        # Header
        style.configure('Header.TLabel', font=(base.actual('family'), 15, 'bold'), foreground=HEADER_FG, background=BG)
        style.configure('SubHeader.TLabel', foreground=SUB_FG, background=BG)

        # Tooltip
        style.configure('Tooltip.TLabel', background=TT_BG, foreground=TT_FG, borderwidth=1, relief='solid')

        # Labelframe (Card)
        style.configure('Card.TLabelframe', background=BG, bordercolor=BORDER, padding=12)
        style.configure('Card.TLabelframe.Label', font=(base.actual('family'), 11, 'bold'), background=BG,
                        foreground=HEADER_FG)

        # Entry
        style.configure('TEntry', fieldbackground=WIDGET_BG, foreground=FG, borderwidth=1, insertcolor=FG)
        style.map('TEntry', bordercolor=[('focus', SELECT_BG)], lightcolor=[('focus', SELECT_BG)])

        # Buttons
        style.configure('TButton', padding=(10, 6), background=WIDGET_BG, foreground=FG, borderwidth=1)
        style.map('TButton', background=[('active', SELECT_BG), ('!disabled', WIDGET_BG)],
                  foreground=[('active', SELECT_FG)])

        style.configure('Primary.TButton', padding=(14, 8), background=PRIMARY_BG, foreground=SELECT_FG)
        style.map('Primary.TButton', background=[('active', '#005a9e')])
        style.configure('Danger.TButton', padding=(14, 8), background=DANGER_BG, foreground=SELECT_FG)
        style.map('Danger.TButton', background=[('active', '#a02d20')])
        style.configure('Accent.TButton', padding=(14, 8), background=ACCENT_BG, foreground=SELECT_FG)
        style.map('Accent.TButton', background=[('active', '#246a24')])

        # Progressbar
        style.configure('Slim.Horizontal.TProgressbar', thickness=14, background=SELECT_BG, troughcolor=WIDGET_BG,
                        bordercolor=BORDER)

        # --- Update non-ttk widgets (if they exist) ---
        if hasattr(self, 'txt'):
            for widget in [self.txt, self.txt_urls]:
                widget.config(background=WIDGET_BG, foreground=FG, insertbackground=FG,
                              relief='solid', bd=1, highlightthickness=1, highlightcolor=BORDER,
                              highlightbackground=BORDER)

    def _make_sep(self, parent):
        sep = ttk.Separator(parent, orient='horizontal')
        sep.pack(fill='x', pady=10)

    def _build_ui(self):
        # --- Scrollable main frame ---
        container = ttk.Frame(self)
        container.pack(fill='both', expand=True)

        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, padding=12)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)

        canvas.bind('<Configure>', on_canvas_configure)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            # Check if the widget under the mouse is the console ScrolledText
            widget = event.widget.winfo_containing(event.x_root, event.y_root)
            if widget and 'scrolledtext' in str(widget).lower():
                return  # Let the ScrolledText handle its own scrolling
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.bind_all("<MouseWheel>", _on_mousewheel)

        root = scrollable_frame  # All widgets go into this frame

        # Header
        hdr = ttk.Frame(root)
        hdr.pack(fill='x', pady=(0, 8))
        ttk.Label(hdr, text='LinkedIn Company Posts Crawler', style='Header.TLabel').pack(anchor='w')
        ttk.Label(hdr, text='Professional Edition · Smart Automation · Modern UI',
                  style='SubHeader.TLabel').pack(anchor='w', pady=(2, 0))

        # == Section: Input URLs ==
        sec_input = ttk.Labelframe(root, text='Nguồn dữ liệu', style='Card.TLabelframe')
        sec_input.pack(fill='x', pady=8)

        mode_line = ttk.Frame(sec_input)
        mode_line.pack(fill='x', pady=(0, 6))
        ttk.Checkbutton(mode_line, text='Batch mode (nhiều URL)', variable=self.var_mode_batch,
                        command=self._toggle_mode).pack(anchor='w')

        # Single URL
        self.single_frame = ttk.Frame(sec_input)
        self.single_frame.pack(fill='x')
        ttk.Label(self.single_frame, text='Company Posts URL:').grid(row=0, column=0, sticky='w', padx=(0, 8))
        self.ent_url = ttk.Entry(self.single_frame, textvariable=self.var_url)
        self.ent_url.grid(row=0, column=1, sticky='we', pady=4)
        self.single_frame.columnconfigure(1, weight=1)
        Tooltip(self.ent_url, 'Dán link dạng https://www.linkedin.com/company/<slug>/posts/?feedView=all')

        # Batch URLs
        self.batch_frame = ttk.Frame(sec_input)
        ttk.Label(self.batch_frame, text='Dán nhiều URL (mỗi dòng một URL):').grid(row=0, column=0, sticky='w')
        self.txt_urls = tk.Text(self.batch_frame, height=6, wrap='none')
        self.txt_urls.grid(row=1, column=0, columnspan=4, sticky='we', pady=4)
        ttk.Button(self.batch_frame, text='Load CSV…', command=self._load_csv).grid(row=1, column=4, sticky='w', padx=8)
        self.batch_frame.columnconfigure(0, weight=1)

        # == Section: Output & Dates ==
        sec_out = ttk.Labelframe(root, text='Xuất liệu & Khoảng ngày', style='Card.TLabelframe')
        sec_out.pack(fill='x', pady=8)

        row1 = ttk.Frame(sec_out)
        row1.pack(fill='x', pady=2)
        ttk.Label(row1, text='Output folder:').grid(row=0, column=0, sticky='w')
        self.ent_out = ttk.Entry(row1, textvariable=self.var_outdir)
        self.ent_out.grid(row=0, column=1, sticky='we')
        ttk.Button(row1, text='Browse…', command=self._choose_outdir).grid(row=0, column=2, padx=6)
        row1.columnconfigure(1, weight=1)
        Tooltip(self.ent_out, 'Thư mục lưu CSV/JSONL và cookies.json')

        row2 = ttk.Frame(sec_out)
        row2.pack(fill='x', pady=2)
        ttk.Label(row2, text='Start date (DD-MM-YYYY):').grid(row=0, column=0, sticky='w')
        ttk.Entry(row2, textvariable=self.var_start_date, width=18).grid(row=0, column=1, sticky='w')
        ttk.Label(row2, text='End date (DD-MM-YYYY):').grid(row=0, column=2, sticky='w', padx=(12, 0))
        ttk.Entry(row2, textvariable=self.var_end_date, width=18).grid(row=0, column=3, sticky='w')
        ttk.Checkbutton(row2, text='Strict date filter (loại bài thiếu ngày)', variable=self.var_strict_date).grid(
            row=1, column=0, columnspan=4, sticky='w', pady=(6, 0))

        # == Section: Performance ==
        sec_perf = ttk.Labelframe(root, text='Thiết lập hiệu năng', style='Card.TLabelframe')
        sec_perf.pack(fill='x', pady=8)
        p = ttk.Frame(sec_perf)
        p.pack(fill='x')
        ttk.Label(p, text='Wait (s):').grid(row=0, column=0, sticky='w')
        ttk.Entry(p, textvariable=self.var_wait, width=6).grid(row=0, column=1, sticky='w', padx=(4, 20))
        ttk.Label(p, text='Scroll rounds:').grid(row=0, column=2, sticky='w')
        ttk.Entry(p, textvariable=self.var_rounds, width=6).grid(row=0, column=3, sticky='w', padx=(4, 20))
        ttk.Label(p, text='Max posts:').grid(row=0, column=4, sticky='w')
        ttk.Entry(p, textvariable=self.var_max, width=6).grid(row=0, column=5, sticky='w', padx=(4, 20))
        p.columnconfigure(6, weight=1)
        Tooltip(p, 'Wait: timeout chờ post đầu; Scroll rounds: vòng cuộn; Max posts: giới hạn bài')

        # == Section: Options ==
        sec_opts = ttk.Labelframe(root, text='Tuỳ chọn', style='Card.TLabelframe')
        sec_opts.pack(fill='x', pady=8)
        opts = ttk.Frame(sec_opts)
        opts.pack(fill='x')
        
        # Browser & Display Options
        browser_opts = ttk.Frame(opts)
        browser_opts.pack(fill='x', pady=2)
        ttk.Label(browser_opts, text='Browser:', font=('TkDefaultFont', 9, 'bold')).pack(side='left', padx=(0, 8))
        cb_headless = ttk.Checkbutton(browser_opts, text='Headless (ẩn browser)', variable=self.var_headless)
        cb_headless.pack(side='left', padx=(0, 14))
        Tooltip(cb_headless, 'Bật: Chạy ngầm không hiển thị browser (nhanh hơn)\nTắt: Hiển thị browser (dễ debug)')
        
        cb_uc = ttk.Checkbutton(browser_opts, text='Use Undetected-CD', variable=self.var_use_uc)
        cb_uc.pack(side='left', padx=(0, 14))
        Tooltip(cb_uc, 'Sử dụng undetected-chromedriver để tránh bị phát hiện')
        
        cb_cookies = ttk.Checkbutton(browser_opts, text='Auto cookies', variable=self.var_use_cookies)
        cb_cookies.pack(side='left', padx=(0, 14))
        Tooltip(cb_cookies, 'Tự động lưu và tải cookies để tránh phải đăng nhập lại')
        
        # Other Options
        other_opts = ttk.Frame(opts)
        other_opts.pack(fill='x', pady=(4, 0))
        ttk.Label(other_opts, text='Khác:', font=('TkDefaultFont', 9, 'bold')).pack(side='left', padx=(0, 8))
        cb_preview = ttk.Checkbutton(other_opts, text='Preview 5 before save', variable=self.var_preview)
        cb_preview.pack(side='left', padx=(0, 14))
        Tooltip(cb_preview, 'Hiển thị 5 bài đầu tiên trước khi lưu')
        
        cb_fix_hashtag = ttk.Checkbutton(other_opts, text='Fix Hashtags', variable=self.var_fix_hashtag)
        cb_fix_hashtag.pack(side='left', padx=(0, 14))
        Tooltip(cb_fix_hashtag, 'Tự động sửa "hashtag#" thành "#"')
        
        cb_dark = ttk.Checkbutton(other_opts, text='Dark Mode', variable=self.var_dark_mode, command=self._toggle_theme)
        cb_dark.pack(side='left')
        Tooltip(cb_dark, 'Chuyển đổi giao diện tối/sáng')

        # == Section: Actions ==
        act = ttk.Frame(root)
        act.pack(fill='x', pady=(8, 4))
        self.btn_start = ttk.Button(act, text='▶ Start', style='Primary.TButton', command=self._on_start)
        self.btn_continue = ttk.Button(act, text='🔑 Tôi đã đăng nhập', style='Accent.TButton',
                                       command=self._on_continue, state='disabled')
        self.btn_stop = ttk.Button(act, text='■ Stop', style='Danger.TButton', command=self._on_stop, state='normal')
        self.btn_savecookies = ttk.Button(act, text='💾 Save cookies', command=self._save_cookies_now)
        self.btn_open = ttk.Button(act, text='📂 Mở thư mục xuất', command=self._open_folder, state='disabled')

        self.btn_start.grid(row=0, column=0, padx=(0, 6))
        self.btn_continue.grid(row=0, column=1, padx=6)
        self.btn_stop.grid(row=0, column=2, padx=6)
        self.btn_savecookies.grid(row=0, column=3, padx=6)
        self.btn_open.grid(row=0, column=4, padx=6)
        act.columnconfigure(5, weight=1)

        # Progress
        p2 = ttk.Frame(root)
        p2.pack(fill='x')
        self.prog = ttk.Progressbar(p2, orient='horizontal', mode='determinate', style='Slim.Horizontal.TProgressbar')
        self.prog.pack(side='left', fill='x', expand=True, padx=(0, 8))
        self.lbl_eta = ttk.Label(p2, text='ETA: --:--')
        self.lbl_eta.pack(side='left')

        # Logs
        sec_log = ttk.Labelframe(root, text='Console', style='Card.TLabelframe')
        sec_log.pack(fill='x', expand=False, pady=8)
        self.txt = ScrolledText(sec_log, height=16, wrap='word', font=('Consolas', 10))
        self.txt.pack(fill='both', expand=True)

        # Apply initial theme to non-ttk widgets
        self._configure_styles()

        # Set background of canvas after styles are loaded
        style = ttk.Style(self)
        bg_color = style.lookup('.', 'background')
        canvas.config(bg=bg_color)

    # ----- actions (unchanged logic) -----
    def _toggle_mode(self):
        if self.var_mode_batch.get():
            self.single_frame.pack_forget()
            self.batch_frame.pack(fill='x')
        else:
            self.batch_frame.pack_forget()
            self.single_frame.pack(fill='x')

    def _choose_outdir(self):
        d = filedialog.askdirectory(initialdir=self.var_outdir.get() or str(Path.home()))
        if d:
            self.var_outdir.set(d)

    def _load_csv(self):
        fp = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not fp:
            return
        try:
            df = pd.read_csv(fp)
            col = None
            for c in df.columns:
                if c.lower() == "url":
                    col = c
                    break
            if not col:
                col = df.columns[0]
            urls = [str(x) for x in df[col].dropna().tolist()]
            self.txt_urls.delete("1.0", "end")
            self.txt_urls.insert("1.0", "\n".join(urls))
            messagebox.showinfo("OK", f"Đã nạp {len(urls)} URL từ CSV.")
        except Exception as e:
            messagebox.showerror("CSV error", str(e))

    def _maybe_prompt_resume(self):
        try:
            ck = read_checkpoint(Path(self.var_outdir.get().strip() or "."))
            if ck and isinstance(ck.get("urls"), list):
                n = len(ck["urls"]) - ck.get("next_index", 0)
                if n > 0:
                    if messagebox.askyesno("Resume", f"Phát hiện checkpoint. Tiếp tục {n} URL còn lại?"):
                        self.var_mode_batch.set(True)
                        self._toggle_mode()
                        self.txt_urls.delete("1.0", "end")
                        self.txt_urls.insert("1.0", "\n".join(ck["urls"]))
                        self.var_start_date.set(ck.get("filters", {}).get("start", ""))
                        self.var_end_date.set(ck.get("filters", {}).get("end", ""))
        except Exception:
            pass

    def _on_start(self):
        if hasattr(self, "running") and self.running:
            messagebox.showinfo("Đang chạy", "Vui lòng đợi tác vụ hiện tại xong.")
            return
        urls: List[str] = []
        if self.var_mode_batch.get():
            urls = [u.strip() for u in self.txt_urls.get("1.0", "end").splitlines() if u.strip()]
        else:
            urls = [self.var_url.get().strip()]
        if not urls:
            messagebox.showwarning("Thiếu URL", "Nhập ít nhất một URL.")
            return

        start_index = 0
        ck = read_checkpoint(Path(self.var_outdir.get().strip() or "."))
        if ck and ck.get("urls") == urls:
            ni = int(ck.get("next_index", 0))
            if 0 <= ni < len(urls):
                if messagebox.askyesno("Resume", f"Khôi phục từ URL thứ {ni + 1}?"):
                    start_index = ni

        self.stop_requested = False
        self.txt.delete("1.0", "end")
        self.enable_open_folder(False)
        th = ScrapeThread(self, urls, start_index=start_index)
        th.start()

    def _on_continue(self):
        self.wait_login_event.set()

    def _on_stop(self):
        self.stop_requested = True
        self.log("⏹ Sẽ dừng sau vòng cuộn hiện tại...")

    def _save_cookies_now(self):
        if not self.driver:
            messagebox.showwarning("Chưa khởi động Chrome", "Hãy bấm Start và đăng nhập trước.")
            return
        cookie_path = Path(self.var_outdir.get().strip() or ".") / "cookies.json"
        ok, n = save_cookies(self.driver, cookie_path)
        if ok:
            self.log(f"Đã lưu {n} cookies → {cookie_path}")
            messagebox.showinfo("OK", f"Saved {n} cookies to\n{cookie_path}")
        else:
            self.log("⚠ Không thể lưu cookies (xem log)")

    def _open_folder(self):
        d = self.var_outdir.get().strip()
        if d and Path(d).exists():
            webbrowser.open(d)

    def enable_continue(self, enable: bool):
        self.btn_continue.config(state=("normal" if enable else "disabled"))

    def enable_open_folder(self, enable: bool):
        self.btn_open.config(state=("normal" if enable else "disabled"))

    def set_running(self, val: bool):
        self.running = val
        self.btn_start.config(state=("disabled" if val else "normal"))
        self.btn_stop.config(state=("normal" if val else "disabled"))

    def log(self, s: str):
        self.log_queue.put(nfc(str(s)))

    def _drain_log_queue(self):
        try:
            while True:
                s = self.log_queue.get_nowait()
                self.txt.insert("end", s + "\n")
                self.txt.see("end")
        except queue.Empty:
            pass
        self.after(100, self._drain_log_queue)

    def init_driver(self):
        return init_driver(
            headless=self.var_headless.get(),
            use_uc=self.var_use_uc.get(),
            fast_mode=True,
        )

    def get_date_range(self) -> Tuple[Optional[datetime], Optional[datetime]]:
        def parse_d_dmy(s: str) -> Optional[datetime]:
            s = s.strip()
            if not s:
                return None
            try:
                d_local = datetime.strptime(s, "%d-%m-%Y").replace(
                    tzinfo=timezone(timedelta(hours=7))
                )
                return d_local.astimezone(timezone.utc)
            except Exception:
                return None

        s_raw = self.var_start_date.get()
        e_raw = self.var_end_date.get()
        start_dt = parse_d_dmy(s_raw)
        end_dt = parse_d_dmy(e_raw)

        swapped = False
        if start_dt and end_dt and start_dt > end_dt:
            swapped = True
            start_dt, end_dt = end_dt, start_dt

        if swapped:
            messagebox.showinfo("Date range", f"Start > End ({s_raw} > {e_raw}). Đã tự hoán đổi.")
            self.log(f"⚠ Start > End ({s_raw} > {e_raw}) — tự động hoán đổi.")

        if not (start_dt or end_dt):
            self.log("Không lọc theo ngày (Start/End để trống).")
        else:
            def as_dmy(dt):
                if not dt:
                    return "—"
                vn = timezone(timedelta(hours=7))
                return dt.astimezone(vn).strftime("%d-%m-%Y")

            self.log(f"Áp dụng khoảng ngày: {as_dmy(start_dt)} → {as_dmy(end_dt)}")
            if self.var_strict_date.get():
                self.log("Áp dụng: Strict date filter (loại bài thiếu/lỗi ngày).")
            else:
                self.log("Áp dụng: Non-Strict date filter (giữ lại bài thiếu/lỗi ngày).")

        return start_dt, end_dt

    # progress/ETA
    def reset_progress(self):
        self.progress_done = 0
        self.prog["value"] = 0
        self.prog["maximum"] = max(self.progress_total, 1)
        self.lbl_eta.config(text="ETA: --:--")

    def update_progress(self, step=1):
        self.progress_done += step
        self.prog["maximum"] = max(self.progress_total, 1)
        self.prog["value"] = min(self.progress_done, self.progress_total)
        self.update_idletasks()

    def set_eta(self, seconds_left: float):
        m, s = divmod(int(seconds_left), 60)
        self.lbl_eta.config(text=f"ETA: {m:02d}:{s:02d}")

    def preview_rows(self, rows: List[Dict], title: str = "Preview 5"):
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("800x500")

        txt = tk.Text(win, wrap="word")
        txt.pack(fill="both", expand=True, padx=8, pady=8)

        for i, r in enumerate(rows, 1):
            txt.insert("end", f"#{i}  URL: {r.get('post_url')}\n")
            txt.insert("end", f"URN: {r.get('urn')}\n")
            txt.insert("end", f"Time ISO: {r.get('time_iso')}\n")
            txt.insert("end", f"Date: {normalize_time_for_output(r.get('time_iso'))}\n")
            txt.insert("end", "-" * 50 + "\n")
            txt.insert("end", (r.get('text') or '') + "\n\n")

    # quick analysis window (giữ nguyên logic, UI nhỏ gọn)
    def show_analysis(self, rows: List[Dict]):
        if not rows:
            return
        try:
            df = pd.DataFrame(rows)
            df["date_dmy"] = df["time_iso"].map(normalize_time_for_output)

            total_posts = len(df)
            days_nonempty = df.dropna(subset=["date_dmy"]).copy()
            n_days = days_nonempty["date_dmy"].nunique() if not days_nonempty.empty else 0

            per_day = (
                df.dropna(subset=["date_dmy"])  # type: ignore
                .groupby("date_dmy").size().sort_values(ascending=False)
            )
            per_day_df = per_day.rename("count").reset_index()
            if not per_day_df.empty:
                max_day = per_day_df["count"].max()
                per_day_df["percent"] = (per_day_df["count"] / max_day * 100).round(1)
                per_day_df["bar"] = per_day_df["count"].apply(
                    lambda c: "█" * max(1, int(20 * c / max_day))
                )

            def extract_tags(x):
                if not isinstance(x, str):
                    return []
                return re.findall(r"#[^\s#]+", x)

            all_tags = []
            for lst in df["text"].map(extract_tags).tolist():
                all_tags.extend([t.lower() for t in lst])

            tag_series = pd.Series(all_tags)
            top_tags_df = pd.DataFrame(columns=["hashtag", "count", "percent", "bar"])
            if not tag_series.empty:
                vc = tag_series.value_counts()
                top_tags_df = (
                    vc.head(25).rename_axis("hashtag").reset_index(name="count")
                )
                max_tag = top_tags_df["count"].max()
                top_tags_df["percent"] = (top_tags_df["count"] / max_tag * 100).round(1)
                top_tags_df["bar"] = top_tags_df["count"].apply(
                    lambda c: "█" * max(1, int(20 * c / max_tag))
                )

            win = tk.Toplevel(self)
            win.title("Quick Analysis")
            win.geometry("920x620")

            # --- Light Theme for this window ---
            s = ttk.Style(win)
            BG, FG, WIDGET_BG, SELECT_BG, SELECT_FG, BORDER = (
                '#f0f0f0', '#000000', '#ffffff', '#0078d7', '#ffffff', '#adadad'
            )
            win.configure(bg=BG)

            s.configure("Light.TNotebook", background=BG, borderwidth=0)
            s.configure("Light.TNotebook.Tab", background="#e0e0e0", foreground=FG, padding=[10, 5], borderwidth=1)
            s.map("Light.TNotebook.Tab", background=[("selected", WIDGET_BG)], bordercolor=[("selected", BORDER)])

            s.configure("Light.TFrame", background=WIDGET_BG)

            s.configure("Light.Treeview", background=WIDGET_BG, foreground=FG, fieldbackground=WIDGET_BG)
            s.map("Light.Treeview", background=[('selected', SELECT_BG)], foreground=[('selected', SELECT_FG)])
            s.configure("Light.Treeview.Heading", background=BG, foreground=FG, padding=6, relief='flat')
            s.map("Light.Treeview.Heading", background=[('active', '#e5e5e5')])

            s.configure("Light.TButton", padding=(8, 4), background='#e0e0e0', foreground=FG, borderwidth=1,
                        bordercolor=BORDER)
            s.map("Light.TButton", background=[('active', '#c0c0c0')])

            s.configure("Light.Vertical.TScrollbar", troughcolor=BG, background='#c1c1c1', borderwidth=0, relief='flat',
                        arrowsize=0)
            s.map("Light.Vertical.TScrollbar", background=[('active', '#a1a1a1')])
            s.configure("Light.Horizontal.TScrollbar", troughcolor=BG, background='#c1c1c1', borderwidth=0,
                        relief='flat', arrowsize=0)
            s.map("Light.Horizontal.TScrollbar", background=[('active', '#a1a1a1')])

            nb = ttk.Notebook(win, style="Light.TNotebook")
            nb.pack(fill="both", expand=True, padx=10, pady=(5, 10))

            def make_table(parent, columns, widths, rows):
                frame = ttk.Frame(parent, style="Light.TFrame")
                tree = ttk.Treeview(frame, columns=columns, show="headings", style="Light.Treeview")
                vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview, style="Light.Vertical.TScrollbar")
                hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview, style="Light.Horizontal.TScrollbar")
                tree.configure(yscroll=vsb.set, xscroll=hsb.set)
                tree.grid(row=0, column=0, sticky="nsew")
                vsb.grid(row=0, column=1, sticky="ns")
                hsb.grid(row=1, column=0, sticky="we")
                frame.rowconfigure(0, weight=1)
                frame.columnconfigure(0, weight=1)

                for c, w in zip(columns, widths):
                    tree.heading(c, text=c)
                    tree.column(c, width=w, anchor="w")
                for r in rows:
                    tree.insert("", "end", values=r)

                def copy_all():
                    vals = ["\t".join(map(str, columns))]
                    for iid in tree.get_children(""):
                        vals.append("\t".join(
                            "" if x is None else str(x)
                            for x in tree.item(iid, "values")
                        ))
                    win.clipboard_clear()
                    win.clipboard_append("\n".join(vals))
                    messagebox.showinfo("Copied", "Đã copy bảng vào clipboard", parent=win)

                def export_csv():
                    fp = filedialog.asksaveasfilename(
                        defaultextension=".csv",
                        filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
                        parent=win
                    )
                    if not fp:
                        return
                    try:
                        import csv as _csv
                        with open(fp, "w", encoding="utf-8-sig", newline="") as f:
                            w = _csv.writer(f)
                            w.writerow(columns)
                            for iid in tree.get_children(""):
                                w.writerow(list(tree.item(iid, "values")))
                        messagebox.showinfo("OK", f"Đã xuất: {fp}", parent=win)
                    except Exception as e:
                        messagebox.showerror("CSV error", str(e), parent=win)

                btns = ttk.Frame(frame, style="Light.TFrame")
                btns.grid(row=2, column=0, sticky="w", pady=(8, 0))
                ttk.Button(btns, text="Copy", command=copy_all, style="Light.TButton").pack(side="left", padx=(0, 6))
                ttk.Button(btns, text="Export CSV", command=export_csv, style="Light.TButton").pack(side="left")
                frame.pack(fill="both", expand=True, padx=10, pady=10)
                return frame

            # Tab 1: Tổng quan
            sum_tab = ttk.Frame(nb, style="Light.TFrame")
            nb.add(sum_tab, text="Tổng quan")
            summary = tk.Text(sum_tab, wrap="word", height=6, relief='solid', bd=1,
                              background=WIDGET_BG, foreground=FG, font=tkfont.nametofont('TkDefaultFont'))
            summary.pack(fill="x", padx=10, pady=10)
            summary.insert("end", f"Tổng số bài: {total_posts}\n")
            summary.insert("end", f"Số ngày có bài: {n_days}\n")
            if not per_day_df.empty:
                top_day = per_day_df.iloc[0]
                summary.insert("end", f"Ngày nhiều bài nhất: {top_day['date_dmy']} ({top_day['count']})\n")
            summary.config(state='disabled')

            # Tab 2: Bài theo ngày
            day_tab = ttk.Frame(nb)
            nb.add(day_tab, text="Bài theo ngày")
            if per_day_df.empty:
                lbl = ttk.Label(day_tab, text="Không có dữ liệu ngày.", background=WIDGET_BG, foreground=FG)
                lbl.pack(pady=20)
            else:
                cols = ["date_dmy", "count", "%", "bar"]
                widths = [120, 80, 60, 260]
                rows_view = per_day_df[["date_dmy", "count", "percent", "bar"]].values.tolist()
                make_table(day_tab, cols, widths, rows_view)

            # Tab 3: Top hashtags
            tag_tab = ttk.Frame(nb)
            nb.add(tag_tab, text="Top hashtags")
            if top_tags_df.empty:
                lbl = ttk.Label(tag_tab, text="Không tìm thấy hashtag.", background=WIDGET_BG, foreground=FG)
                lbl.pack(pady=20)
            else:
                cols = ["hashtag", "count", "%", "bar"]
                widths = [240, 80, 60, 260]
                rows_view = top_tags_df[["hashtag", "count", "percent", "bar"]].values.tolist()
                make_table(tag_tab, cols, widths, rows_view)

            # Set tab content background
            for tab in [day_tab, tag_tab]:
                tab.configure(style="Light.TFrame")


        except Exception as e:
            self.log(f"⚠ Analysis error: {e}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
