# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Chỉ cần 3 output text và 5 ảnh runtime; dùng đường dẫn tương đối, ví dụ `evidence/03-incident-trace.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Thị Vàng
- **MSSV:** 2A202602897
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/vanganh2301/K4-L3-DAY13-NguyenThiVang-2A202602897-Monitoring-LLMOps
- **Commit SHA cuối:** 9cf04d42f7bca61ccb8ecd6b995c62f0aa188af7
- **Challenge ID:** day13-k4-l3b-monitoring-llmops-v1
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602897`

## 2. Evidence index

| # | Evidence | Đường dẫn |
|---|---|---|
| 01 | Pytest cuối (`git log -1` + `pytest -q`) | `evidence/01-pytest.png` |
| 02 | Log validator (`validate_logs.py` Score 100/100) | `evidence/02-log-validator.png` |
| 03 | Dashboard validator (`validate_dashboard.py` 6/6 panel) | `evidence/03-dashboard-validator.png` |
| 04 | Structured log (`request_received` + `response_sent` JSON) | `evidence/04-structured-log.png` |
| 05 | PII redaction log (Che email, phone, CCCD, card) | `evidence/05-pii-redaction.png` |
| 06 | Trace list (Langfuse project cá nhân $\ge 10$ traces) | `evidence/06-trace-list.png` |
| 07 | Trace waterfall (Timeline `lab-agent-run` $\rightarrow$ `retrieval` & `generation`) | `evidence/07-trace-waterfall.png` |
| 08 | Trace metadata & generation (`08a` / `08b`) | `evidence/08-trace-metadata.png` |
| 09 | Prompt versions (`v1` baseline/production, `v2` candidate) | `evidence/09-prompt-versions.png` |
| 10 | Prompt promote & rollback (`10a` / `10b`) | `evidence/10-prompt-rollback.png` |
| 11 | Dashboard overview (Đủ 6 panels với threshold và time range) | `evidence/11-dashboard-overview.png` |
| 12 | Incident metric (Dashboard ghi nhận P95 latency tăng vọt) | `evidence/12-incident-metric.png` |
| 13 | Incident log (Dòng log có `correlation_id` và latency cao) | `evidence/13-incident-log.png` |
| 14 | Incident trace (Langfuse trace cùng `correlation_id`, span `retrieval` chậm) | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | Đạt chuẩn toàn bộ correlation ID, enrichment context và PII scrubbing |
| `validate_dashboard.py` | 6/6 panel | 6/6 panel | Hợp lệ 6/6 panel theo dashboard contract |
| `pytest` | 22 passed | 24 passed | Bổ sung test PII cho CCCD và Credit Card, 100% tests pass |
| Số traces hợp lệ | 0 | 15+ traces | Đầy đủ cây span root `lab-agent-run`, child `retrieval` và `generation` |
| Số PII leak | 0 | 0 | Scrubber che giấu 100% email, số điện thoại, CCCD và thẻ |
| Latency P95 / TTFT P95 | 158 ms / 50 ms | 2,656 ms / 53 ms | Latency P95 tăng vọt khi kích hoạt sự cố `rag_slow` theo challenge |
| Retrieval success rate | 100% | 100% | Toàn bộ truy vấn RAG đều thành công |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Trong `CorrelationIdMiddleware`, request nhận header `x-request-id` từ client hoặc tự động sinh mới theo định dạng `req-<8-hex>` (`f"req-{uuid.uuid4().hex[:8]}"`). Sau khi `clear_contextvars()` để tránh leak context, ID được bind vào structlog contextvars và gán vào `request.state.correlation_id`, đồng thời trả về trong response header `x-request-id` cùng với `x-response-time-ms`.
- **Các metadata được ghi vào structured log:** Mỗi log record chứa: `ts`, `level`, `service`, `event`, `correlation_id`, `user_id_hash`, `session_id`, `feature`, `model`, `env`, và payload chứa message preview đã được sanitize.
- **Cách bảo đảm PII được scrub trước khi ghi:** Đăng ký processor `scrub_event` trong chuỗi `structlog` processors ngay trước `JsonlFileProcessor` và `JSONRenderer`. Hàm `scrub_text` dùng regex để chuyển đổi toàn bộ email, số điện thoại VN, CCCD 12 số và thẻ tín dụng thành marker `[REDACTED_...]`, đồng thời `user_id` được hash bằng SHA-256 (`user_id_hash`).
- **Cách kiểm chứng kết quả:** Chạy `python scripts/validate_logs.py` đạt 100/100, chạy bộ test `tests/test_pii.py` đạt 4/4 passed, và kiểm tra thủ công log JSON không còn bất kỳ chuỗi PII thô nào.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Toàn bộ request gửi lên Langfuse Cloud sử dụng API keys thuộc project riêng `day13-k4-l3b-2A202602897`, trace metadata có chứa MSSV và tags môi trường `dev`.
- **Cấu trúc root/retrieval/generation observations:** Mỗi request tạo một root observation `@observe(name="lab-agent-run", as_type="agent")`, bên trong chứa 2 child observations: `@observe(name="retrieval")` (truy xuất tài liệu) và `@observe(name="generation", as_type="generation")` (gọi FakeLLM với model, input/output tokens, cost). Cả 2 đều cấu hình `capture_input=False, capture_output=False` để không lưu PII.
- **Cách nối trace với log:** Sử dụng chung `correlation_id` (ví dụ `req-4f1a64fc`) được gắn vào `metadata.correlation_id` trong Langfuse trace và trường `correlation_id` trong file log `data/logs.jsonl`.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** Version 1 mang nhãn `baseline` và `production`.
- **Version/label candidate:** Version 2 mang nhãn `candidate` và `latest`.
- **Trace ID của mỗi version:**
  - Trace ID Version 1 (baseline): `3ec17ee3657d99cafb89a3228b6ab056`
  - Trace ID Version 2 (candidate): `3ec17ee3657d99cafb89a3228b6ab056`
- **Cách promote và rollback `production`:**
  - *Promote:* Trên giao diện Langfuse UI, chuyển nhãn `production` từ Version 1 sang Version 2. Ứng dụng ngay lập tức áp dụng prompt v2 mà không cần khởi động lại server.
  - *Rollback:* Khi cần hoàn tác, chuyển nhãn `production` trên Langfuse UI quay trở lại Version 1. Ứng dụng tự động tải và sử dụng lại prompt v1 an toàn.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dựng đủ 6 panel theo đúng contract `config/dashboard.yaml`: Latency (P50/P95/P99 và TTFT P95), Traffic (req/min), Errors (Error rate và Retrieval success), Cost over time, Input/Output Tokens, Quality proxy.
- **SLO và lý do chọn:** Chọn SLO `fast_successful_requests`: 99.5% requests hoàn thành thành công với độ trễ $\le 3000$ ms trong cửa sổ 28 ngày. Ngưỡng này phản ánh trải nghiệm người dùng tương tác thời gian thực với trợ lý AI.
- **Cách tính error budget:** Với SLO target 99.5%, Error budget là $100\% - 99.5\% = 0.5\%$. Giả sử có 10,000 requests trong 28 ngày, hệ thống cho phép tối đa $10,000 \times 0.005 = 50$ requests bị chậm quá 3000ms hoặc gặp lỗi.
- **Ba alert và runbook tương ứng:**
  - Alert 1: `high_latency_p95` (P95 latency > 3000ms trong 5m, Severity: warning, Kênh: Slack, Runbook: `docs/alerts.md#alert-1`).
  - Alert 2: `high_error_rate` (Error rate > 2% trong 5m, Severity: critical, Kênh: Slack, Runbook: `docs/alerts.md#alert-2`).
  - Alert 3: `low_quality_score` (Mean quality score < 0.75 trong 5m, Severity: warning, Kênh: Slack, Runbook: `docs/alerts.md#alert-3`).

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** 12:05 – 12:08 UTC
- **Triệu chứng từ metrics:** Dashboard ghi nhận P95 Latency tăng vọt từ mức baseline **~158 ms** lên **2,656 ms** (vượt xa ngưỡng SLO 2,000 ms), trong khi Error Rate vẫn ở mức 0% và Retrieval Success đạt 100%.
- **Log line và correlation ID liên quan:**
  - `correlation_id`: `req-4f1a64fc`
  - Log `response_sent` ghi nhận `latency_ms: 2652`, `tool_name: "retrieval"`, `tool_success: true`.
- **Trace ID và span gây ảnh hưởng:**
  - Trace tương ứng với `correlation_id: req-4f1a64fc`
  - Span **`retrieval`** bị nghẽn và chiếm **~2.5 s** (khoảng 94% tổng độ trễ), trong khi span **`generation`** chỉ mất **~0.15 s**.
- **Root cause:** Sự cố chậm tầng truy xuất dữ liệu (`rag_slow`), do Vector Database / tầng retrieval gặp độ trễ cao hoặc nghẽn I/O khi tìm kiếm tài liệu tham khảo.
- **Fix action:** Áp dụng timeout cho lệnh gọi retrieval (ví dụ max 1.0s), giảm số lượng documents `top-k` cần trích xuất, kích hoạt bộ nhớ cache câu trả lời hoặc fallback sang câu trả lời chung khi retrieval bị timeout.
- **Preventive measure:** Thêm alert riêng biệt cho P95 Latency của span `retrieval`, cấu hình Circuit Breaker cho Vector Database và đo lường độc lập hiệu năng từng stage trong trace.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Quyết định đặt `clear_contextvars()` ở đầu `CorrelationIdMiddleware` và đăng ký `scrub_event` processor trước `JSONRenderer`. Điều này bảo đảm mọi async request đều có ngữ cảnh sạch sẽ và dữ liệu PII được làm sạch trước khi serialize ghi ra file log.
- **Một lỗi/blocker đã gặp:** Trong quá trình triển khai cấu trúc trace quan sát, decorator `@observe` nếu không tắt capture input/output có nguy cơ lưu dữ liệu nhạy cảm lên SaaS tracing.
- **Cách tìm nguyên nhân và xử lý:** Cấu hình rõ ràng `capture_input=False, capture_output=False` cho cả hai span `retrieval` và `generation`, đồng thời truyền prompt object qua `propagate_attributes`.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics phát hiện triệu chứng và thời điểm hệ thống bất thường; Logs dựa vào mốc thời gian đó để định vị request cụ thể qua `correlation_id`; Traces dùng `correlation_id` để đào sâu vào từng span (retrieval vs generation) nhằm xác định chính xác nguyên nhân gốc rễ (Root Cause).
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Quản lý prompt theo version và label giúp kiểm soát chi phí token và độ trễ, đồng thời cho phép rollback tức thì về phiên bản ổn định khi prompt mới gây suy giảm chất lượng hoặc tăng vọt chi phí.
- **Điều quan trọng nhất đã học:** Kỹ năng xây dựng hệ thống quan sát toàn diện (Observability) và quy trình điều tra sự cố chuẩn mực trong môi trường LLMOps thực tế.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Các mô hình LLM và RAG hiện tại đang ở dạng Mock; trong tương lai có thể tích hợp mô hình thực tế với streaming tokens để đo lường thêm TTFT thực nghiệm.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Có đúng 3 file text và 5 ảnh runtime theo hướng dẫn.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [x] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
