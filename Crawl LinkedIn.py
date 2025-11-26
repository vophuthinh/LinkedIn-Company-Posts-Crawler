# -*- coding: utf-8 -*-
"""
LinkedIn Profile GUI Crawler (Single / Batch)
- Nhập 1 URL (vd: https://www.linkedin.com/in/jasica-nagpal/) hoặc Batch (textarea/CSV có cột 'url')
- Đăng nhập tay lần đầu (bấm "Tôi đã đăng nhập") → lưu cookies.json; lần sau tự nạp
- Trích xuất: name, headline, location, about (đã làm sạch), experience_top3 (đã rút gọn),
             education_top3, licenses_certifications_top, skills_top, profile_url
- Xuất: CSV (UTF-8 BOM) + JSONL

Cài đặt nhanh:
    pip install -U selenium pandas
"""

import csv
import json
import queue
import random
import re
import time
import unicodedata
import webbrowser
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# --- HTTP/locale: ưu tiên English để giảm trùng VN/EN (có thể đổi lại nếu muốn) ---
ACCEPT_LANG = "en-US,en;q=0.9,vi-VN;q=0.6,vi;q=0.5"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# ======================== Chuỗi & chuẩn hóa ========================
def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)

def clean_text(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = nfc(s)
    s = re.sub(r"\u00A0", " ", s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = s.strip()
    return s or None

def normalize_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return u
    if not u.startswith("http"):
        u = "https://www.linkedin.com" + (u if u.startswith("/") else ("/" + u))
    u = u.split("?")[0].split("#")[0]
    return u if u.endswith("/") else (u + "/")

# ======== Cleaners & Pretty Format (chống lặp VN/EN, rút gọn Experience) ========
def _norm_near_dup(s: str) -> str:
    x = s.lower()
    x = x.replace(" – ", " đến ").replace(" — ", " đến ").replace(" - ", " đến ")
    x = x.replace(" to ", " đến ").replace("present", "hiện tại")
    x = x.replace("·", " ")
    x = re.sub(r"(và hơn|and)\s+\d+\s+(kỹ năng|more skills)[^,]*", "", x)
    x = re.sub(r"\s+", " ", x).strip()
    return x

def unique_lines_pretty(text: str) -> str:
    if not text:
        return text
    out, seen = [], set()
    for raw in [l.strip() for l in text.splitlines() if l.strip()]:
        k = _norm_near_dup(raw)
        if k and k not in seen:
            seen.add(k)
            out.append(raw)
    return "\n".join(out)

def pretty_about(text: str) -> str:
    t = unique_lines_pretty(text or "")
    paras, buf = [], []
    for line in t.splitlines():
        buf.append(line)
        if len(line) > 100:
            paras.append(" ".join(buf)); buf = []
    if buf: paras.append(" ".join(buf))
    return "\n\n".join(p.strip() for p in paras if p.strip())

def prettify_experience_block(block: str, max_desc_chars: int = 300) -> str:
    if not block:
        return ""
    lines = [l for l in unique_lines_pretty(block).splitlines() if l.strip()]

    title = lines[0] if lines else None
    company = next((l for l in lines[1:]
                    if "·" in l or re.search(r"\b(full[- ]time|part[- ]time|contract|intern|freelance)\b", l, re.I)), None)
    date_line = next((l for l in lines
                      if re.search(r"(thg\s*\d+|\d{4}|\b\d{1,2}/\d{4}\b)", l)), None)
    location = next((l for l in lines
                     if re.search(r"Việt|United|Kingdom|City|Province|State|Quốc|United States|United Kingdom", l)), None)

    ignore = set([title, company, date_line, location])
    desc_lines = [l for l in lines if l not in ignore and len(l.split()) > 3]
    desc = " ".join(desc_lines).strip()
    if len(desc) > max_desc_chars:
        desc = desc[:max_desc_chars].rstrip() + "…"

    head = title or ""
    if company:
        head = f"{title} — {company}" if title else company
    info = " | ".join([p for p in [date_line, location] if p])

    parts = [p for p in [head, info, desc] if p]
    return " | ".join(parts)

# ======================== Selenium init ========================
def init_driver(headless: bool = False, block_images: bool = False):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument(f"--lang={ACCEPT_LANG}")
    opts.add_argument(f"user-agent={USER_AGENT}")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    prefs = {"intl.accept_languages": ACCEPT_LANG}
    if block_images:
        prefs["profile.managed_default_content_settings.images"] = 2
    opts.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=opts)
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"},
        )
    except Exception:
        pass
    return driver

def wait_main_loaded(driver, timeout=20):
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "main"))
        )
    except Exception:
        pass

def humandelay(a=0.4, b=0.9):
    time.sleep(random.uniform(a, b))

# ======================== Cookies ========================
def load_cookies(driver, path: Path) -> int:
    if not path.exists():
        return 0
    try:
        driver.get("https://www.linkedin.com/")
        time.sleep(1)
        cookies = json.loads(path.read_text(encoding="utf-8"))
        added = 0
        for c in cookies:
            if isinstance(c.get("expiry"), float):
                c["expiry"] = int(c["expiry"])
            try:
                driver.add_cookie(c)
                added += 1
            except Exception:
                pass
        driver.get("https://www.linkedin.com/feed/")
        time.sleep(1)
        return added
    except Exception:
        return 0

def save_cookies(driver, path: Path) -> int:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        cookies = driver.get_cookies() or []
        path.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
        return len(cookies)
    except Exception:
        return 0

# ======================== DOM utilities ========================
def get_first_text(driver, xpaths: List[str]) -> Optional[str]:
    for xp in xpaths:
        try:
            el = driver.find_element(By.XPATH, xp)
            txt = el.text.strip()
            if txt:
                return txt
        except Exception:
            continue
    return None

def get_many_texts(driver, xp: str, limit=3) -> List[str]:
    out = []
    try:
        for el in driver.find_elements(By.XPATH, xp)[:limit]:
            t = el.text.strip()
            if t:
                out.append(t)
    except Exception:
        pass
    return out

def _find_el_by_xpaths(driver, xps):
    for xp in xps:
        try:
            el = driver.find_element(By.XPATH, xp)
            return el
        except Exception:
            continue
    return None

def _expand_all_in_section(driver, section_el):
    try:
        driver.execute_script("""
            const sec = arguments[0];
            if (!sec) return;
            const btns = sec.querySelectorAll(
              "button.inline-show-more-text__button, \
               button[aria-expanded='false'], \
               button[aria-label*='See more'], \
               button[aria-label*='Xem thêm'], \
               button[aria-controls*='about'], \
               button[aria-controls*='education'], \
               button[aria-controls*='experience'], \
               button[aria-controls*='certifications'], \
               button[aria-controls*='skills']"
            );
            for (const b of btns) { try { b.click(); } catch(e){} }
        """, section_el)
        time.sleep(0.3)
    except Exception:
        pass

def _get_inner_text(driver, el):
    try:
        txt = driver.execute_script("""
            const el = arguments[0];
            if (!el) return null;
            return (el.innerText || el.textContent || "");
        """, el)
        if txt:
            t = re.sub(r"[ \t]+\n", "\n", txt)
            t = re.sub(r"\n[ \t]+", "\n", t)
            t = re.sub(r"\n{3,}", "\n\n", t)
            return t.strip()
    except Exception:
        pass
    try:
        return el.text.strip()
    except Exception:
        return None

def try_open_details(driver, base_profile_url: str, detail_slug: str, wait_sec: int = 20):
    u = base_profile_url.rstrip("/") + f"/details/{detail_slug}/"
    driver.get(u)
    wait_main_loaded(driver, timeout=wait_sec)
    for y in (200, 600, 1000, 0):
        driver.execute_script(f"window.scrollTo(0,{y});")
        time.sleep(0.25)

# ======================== Extractors ========================
def extract_about(driver, base_profile_url: str) -> Optional[str]:
    sec = _find_el_by_xpaths(driver, [
        "//section[contains(@id,'about') or .//h2[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'about') or contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'giới thiệu') or contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'summary')]]",
        "//main//*[self::h2 or self::h3][contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'about') or contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'giới thiệu') or contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'summary')]/ancestor::section[1]",
    ])
    if sec is not None:
        _expand_all_in_section(driver, sec)
        txt = _get_inner_text(driver, sec)
        if txt:
            return clean_text(pretty_about(txt))

    for slug in ("about", "summary"):
        try_open_details(driver, base_profile_url, slug)
        sec = _find_el_by_xpaths(driver, [
            "//section[contains(@id,'about') or .//h2[contains(.,'About') or contains(.,'Giới thiệu') or contains(.,'Summary')]]",
            "//main//*[self::h2 or self::h3][contains(.,'About') or contains(.,'Giới thiệu') or contains(.,'Summary')]/ancestor::section[1]",
            "//main"
        ])
        if sec is not None:
            _expand_all_in_section(driver, sec)
            txt = _get_inner_text(driver, sec)
            if txt:
                return clean_text(pretty_about(txt))
    return None

def extract_education(driver, base_profile_url: str, limit=3) -> Optional[str]:
    sec = _find_el_by_xpaths(driver, [
        "//section[contains(@id,'education') or .//h2[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'education') or contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'học vấn')]]",
        "//main//*[self::h2 or self::h3][contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'education') or contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'học vấn')]/ancestor::section[1]",
    ])
    items = []
    if sec is not None:
        _expand_all_in_section(driver, sec)
        try:
            els = sec.find_elements(By.XPATH, ".//li[contains(@class,'pvs-list__item') or contains(@class,'artdeco-list__item')]")
            for el in els[:limit]:
                t = _get_inner_text(driver, el)
                if t:
                    items.append(t)
        except Exception:
            pass

    if not items:
        try_open_details(driver, base_profile_url, "education")
        sec = _find_el_by_xpaths(driver, [
            "//section[contains(@id,'education') or .//h2[contains(.,'Education') or contains(.,'Học vấn')]]",
            "//main//*[self::h2 or self::h3][contains(.,'Education') or contains(.,'Học vấn')]/ancestor::section[1]",
            "//main"
        ])
        if sec is not None:
            _expand_all_in_section(driver, sec)
            try:
                els = sec.find_elements(By.XPATH, ".//li[contains(@class,'pvs-list__item') or contains(@class,'artdeco-list__item')]")
                for el in els[:limit]:
                    t = _get_inner_text(driver, el)
                    if t:
                        items.append(t)
            except Exception:
                pass

    items = [clean_text(x) for x in items if x]
    items = [x for x in items if x]
    return " | ".join(items) if items else None

def extract_certifications(driver, base_profile_url: str, limit=10) -> Optional[str]:
    LOWER = "abcdefghijklmnopqrstuvwxyz"; UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    sec = _find_el_by_xpaths(driver, [
        "//section[.//h2[contains(translate(.,'{U}','{L}'),'licenses') or contains(translate(.,'{U}','{L}'),'certifications') or contains(translate(.,'{U}','{L}'),'giấy phép') or contains(translate(.,'{U}','{L}'),'chứng chỉ')]]".format(U=UPPER, L=LOWER),
        ("//main//*[self::h2 or self::h3][contains(translate(.,'{U}','{L}'),'licenses') or contains(translate(.,'{U}','{L}'),'certifications') or contains(translate(.,'{U}','{L}'),'giấy phép') or contains(translate(.,'{U}','{L}'),'chứng chỉ')]/ancestor::section[1]").format(U=UPPER, L=LOWER),
    ])
    items = []
    if sec is not None:
        _expand_all_in_section(driver, sec)
        try:
            els = sec.find_elements(By.XPATH, ".//li[contains(@class,'pvs-list__item') or contains(@class,'artdeco-list__item')]")
            for el in els[:limit]:
                t = _get_inner_text(driver, el)
                if t:
                    items.append(t)
        except Exception:
            pass

    if not items:
        try_open_details(driver, base_profile_url, "certifications")
        sec = _find_el_by_xpaths(driver, [
            "//section[.//h2[contains(.,'Licenses') or contains(.,'Certifications') or contains(.,'Chứng chỉ') or contains(.,'Giấy phép')]]",
            "//main"
        ])
        if sec is not None:
            _expand_all_in_section(driver, sec)
            try:
                els = sec.find_elements(By.XPATH, ".//li[contains(@class,'pvs-list__item') or contains(@class,'artdeco-list__item')]")
                for el in els[:limit]:
                    t = _get_inner_text(driver, el)
                    if t:
                        items.append(t)
            except Exception:
                pass

    items = [clean_text(x) for x in items if x]
    simplified = []
    for it in items:
        first = it.split("\n", 1)[0].strip()
        simplified.append(first if first else it)
    return " | ".join(simplified[:limit]) if simplified else None

def extract_skills(driver, base_profile_url: str, limit=25) -> Optional[str]:
    LOWER = "abcdefghijklmnopqrstuvwxyz"; UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def _collect_from_section(sec, cap=limit):
        out = []
        if not sec:
            return out
        _expand_all_in_section(driver, sec)
        try:
            els = sec.find_elements(By.XPATH, ".//li[contains(@class,'pvs-list__item') or contains(@class,'artdeco-list__item')]")
            for el in els[:cap]:
                t = _get_inner_text(driver, el)
                if t:
                    t1 = t.split("\n", 1)[0].strip()
                    if t1:
                        out.append(t1)
        except Exception:
            pass
        return out

    sec = _find_el_by_xpaths(driver, [
        "//section[.//h2[contains(translate(.,'{U}','{L}'),'skills') or contains(translate(.,'{U}','{L}'),'kỹ năng')]]".format(U=UPPER, L=LOWER),
        ("//main//*[self::h2 or self::h3][contains(translate(.,'{U}','{L}'),'skills') or contains(translate(.,'{U}','{L}'),'kỹ năng')]/ancestor::section[1]").format(U=UPPER, L=LOWER),
    ])
    items = _collect_from_section(sec, limit)

    if not items:
        try_open_details(driver, base_profile_url, "skills")
        sec = _find_el_by_xpaths(driver, [
            "//section[.//h2[contains(.,'Skills') or contains(.,'Kỹ năng')]]",
            "//main"
        ])
        items = _collect_from_section(sec, limit)

    seen = set(); uniq = []
    for s in items:
        key = re.sub(r"\s+", " ", s.strip().lower())
        if key and key not in seen:
            seen.add(key); uniq.append(s.strip())
    return " | ".join(uniq[:limit]) if uniq else None

# ======================== Scrape profile ========================
def scrape_profile(driver, url: str) -> Dict:
    base_url = normalize_url(url)
    driver.get(base_url)
    wait_main_loaded(driver, 25)

    for y in (200, 600, 1000, 0):
        driver.execute_script(f"window.scrollTo(0,{y});")
        humandelay(0.3, 0.7)

    name = get_first_text(driver, [
        "//main//h1 | //main//h1//span",
        "//*[@data-test-id='hero-title']",
    ])
    headline = get_first_text(driver, [
        "//main//*[contains(@class,'text-body-medium') or contains(@class,'inline')][1]",
        "//main//div[contains(@class,'pv-text-details')]//div[contains(@class,'inline')][1]",
    ])
    location = get_first_text(driver, [
        "//main//*[contains(@class,'text-body-small')][1]",
        "//main//span[contains(@class,'text-body-small')][1]",
    ])

    about = extract_about(driver, base_url)

    driver.execute_script("window.scrollTo(0, document.body.scrollHeight - 800);")
    time.sleep(0.5)
    education_top3 = extract_education(driver, base_url, limit=3)

    exp_items = get_many_texts(
        driver,
        "//section[contains(@id,'experience') or .//h2[contains(.,'Experience') or contains(.,'Kinh nghiệm')]]"
        "//li[contains(@class,'pvs-list__item') or contains(@class,'artdeco-list__item')]",
        limit=3
    )
    if not exp_items:
        try_open_details(driver, base_url, "experience")
        sec = _find_el_by_xpaths(driver, [
            "//section[contains(@id,'experience') or .//h2[contains(.,'Experience') or contains(.,'Kinh nghiệm')]]",
            "//main"
        ])
        if sec is not None:
            _expand_all_in_section(driver, sec)
            try:
                els = sec.find_elements(By.XPATH, ".//li[contains(@class,'pvs-list__item') or contains(@class,'artdeco-list__item')]")
                for el in els[:3]:
                    t = _get_inner_text(driver, el)
                    if t:
                        exp_items.append(t)
            except Exception:
                pass

    exp_items = [prettify_experience_block(x) for x in exp_items if x]
    exp_items = [x for x in exp_items if x]
    experience_top3 = " || ".join(exp_items) if exp_items else None

    licenses_top = extract_certifications(driver, base_url, limit=10)
    skills_top = extract_skills(driver, base_url, limit=25)

    return {
        "profile_url": base_url,
        "name": clean_text(name),
        "headline": clean_text(headline),
        "location": clean_text(location),
        "about": clean_text(about),
        "experience_top3": experience_top3,
        "education_top3": education_top3,
        "licenses_certifications_top": licenses_top,
        "skills_top": skills_top,
    }

# ======================== GUI + luồng ========================
@dataclass
class TaskConfig:
    urls: List[str]
    out_dir: Path
    use_cookies: bool
    wait_sec: int

class ScrapeThread(threading.Thread):
    def __init__(self, app, cfg: TaskConfig):
        super().__init__(daemon=True)
        self.app = app
        self.cfg = cfg

    def run(self):
        app = self.app
        app.set_running(True)
        app.reset_progress(total=len(self.cfg.urls))
        rows: List[Dict] = []
        driver = None
        try:
            app.log("Khởi động Chrome...")
            driver = init_driver(headless=False, block_images=False)
            app.driver = driver

            cookie_path = self.cfg.out_dir / "cookies.json"
            if self.cfg.use_cookies and cookie_path.exists():
                n = load_cookies(driver, cookie_path)
                app.log(f"Đã nạp {n} cookies từ: {cookie_path}")

            if not (self.cfg.use_cookies and cookie_path.exists()):
                app.log("Mở trang đăng nhập LinkedIn...")
                driver.get("https://www.linkedin.com/login")
                app.log("Đăng nhập trong Chrome, sau đó bấm 'Tôi đã đăng nhập'.")
                app.wait_login_event.clear()
                app.enable_continue(True)
                app.wait_login_event.wait()
                app.enable_continue(False)
                if self.cfg.use_cookies:
                    n = save_cookies(driver, cookie_path)
                    app.log(f"Đã lưu {n} cookies → {cookie_path}")

            for i, url in enumerate(self.cfg.urls, 1):
                if app.stop_requested:
                    app.log("⏹ Dừng theo yêu cầu.")
                    break
                url = normalize_url(url)
                app.log(f"[{i}/{len(self.cfg.urls)}] {url}")
                try:
                    row = scrape_profile(driver, url)
                    rows.append(row)
                except Exception as e:
                    app.log(f"  ⚠ Lỗi: {e}")
                finally:
                    app.step_progress(1)
                    time.sleep(max(0.5, self.cfg.wait_sec / 10))

            if rows:
                app.preview_profile(rows[0])

            self.cfg.out_dir.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            csv_path = self.cfg.out_dir / f"profiles_{ts}.csv"
            jsonl_path = self.cfg.out_dir / f"profiles_{ts}.jsonl"
            pd.DataFrame(rows).to_csv(csv_path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_ALL)
            with open(jsonl_path, "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            app.log(f"✅ Đã lưu → {csv_path}")
            app.enable_open_folder(True)
        except Exception as e:
            app.log(f"❌ Lỗi: {e}")
            messagebox.showerror("Lỗi", str(e))
        finally:
            try:
                if driver:
                    driver.quit()
            except Exception:
                pass
            app.set_running(False)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LinkedIn Profile — GUI Crawler")
        self.geometry("960x640")
        self.driver = None
        self.stop_requested = False

        self.var_mode_batch = tk.BooleanVar(value=False)
        self.var_url = tk.StringVar(value="https://www.linkedin.com/in/jasica-nagpal/")
        self.var_outdir = tk.StringVar(value=str(Path.home() / "LinkedInProfilesOut"))
        self.var_wait = tk.StringVar(value="6")
        self.var_use_cookies = tk.BooleanVar(value=True)

        self.wait_login_event = threading.Event()
        self.progress_total = 1
        self.progress_done = 0

        self._build_ui()
        self.log_queue = queue.Queue()
        self.after(100, self._drain_log_queue)

    def _build_ui(self):
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        top = ttk.Frame(frm)
        top.grid(row=0, column=0, columnspan=4, sticky="we")
        ttk.Checkbutton(top, text="Batch mode (nhiều URL)", variable=self.var_mode_batch, command=self._toggle_mode).pack(anchor="w")

        self.single = ttk.Frame(frm)
        self.single.grid(row=1, column=0, columnspan=4, sticky="we", pady=6)
        ttk.Label(self.single, text="Profile URL:").grid(row=0, column=0, sticky="w")
        ttk.Entry(self.single, textvariable=self.var_url, width=120).grid(row=0, column=1, columnspan=3, sticky="we")

        self.batch = ttk.Frame(frm)
        ttk.Label(self.batch, text="Dán nhiều URL (mỗi dòng một /in/):").grid(row=0, column=0, sticky="w")
        self.txt_urls = tk.Text(self.batch, height=8, wrap="none")
        self.txt_urls.grid(row=1, column=0, columnspan=3, sticky="we", pady=4)
        ttk.Button(self.batch, text="Load CSV...", command=self._load_csv).grid(row=1, column=3, sticky="w", padx=8)

        ofrm = ttk.Frame(frm)
        ofrm.grid(row=2, column=0, columnspan=4, sticky="we", pady=6)
        ttk.Label(ofrm, text="Output folder:").grid(row=0, column=0, sticky="w")
        ttk.Entry(ofrm, textvariable=self.var_outdir, width=70).grid(row=0, column=1, sticky="we")
        ttk.Button(ofrm, text="Browse...", command=self._choose_outdir).grid(row=0, column=2, padx=6)
        ttk.Checkbutton(ofrm, text="Use cookies", variable=self.var_use_cookies).grid(row=0, column=3, padx=6)

        pfrm = ttk.Frame(frm)
        pfrm.grid(row=3, column=0, columnspan=4, sticky="we")
        ttk.Label(pfrm, text="Wait between profiles (s):").grid(row=0, column=0, sticky="w")
        ttk.Entry(pfrm, textvariable=self.var_wait, width=6).grid(row=0, column=1, sticky="w")

        bfrm = ttk.Frame(frm)
        bfrm.grid(row=4, column=0, columnspan=4, sticky="we", pady=(8,4))
        self.btn_start = ttk.Button(bfrm, text="Start", command=self._on_start)
        self.btn_start.grid(row=0, column=0, padx=6)
        self.btn_continue = ttk.Button(bfrm, text="Tôi đã đăng nhập", command=self._on_continue, state="disabled")
        self.btn_continue.grid(row=0, column=1, padx=6)
        self.btn_stop = ttk.Button(bfrm, text="Stop", command=self._on_stop, state="disabled")
        self.btn_stop.grid(row=0, column=2, padx=6)
        self.btn_savecookies = ttk.Button(bfrm, text="Save cookies", command=self._save_cookies_now)
        self.btn_savecookies.grid(row=0, column=3, padx=6)
        self.btn_open = ttk.Button(bfrm, text="Mở thư mục xuất", command=self._open_folder, state="disabled")
        self.btn_open.grid(row=0, column=4, padx=6)

        p2 = ttk.Frame(frm)
        p2.grid(row=5, column=0, columnspan=4, sticky="we")
        self.prog = ttk.Progressbar(p2, orient="horizontal", mode="determinate")
        self.prog.grid(row=0, column=0, sticky="we", padx=(0,8))
        self.lbl_eta = ttk.Label(p2, text="ETA: --:--")
        self.lbl_eta.grid(row=0, column=1, sticky="e")
        frm.columnconfigure(1, weight=1)

        self.txt = tk.Text(frm, height=15, wrap="word")
        self.txt.grid(row=6, column=0, columnspan=4, sticky="nsew")
        frm.rowconfigure(6, weight=1)

    # ---------- GUI handlers ----------
    def _toggle_mode(self):
        if self.var_mode_batch.get():
            self.single.grid_remove()
            self.batch.grid(row=1, column=0, columnspan=4, sticky="we", pady=6)
        else:
            self.batch.grid_remove()
            self.single.grid(row=1, column=0, columnspan=4, sticky="we", pady=6)

    def _choose_outdir(self):
        d = filedialog.askdirectory(initialdir=self.var_outdir.get() or str(Path.home()))
        if d:
            self.var_outdir.set(d)

    def _load_csv(self):
        fp = filedialog.askopenfilename(filetypes=[("CSV files","*.csv"),("All files","*.*")])
        if not fp:
            return
        try:
            df = pd.read_csv(fp)
            col = None
            for c in df.columns:
                if c.lower() == "url":
                    col = c; break
            if not col:
                col = df.columns[0]
            urls = [str(x) for x in df[col].dropna().tolist()]
            self.txt_urls.delete("1.0","end")
            self.txt_urls.insert("1.0","\n".join(urls))
            messagebox.showinfo("OK", f"Đã nạp {len(urls)} URL từ CSV.")
        except Exception as e:
            messagebox.showerror("CSV error", str(e))

    def _on_start(self):
        if getattr(self, "running", False):
            return
        if self.var_mode_batch.get():
            urls = [u.strip() for u in self.txt_urls.get("1.0","end").splitlines() if "/in/" in u]
        else:
            urls = [self.var_url.get().strip()]
        urls = [u for u in urls if u]
        if not urls:
            messagebox.showwarning("Thiếu URL","Nhập ít nhất một URL /in/.")
            return
        self.txt.delete("1.0","end")
        self.enable_open_folder(False)
        cfg = TaskConfig(
            urls=urls,
            out_dir=Path(self.var_outdir.get() or "."),
            use_cookies=self.var_use_cookies.get(),
            wait_sec=int(self.var_wait.get() or 6)
        )
        th = ScrapeThread(self, cfg)
        th.start()

    def _on_continue(self):
        self.wait_login_event.set()

    def _on_stop(self):
        self.stop_requested = True

    def _save_cookies_now(self):
        if not self.driver:
            messagebox.showwarning("Chưa khởi động Chrome", "Bấm Start và đăng nhập trước.")
            return
        n = save_cookies(self.driver, Path(self.var_outdir.get() or ".")/"cookies.json")
        messagebox.showinfo("OK", f"Đã lưu {n} cookies")

    def _open_folder(self):
        d = self.var_outdir.get().strip()
        if d and Path(d).exists():
            webbrowser.open(d)

    def set_running(self, val: bool):
        self.running = val
        self.btn_start.config(state=("disabled" if val else "normal"))
        self.btn_stop.config(state=("normal" if val else "disabled"))

    def enable_continue(self, enable: bool):
        self.btn_continue.config(state=("normal" if enable else "disabled"))

    def enable_open_folder(self, enable: bool):
        self.btn_open.config(state=("normal" if enable else "disabled"))

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

    def reset_progress(self, total: int):
        self.progress_total = max(1, total)
        self.progress_done = 0
        self.prog["maximum"] = self.progress_total
        self.prog["value"] = 0
        self.lbl_eta.config(text="ETA: --:--")
        self.set_running(True)

    def step_progress(self, step: int):
        self.progress_done += step
        self.prog["value"] = min(self.progress_done, self.progress_total)

    def preview_profile(self, row: Dict):
        win = tk.Toplevel(self)
        win.title("Preview 1 profile")
        win.geometry("900x560")
        t = tk.Text(win, wrap="word")
        t.pack(fill="both", expand=True, padx=10, pady=10)
        order = [
            ("profile_url", "URL"),
            ("name", "Name"),
            ("headline", "Headline"),
            ("location", "Location"),
            ("about", "About"),
            ("experience_top3", "Experience (top3)"),
            ("education_top3", "Education (top3)"),
            ("licenses_certifications_top", "Licenses & Certifications"),
            ("skills_top", "Skills"),
        ]
        for k, label in order:
            t.insert("end", f"{label}:\n")
            t.insert("end", (row.get(k) or "") + "\n\n")

if __name__ == "__main__":
    app = App()
    app.mainloop()
