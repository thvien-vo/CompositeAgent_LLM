# PROGRESS - CompositeAgent

Hạn: chạy ổn định trước 29/10/2026, thuyết trình 30/10/2026.
Số kiểm chứng (demo.py, CFRP [0/45/-45/90]s, 0.125 mm, Nx=1000, Ny=500, Nxy=100 N/m):
max_failure_index ≈ 0.00238, critical_ply = 4, ABD(1,1) ≈ 5.94e7 N/m. demo.py tự in `CHECK ... PASS/FAIL`.

## Nhật ký

### 27/10/2026
- [x] Đọc toàn bộ code. git init + commit trạng thái ban đầu (`2b15e21`).
- [x] demo.py: max_failure_index = 0.0023807, critical_ply = 4, ABD(1,1) = 5.93995e7 N/m → **PASS**.
- [x] Môi trường: HF_TOKEN có; Ollama 0.40.11 đã cài và đang chạy (chỉ có model `cylinder-agent`);
      đang tải `gemma3:4b` và `nomic-embed-text`. Docker chưa cài, WSL chưa cài
      → theo chỉ dẫn: bỏ qua PostgreSQL + pgvector, giữ RAG bản Python.
- [x] Phát hiện lỗi trong llm.py gốc (v1) với Hugging Face:
  1. Prompt không đưa cấu trúc JSON cho HF (chỉ Ollama bị ép schema) → gpt-oss-120b đặt `Nx, Ny...` ở ngoài
     `"loads"` → `_fix_units` âm thầm điền 0 → CLT chạy với **tải = 0** và báo "an toàn". Không có cảnh báo.
  2. Prompt giải thích yêu cầu so sánh σ2 với độ bền ngang nhưng không đưa độ bền vào prompt.
  3. gpt-oss là model suy luận: `max_tokens` nhỏ → `content = None`.
- [x] llm.py v2 ("LLM đọc, Python tính"): LLM chỉ CHÉP số + đơn vị như trong đề (schema bị ép cho cả HF
      lẫn Ollama); Python khai triển xếp lớp (`layup.py`, vd [0/90]2s → 8 lớp) và đổi đơn vị.
      HF dùng provider Cerebras (~1 s/lần), lỗi thì thử lại với provider auto, rồi mới chuyển Ollama.
      Bước giải thích nhận thêm độ bền vật liệu + tóm tắt tính sẵn bằng Python (lớp tới hạn, thành phần
      ứng suất quyết định, hệ số an toàn); guardrail `check_explanation` dò số lạ trong lời giải thích.
- [x] `layup.py`: 19/19 test tự kiểm tra PASS.
- [x] `benchmark_llm.py`: 10 đề dev + 6 đề holdout (holdout không dùng để chỉnh prompt).
      Kết quả dev, Hugging Face: **v1 gốc 0/10 đúng hoàn toàn** (tải = 0 ở cả 10 đề; khai triển sai [..]2s ở 2 đề),
      **v2 10/10**. File: `deliverables/benchmark/llm_benchmark_dev_20261027_1804.md`.
- [x] main.py chạy trọn LLM → ML → MATLAB → LLM với HF: 12.3 s, kết quả trùng demo.py, giải thích đúng
      (σ2 = 0.1518 MPa so với Yt = 63.76 MPa), guardrail không báo số lạ.
- [ ] Đang làm: chờ gemma3:4b tải xong → benchmark Ollama (v1, v2) → chọn mặc định.
