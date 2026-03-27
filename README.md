**Project Structure:**
```bash
smart-home/
│
├── backend/                     # Xử lý logic, giao tiếp Adafruit và Database
│   ├── .env                     # File chứa các biến môi trường (Mật khẩu MySQL, Adafruit IO Key)
│   ├── requirements.txt         # Danh sách thư viện Python cần cài (adafruit-io, mysql-connector, flask/fastapi)
│   ├── main.py                  # File khởi chạy server API chính
│   │
│   ├── config/
│   │   ├── adafruit_config.py   # Cấu hình kết nối MQTT tới Adafruit IO [cite: 78, 441]
│   │   └── db_config.py         # Cấu hình kết nối tới MySQL Workbench
│   │
│   ├── mqtt/                    # Module giao tiếp với Adafruit IO (Tương ứng M5) [cite: 441]
│   │   ├── subscriber.py        # Script chạy ngầm lắng nghe dữ liệu cảm biến (Nhiệt độ, độ ẩm, khí gas)
│   │   └── publisher.py         # Script gửi lệnh điều khiển ngược lại thiết bị (Bật/tắt đèn, quạt, khóa cửa)
│   │
│   ├── database/                # Tương tác với MySQL
│   │   ├── schema.sql           # File chứa mã SQL để tạo các bảng (sensor_data, device_logs, users)
│   │   └── crud.py              # Các hàm thao tác DB (Insert dữ liệu mới, Query dữ liệu lịch sử 90 ngày) 
│   │
│   ├── api/                     # API cung cấp dữ liệu cho Dashboard
│   │    └── routes.py           # Định nghĩa các endpoint (VD: /api/sensors/history, /api/devices/toggle)
│   │
│   ├── scripts/                     # API cung cấp dữ liệu cho Dashboard
│       ├── inspect_db.py
│       ├── list_routes.py
│       └── test_login.py
├── frontend/                    # Giao diện người dùng (Dashboard)
│   ├── index.html               # Trang chủ Dashboard tổng quan
│   ├── pages/ (devices, login, members, modes, power).html               
│   │
│   ├── css/                     # Chứa các file style (UI/UX)
│   │   ├── style.css            # Style chung cho toàn hệ thống
│   │   └── dashboard.css        # Layout cho các khối: Security, Environment, Control [cite: 432, 433, 434]
│   │
│   ├── js/                      # Logic xử lý giao diện
│   │   ├── main.js              # Khởi tạo và xử lý sự kiện UI chung
│   │   ├── api_client.js        # Gọi API từ backend để lấy dữ liệu mới nhất
│   │   ├── charts.js            # Khởi tạo và vẽ biểu đồ xu hướng lịch sử (dùng Chart.js hoặc thư viện tương đương) [cite: 150]
│   │   ├── ui_interactions.js   # xử lý giao diện cho các trang trừ login.html
│   │   └── control.js           # Xử lý các thao tác bấm nút (kích hoạt kịch bản Scene, điều khiển thiết bị)
│   │
│   └── assets/                  # Tài nguyên tĩnh
│       ├── icons/               # Icon nhiệt độ, độ ẩm, cảnh báo cháy, khóa cửa
│       └── images/              # Hình ảnh minh họa (nếu có)
│
└── docs/                        # Tài liệu dự án
    ├── README.md                # Hướng dẫn cài đặt database, chạy backend và frontend
    └── api_documentation.md     # Tài liệu mô tả các API để team dễ làm việc chung

```
