## 📂 Project Structure

```text
smart-home/
│
├── backend/                  # Xử lý logic, giao tiếp Adafruit và Database
│   ├── config/               # Cấu hình hệ thống
│   │   ├── adafruit_config.py# Cấu hình kết nối MQTT tới Adafruit IO
│   │   └── db_config.py      # Cấu hình kết nối tới MySQL Workbench
│   ├── mqtt/                 # Module giao tiếp với Adafruit IO (Tương ứng M5)
│   │   ├── subscriber.py     # Script lắng nghe dữ liệu cảm biến (Temp, Humid, Gas)
│   │   └── publisher.py      # Script gửi lệnh điều khiển (Đèn, quạt, khóa)
│   ├── database/             # Tương tác với MySQL
│   │   ├── schema.sql        # File SQL tạo bảng (sensor_data, device_logs, users)
│   │   └── crud.py           # Hàm thao tác DB (Insert, Query dữ liệu 90 ngày)
│   ├── api/                  # API cung cấp dữ liệu cho Dashboard
│   │   └── routes.py         # Các endpoint (/api/sensors/history, /api/devices/toggle)
│   ├── scripts/              # Các kịch bản bổ trợ
│   │   ├── inspect_db.py
│   │   ├── list_routes.py
│   │   └── test_login.py
│   ├── .env                  # Biến môi trường (Mật khẩu MySQL, Adafruit Key) - [HIDDEN]
│   ├── requirements.txt      # Danh sách thư viện Python cần cài
│   └── main.py               # File khởi chạy server API chính
│
├── frontend/                 # Giao diện người dùng (Dashboard)
│   ├── index.html            # Trang chủ Dashboard tổng quan
│   ├── pages/                # Các trang chức năng (devices, login, members, modes, power)
│   ├── css/                  # Chứa các file style (UI/UX)
│   │   ├── style.css         # Style chung toàn hệ thống
│   │   └── dashboard.css     # Layout: Security, Environment, Control
│   ├── js/                   # Logic xử lý giao diện
│   │   ├── main.js           # Xử lý sự kiện UI chung
│   │   ├── api_client.js     # Gọi API từ backend
│   │   ├── charts.js         # Vẽ biểu đồ xu hướng (Chart.js)
│   │   ├── ui_interactions.js# Xử lý giao diện các trang phụ
│   │   └── control.js        # Điều khiển thiết bị và kịch bản (Scene)
│   └── assets/               # Tài nguyên tĩnh (Icons, Images)
│
└── docs/                     # Tài liệu dự án
    ├── README.md             # Hướng dẫn cài đặt và vận hành
    └── api_documentation.md  # Tài liệu mô tả chi tiết các API
