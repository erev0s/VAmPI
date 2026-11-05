# Hướng dẫn vận hành Controlled BOLA Lab

Tài liệu này dành cho **operator trên Machine B** và người chạy tool đánh giá trên **Machine A**. Lab là service Flask độc lập, chỉ phục vụ thực nghiệm Broken Object Level Authorization (BOLA); nó không thay đổi, không dùng chung database và không thay thế VAmPI gốc.

Xem thêm [hướng dẫn kỹ thuật và triển khai](bola-lab.md) và [OpenAPI public](../openapi_specs/bola-lab.openapi.json).

## 1. Mô hình bảo mật và phạm vi

- **Machine B** giữ controller, SQLite, bearer token, marker và answer sheet private.
- **Machine A** chỉ nhận base URL, OpenAPI public, token được cấp qua kênh bảo vệ và policy/pointer được phép cung cấp.
- Public API chỉ có `GET /health`, `GET /me` và `GET /books/{book_id}`.
- Không có API public để đăng ký user, login, tạo/sửa/xóa book, reset lab, chọn scenario hoặc lấy answer sheet.
- Không gọi `/createdb`: đó là endpoint của VAmPI gốc, không thuộc BOLA Lab.

> Không commit, in log, gửi qua chat hoặc đưa vào tool Machine A các file `issued-tokens.json`, `active-run.json`, `answer-sheet.json`, `operator-config.json`, `lab.sqlite3` hay `server.lock`.

## 2. Cài đặt môi trường BOLA Lab

Dùng dependency riêng của lab. Không cài `requirements.txt` của VAmPI vào virtual environment này.

```bash
python3 -m venv .venv-bola-lab
```

```bash
. .venv-bola-lab/bin/activate && python -m pip install -r requirements.bola-lab.txt
```

## 3. Tạo dữ liệu ban đầu và user

User **không được tạo bằng HTTP API**. Controller cục bộ tạo sẵn toàn bộ dữ liệu cho mỗi run:

| Principal | Role | Mục đích |
| --- | --- | --- |
| `admin` | `admin` | Control cho phép đo S11; policy mặc định là `UNKNOWN` ngoài control này. |
| `userA` | `user` | Requester chính trong các phép thử cross-owner. |
| `userB` | `user` | Owner của resource mục tiêu `book-B1`/`book-B2`. |

| Resource | Owner | Title |
| --- | --- | --- |
| `book-A1` | `userA` | User A book one |
| `book-A2` | `userA` | User A book two |
| `book-B1` | `userB` | User B book one |
| `book-B2` | `userB` | User B book two |

Tạo thư mục state chỉ operator được đọc và khởi tạo S01:

```bash
mkdir -m 700 bola-lab-state
```

```bash
python -m bola_lab.controller --state-dir "$PWD/bola-lab-state" --scenario S01 --token-ttl 3600 init
```

```bash
python -m bola_lab.controller --state-dir "$PWD/bola-lab-state" validate
```

Controller tạo SQLite và các file owner-only (`0700` cho thư mục, `0600` cho file), đồng thời tạo bearer token và marker mới mỗi run. ID resource và authorization semantics vẫn ổn định.

Sau `init` hoặc `reset`, controller in một tóm tắt local-only gồm principal/resource đã seed và đường dẫn tuyệt đối đến artifact private: `lab.sqlite3` (database), `operator-config.json` (pointer, identity/resource và policy), `issued-tokens.json` (bearer token), `active-run.json` (manifest) và `answer-sheet.json` (ground truth). Tóm tắt **không** in bearer token, signing secret, marker, run ID hoặc nội dung answer sheet. Sau `reset`, token và marker cũ đã bị thay thế nên không còn hợp lệ.

### Token

Operator lấy token từ state private **chỉ qua kênh được bảo vệ**. Khi test thủ công, dùng placeholder sau và thay bằng token được cấp; không ghi giá trị token vào shell history, script, commit hoặc log:

```bash
export USER_A_TOKEN='<bearer-token-received-securely>'
```

Khi kết thúc:

```bash
unset USER_A_TOKEN
```

## 4. Khởi động và dừng service

Sau `init`/`validate`, chạy service ở Machine B:

```bash
BOLA_LAB_STATE_DIR="$PWD/bola-lab-state" BOLA_LAB_HOST=127.0.0.1 BOLA_LAB_PORT=5003 python bola_lab_app.py
```

Dùng `BOLA_LAB_HOST=0.0.0.0` chỉ khi Machine A cần truy cập qua một interface mạng lab đã được phê duyệt. Không thay scenario khi process đang chạy. Dừng process bằng `Ctrl+C` trước khi reset.

Kiểm tra readiness từ một terminal khác:

```bash
curl -sS http://127.0.0.1:5003/health
```

Response trung tính:

```json
{"status":"ready"}
```

## 5. Public API

| API | Auth | Mục đích | Pointer ổn định |
| --- | --- | --- | --- |
| `GET /health` | Không | Kiểm tra readiness | Không có dữ liệu scenario |
| `GET /me` | Bearer | Xác nhận principal hiện tại | `/principal/username` |
| `GET /books/{book_id}` | Bearer | Đọc một resource để đánh giá authorization | `/data/id`, `/data/secret` |

### `GET /me`

```bash
curl -sS -H "Authorization: Bearer $USER_A_TOKEN" http://127.0.0.1:5003/me
```

Ví dụ response:

```json
{"principal":{"role":"user","username":"userA"}}
```

### `GET /books/{book_id}`

```bash
curl -i -sS -H "Authorization: Bearer $USER_A_TOKEN" http://127.0.0.1:5003/books/book-B1
```

Form resource đầy đủ, khi scenario/policy cho phép trả private data:

```json
{
  "data": {
    "id": "book-B1",
    "owner": "userB",
    "title": "User B book one",
    "secret": "<generated-private-marker>"
  }
}
```

`401` luôn là `{"error":"unauthorized"}` khi thiếu, sai hoặc hết hạn token. `404` luôn là `{"error":"not_found"}` khi resource/path không tồn tại. Không suy luận authorization chỉ từ `200` hoặc `403`; phải đánh giá body, identity trả về và policy được cấp.

## 6. Quy trình chạy test case thủ công

Mỗi run chỉ dùng một scenario. Quy trình chuẩn:

1. Dừng service hiện có.
2. Khởi tạo lần đầu bằng `init`, hoặc thay scenario bằng `reset`.
3. Chạy `validate`.
4. Khởi động service mới.
5. Cấp token mới qua kênh bảo vệ và chạy request của `userA`; dùng `userB` làm owner control khi cần.
6. Dừng service trước khi chuyển scenario tiếp theo.

Ví dụ chuyển sang S03:

```bash
python -m bola_lab.controller --state-dir "$PWD/bola-lab-state" --scenario S03 --token-ttl 3600 reset
```

```bash
python -m bola_lab.controller --state-dir "$PWD/bola-lab-state" validate
```

Sau `reset`, token và marker cũ không còn hợp lệ; luôn dùng token mới được operator cấp.

## 7. Danh sách S01–S12

Bảng này mô tả **evidence cần quan sát** khi `userA` yêu cầu `book-B1`, trừ khi ghi khác. Answer sheet private là authority cuối cùng để chấm; không suy luận policy từ hành vi server.

| Case | Quan sát chính | Kết luận/cảnh báo |
| --- | --- | --- |
| S01 | `200`, `data.id=book-B1`, có private `secret` của `userB` | BOLA được xác nhận. |
| S02 | `200`, denial envelope, không có private secret | Không coi `200` là evidence của BOLA. |
| S03 | `403` nhưng body vẫn có `book-B1` và private secret | BOLA được xác nhận từ body; `403` không làm disclosure an toàn. |
| S04 | `403`, denial envelope, không có private data | Denial control; cần policy/owner control để kết luận policy-consistent. |
| S05 | `200`, `data: null` | Không có disclosure; `INSUFFICIENT_EVIDENCE` được chấp nhận. |
| S06 | `200`, public fields, `secret: "***"` | Mask không phải private marker. |
| S07 | `200` nhưng trả đúng `book-A1` của requester | Không tính là lộ target `book-B1`; kiểm tra `/data/id`. |
| S08 | `200`, `book-B1` được trả cho `userA` | Cross-owner hợp lệ vì B1 được share cho A. |
| S09 | `200`, chỉ có `id`, `owner`, `title` | Different owner không tự tạo BOLA khi chỉ public fields xuất hiện. |
| S10 | B1/B2 dùng marker trùng; B2 thiếu `/data/id` | Nếu không chứng minh được marker thuộc target B2, `INSUFFICIENT_EVIDENCE` là chấp nhận được. |
| S11 | Response leak của `userA` và denial control của `admin` có byte length bằng nhau | Không dùng response length là rule quyết định. |
| S12 | `202`, body form thay đổi nhưng có target private data | Status/format khác không phủ định disclosure. |

### Request bổ sung cho S10

Khi scenario là S10, dùng cùng token `userA` để đọc cả hai resource:

```bash
curl -sS -H "Authorization: Bearer $USER_A_TOKEN" http://127.0.0.1:5003/books/book-B1
```

```bash
curl -sS -H "Authorization: Bearer $USER_A_TOKEN" http://127.0.0.1:5003/books/book-B2
```

Không tự gán marker trả về ở B2 cho B2 nếu `/data/id` bị thiếu. Đây là thử nghiệm attribution ambiguity, không phải lỗi format cần sửa.

### Owner control

Operator cấp token `userB` qua kênh bảo vệ; owner luôn nhận full resource của `book-B1` trong mọi scenario. Đây là control tách biệt với hành vi cross-owner.

## 8. Automated verification

Sau khi activate `.venv-bola-lab`, chạy:

```bash
python -m compileall -q bola_lab bola_lab_app.py tests
```

```bash
python -W error::ResourceWarning -m unittest discover -s tests -v
```

Trên Ubuntu với Python 3.14 và commit `d88b351`, các lệnh đã PASS: `13` tests, `OK`, gồm tất cả S01–S12, token invalid/expired, owner control, private-path isolation, S10 ambiguity, S11 byte balance, reset isolation và stale lock cleanup.

Các test tạo state tạm và tự cleanup. Test PASS không tạo một dataset bền vững để chạy thủ công; dùng controller `init` khi cần state bền vững.

## 9. Docker Compose cô lập

Docker image dùng Python 3.11 và dependency BOLA Lab riêng, không phụ thuộc Python/virtual environment của host. Dùng project, port loopback và volume riêng để không tác động container hay volume VAmPI khác:

```bash
export BOLA_LAB_PUBLISH_ADDRESS=127.0.0.1
```

```bash
export BOLA_LAB_PUBLISH_PORT=5503
```

```bash
export BOLA_LAB_VOLUME_NAME=vampi-bola-acceptance-state
```

```bash
docker compose -p vampi-bola-acceptance -f docker-compose.lab.yaml build bola-lab
```

Khởi tạo private state S01 trong **volume acceptance**:

```bash
docker compose -p vampi-bola-acceptance -f docker-compose.lab.yaml run --rm --no-deps bola-lab python -m bola_lab.controller --state-dir /var/lib/bola-lab --scenario S01 --token-ttl 3600 init
```

Chỉ chạy service BOLA Lab:

```bash
docker compose -p vampi-bola-acceptance -f docker-compose.lab.yaml up -d --no-build bola-lab
```

```bash
curl -sS http://127.0.0.1:5503/health
```

Dừng service nhưng giữ volume và private data:

```bash
docker compose -p vampi-bola-acceptance -f docker-compose.lab.yaml stop bola-lab
```

Không chạy `docker compose down -v`, không prune volume và không tác động đến các service upstream VAmPI.

## 10. Sau một lượt đánh giá

1. Dừng service trên Machine B.
2. Operator xem answer sheet private cục bộ và so sánh với output tool.
3. Không gọi lại tool để tạo đáp án.
4. Khi bắt đầu lượt mới, reset scenario sau khi service đã dừng, cấp token mới và khởi động process mới.
