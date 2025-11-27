# LinkedIn Company Posts Crawler - PRO

> Tool chuyên nghiệp để crawl bài viết từ LinkedIn company pages với nhiều tính năng nâng cao

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Selenium](https://img.shields.io/badge/Selenium-4.9+-green.svg)](https://selenium-python.readthedocs.io/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📋 Mục Lục

- [Tính Năng](#-tính-năng)
- [Cài Đặt](#-cài-đặt)
- [Hướng Dẫn Sử Dụng](#-hướng-dẫn-sử-dụng)
- [Cấu Trúc Dữ Liệu](#-cấu-trúc-dữ-liệu)
- [Tính Năng Nâng Cao](#-tính-năng-nâng-cao)
- [Troubleshooting](#-troubleshooting)
- [Changelog](#-changelog)

---

## ✨ Tính Năng

### 🎯 Core Features

- ✅ **Multi-URL Crawling**: Crawl nhiều company URLs cùng lúc (textarea hoặc CSV)
- ✅ **Date Filtering**: Lọc bài viết theo khoảng thời gian (DD-MM-YYYY, múi giờ VN)
- ✅ **Smart Stop**: Tự động dừng khi gặp bài cũ hơn ngày bắt đầu
- ✅ **Resume/Checkpoint**: Tự động lưu và khôi phục tiến trình
- ✅ **Multi-format Output**: CSV và JSONL với encoding UTF-8
- ✅ **Cookie Management**: Tự động lưu và tái sử dụng cookies

### 🔧 Advanced Features

- ✅ **Retry Mechanism**: Tự động retry với exponential backoff khi gặp lỗi network
- ✅ **Rate Limiting**: Kiểm soát tốc độ requests để tránh bị LinkedIn rate limit
- ✅ **Adaptive Rate Limiter**: Tự động điều chỉnh khi gặp rate limit errors
- ✅ **Smart Scrolling**: Ngẫu nhiên hóa hành vi cuộn để mô phỏng người dùng thật
- ✅ **Random Delays**: Tạm nghỉ ngẫu nhiên giữa các URL và vòng cuộn
- ✅ **Undetected Chrome**: Sử dụng undetected-chromedriver để tránh phát hiện
- ✅ **Strict Date Filter**: Tùy chọn loại bỏ các bài thiếu timestamp

### 🎨 UI Features

- ✅ **Modern Interface**: Theme 'clam' với tooltips và keyboard shortcuts
- ✅ **Dark Mode**: Giao diện tối/sáng (tùy chọn)
- ✅ **Scrollable Interface**: Giao diện có thể cuộn, phù hợp nhiều màn hình
- ✅ **Real-time Progress**: Progress bar với ETA và thống kê
- ✅ **Preview Mode**: Xem trước 5 bài đầu tiên trước khi lưu
- ✅ **Quick Analysis**: Phân tích nhanh sau khi crawl (tổng số, phân bố ngày, top hashtag)

### ⌨️ Keyboard Shortcuts

| Phím tắt | Chức năng |
|----------|-----------|
| **F5** | Start crawling |
| **Esc** | Stop crawling |
| **Ctrl+S** | Save cookies |
| **Ctrl+O** | Open output folder |

---

## 🚀 Cài Đặt

### Yêu Cầu

- Python 3.11+ (khuyến nghị 3.11.9)
- Chrome Browser (phiên bản mới nhất)
- ~500MB disk space cho dependencies

### Quick Setup

```bash
# 1. Tạo virtual environment
python -m venv venv

# 2. Kích hoạt venv
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# macOS/Linux:
source venv/bin/activate

# 3. Cài đặt dependencies
pip install -r requirements.txt
```

**Xem chi tiết:** [SETUP.md](SETUP.md)

---

## 📖 Hướng Dẫn Sử Dụng

### 1. Khởi Động Tool

```bash
# Version cơ bản
python "Crawl Post Linkedln.py"

# Hoặc version UI nâng cấp (khuyến nghị)
python "LinkedIn_Crawler_UI.py"
```

### 2. Nhập URLs

**Cách 1: Gõ trực tiếp**
```
https://www.linkedin.com/company/microsoft/posts/?feedView=all
https://www.linkedin.com/company/google/posts/?feedView=all
```

**Cách 2: Load từ CSV**
- Click **"Load from CSV"**
- File CSV cần có cột `url` hoặc `URL`

### 3. Cấu Hình Filters

| Field | Mô tả | Ví dụ |
|-------|-------|-------|
| **Start Date** | Ngày bắt đầu (DD-MM-YYYY) | `01-10-2024` |
| **End Date** | Ngày kết thúc (DD-MM-YYYY) | `31-10-2024` |
| **Strict Date Filter** | Loại bỏ bài thiếu ngày | ☑️ Bật/Tắt |

### 4. Settings

| Setting | Mô tả | Default |
|---------|-------|---------|
| **Max Posts** | Số bài tối đa mỗi company | 300 |
| **Scroll Rounds** | Số lần cuộn trang | 60 |
| **Wait (sec)** | Thời gian chờ load | 30 |
| **Headless** | Chạy ngầm không hiện browser | Tắt |
| **Use UC** | Dùng undetected-chromedriver | Bật |
| **Preview** | Hiển thị 5 bài đầu | Bật |
| **Fix Hashtags** | Sửa lỗi hashtag | Bật |

### 5. Bắt Đầu Crawl

1. Click **"Start"** (hoặc nhấn **F5**)
2. Nếu chưa đăng nhập, đăng nhập LinkedIn trong browser
3. Click **"Tôi đã đăng nhập"** sau khi đăng nhập xong
4. Theo dõi tiến trình trong Console
5. Click **"Stop"** (hoặc **Esc**) nếu muốn dừng

### 6. Xem Kết Quả

- Click **"Mở thư mục xuất"** (hoặc **Ctrl+O**)
- Files được lưu trong thư mục Output (mặc định: `LinkedInOut/`)

---

## 📁 Cấu Trúc Output

```
LinkedInOut/
├── microsoft_posts_20241006_134503.jsonl    # JSONL format
├── microsoft_posts_20241006_134503.csv      # CSV format (UTF-8 BOM)
├── cookies.json                              # Saved cookies
└── checkpoint.json                           # Resume checkpoint
```

### File Naming Pattern

```
{company-slug}_posts_{YYYYMMDD}_{HHMMSS}.{ext}
```

---

## 📊 Cấu Trúc Dữ Liệu

Mỗi bài post có các trường sau:

```json
{
  "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7123456789/",
  "urn": "urn:li:activity:7123456789",
  "time_iso": "2024-10-06T10:30:00Z",
  "text": "Nội dung bài viết đã được làm sạch...",
  "date_dmy": "06-10-2024"
}
```

### Mô Tả Các Trường

| Trường | Mô tả | Ví dụ |
|--------|-------|-------|
| **post_url** | URL đầy đủ của bài post | `https://www.linkedin.com/feed/update/...` |
| **urn** | Unique Resource Name của LinkedIn | `urn:li:activity:7123456789` |
| **time_iso** | Thời gian đăng bài (ISO 8601, UTC) | `2024-10-06T10:30:00Z` |
| **text** | Nội dung bài viết (đã làm sạch) | `"Nội dung bài viết..."` |
| **date_dmy** | Ngày đăng bài (DD-MM-YYYY, VN timezone) | `06-10-2024` |

---

## 🔄 Resume Feature

Tool tự động lưu tiến trình vào `checkpoint.json`. Nếu bị gián đoạn:

1. Chạy lại tool
2. Tool sẽ tự động phát hiện checkpoint
3. Chọn **"Yes"** để tiếp tục từ URL cuối cùng
4. Hoặc chọn **"No"** để bắt đầu lại

**Checkpoint chứa:**
- Danh sách URLs
- Index URL hiện tại
- Filters đã áp dụng
- Timestamp

---

## ⚙️ Tính Năng Nâng Cao

### Retry Mechanism

Tool tự động retry khi gặp lỗi network/timeout:

- **Max attempts**: 3 lần (có thể cấu hình)
- **Exponential backoff**: Delay tăng dần (4s → 8s → 16s)
- **Retryable errors**: TimeoutException, WebDriverException, ConnectionError

**Cấu hình trong `config.py`:**
```python
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_BASE_DELAY = 4.0
DEFAULT_RETRY_MAX_DELAY = 30.0
```

### Rate Limiting

Kiểm soát tốc độ requests để tránh bị LinkedIn rate limit:

- **Default**: 10 requests / 60 giây
- **Min delay**: 1 giây giữa các requests
- **Adaptive mode**: Tự động điều chỉnh khi gặp rate limit

**Cấu hình trong `config.py`:**
```python
DEFAULT_RATE_LIMIT_REQUESTS = 10
DEFAULT_RATE_LIMIT_WINDOW = 60
DEFAULT_RATE_LIMIT_MIN_DELAY = 1.0
USE_ADAPTIVE_RATE_LIMITER = False
```

### Smart Scrolling

Ngẫu nhiên hóa hành vi cuộn để mô phỏng người dùng thật:

- Random scroll distance (900-1300px)
- Random delays (0.6-1.2s)
- Long pauses ngẫu nhiên (mỗi 8-15 rounds)

---

## 🐛 Troubleshooting

### Lỗi Thường Gặp

#### 1. "No module named 'pandas'"

**Nguyên nhân:** Chưa kích hoạt virtual environment.

**Giải pháp:**
```bash
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

#### 2. "ChromeDriver not found"

**Nguyên nhân:** Chrome chưa được cài đặt hoặc version không tương thích.

**Giải pháp:**
- Cài đặt Chrome browser
- Cập nhật Chrome lên phiên bản mới nhất
- Nếu dùng undetected-chromedriver, nó sẽ tự động tải driver

#### 3. "Access Denied" trên LinkedIn

**Nguyên nhân:** Chưa đăng nhập hoặc bị rate limit.

**Giải pháp:**
- Đăng nhập LinkedIn trước
- Giảm tốc độ crawl (tăng Wait time)
- Bật "Use UC" mode
- Kiểm tra cookies có hợp lệ không

#### 4. Tool không phản hồi

**Giải pháp:**
- Click "Stop" và đợi
- Khởi động lại tool
- Kiểm tra checkpoint để resume

#### 5. Không crawl được bài nào

**Giải pháp:**
- Kiểm tra URL có đúng định dạng không
- Đảm bảo đã đăng nhập LinkedIn
- Kiểm tra date filter có quá chặt không
- Tăng số Scroll Rounds

### Performance Tips

- ✅ **Crawl ban đêm**: Ít bị rate limit hơn
- ✅ **Batch nhỏ**: Chia URLs thành nhiều lần chạy
- ✅ **Clean cookies**: Xóa `cookies.json` nếu có lỗi login
- ✅ **Use Undetected-CD**: Giúp tránh bị phát hiện tốt hơn
- ✅ **Tăng Wait time**: Nếu gặp timeout, tăng thời gian chờ

---

## 📋 Changelog

### Version 2.1 (Current)

**New Features:**
- ✅ Retry mechanism với exponential backoff
- ✅ Rate limiting với adaptive mode
- ✅ Shared scraping module (`scraper_core.py`)
- ✅ Improved error handling với logging
- ✅ Input validation module

**Improvements:**
- ✅ Giảm code duplication
- ✅ Better code structure
- ✅ Enhanced reliability
- ✅ Better documentation

### Version 2.0

- ✅ UI nâng cấp với Dark Mode
- ✅ Tooltips và keyboard shortcuts
- ✅ Scrollable interface
- ✅ Improved error handling
- ✅ Better cookie management

### Version 1.0

- ✅ GUI thân thiện với Tkinter
- ✅ Multi-URL crawling với CSV support
- ✅ Date filtering với VN timezone
- ✅ Resume/checkpoint functionality
- ✅ Multi-format output (CSV, JSONL)
- ✅ Real-time analysis và preview
- ✅ Cookie management
- ✅ Undetected Chrome support
- ✅ Smart scrolling với random delays
- ✅ Strict date filter option

---

## ⚠️ Lưu Ý Quan Trọng

### Về LinkedIn

- ⚠️ **Rate Limiting**: LinkedIn có giới hạn requests, không crawl quá nhanh
- ⚠️ **Login**: Cần đăng nhập LinkedIn trước khi chạy tool
- ⚠️ **Cookies**: Tool tự động lưu cookies để tránh phải login lại
- ⚠️ **Terms of Service**: Tuân thủ Terms of Service của LinkedIn

### Về Performance

- ⚡ **Headless Mode**: Nhanh hơn nhưng khó debug
- ⚡ **Fast Mode**: Tự động tắt hình ảnh, tăng tốc đáng kể
- ⚡ **Scroll Rounds**: Tăng để crawl nhiều bài hơn, giảm để nhanh hơn
- ⚡ **Random Delays**: Tool tự động thêm khoảng nghỉ ngẫu nhiên

### Về Dữ Liệu

- 📅 **Date Format**: Luôn dùng DD-MM-YYYY (định dạng VN)
- 🌍 **Timezone**: Tự động chuyển về múi giờ VN (+7)
- 📝 **Encoding**: Output UTF-8, tương thích với Excel tiếng Việt
- ✅ **Strict Date Filter**: Khi bật, chỉ giữ lại các bài có timestamp hợp lệ

---

## ⚖️ Disclaimer

Tool này chỉ dành cho mục đích **nghiên cứu và học tập**. Người dùng cần:

- ✅ Tuân thủ Terms of Service của LinkedIn
- ✅ Không sử dụng vào mục đích thương mại trái phép
- ✅ Tôn trọng robots.txt và rate limiting
- ✅ Chịu trách nhiệm về việc sử dụng tool
- ✅ Không crawl quá nhiều dữ liệu trong thời gian ngắn

---

## 📝 Notes

- Tool tự động xử lý các overlay và popup của LinkedIn
- Có thể crawl cả bài viết và bài viết dạng article
- Hỗ trợ cả tiếng Việt và tiếng Anh trong nội dung
- Output files được đặt tên theo pattern: `{company-slug}_posts_{timestamp}.{ext}`

---

## 🤝 Hỗ Trợ

Nếu gặp vấn đề:

1. Kiểm tra phần **Troubleshooting** trước
2. Đọc log trong tool để tìm lỗi cụ thể
3. Thử với 1 URL đơn giản trước
4. Kiểm tra kết nối internet và trình duyệt
5. Đảm bảo đã cài đặt đầy đủ dependencies (xem [SETUP.md](SETUP.md))

---

## 📄 License

MIT License - Xem file LICENSE để biết thêm chi tiết.

---

**Made with ❤️ for research and learning purposes**
