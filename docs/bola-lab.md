# Controlled BOLA evaluation lab

Để xem hướng dẫn vận hành từng bước bằng tiếng Việt, bao gồm user được controller tạo sẵn, API public và manual test case S01–S12, xem [hướng dẫn operator tiếng Việt](bola-lab-operator-guide.vi.md).

## Mục đích và tách biệt với upstream

Repository này có một **Flask service opt-in, triển khai độc lập** để đánh giá BOLA có kiểm soát. Nó không import, sửa đổi hoặc dùng chung persistence với `app.py`, `config.py`, models, routes, database hoặc OpenAPI của VAmPI gốc. Controller ghi Git commit baseline upstream vào từng answer sheet private.

VAmPI gốc vẫn là đối tượng so sánh. Lab chỉ được khởi động bằng [`bola_lab_app.py`](../bola_lab_app.py) sau khi private state được chuẩn bị tại chỗ.

## Hợp đồng public data-plane

Lab chỉ public các route sau:

| Route | Auth | Response pointer ổn định |
| --- | --- | --- |
| `GET /health` | không | chỉ trả neutral `{"status":"ready"}` |
| `GET /me` | bearer | principal: `/principal/username` |
| `GET /books/{book_id}` | bearer | resource ID: `/data/id`; restricted field: `/data/secret` |

Public specification là [`openapi_specs/bola-lab.openapi.json`](../openapi_specs/bola-lab.openapi.json). Nó không đổi giữa các scenario và cố ý không chứa tên scenario, marker, ground truth, token, controller route hoặc reset function.

Dạng book thông thường:

```json
{
  "data": {
    "id": "book-B1",
    "owner": "userB",
    "title": "User B book one",
    "secret": "private marker"
  }
}
```

Một số experiment cố ý dùng response null/masked/public-only/wrong-resource hoặc alternate form. Khi có `data.id`, giá trị này luôn định danh resource thực sự được trả; nó không bị gắn nhãn lại để giống resource đã yêu cầu.

## Controller private và khả năng tái lập

Controller là Python code chỉ chạy local, không phải HTTP API. Chọn một thư mục mới chỉ operator lab có quyền truy cập:

```bash
mkdir -m 700 bola-lab-state
```

```bash
python3 -m bola_lab.controller --state-dir "$PWD/bola-lab-state" --scenario S01 --token-ttl 3600 init
```

Controller tạo các file atomic, owner-only (`0700` cho thư mục; `0600` cho file):

- `active-run.json`: run configuration immutable-at-startup và signing secret;
- `lab.sqlite3`: principal, resource, actual owner và share;
- `issued-tokens.json`: bearer token do operator cấp;
- `operator-config.json`: pointer và policy input, không có marker hoặc đáp án;
- `answer-sheet.json`: ground truth và accepted outcome chỉ dành cho evaluator.

Sau `init` hoặc `reset`, controller in ra local-only summary gồm principal/resource đã seed, đường dẫn tuyệt đối tới các artifact trên và bước `validate`/khởi động service tiếp theo. Tóm tắt cố ý **không** in bearer token, signing secret, marker, run ID hay nội dung answer sheet. Token phải được lấy cục bộ từ `issued-tokens.json` bằng quy trình protected-channel của operator; không copy file này hoặc cả state directory sang máy chạy tool.

Khi `reset` thành công, controller nêu rõ token bearer và marker cũ đã được thay thế nên token cũ không còn hợp lệ. Chúng được Git ignore nếu tạo tại repository root. Controller từ chối reset hoặc đổi scenario khi server lock chỉ process đang chạy. Service chỉ đọc/validate manifest một lần khi boot, lock run bằng atomic operation và không quan sát thay đổi file config về sau. Dừng process trước khi reset:

```bash
python3 -m bola_lab.controller --state-dir "$PWD/bola-lab-state" --scenario S04 --token-ttl 3600 reset
```

```bash
python3 -m bola_lab.controller --state-dir "$PWD/bola-lab-state" validate
```

Mỗi lần khởi tạo tạo bearer token và secret marker mới. Resource ID và authorization semantics vẫn deterministic. Chỉ S10 cố ý dùng chung secret marker cho cặp `book-B1`/`book-B2`.

BOLA Lab không có password authentication cho principal. Operator có thể xem account/role cục bộ mà không in token:

```bash
python -m bola_lab.operator_accounts --state-dir "$PWD/bola-lab-state" list
```

Chỉ trong terminal Machine B được bảo vệ, operator mới dùng `show-token <username>` để in một bearer token hiện hành. Lệnh này chủ động cảnh báo về terminal scrollback/log; không dùng token output trong chat, commit hoặc script.

## Khởi động service độc lập

BOLA Lab có dependency riêng. Nó hỗ trợ Python hiện hành độc lập với legacy stack được pin của VAmPI: **không** cài [`requirements.txt`](../requirements.txt) vào environment này. File đó chỉ dành cho VAmPI gốc.

```bash
python3 -m venv .venv-bola-lab
```

```bash
. .venv-bola-lab/bin/activate && python -m pip install -r requirements.bola-lab.txt
```

```bash
BOLA_LAB_STATE_DIR="$PWD/bola-lab-state" BOLA_LAB_HOST=127.0.0.1 BOLA_LAB_PORT=5003 python bola_lab_app.py
```

Launcher mặc định bind loopback. Để phục vụ nhiều client LAN, operator phải đặt rõ **một IP LAN của Machine B** và `BOLA_LAB_ALLOWED_CLIENTS` gồm các IPv4/IPv6 host hoặc CIDR được chấp thuận, ví dụ:

```bash
BOLA_LAB_STATE_DIR="$PWD/bola-lab-state" BOLA_LAB_HOST=192.168.10.10 BOLA_LAB_PORT=5003 BOLA_LAB_ALLOWED_CLIENTS="192.168.10.20,192.168.10.21,2001:db8:10::20" python bola_lab_app.py
```

Unset allowlist chỉ chấp nhận loopback; loopback luôn được giữ cho operator local. Empty/malformed/wildcard/duplicate hoặc CIDR quá rộng làm service fail closed. App dùng riêng TCP peer address, không tin `Forwarded`, `X-Forwarded-For` hay `X-Real-IP`, và từ chối client LAN ngoài allowlist bằng neutral `404 {"error":"not_found"}` trước `/health`, authentication và scenario routing. Vì thế mọi client được phép giữ nguyên semantics S01–S12.

Firewall trên Machine B là lớp kiểm soát chính. Chỉ permit đúng IP client tới interface/port đã chọn; không tự động thay đổi firewall. Với Docker Engine, đừng mặc định UFW `INPUT` rule bảo vệ published port vì Docker có thể chuyển lưu lượng qua NAT/FORWARD chain. Xác minh bằng kết nối thật từ một client allowed và một client denied, bao gồm IPv6 nếu publish IPv6.

Application log, error, `/health` và các public response khác không chứa scenario identifier, controller secret, issued token, private answer hay marker trừ khi một scenario cố ý disclosure secret resource qua endpoint resource đang được kiểm thử.

Docker là tùy chọn và không thay đổi upstream image/service. [`Dockerfile.bola-lab`](../Dockerfile.bola-lab) cung cấp Python 3.11 runtime riêng và chỉ cài `requirements.bola-lab.txt`; container không dùng Python host, host virtual environment hoặc legacy dependency của VAmPI. Chuẩn bị named volume bằng one-off local controller container **trước** khi khởi động public service:

```bash
docker compose -f docker-compose.lab.yaml run --rm --no-deps bola-lab python -m bola_lab.controller --state-dir /var/lib/bola-lab --scenario S01 --token-ttl 3600 init
```

```bash
docker compose -f docker-compose.lab.yaml up --build
```

Controller điều chỉnh volume directory về mode `0700` trước khi ghi state. Compose mặc định publish `127.0.0.1:5003`; để mở LAN, đặt `BOLA_LAB_PUBLISH_ADDRESS` thành **địa chỉ LAN cụ thể của Machine B**, không phải `0.0.0.0`, và export `BOLA_LAB_ALLOWED_CLIENTS` trước khi chạy Compose. `BOLA_LAB_VOLUME_NAME` chọn named volume riêng cho isolated trial. Chỉ container port `5003` là data-plane port. Không publish operator state directory, controller shell hoặc reset service.

Docker networking có thể làm peer address trong container khác IP gốc của Machine A, nhất là Docker Desktop, proxy hoặc NAT tùy biến. Không allow Docker gateway và không tin forwarding header để vượt qua hạn chế đó. Xác minh source IP thực tế bằng hai LAN client trước khi coi app allowlist là có hiệu lực; nếu không bảo toàn source IP, giữ loopback publish hoặc chạy direct process với đường mạng/firewall bảo toàn source IP. Firewall host vẫn phải enforce client restriction trên Docker backend/NAT path thực tế.

Để chạy acceptance không phá hủy dữ liệu, dùng Compose project, loopback port và volume name riêng:

```bash
BOLA_LAB_PUBLISH_ADDRESS=127.0.0.1 BOLA_LAB_PUBLISH_PORT=5503 BOLA_LAB_VOLUME_NAME=vampi-bola-acceptance-state docker compose -p vampi-bola-acceptance -f docker-compose.lab.yaml config
```

Lệnh này không đụng đến volume `vampi_bola-lab-state` thông thường.

Trước khi reset, dừng service rồi chuẩn bị lượt chạy tiếp theo bằng cùng one-off controller command, thay `init` bằng `reset`.

```bash
docker compose -f docker-compose.lab.yaml down
```

```bash
docker compose -f docker-compose.lab.yaml run --rm --no-deps bola-lab python -m bola_lab.controller --state-dir /var/lib/bola-lab --scenario S04 --token-ttl 3600 reset
```

Chỉ dùng one-off controller container trong operator context của Machine B; nó không in bearer token. Đọc token artifact owner-only tại chỗ qua protected channel được phê duyệt khi cấp token cho Machine A.

## Dữ liệu và policy

Mỗi run seed `admin`, `userA`, `userB`, cùng `book-A1`, `book-A2`, `book-B1`, `book-B2`. `books.owner` là ownership record thực tế. Policy chuẩn: owner được đọc private data; shared-reader được quyền tương đương khi có cấu hình share; public chỉ xem được ID/owner/title. Admin policy là `UNKNOWN` trong operator configuration, trừ S11 measurement control.

Answer sheet là authority cho policy; nó rõ ràng **không** suy luận intended policy từ hành vi server. Mọi cross-user answer row ghi các chiều độc lập:

- `authorization_allowed`
- `private_data_disclosed`
- `returned_resource_identity`
- `expected_classification`
- `acceptable_conclusions`
- `evidence_requirements`

HTTP status chỉ là transport evidence. `200` không bao giờ tự chứng minh authorization, và `403` không bao giờ tự chứng minh không có private data được gửi.

### Bảng scenario

| Case | Hành vi unauthorized read | Điểm đánh giá |
| --- | --- | --- |
| S01 | `200` với target được yêu cầu và secret thật | Xác nhận BOLA. |
| S02 | `200` denial envelope, không secret | Không có disclosure được xác nhận; chỉ policy-consistent khi biết denial convention, nếu không `INSUFFICIENT_EVIDENCE` được chấp nhận. |
| S03 | `403` với target được yêu cầu và secret thật | Xác nhận BOLA từ body dù status là `403`. |
| S04 | `403` denial envelope, không private data | Policy-consistent khi có denial convention và owner control. |
| S05 | `200` với `data: null` | Không disclosure; `INSUFFICIENT_EVIDENCE` được chấp nhận. |
| S06 | `200` public data với `secret: "***"` | Field key/mask không phải disclosure marker thật. |
| S07 | `200` với book của chính requester | Returned ID khác target được yêu cầu một cách truthful; không tính là disclosure target. |
| S08 | `200` với secret B1 sau khi share B1 cho A | Cross-owner access policy-consistent, không phải BOLA. |
| S09 | `200` chỉ có public ID/owner/title | Khác ownership không tự tạo violation. |
| S10 | Duplicate marker pair; B2 variant bỏ resource ID | Dùng toàn bộ evidence. Nếu không thể source attribution, `INSUFFICIENT_EVIDENCE` được chấp nhận. |
| S11 | Leaking response và admin denial control có serialized UTF-8 byte length bằng nhau | Không dùng body length làm decision rule duy nhất; compression không bật. |
| S12 | `202` alternate body form với target data tương tự | Khác format/status không phủ định disclosure đã chứng minh. |

Owner luôn nhận full resource trong mọi scenario. Token invalid hoặc expired nhận neutral `401` response.

## Input thủ công cho tool

Chỉ cung cấp cho external tool:

```json
{
  "principal_pointer": "/principal/username",
  "resource_id_pointer": "/data/id",
  "restricted_field_pointers": ["/data/secret"],
  "ownership": "The stored owner may read private data; declared shares may grant equivalent access.",
  "denial_convention_when_supplied": {"pointer": "/result", "value": "access_denied"}
}
```

Dùng account/resource list và policy từ `operator-config.json`; chỉ cấp denial convention cho evaluation profile đã khai báo là biết convention. Không cấp answer sheet private, marker value, scenario name hoặc controller artifact cho tool.

## Quy trình hai máy

1. **Machine B (lab)**: tạo protected state directory; chạy `init` cho một scenario; validate; khởi động lab trên interface/port mạng lab đã phê duyệt.
2. **Machine A (tool)**: đặt base URL `http://MACHINE_B:5003`, import public OpenAPI JSON và nhập bearer token thủ công từ operator qua protected channel. Chỉ thêm pointer, identity/resource/policy configuration đã tài liệu hóa và denial convention nếu có.
3. **Chạy**: giữ ổn định lab process và network path. Không reset hoặc đổi scenario trong lúc chạy.
4. **Sau khi hoàn tất**: dừng lab ở Machine B, xem private answer sheet cục bộ và so sánh accepted conclusion. Evaluator không gọi tool lại để tạo đáp án.
5. **Giữa các run**: reset sau khi process kết thúc, cấp token mới và khởi động service process mới.

## Các tầng xác minh

Chạy source và integration check:

Sau khi activate dedicated `.venv-bola-lab` environment ở trên:

```bash
python -m compileall -q bola_lab bola_lab_app.py tests
```

```bash
python -W error::ResourceWarning -m unittest discover -s tests -v
```

Integration suite khởi động local WSGI HTTP server thật và cover S01–S12, owner control, `/me`, invalid/expired token, S03 body leakage, masking, wrong-object truthfulness, sharing, S10 ambiguity, S11 UTF-8 byte equality, file mode, live-reset refusal, startup lock, reset isolation và cố truy cập private/control path qua HTTP.

Docker validation tách biệt: chỉ báo pass khi Docker sẵn sàng và isolated compose service đã build/chạy. Controller không thể initialize named volume chưa mount từ public container; deployer phải provision private volume state trước trên lab host.

## Giới hạn

Increment này không triển khai mutation/post-state case, async flow, mixed-resource list, redirect/login HTML, share revocation trong run, ownership transfer, cross-account cache, BFLA hoặc ZAP integration. Không thể kết luận về detection quality của tool chỉ vì lab hoạt động đúng thiết kế.
