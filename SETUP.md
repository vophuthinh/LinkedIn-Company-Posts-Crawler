# 🚀 Hướng Dẫn Cài Đặt và Setup

## 📋 Yêu Cầu Hệ Thống

- **Python**: 3.11 hoặc cao hơn (khuyến nghị 3.11.9)
- **Chrome Browser**: Phiên bản mới nhất
- **OS**: Windows, macOS, hoặc Linux
- **RAM**: Tối thiểu 4GB (khuyến nghị 8GB)
- **Disk Space**: ~500MB cho dependencies

---

## 🔧 Cài Đặt

### Bước 1: Clone hoặc Download Project

```bash
# Nếu dùng git
git clone <repository-url>
cd LinkedIn

# Hoặc download và giải nén vào thư mục LinkedIn
```

### Bước 2: Tạo Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Lưu ý:** Nếu PowerShell báo lỗi execution policy:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Bước 3: Cài Đặt Dependencies

Sau khi kích hoạt virtual environment (bạn sẽ thấy `(venv)` ở đầu dòng lệnh):

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Dependencies sẽ được cài đặt:**
- ✅ selenium (>=4.9.0) - Web automation
- ✅ pandas (>=2.0.0) - Data processing
- ✅ numpy (>=1.23.2) - Numerical computing
- ✅ openpyxl (>=3.0.0) - Excel file support
- ✅ undetected-chromedriver (>=3.5.0) - Anti-detection browser

### Bước 4: Verify Installation

```bash
python --version
# Sẽ hiển thị: Python 3.11.x

pip list
# Kiểm tra các packages đã được cài đặt
```

---

## 🎯 Quick Start

### Chạy Tool Lần Đầu

1. **Kích hoạt virtual environment:**
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

2. **Chạy tool:**
   ```bash
   # Version cơ bản
   python "Crawl Post Linkedln.py"
   
   # Hoặc version UI nâng cấp (khuyến nghị)
   python "LinkedIn_Crawler_UI.py"
   ```

3. **Đăng nhập LinkedIn:**
   - Tool sẽ mở Chrome browser
   - Đăng nhập LinkedIn trong browser
   - Click nút **"Tôi đã đăng nhập"** trong tool

4. **Bắt đầu crawl:**
   - Nhập URL(s) của company LinkedIn
   - Cấu hình filters và settings
   - Click **"Start"** (hoặc nhấn **F5**)

---

## 📁 Cấu Trúc Project

```
LinkedIn/
├── Crawl Post Linkedln.py      # Main script (basic version)
├── LinkedIn_Crawler_UI.py      # Enhanced UI version (recommended)
├── scraper_core.py             # Shared scraping core module
├── config.py                   # Configuration constants
├── utils.py                    # Shared utility functions
├── validators.py               # Input validation
├── retry_handler.py            # Retry mechanism
├── rate_limiter.py             # Rate limiting
├── requirements.txt            # Python dependencies
├── README.md                   # Documentation chính
├── SETUP.md                    # File này
└── venv/                       # Virtual environment (tạo sau khi setup)
```

---

## ⚙️ Cấu Hình

### Rate Limiting (Tùy chọn)

Chỉnh sửa `config.py` để điều chỉnh rate limiting:

```python
# Rate limiting settings
DEFAULT_RATE_LIMIT_REQUESTS = 10  # Max requests per time window
DEFAULT_RATE_LIMIT_WINDOW = 60    # Time window in seconds
DEFAULT_RATE_LIMIT_MIN_DELAY = 1.0  # Minimum delay between requests
USE_ADAPTIVE_RATE_LIMITER = False  # Use adaptive rate limiter
```

### Retry Settings (Tùy chọn)

```python
# Retry settings
DEFAULT_RETRY_ATTEMPTS = 3        # Max retry attempts
DEFAULT_RETRY_BASE_DELAY = 4.0    # Base delay for exponential backoff
DEFAULT_RETRY_MAX_DELAY = 30.0    # Maximum delay between retries
```

---

## 🔄 Sử Dụng Virtual Environment

### Kích Hoạt (Mỗi lần mở terminal mới)

**PowerShell:**
```powershell
.\venv\Scripts\Activate.ps1
```

**CMD:**
```cmd
venv\Scripts\activate.bat
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

### Tắt Virtual Environment

```bash
deactivate
```

---

## 🐛 Troubleshooting

### Lỗi: "No module named 'pandas'"

**Nguyên nhân:** Chưa kích hoạt virtual environment hoặc chưa cài đặt dependencies.

**Giải pháp:**
```bash
# 1. Kích hoạt venv
.\venv\Scripts\Activate.ps1

# 2. Cài đặt lại dependencies
pip install -r requirements.txt
```

### Lỗi: "ChromeDriver not found"

**Nguyên nhân:** Chrome browser chưa được cài đặt hoặc version không tương thích.

**Giải pháp:**
1. Cài đặt Chrome browser từ [chrome.google.com](https://www.google.com/chrome/)
2. Cập nhật Chrome lên phiên bản mới nhất
3. Nếu dùng `undetected-chromedriver`, nó sẽ tự động tải driver phù hợp

### Lỗi: PowerShell Execution Policy

**Nguyên nhân:** PowerShell chặn script execution.

**Giải pháp:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Lỗi: "DLL load failed"

**Nguyên nhân:** Python version không tương thích hoặc thiếu Visual C++ Redistributable.

**Giải pháp:**
1. Sử dụng Python 3.11.9 (stable version)
2. Cài đặt [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)

### Lỗi: Import Error với shared modules

**Nguyên nhân:** Thiếu các module files.

**Giải pháp:**
- Đảm bảo tất cả files trong project đều có mặt:
  - `config.py`
  - `utils.py`
  - `validators.py`
  - `retry_handler.py`
  - `rate_limiter.py`
  - `scraper_core.py`

---

## 📝 Lưu Ý Quan Trọng

### Virtual Environment

- ✅ **Luôn kích hoạt venv** trước khi chạy tool
- ✅ Virtual environment chỉ dành cho project này
- ✅ Không commit thư mục `venv/` vào git (đã có trong `.gitignore`)

### Dependencies

- ✅ Không cần cài đặt lại nếu đã có venv
- ✅ Nếu xóa `venv/`, cần tạo lại và cài đặt lại dependencies
- ✅ Cập nhật dependencies: `pip install --upgrade -r requirements.txt`

### Python Version

- ✅ **Khuyến nghị:** Python 3.11.9 (stable)
- ⚠️ **Tránh:** Python 3.14 alpha/beta (có thể gây lỗi DLL)

---

## ✅ Checklist Setup

Sau khi setup, kiểm tra:

- [ ] Python 3.11+ đã được cài đặt
- [ ] Virtual environment đã được tạo
- [ ] Dependencies đã được cài đặt (`pip list`)
- [ ] Chrome browser đã được cài đặt
- [ ] Tool có thể chạy được (`python "Crawl Post Linkedln.py"`)
- [ ] Không có lỗi import

---

## 🎓 Next Steps

Sau khi setup xong:

1. Đọc [README.md](README.md) để hiểu cách sử dụng
2. Chạy tool với 1 URL test để kiểm tra
3. Xem phần **Troubleshooting** nếu gặp vấn đề

---

## 📞 Hỗ Trợ

Nếu gặp vấn đề trong quá trình setup:

1. Kiểm tra phần **Troubleshooting** ở trên
2. Đảm bảo đã làm đúng các bước
3. Kiểm tra Python version: `python --version`
4. Kiểm tra venv đã được kích hoạt: `which python` (macOS/Linux) hoặc `where python` (Windows)

---

**Chúc bạn sử dụng tool thành công!** 🎉
