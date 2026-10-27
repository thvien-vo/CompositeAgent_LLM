# Kết quả Việc 1 (số đo thật cho vật liệu có tên) và Việc 2 (không để tải thành 0 im lặng)

Ngày 27/10/2026, 21:30-22:05. Mốc trước khi sửa: git tag `before-task12` (commit `e0a9162`).
"Đúng hoàn toàn" = đầu vào CLT cuối cùng của agent đúng: vật liệu, mọi góc, độ dày, 6 tải; với bộ mới còn phải
đúng **nguồn tính chất** (dòng CSV đo thật hay ML theo nhóm); 2 đề mơ hồ chỉ đúng khi agent **từ chối kèm lỗi rõ ràng**.

## Bảng trước / sau

| Bộ đề | gemma3:4b trước | gemma3:4b sau | HF gpt-oss-120b trước | HF gpt-oss-120b sau |
|---|---|---|---|---|
| 28 đề cũ (dev 10 + holdout 6 + holdout2 6 + holdout3 6) | 24/28 | **28/28** | 28/28 (*) | **28/28** |
| 16 đề mới - tổng | 4/16 | **16/16** | 5/16 | **16/16** |
| - 8 đề tên vật liệu (M1-M8) | 2/8 | 8/8 | 2/8 | 8/8 |
| - 8 đề tải viết bằng lời / mơ hồ (L1-L8) | 2/8 | 8/8 | 3/8 | 8/8 |
| - trong đó 2 đề phải từ chối (L7, L8) | 0/2 | 2/2 | 0/2 | 2/2 |
| LLM một mình, 28 đề cũ (trước bước kiểm tra Python) | 10/28 | 9/28 | 28/28 (*) | 28/28 |

(*) HF trên 28 đề cũ trước khi sửa: đo ở phiên 27/10 chiều (files `llm_benchmark_*_20261027_184x`), code trích xuất
không đổi đến mốc `before-task12`; không gọi lại để tiết kiệm credit.

Lỗi "sai im lặng" (agent tính tiếp với đầu vào sai, không báo):
- Trước: gemma N4 (tải bằng lời bị đặt vào Nxy), L1 (như vậy), L3 và L4 (**tải = 0**: số viết bằng chữ bị bộ kiểm tra
  bỏ đi), L7/L8 (tự đoán hướng); HF L3, L4 (**tải = 0**, dù HF đọc đúng), L2 (sai dấu nén), L7/L8.
- Sau: **0** ca sai im lặng trong cả 88 lần chạy (44 đề x 2 backend).

Kiểm tra tất định `python\test_checks.py` (không gọi LLM): 44 đề x 3 kiểu câu trả lời giả của LLM (hoàn hảo / quên hết
tải / đặt tải sai chỗ) → 42/42 đúng ở cả 3 kiểu, 2 đề mơ hồ bị từ chối ở cả 3 kiểu.

RAG (không đổi code RAG, chạy lại để kiểm tra hồi quy): gemma dev 11/12, holdout 5/6 (giống trước); HF holdout 6/6.

## File kết quả
- Trước: `llm_benchmark_old28_20261027_2137` (gemma), `llm_benchmark_new_20261027_2138` (gemma),
  `llm_benchmark_new_20261027_2139` (HF); log demo gốc trong `baseline_before_task12\`.
- Sau: `llm_benchmark_old28_20261027_2155` (gemma), `llm_benchmark_new_20261027_2156` (gemma),
  `llm_benchmark_old28_20261027_2157` (HF), `llm_benchmark_new_20261027_2158` (HF).
- Lưu ý trung thực: các bộ đề cũ (kể cả holdout) đã được dùng để tìm lỗi lần này (vd T5, D7), nên **không còn là đề mù**;
  16 đề mới được viết trước khi sửa code, nhưng cũng đã được dùng để kiểm tra trong lúc sửa.
