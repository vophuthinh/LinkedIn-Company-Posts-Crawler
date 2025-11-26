# LinkedIn Company Posts Crawler - PRO

## 📋 Mô tả

Tool crawl bài viết từ trang LinkedIn của các công ty với giao diện đồ họa (GUI) thân thiện. Hỗ trợ crawl nhiều URL cùng lúc, lọc theo ngày tháng, và tự động phân tích dữ liệu.

## ✨ Tính năng chính

### 🎯 Crawling Features
- **Single URL hoặc Batch**: Nhập một URL hoặc nhiều URL (textarea/CSV)
- **Lọc ngày**: Định dạng **DD-MM-YYYY** (múi giờ VN), tự động swap nếu nhập ngược
- **Stop-by-time**: Tự động dừng khi gặp bài cũ hơn ngày bắt đầu
- **Stop an toàn**: Nút "Stop" - dừng sau vòng cuộn hiện tại
- **Resume**: Tự động lưu checkpoint, có thể khôi phục khi bấm Start
- **Strict Date Filter**: Tùy chọn loại bỏ các bài thiếu timestamp hoặc lỗi định dạng ngày

### 📊 Analysis & Output
- **Preview 5 bài** đầu tiên trước khi lưu (có thể tắt/bật)
- **Quick analysis**: Tổng số bài, phân bố theo ngày, top hashtag
- **Multi-format output**: CSV (.csv), JSONL (.jsonl)
- **Cookie management**: Tự động lưu và tái sử dụng cookies

### 🔧 Advanced Settings
- **Headless mode**: Chạy ngầm không hiển thị browser
- **Undetected Chrome**: Sử dụng undetected-chromedriver để tránh phát hiện
- **Fast mode**: Tắt hình ảnh để tăng tốc độ (tự động bật)
- **Hashtag fix**: Tự động sửa "hashtag#" thành "#"
- **Smart scrolling**: Ngẫu nhiên hóa hành vi cuộn trang để mô phỏng người dùng thật
- **Random delays**: Tạm nghỉ ngẫu nhiên giữa các URL và các vòng cuộn

### 🎨 UI Features
- **Dark Mode**: Giao diện tối/sáng (tùy chọn)
- **Modern UI**: Theme 'clam' với tooltips và phím tắt
- **Keyboard shortcuts**: F5 (Start), Esc (Stop), Ctrl+S (Save cookies), Ctrl+O (Open folder)
- **Scrollable interface**: Giao diện có thể cuộn, phù hợp với nhiều màn hình

## 🚀 Cài đặt

### Requirements
```bash
pip install -U selenium pandas openpyxl
```

### Optional (Khuyến nghị)
```bash
pip install undetected-chromedriver
```

## 📖 Hướng dẫn sử dụng

### 1. Chạy ứng dụng

**File chính:**
```bash
python "Crawl Post Linkedln.py"
```

**File với UI nâng cấp (khuyến nghị):**
```bash
python "LinkedlnTest.py"
```

### 2. Nhập URL

- **Cách 1**: Gõ trực tiếp LinkedIn company URLs (mỗi URL một dòng)
- **Cách 2**: Click "Load from CSV" để load từ file CSV

**Ví dụ URLs hợp lệ:**
```
https://www.linkedin.com/company/microsoft/posts/?feedView=all
https://www.linkedin.com/company/google/posts/?feedView=all
https://www.linkedin.com/company/facebook/posts/?feedView=all
```

### 3. Cấu hình Filters

- **Start Date**: Ngày bắt đầu (DD-MM-YYYY) - Ví dụ: `01-10-2024`
- **End Date**: Ngày kết thúc (DD-MM-YYYY) - Ví dụ: `31-10-2024`
- **Strict Date Filter**: Bật để loại bỏ các bài thiếu ngày hoặc lỗi định dạng
- Để trống nếu không muốn lọc theo ngày

### 4. Settings

| Setting | Mô tả | Giá trị mặc định |
|---------|--------|------------------|
| Max Posts | Số bài tối đa mỗi company | 300 |
| Scroll Rounds | Số lần cuộn trang | 60 |
| Wait (sec) | Thời gian chờ load | 30 |
| Headless | Chạy ngầm không hiện browser | Tắt (UI) / Bật (Test) |
| Use UC | Dùng undetected-chromedriver | Bật |
| Preview | Hiển thị 5 bài đầu | Bật |
| Fix Hashtags | Sửa lỗi hashtag | Bật |
| Strict Date | Loại bài thiếu ngày | Tắt |

### 5. Output

- **Output Directory**: Thư mục lưu kết quả (mặc định: `~/LinkedInOut`)
- Click "Browse" để chọn thư mục khác

### 6. Bắt đầu Crawl

1. Click **"Start"** (hoặc nhấn **F5**)
2. Nếu chưa đăng nhập, đăng nhập LinkedIn trong trình duyệt, sau đó click **"Tôi đã đăng nhập"**
3. Theo dõi tiến trình trong phần **Console**
4. Click **"Stop"** (hoặc nhấn **Esc**) nếu muốn dừng giữa chừng
5. Click **"Mở thư mục xuất"** (hoặc nhấn **Ctrl+O**) để xem kết quả

## 📁 Cấu trúc Output

```
LinkedInOut/
├── company-slug_posts_20241006_134503.jsonl    # File JSONL chính
├── company-slug_posts_20241006_134503.csv      # File CSV
├── cookies.json                                 # Cookies được lưu
└── checkpoint.json                              # Checkpoint (tạm thời)
```

## 📊 Cấu trúc dữ liệu

Mỗi bài post sẽ có các trường sau:

```json
{
  "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:...",
  "urn": "urn:li:activity:7123456789",
  "time_iso": "2024-10-06T10:30:00Z",
  "text": "Nội dung bài viết...",
  "date_dmy": "06-10-2024"
}
```

### Các trường dữ liệu:

- **post_url**: URL đầy đủ của bài post
- **urn**: Unique Resource Name của LinkedIn
- **time_iso**: Thời gian đăng bài ở định dạng ISO 8601 (UTC)
- **text**: Nội dung bài viết (đã được làm sạch)
- **date_dmy**: Ngày đăng bài ở định dạng DD-MM-YYYY (múi giờ VN)

## 🔄 Resume Feature

Tool tự động lưu tiến trình vào `checkpoint.json`. Nếu bị gián đoạn:

1. Chạy lại tool
2. Tool sẽ tự động phát hiện checkpoint và hỏi có muốn resume không
3. Chọn **"Yes"** để tiếp tục từ URL cuối cùng
4. Hoặc click **"Start"** và chọn resume khi được hỏi

## ⚠️ Lưu ý quan trọng

### Về LinkedIn
- **Rate Limiting**: LinkedIn có giới hạn requests, không crawl quá nhanh
- **Login**: Cần đăng nhập LinkedIn trước khi chạy tool
- **Cookies**: Tool tự động lưu cookies để tránh phải login lại
- **Terms of Service**: Tuân thủ Terms of Service của LinkedIn

### Về Performance
- **Headless Mode**: Nhanh hơn nhưng khó debug
- **Fast Mode**: Tự động tắt hình ảnh, tăng tốc đáng kể
- **Scroll Rounds**: Tăng để crawl nhiều bài hơn, giảm để nhanh hơn
- **Random Delays**: Tool tự động thêm khoảng nghỉ ngẫu nhiên để tránh bị phát hiện

### Về Dữ liệu
- **Date Format**: Luôn dùng DD-MM-YYYY (định dạng VN)
- **Timezone**: Tự động chuyển về múi giờ VN (+7)
- **Encoding**: Output UTF-8, tương thích với Excel tiếng Việt
- **Strict Date Filter**: Khi bật, chỉ giữ lại các bài có timestamp hợp lệ

## 🐛 Troubleshooting

### Lỗi thường gặp

1. **"No such file or directory"**
   - Kiểm tra đường dẫn Output Directory
   - Tạo thư mục Output thủ công

2. **"ChromeDriver not found"**
   - Cài đặt Chrome browser
   - Cập nhật Chrome lên phiên bản mới nhất
   - Nếu dùng undetected-chromedriver, nó sẽ tự động tải driver phù hợp

3. **"Access Denied" trên LinkedIn**
   - Đăng nhập LinkedIn trước
   - Giảm tốc độ crawl (tăng Wait time)
   - Bật "Use UC" mode (undetected-chromedriver)
   - Kiểm tra cookies có hợp lệ không

4. **Tool không phản hồi**
   - Click "Stop" và đợi
   - Khởi động lại tool
   - Kiểm tra checkpoint để resume

5. **Không crawl được bài nào**
   - Kiểm tra URL có đúng định dạng không
   - Đảm bảo đã đăng nhập LinkedIn
   - Kiểm tra date filter có quá chặt không
   - Tăng số Scroll Rounds

### Performance Tips

- **Crawl ban đêm**: Ít bị rate limit hơn
- **Batch nhỏ**: Chia URLs thành nhiều lần chạy
- **Clean cookies**: Xóa cookies.json nếu có lỗi login
- **Use Undetected-CD**: Giúp tránh bị phát hiện tốt hơn
- **Tăng Wait time**: Nếu gặp timeout, tăng thời gian chờ

## ⌨️ Keyboard Shortcuts

| Phím tắt | Chức năng |
|----------|-----------|
| **F5** | Start crawling |
| **Esc** | Stop crawling |
| **Ctrl+S** | Save cookies |
| **Ctrl+O** | Open output folder |

## 📋 Changelog

### Version 2.0 (Current - LinkedlnTest.py)
- ✅ UI nâng cấp với Dark Mode
- ✅ Tooltips và keyboard shortcuts
- ✅ Scrollable interface
- ✅ Improved error handling
- ✅ Better cookie management

### Version 1.0 (Crawl Post Linkedln.py)
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

## 🤝 Hỗ trợ

Nếu gặp vấn đề:

1. Kiểm tra phần **Troubleshooting** trước
2. Đọc log trong tool để tìm lỗi cụ thể
3. Thử với 1 URL đơn giản trước
4. Kiểm tra kết nối internet và trình duyệt
5. Đảm bảo đã cài đặt đầy đủ dependencies

## ⚖️ Disclaimer

Tool này chỉ dành cho mục đích nghiên cứu và học tập. Người dùng cần:

- Tuân thủ Terms of Service của LinkedIn
- Không sử dụng vào mục đích thương mại trái phép
- Tôn trọng robots.txt và rate limiting
- Chịu trách nhiệm về việc sử dụng tool
- Không crawl quá nhiều dữ liệu trong thời gian ngắn

## 📝 Notes

- Tool tự động xử lý các overlay và popup của LinkedIn
- Có thể crawl cả bài viết và bài viết dạng article
- Hỗ trợ cả tiếng Việt và tiếng Anh trong nội dung
- Output files được đặt tên theo pattern: `{company-slug}_posts_{timestamp}.{ext}`
