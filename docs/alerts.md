# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: P95 latency của `response_sent.latency_ms` (ngưỡng SLO: 3000ms)
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` duy trì trong 5 phút
- Ảnh hưởng tới người dùng: Người dùng trải nghiệm phản hồi chậm, thời gian chờ câu trả lời tăng cao.
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel Latency để xác định P50/P95/P99 và TTFT, khoanh vùng thời điểm bắt đầu suy giảm hiệu năng.
  2. Lọc file `data/logs.jsonl` trong khoảng thời gian xảy ra sự cố, tìm các `correlation_id` có `latency_ms` vượt ngưỡng 3000ms.
  3. Mở Langfuse trace với `correlation_id` tương ứng để đối chiếu span `retrieval` và `generation` xem bước nào gây nghẽn.
- Mitigation tạm thời: Rollback prompt về version ổn định nếu do prompt dài/chưa tối ưu, hoặc chuyển đổi sang fallback RAG / cache kết quả truy vấn.
- Owner: `student-2A202602897`

## Alert 2

- Tên: `HighErrorRate`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Error rate phần trăm của API (`request_failed` / `request_received`) (ngưỡng guardrail: 2%)
- Điều kiện và thời gian duy trì: `error_rate_pct > 2%` duy trì trong 5 phút
- Ảnh hưởng tới người dùng: Người dùng nhận phản hồi lỗi HTTP 500 hoặc không hoàn thành yêu cầu chat.
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel Errors để xem tổng số lỗi và phân loại theo `error_type` (e.g. `RuntimeError`, `Vector store timeout`).
  2. Tra cứu trong `data/logs.jsonl` các bản ghi `event == "request_failed"` để trích xuất `correlation_id`, `error_type` và message lỗi.
  3. Mở trace trên Langfuse để kiểm tra span gặp lỗi (như `retrieval` thất bại) và context đầu vào.
- Mitigation tạm thời: Bật cơ chế retry/circuit breaker, chuyển sang chế độ trả lời không dùng retrieval (fallback general answer) nếu vector store timeout, thông báo status page.
- Owner: `student-2A202602897`

## Alert 3

- Tên: `LowQualityScore`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Điểm chất lượng trung bình `quality_score` (ngưỡng guardrail: 0.75)
- Điều kiện và thời gian duy trì: `mean(quality_score) < 0.75` duy trì trong 5 phút
- Ảnh hưởng tới người dùng: Câu trả lời bị giảm chất lượng, thiếu thông tin trích xuất từ tài liệu hoặc câu trả lời không liên quan.
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel Quality để kiểm tra xu hướng giảm `quality_score` trung bình.
  2. Lọc `data/logs.jsonl` để lấy các request có `quality_score < 0.75` và đối chiếu với `tool_success` cũng như `prompt_version`.
  3. Mở trace trên Langfuse để kiểm tra tài liệu `docs` được truyền vào prompt và so sánh đầu ra LLM với prompt template.
- Mitigation tạm thời: Rollback prompt version trên Langfuse về version baseline, kiểm tra lại corpus retrieval để bổ sung tài liệu tham khảo chính xác.
- Owner: `student-2A202602897`

