# -*- coding: utf-8 -*-
"""
Input validation utilities for LinkedIn Crawler
"""

import re
from datetime import datetime
from typing import List, Tuple, Optional
from config import LINKEDIN_URL_PATTERNS, DATE_FORMAT_DMY


def validate_linkedin_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate LinkedIn company posts URL
    
    Args:
        url: URL to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url or not isinstance(url, str):
        return False, "URL không được để trống"
    
    url = url.strip()
    
    # Check basic format
    if not url.startswith("http"):
        return False, "URL phải bắt đầu với http:// hoặc https://"
    
    # Check LinkedIn domain
    if "linkedin.com" not in url:
        return False, "URL phải là từ LinkedIn (linkedin.com)"
    
    # Check company posts pattern
    if not re.match(LINKEDIN_URL_PATTERNS['company_posts'], url):
        # Try to fix by adding /posts/?feedView=all
        if re.match(LINKEDIN_URL_PATTERNS['company_base'], url):
            return True, None  # Accept base URL, will be fixed later
        return False, "URL không đúng định dạng. Ví dụ: https://www.linkedin.com/company/microsoft/posts/?feedView=all"
    
    return True, None


def validate_urls(urls: List[str]) -> Tuple[bool, Optional[str], List[str]]:
    """
    Validate a list of URLs
    
    Args:
        urls: List of URLs to validate
        
    Returns:
        Tuple of (is_valid, error_message, valid_urls)
    """
    if not urls:
        return False, "Danh sách URL không được để trống", []
    
    valid_urls = []
    errors = []
    
    for i, url in enumerate(urls, 1):
        url = url.strip()
        if not url:
            continue  # Skip empty lines
        
        is_valid, error_msg = validate_linkedin_url(url)
        if is_valid:
            valid_urls.append(url)
        else:
            errors.append(f"URL #{i}: {error_msg}")
    
    if not valid_urls:
        return False, "Không có URL hợp lệ nào", []
    
    if errors:
        error_msg = f"Tìm thấy {len(valid_urls)} URL hợp lệ, {len(errors)} URL lỗi:\n" + "\n".join(errors[:5])
        if len(errors) > 5:
            error_msg += f"\n... và {len(errors) - 5} lỗi khác"
        return True, error_msg, valid_urls
    
    return True, None, valid_urls


def validate_date_format(date_str: str) -> Tuple[bool, Optional[str]]:
    """
    Validate date format DD-MM-YYYY
    
    Args:
        date_str: Date string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not date_str or not date_str.strip():
        return True, None  # Empty is allowed
    
    date_str = date_str.strip()
    
    # Check format
    try:
        datetime.strptime(date_str, DATE_FORMAT_DMY)
        return True, None
    except ValueError:
        return False, f"Định dạng ngày không đúng. Phải là DD-MM-YYYY (ví dụ: 01-10-2024)"


def validate_date_range(start_date: str, end_date: str) -> Tuple[bool, Optional[str]]:
    """
    Validate date range
    
    Args:
        start_date: Start date string (DD-MM-YYYY)
        end_date: End date string (DD-MM-YYYY)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Validate formats
    if start_date:
        is_valid, error = validate_date_format(start_date)
        if not is_valid:
            return False, f"Start date: {error}"
    
    if end_date:
        is_valid, error = validate_date_format(end_date)
        if not is_valid:
            return False, f"End date: {error}"
    
    # Validate range if both provided
    if start_date and end_date:
        try:
            start_dt = datetime.strptime(start_date.strip(), DATE_FORMAT_DMY)
            end_dt = datetime.strptime(end_date.strip(), DATE_FORMAT_DMY)
            
            if start_dt > end_dt:
                return True, "Start date > End date (sẽ tự động hoán đổi)"
        except ValueError:
            pass  # Already validated above
    
    return True, None


def validate_numeric_input(value: str, field_name: str, min_val: int = 1, max_val: int = 10000) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Validate numeric input
    
    Args:
        value: String value to validate
        field_name: Name of the field (for error message)
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        
    Returns:
        Tuple of (is_valid, error_message, parsed_value)
    """
    if not value or not value.strip():
        return False, f"{field_name} không được để trống", None
    
    try:
        num = int(value.strip())
        if num < min_val:
            return False, f"{field_name} phải >= {min_val}", None
        if num > max_val:
            return False, f"{field_name} phải <= {max_val}", None
        return True, None, num
    except ValueError:
        return False, f"{field_name} phải là số nguyên", None


def validate_all_inputs(
    urls: List[str],
    start_date: str = "",
    end_date: str = "",
    wait_sec: str = "",
    scroll_rounds: str = "",
    max_posts: str = ""
) -> Tuple[bool, Optional[str], dict]:
    """
    Validate all user inputs
    
    Returns:
        Tuple of (is_valid, error_message, validated_data)
    """
    errors = []
    validated = {}
    
    # Validate URLs
    is_valid, error_msg, valid_urls = validate_urls(urls)
    if not is_valid:
        errors.append(error_msg)
    else:
        validated['urls'] = valid_urls
        if error_msg:  # Warnings
            errors.append(error_msg)
    
    # Validate dates
    is_valid, error_msg = validate_date_range(start_date, end_date)
    if not is_valid:
        errors.append(error_msg)
    else:
        validated['start_date'] = start_date.strip() if start_date else ""
        validated['end_date'] = end_date.strip() if end_date else ""
        if error_msg:  # Warnings
            errors.append(error_msg)
    
    # Validate numeric inputs
    if wait_sec:
        is_valid, error_msg, value = validate_numeric_input(wait_sec, "Wait (sec)", 1, 300)
        if not is_valid:
            errors.append(error_msg)
        else:
            validated['wait_sec'] = value
    
    if scroll_rounds:
        is_valid, error_msg, value = validate_numeric_input(scroll_rounds, "Scroll rounds", 1, 1000)
        if not is_valid:
            errors.append(error_msg)
        else:
            validated['scroll_rounds'] = value
    
    if max_posts:
        is_valid, error_msg, value = validate_numeric_input(max_posts, "Max posts", 1, 10000)
        if not is_valid:
            errors.append(error_msg)
        else:
            validated['max_posts'] = value
    
    if errors:
        return False, "\n".join(errors), validated
    
    return True, None, validated

