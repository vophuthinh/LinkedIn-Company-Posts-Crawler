# -*- coding: utf-8 -*-
"""
Shared scraping core functions for LinkedIn Company Posts Crawler
This module contains the core scraping logic shared between different UI versions
"""

import logging
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, WebDriverException

# Import shared modules
try:
    from config import SELECTORS, MAX_STABLE_ROUNDS, SCROLL_BASE_PX, SCROLL_VARIATION
    from utils import (
        normalize_time, inside_date_range, normalize_time_for_output,
        url_to_slug, clean_text_keep_newlines, get_random_delay, get_long_pause,
        should_take_long_pause
    )
    from retry_handler import retry_on_failure, RetryConfig
    from rate_limiter import get_rate_limiter, RateLimiter
except ImportError:
    # Fallback if modules not available
    SELECTORS = {
        'post_container': '.organization-content-list__posts-list-item, .feed-shared-update-v2',
        'posts_link': 'a[href*="/posts/"]',
        'overlay_xpaths': []
    }
    MAX_STABLE_ROUNDS = 3
    SCROLL_BASE_PX = 1100
    SCROLL_VARIATION = 200
    
    # Fallback functions
    def normalize_time(*args, **kwargs):
        return None
    def inside_date_range(*args, **kwargs):
        return True
    def normalize_time_for_output(*args, **kwargs):
        return None
    def url_to_slug(*args, **kwargs):
        return "company"
    def clean_text_keep_newlines(*args, **kwargs):
        return None
    def get_random_delay():
        return 0
    def get_long_pause():
        return 5.0
    def should_take_long_pause(*args, **kwargs):
        return False
    def retry_on_failure(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    class RetryConfig:
        pass
    def get_rate_limiter(*args, **kwargs):
        class DummyRateLimiter:
            def wait_if_needed(self):
                return 0.0
        return DummyRateLimiter()

logger = logging.getLogger(__name__)

# JavaScript extractor (shared)
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


def close_overlays(driver):
    """Close any overlay dialogs/popups on LinkedIn"""
    xpaths = SELECTORS.get('overlay_xpaths', [])
    if not xpaths:
        # Fallback xpaths
        xpaths = [
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'accept')]",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'đồng ý')]",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'chấp nhận')]",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'got it')]",
            "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'ok')]",
            "//button[@aria-label='Dismiss' or contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'dismiss')]",
            "//button[contains(@class,'artdeco-modal__dismiss')]",
            "//button[contains(@class,'ember-view') and contains(.,'Close')]",
        ]
    
    for xp in xpaths:
        try:
            for b in driver.find_elements(By.XPATH, xp):
                try:
                    driver.execute_script("arguments[0].click();", b)
                    time.sleep(0.2)
                except Exception as e:
                    logger.debug(f"Error clicking overlay button: {e}")
        except Exception as e:
            logger.debug(f"Error finding overlay elements: {e}")


def smart_scroll(driver, outer_rounds=2, base_step_px=None):
    """Smart scrolling with randomization"""
    if base_step_px is None:
        base_step_px = SCROLL_BASE_PX
    
    for _ in range(outer_rounds):
        # Randomize scroll distance
        scroll_amount = random.randint(base_step_px - SCROLL_VARIATION, base_step_px + SCROLL_VARIATION)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        
        # Randomize delay
        try:
            from config import SCROLL_DELAY_MIN, SCROLL_DELAY_MAX
            delay = random.uniform(SCROLL_DELAY_MIN, SCROLL_DELAY_MAX)
        except ImportError:
            delay = random.uniform(0.6, 1.2)
        time.sleep(delay)

        # Inner scroll for more natural behavior
        driver.execute_script("window.scrollBy(0, 100);")
        try:
            from config import INNER_SCROLL_DELAY_MIN, INNER_SCROLL_DELAY_MAX
            inner_delay = random.uniform(INNER_SCROLL_DELAY_MIN, INNER_SCROLL_DELAY_MAX)
        except ImportError:
            inner_delay = random.uniform(0.5, 1.0)
        time.sleep(inner_delay)


def _scrape_url_internal(
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
    """Internal scraping function (without retry wrapper)"""
    driver.get(url)
    
    close_overlays(driver)
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
    except TimeoutException:
        logger.error(f"Timeout waiting for page to load: {url}")
        if app:
            app.log(f"  → ⚠ Timeout: Trang không tải được sau 20 giây")
        return [], False
    except WebDriverException as e:
        logger.error(f"WebDriver error loading page: {e}")
        if app:
            app.log(f"  → ⚠ Lỗi trình duyệt: {e}")
        return [], False

    try:
        if "/posts" not in driver.current_url:
            links = driver.find_elements(By.CSS_SELECTOR, SELECTORS.get('posts_link', 'a[href*="/posts/"]'))
            if links:
                driver.execute_script("arguments[0].click();", links[0])
                WebDriverWait(driver, wait_sec).until(lambda d: "/posts" in d.current_url)
        if "feedView=all" not in driver.current_url:
            base = driver.current_url.split("?")[0]
            driver.get(base + "?feedView=all")
    except TimeoutException:
        logger.warning(f"Timeout navigating to posts page")
        if app:
            app.log(f"  → ⚠ Timeout khi chuyển đến trang posts")
    except WebDriverException as e:
        logger.warning(f"Error navigating to posts: {e}")
        if app:
            app.log(f"  → ⚠ Lỗi khi chuyển đến trang posts: {e}")

    try:
        post_selector = SELECTORS.get('post_container', '.organization-content-list__posts-list-item, .feed-shared-update-v2')
        WebDriverWait(driver, wait_sec).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, post_selector))
        )
        if app:
            app.log("  → Đã tìm thấy khu vực bài post. Bắt đầu cuộn.")
    except TimeoutException:
        logger.warning(f"Timeout waiting for post container")
        if app:
            app.log(f"  → ⚠ Timeout: Không tìm thấy khu vực bài post sau {wait_sec} giây. Tiếp tục cuộn...")
    except Exception as e:
        logger.warning(f"Error waiting for post container: {e}")
        if app:
            app.log(f"  → ⚠ Lỗi khi đợi khu vực bài post: {e}. Tiếp tục cuộn...")

    collected: Dict[str, Dict] = {}
    stable_rounds, prev_n = 0, -1
    stop_by_time_hit = False

    for i in range(scroll_rounds):
        if stop_flag():
            break
        try:
            raw = driver.execute_script(EXTRACT_JS) or []
        except WebDriverException as e:
            logger.warning(f"Error executing extraction script: {e}")
            if app:
                app.log(f"  → ⚠ Lỗi khi trích xuất dữ liệu: {e}")
            raw = []
        except Exception as e:
            logger.error(f"Unexpected error in extraction: {e}", exc_info=True)
            if app:
                app.log(f"  → ⚠ Lỗi không xác định khi trích xuất: {e}")
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
                    except ValueError as e:
                        logger.debug(f"Error parsing date for stop check: {e}")
                    except Exception as e:
                        logger.warning(f"Unexpected error checking date: {e}")

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

        if n >= max_posts or stable_rounds >= MAX_STABLE_ROUNDS or stop_by_time_hit:
            break

        # Long pause if needed
        if should_take_long_pause(i):
            long_pause = get_long_pause()
            if app:
                app.log(f"  → Tạm nghỉ dài {long_pause:.1f} giây để mô phỏng người dùng...")
            time.sleep(long_pause)

        smart_scroll(driver, outer_rounds=2, base_step_px=SCROLL_BASE_PX)

    return list(collected.values()), stop_by_time_hit


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
        app=None,
        use_retry: bool = True,
        rate_limiter: Optional[RateLimiter] = None
) -> Tuple[Optional[List[Dict]], bool]:
    """
    Scrape LinkedIn company posts with optional retry mechanism and rate limiting.
    
    Args:
        use_retry: Enable retry mechanism for network errors
        rate_limiter: RateLimiter instance (creates default if None)
    
    Returns:
        Tuple of (rows, stopped_by_time_lower_bound)
    """
    # Apply rate limiting before scraping
    if rate_limiter:
        wait_time = rate_limiter.wait_if_needed()
        if wait_time > 0 and app:
            app.log(f"  → Rate limiting: đã đợi {wait_time:.1f}s")
    
    if use_retry:
        try:
            from config import DEFAULT_RETRY_ATTEMPTS, DEFAULT_RETRY_BASE_DELAY, DEFAULT_RETRY_MAX_DELAY
            retry_config = RetryConfig(
                max_attempts=DEFAULT_RETRY_ATTEMPTS,
                base_delay=DEFAULT_RETRY_BASE_DELAY,
                max_delay=DEFAULT_RETRY_MAX_DELAY
            )
        except ImportError:
            retry_config = RetryConfig()
        
        def on_retry_callback(attempt, exception):
            if app:
                app.log(f"  → ⚠ Retry {attempt}/{retry_config.max_attempts}: {type(exception).__name__}")
            logger.warning(f"Retry {attempt}/{retry_config.max_attempts} for {url}: {exception}")
        
        @retry_on_failure(retry_config, on_retry=on_retry_callback)
        def _scrape_with_retry():
            return _scrape_url_internal(
                driver, url, wait_sec, scroll_rounds, max_posts,
                start_dt, end_dt, apply_hashtag_fix, strict_date_filter,
                update_progress, stop_flag, app
            )
        
        try:
            result = _scrape_with_retry()
            # Notify rate limiter of success
            if rate_limiter and hasattr(rate_limiter, 'on_success'):
                rate_limiter.on_success()
            return result
        except Exception as e:
            # Notify rate limiter of error
            if rate_limiter and hasattr(rate_limiter, 'on_rate_limit_error'):
                if "rate limit" in str(e).lower() or "429" in str(e):
                    rate_limiter.on_rate_limit_error()
            raise
    else:
        result = _scrape_url_internal(
            driver, url, wait_sec, scroll_rounds, max_posts,
            start_dt, end_dt, apply_hashtag_fix, strict_date_filter,
            update_progress, stop_flag, app
        )
        if rate_limiter and hasattr(rate_limiter, 'on_success'):
            rate_limiter.on_success()
        return result

