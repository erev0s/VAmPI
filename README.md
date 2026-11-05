# VAmPI
**API có lỗ hổng** *(dựa trên OpenAPI 3)*
![vampi](https://i.imgur.com/zR0quKf.jpg)

[![Docker Image CI](https://github.com/erev0s/VAmPI/actions/workflows/docker-image.yml/badge.svg)](https://github.com/erev0s/VAmPI/actions/workflows/docker-image.yml) ![Docker Pulls](https://img.shields.io/docker/pulls/erev0s/vampi)

VAmPI là API Flask được thiết kế có chủ đích các lỗ hổng thuộc OWASP API Top 10. Dự án hỗ trợ đánh giá hiệu quả của công cụ phát hiện lỗ hổng API và phục vụ học tập/giảng dạy. Biến cấu hình cho phép bật hoặc tắt phần hành vi dễ tổn thương trong khi kiểm thử, từ đó đánh giá được false positive/false negative. Xem thêm tại [erev0s.com](https://erev0s.com/blog/vampi-vulnerable-api-security-testing/).

## Tính năng

- Dựa trên OWASP API Top 10.
- Có OpenAPI 3 và Postman Collection.
- Có công tắc toàn cục bật/tắt môi trường dễ tổn thương.
- Xác thực dựa trên token (có thể điều chỉnh thời hạn trong `app.py`).
- Có Swagger UI để tương tác trực tiếp với API.

Luồng VAmPI: người chưa đăng ký chỉ xem được thông tin tối thiểu của user mẫu. User có thể đăng ký, đăng nhập để nhận token, rồi tạo book. Mỗi book có `title` và `secret`; secret của book về nguyên tắc chỉ owner được xem.

| **Thao tác** | **Path** | **Mô tả** |
|:---:|:---:|:---|
| GET | `/createdb` | Tạo và nạp database bằng dữ liệu mẫu |
| GET | `/` | Trang chủ VAmPI |
| GET | `/me` | Hiển thị user đã xác thực |
| GET | `/users/v1` | Danh sách user với thông tin cơ bản |
| GET | `/users/v1/_debug` | Hiển thị toàn bộ thông tin user |
| POST | `/users/v1/register` | Đăng ký user mới |
| POST | `/users/v1/login` | Đăng nhập VAmPI |
| GET | `/users/v1/{username}` | Xem user theo username |
| DELETE | `/users/v1/{username}` | Xóa user (chỉ admin) |
| PUT | `/users/v1/{username}/email` | Cập nhật email user |
| PUT | `/users/v1/{username}/password` | Cập nhật mật khẩu user |
| GET | `/books/v1` | Lấy danh sách book |
| POST | `/books/v1` | Thêm book |
| GET | `/books/v1/{book}` | Lấy book và secret theo title |

Để xem chi tiết, chạy VAmPI và mở `http://127.0.0.1:5000/ui/`, hoặc mở OpenAPI trong thư mục `openapi_specs` bằng [Swagger Editor](https://editor.swagger.io).

## Các lỗ hổng có trong VAmPI

- SQLi Injection
- Unauthorized Password Change
- Broken Object Level Authorization
- Mass Assignment
- Excessive Data Exposure through debug endpoint
- User and Password Enumeration
- RegexDOS (Denial of Service)
- Lack of Resources & Rate Limiting
- JWT authentication bypass via weak signing key

## Chạy VAmPI

### Chạy local

Cài dependency rồi chạy `app.py`:

```bash
pip3 install -r requirements.txt
```

```bash
python3 app.py
```

### Chạy Docker

Image có trên [Docker Hub](https://hub.docker.com/r/erev0s/vampi):

```bash
docker run -p 5000:5000 erev0s/vampi:latest
```

Trên macOS mới, có thể dùng `-p 5001:5000` để tránh xung đột AirPlay Receiver.

### Chạy Docker Compose

Compose chạy hai instance: secure ở port `5001` và vulnerable ở port `5002`.

```bash
docker-compose up -d
```

## Swagger UI

Truy cập `/ui` trên host đang chạy API:

```text
http://127.0.0.1:5000/ui/
```

## Tùy chỉnh thời hạn token và chế độ dễ tổn thương

Khi chạy trực tiếp `python3 app.py`, có thể điều chỉnh `alive` và `vuln` trong `app.py`. `alive` tính bằng giây; `vuln=1` bật chế độ vulnerable và `vuln=0` bật chế độ comparatively secure.

Khi chạy Docker, truyền biến môi trường hoặc sửa Dockerfile rồi build lại:

```bash
docker run -d -e vulnerable=0 -e tokentimetolive=300 -p 5000:5000 erev0s/vampi:latest
```

Có thể chạy instance thứ hai với `vulnerable=1` ở port khác để so sánh.

## Controlled BOLA evaluation lab

Có một Flask service opt-in, triển khai riêng cho thí nghiệm BOLA lặp lại được mà không thay đổi VAmPI gốc. Xem [hướng dẫn kỹ thuật BOLA Lab](docs/bola-lab.md) về controller private, OpenAPI public, scenario, test và vận hành hai máy. Hướng dẫn vận hành chi tiết tiếng Việt nằm tại [docs/bola-lab-operator-guide.vi.md](docs/bola-lab-operator-guide.vi.md).

## Câu hỏi thường gặp

- **Có lỗi database khi gọi endpoint?**
  Hãy gọi `/createdb` để nạp user/book mẫu cho VAmPI gốc.

[Ảnh từ freepik - www.freepik.com](https://www.freepik.com/vectors/party)
