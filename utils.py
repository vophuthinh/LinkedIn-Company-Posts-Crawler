# -*- coding: utf-8 -*-
"""
Shared utilities for LinkedIn Crawler
Common functions used across multiple files
"""

import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from config import (
    VN_TIMEZONE_OFFSET,
    DATE_FORMAT_DMY,
    RANDOM_DELAY_MIN,
    RANDOM_DELAY_MAX,
    LONG_PAUSE_MIN,
    LONG_PAUSE_MAX,
    SCROLL_BASE_PX,
    SCROLL_VARIATION,
    SCROLL_DELAY_MIN,
    SCROLL_DELAY_MAX,
    INNER_SCROLL_DELAY_MIN,
    INNER_SCROLL_DELAY_MAX,
    BETWEEN_URL_DELAY_MIN,
    BETWEEN_URL_DELAY_MAX,
)

# Setup logging
logger = logging.getLogger(__name__)


# ==================== Text Utilities ====================

def nfc(s: str) -> str:
    """Normalize Unicode string to NFC form"""
    return unicodedata.normalize("NFC", s)


def fix_hashtag(text: str) -> str:
    """Fix hashtag format: 'hashtag#' -> '#'"""
    return re.sub(r"(?i)\bhashtag#", "#", text)


def clean_text_keep_newlines(s: Optional[str], apply_hashtag_fix: bool = True) -> Optional[str]:
    """Clean text while preserving newlines"""
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


# ==================== Time Utilities ====================

def parse_rel_time_to_dt(rel: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """Parse relative time string to datetime"""
    if not rel:
        return None
    rel = rel.strip().lower()
    now = now or datetime.now(timezone.utc)

    # English patterns
    patterns_en = [
        (r"^(\d+)\s*m(?:in)?$", "minutes"),
        (r"^(\d+)\s*h(?:our)?$", "hours"),
        (r"^(\d+)\s*d(?:ay)?$", "days"),
        (r"^(\d+)\s*w(?:eek)?$", "weeks"),
        (r"^(\d+)\s*mo(?:nth)?$", "months"),
        (r"^(\d+)\s*y(?:ear)?$", "years"),
    ]
    
    for pat, unit in patterns_en:
        m = re.match(pat, rel)
        if m:
            v = int(m.group(1))
            if unit == "minutes":
                return now - timedelta(minutes=v)
            elif unit == "hours":
                return now - timedelta(hours=v)
            elif unit == "days":
                return now - timedelta(days=v)
            elif unit == "weeks":
                return now - timedelta(weeks=v)
            elif unit == "months":
                return now - timedelta(days=30 * v)
            elif unit == "years":
                return now - timedelta(days=365 * v)

    # Vietnamese patterns
    patterns_vi = [
        (r"(\d+)\s*phút", "minutes"),
        (r"(\d+)\s*giờ", "hours"),
        (r"(\d+)\s*ngày", "days"),
        (r"(\d+)\s*tuần", "weeks"),
        (r"(\d+)\s*tháng", "months"),
        (r"(\d+)\s*năm", "years"),
    ]
    
    for pat, unit in patterns_vi:
        m = re.search(pat, rel)
        if m:
            v = int(m.group(1))
            if unit == "minutes":
                return now - timedelta(minutes=v)
            elif unit == "hours":
                return now - timedelta(hours=v)
            elif unit == "days":
                return now - timedelta(days=v)
            elif unit == "weeks":
                return now - timedelta(weeks=v)
            elif unit == "months":
                return now - timedelta(days=30 * v)
            elif unit == "years":
                return now - timedelta(days=365 * v)
    
    return None


def normalize_time(time_iso: Optional[str], time_text: Optional[str]) -> Optional[str]:
    """Normalize time to ISO 8601 format"""
    # 1. Prioritize time_iso
    if time_iso:
        s = time_iso.strip()
        s = re.sub(r"([+-]\d{4})$", r"\1", s.replace("+0000", "+00:00"))

        try:
            # If it already contains Z or a timezone
            if "Z" in s or re.search(r"[-+]\d{2}:\d{2}$", s):
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

            # Date/time without timezone
            try:
                dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
                return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
            except ValueError:
                pass

            # Date only
            try:
                dt = datetime.strptime(s, "%Y-%m-%d")
                return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
            except ValueError:
                pass

        except Exception as e:
            logger.debug(f"Error parsing ISO time: {e}")
            pass

    # 2. Fallback to relative time
    if time_text:
        dt = parse_rel_time_to_dt(time_text)
        if dt:
            return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    return None


def inside_date_range(
    iso_str: Optional[str],
    start: Optional[datetime],
    end: Optional[datetime],
    strict: bool = True,
) -> bool:
    """Check if ISO time string is within date range"""
    if not (start or end):
        return True

    if not iso_str:
        return not strict

    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except Exception as e:
        logger.debug(f"Error parsing date for range check: {e}")
        return not strict

    if start and dt < start:
        return False
    if end and dt > (end + timedelta(days=1) - timedelta(seconds=1)):
        return False
    return True


def normalize_time_for_output(iso_str: Optional[str]) -> Optional[str]:
    """Convert ISO time to DD-MM-YYYY format (VN timezone)"""
    try:
        if not iso_str:
            return None
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        vn = timezone(timedelta(hours=VN_TIMEZONE_OFFSET))
        dt = dt.astimezone(vn)
        return dt.strftime(DATE_FORMAT_DMY)
    except Exception as e:
        logger.debug(f"Error normalizing time for output: {e}")
        return None


# ==================== URL Utilities ====================

def url_to_slug(u: str) -> str:
    """Extract company slug from LinkedIn URL"""
    try:
        p = urlparse(u)
        parts = [x for x in p.path.split("/") if x]
        for i, seg in enumerate(parts):
            if seg == "company" and i + 1 < len(parts):
                return re.sub(r"[^a-z0-9\-]+", "-", parts[i + 1].lower())
        return re.sub(r"[^a-z0-9\-]+", "-", (parts[-1] if parts else "company"))
    except Exception as e:
        logger.warning(f"Error extracting slug from URL {u}: {e}")
        return "company"


# ==================== Random Utilities ====================

def get_random_delay() -> float:
    """Get random delay between URLs"""
    import random
    return random.uniform(BETWEEN_URL_DELAY_MIN, BETWEEN_URL_DELAY_MAX)


def get_long_pause() -> float:
    """Get random long pause during scrolling"""
    import random
    return random.uniform(LONG_PAUSE_MIN, LONG_PAUSE_MAX)


def should_take_long_pause(round_index: int) -> bool:
    """Check if should take long pause at this round"""
    import random
    if round_index > 0:
        pause_interval = random.randint(RANDOM_DELAY_MIN, RANDOM_DELAY_MAX)
        return round_index % pause_interval == 0
    return False

