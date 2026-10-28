# PROGRESS - CompositeAgent

Hạn: chạy ổn định trước 29/10/2026, thuyết trình 30/10/2026.
Số kiểm chứng (demo.py, CFRP [0/45/-45/90]s, 0.125 mm, Nx=1000, Ny=500, Nxy=100 N/m):
max_failure_index ≈ 0.00238, critical_ply = 4, ABD(1,1) ≈ 5.94e7 N/m. demo.py tự in `CHECK ... PASS/FAIL`.
Lần chạy gần nhất: 0.0023807 / 4 / 5.93995e7 → **PASS** (chạy lại sau mỗi thay đổi).

## Cách chạy
- Demo 1 bước: double-click `run_demo.bat` (hoặc `run_demo.bat --offline`, `--interactive`, `--lang vi`).
- Agent: `venv\Scripts\python.exe python\main.py "CFRP [0/90]s, 0.125 mm plies, Nx = 1 kN/m"`
- RAG: `venv\Scripts\python.exe python\rag.py "What is Xt of IM7/8552?"`
- Benchmark: `python\benchmark_llm.py --set old28|new|dev|holdout|holdout2|holdout3`, `python\benchmark_rag.py --set dev|holdout`
- Kiểm tra tất định (không gọi LLM): `python\test_checks.py` → ALL PASS
- Số lần gọi Hugging Face: mỗi lần gọi ghi 1 dòng vào `logs\hf_calls.log`.

## Tài liệu thuyết trình cập nhật (28/10): XONG
- Slide: 19 trang (thêm slide 13-16 về tối ưu Lớp 1: bài toán, phương pháp, kiểm chứng, kết quả). Slide 1 ghi người
  trình bày Võ Nguyễn Thanh Viên, thầy hướng dẫn TS. Nguyễn Sỹ Ngọc (Khoa Cơ khí, HCMUT), đối tác GS. Masaaki Nishikawa
  (ĐH Kyoto). Slide Hạn chế / Bước tiếp theo: thêm Lớp 2, Lớp 3, mất ổn định do cắt và hạn chế của chế độ offline.
- Mức giảm khối lượng chỉ nêu cho ca không có lực cắt (-50 %, -37.5 %, nén -8.3 % đến -16.7 %); ca có lực cắt ghi rõ
  chưa xét mất ổn định do cắt (Ritz: cắt thuần 12 lớp không đủ, cần khoảng 46 lớp). Hình so sánh tựa đẳng hướng được cắt
  chỉ giữ 4 ca không có cắt.
- Slide 13-16 và các thay đổi trên được sửa trực tiếp trong file .pptx; `make_slides.py` vẫn sinh bản 15 slide cũ
  (chạy lại sẽ ghi đè các thay đổi này).
- Kịch bản `KICH_BAN_THUYET_TRINH.md` + `.docx` (sinh lại bằng `md_to_docx.py`): phần nói slide 13-16, thuật ngữ tối ưu,
  câu hỏi Q17-Q26, ghi chú: demo chạy chế độ có mạng; nếu buộc dùng `--offline` thì không đọc to lời giải thích của gemma3.
- Kiểm tra bố cục: xuất PDF/PNG bằng PowerPoint, xem từng slide: không chồng chữ, không tràn khung.

## Lớp 1 - Tối ưu thứ tự xếp lớp (28/10): XONG
Mốc trước khi làm: tag `before-optimization` (`dec149b`). Chỉ THÊM file trong `python/optimization/` và
`deliverables/optimization/` (+ mục này); `git diff before-optimization` trên các file cũ: trống.
Báo cáo: `deliverables/optimization/BAO_CAO_LOP1.md` (tiếng Việt + 1 trang tiếng Anh cho GS. Nishikawa), bảng
`results/*.csv`, `results/tables.md`, hình `figures/*.png`. Chạy lại: `python\optimization\run_optimization.bat [--quick]`.
Thư viện mới (venv): pymoo 0.6.2, pytest 9.1.1, matplotlib 3.11.2 (ghi trong `python/optimization/requirements-opt.txt`).
- Bộ tính CLT numpy (cùng quy ước `clt_engine.m`), Max Stress / Tsai-Wu (F12* = -0.5) / Max Strain theo hệ số dự trữ RF,
  mất ổn định công thức đóng (dò mode có chứng minh đủ) + Ritz có Nxy (bổ sung), luật thiết kế bật/tắt + repair,
  vét cạn (chuỗi họ góc, đếm số lượng + quy hoạch động, cận dưới chứng minh được), GA, GA + tìm kiếm cục bộ, NSGA-II
  (pymoo), hàm `optimize(...)` trả `OptimizationResult`; IM7/8552 số đo NCAMP, thiếu độ bền -> ML + cảnh báo.
- Kiểm chứng: Python vs MATLAB 60/60 tấm ngẫu nhiên, sai số <= 2.5e-15. 8 ca tải x 2 độ dày lớp (0.125 / 0.18288 mm):
  vét cạn chứng minh tối ưu cả 16 bài; GA, GA+LS, NSGA-II **20/20 seed đúng tối ưu ở cả 16 bài** (ngân sách 10 000).
  Le Riche & Haftka: trùng tối ưu công bố 3973.01 / 9998.19 / 13518.66, Ny/Nx = 0.25 tìm được 12678.78 (+0.031 %
  so với thiết kế GA trong luận án); bài 1995: n* = 48 lớp và thiết kế ca 2, 3 trùng nguyên văn bài báo.
  pytest: 78/78 đạt (gồm 2 test MATLAB). MATLAB tính lại 83 phương án tối ưu cuối: 83/83 đạt, sai số <= 3.1e-15.
- Giảm khối lượng so với tựa đẳng hướng (lớp 0.125 mm, ca không có lực cắt): -50 % kéo một phương, -37.5 % kéo hai
  phương, -16.7 % nén một phương, -8.3 % nén hai phương; tải rất lớn: không khả thi <= 64 lớp. Ca có lực cắt: mô hình
  chính chưa có mất ổn định do cắt nên không dùng con số giảm khối lượng làm kết quả.
- Hạn chế chính: công thức đóng không có mất ổn định do cắt (Ritz: phương án cắt thuần 12 lớp chỉ chịu 2.3 % tải,
  cần 46 lớp); bỏ qua D16/D26 (tỉ số <= 0.15); bài LC3 1995 "đánh lừa GA" chỉ 3/20.
- Sửa trong lúc làm: NSGA-II của pymoo làm mất tối ưu khi nhiều thiết kế cùng (số lớp, biên) -> khoảng cách chen chúc
  tính trên vector mục tiêu khác nhau (test hồi quy); GA thêm tìm kiếm cục bộ + bước bớt lớp (LC2 1995: 6/20 -> 20/20).
- Sự cố máy (28/10 ~02:10-02:18, ĐÃ XỬ LÝ): sau một lần chạy song song 16 tiến trình bị lỗi cấp phát bộ nhớ OpenBLAS,
  dịch vụ WMI của Windows treo (`tasklist`, `platform.platform()` của Python, `import matlab.engine` đều treo). Sau khi
  khởi động lại máy đã kiểm tra: `demo.py` PASS (0.00238 / 4); `run_demo.bat` có mạng và `--offline` chạy đúng;
  `matlab_recheck` 83/83 đạt; pytest 78/78. Module tối ưu tự tránh WMI (`optimization/__init__.py`, `run_tests.py`).

## Việc 1 + 2 (27/10 tối): XONG - chi tiết trong deliverables/benchmark/KET_QUA_VIEC_1_2.md
Mốc trước khi sửa: tag `before-task12` (`e0a9162`). Demo gốc: online 25 s, offline 39 s, demo.py PASS (log trong
deliverables/benchmark/baseline_before_task12/).
- **Việc 1** (`python\materials.py`, mới): schema LLM có thêm `material_name` (tên chép nguyên văn, phải có trong đề);
  Python còn quét chính văn bản đề. Chỉ dùng số đo khi khớp **duy nhất cả sợi và nhựa** với 1 dòng CSV (bỏ qua
  hoa/thường, "/", "-", khoảng trắng, tên hãng Hexcel, Cytec...). Chỉ ghi "IM7" (4 dòng), tên không có trong dữ liệu →
  ML theo nhóm như cũ, in lý do. Đổi đơn vị GPa x1e9, MPa x1e6; IM7/8552: E1 = 1.621e11 Pa (đã kiểm tra).
  Ô trống (S của T650/5250-5) và ν12 bất thường (0.164 của T40-800/5215, theo ml.EXCLUDE) → ML nhóm CFRP + cảnh báo
  ghi rõ cột. Luôn in nguồn: "measured: NCAMP NCP-RP-2009-028 Rev B, p.37" hoặc "ML prediction (group CFRP)".
  Không sửa ml.py, model, CSV. clt_engine.m nhận đúng các trường như cũ (material_name không gửi sang MATLAB).
- **Việc 2** (`llm.py`, `numwords.py` mới): số viết bằng chữ (Anh/Việt: "one thousand five hundred", "hai") → chữ số;
  đơn vị viết bằng chữ ("newtons per metre"); Python quét **mọi** đại lượng "số + đơn vị tải" trong đề và xác định tải
  của nó từ chính mệnh đề chứa nó (ký hiệu Nx..., "along x", "y direction", "shear", "twisting", "compressive" → âm);
  LLM đặt sai chỗ → sửa theo đề + cảnh báo; tải không rõ hướng → **từ chối, báo lỗi rõ** (không hỏi lại LLM vì vô ích);
  đề có từ chỉ tải mà mọi tải = 0 → hỏi lại LLM 1 lần rồi báo lỗi; số trong đề không được dùng → cảnh báo.
  Ngoài ra: góc / độ dày từng lớp liệt kê trong đề ("30°, -30°..." , "45° (0.3 mm)") được Python đọc thẳng.
- 16 đề thử mới (bộ `new`, viết trước khi sửa): 8 tên vật liệu (đúng tên, tên hãng + đảo thứ tự, chỉ "IM7", tên không
  có, ô trống S, ν12 bất thường, dòng giáo trình, GFRP), 8 tải (bằng lời, kN/m, N/mm, số bằng chữ Anh/Việt, mô-men
  xoắn bằng lời, 2 đề mơ hồ phải từ chối).

| Bộ đề | gemma trước | gemma sau | HF trước | HF sau |
|---|---|---|---|---|
| 28 đề cũ | 24/28 | **28/28** | 28/28 | **28/28** |
| 16 đề mới | 4/16 | **16/16** | 5/16 | **16/16** |
| sai im lặng | nhiều (L3, L4: tải = 0) | **0** | L3, L4 tải = 0; L2 sai dấu | **0** |

- RAG chạy lại: gemma 11/12 + 5/6, HF holdout 6/6 (như trước). test_checks.py: ALL PASS.
- run_demo có thêm đề 3 (IM7/8552 + tải bằng lời) và đề 4 (tải không rõ hướng → agent phải từ chối). Online 20-45 s (2 lần đo),
  offline 55-57 s (không tính thời gian dừng, gồm khởi động MATLAB). Chạy qua chính run_demo.bat cả 2 chế độ: OK.
  demo.py vẫn PASS. Log dự phòng mới: deliverables/demo_log_backup_online.txt, demo_log_backup_offline.txt.
- Hugging Face trong lượt làm Việc 1 + 2: **96 lần gọi** (giới hạn 150): 8 demo gốc, 16 benchmark đề mới trước khi sửa,
  44 benchmark sau khi sửa, 11 demo online thử, 6 RAG holdout, 11 demo online cuối (qua run_demo.bat).
  Đếm trong `logs\hf_calls.log` (8 lần đầu đếm từ log demo gốc vì bộ đếm được thêm sau).
- Hạn chế còn lại của Việc 1+2: chỉ 25 vật liệu có số đo; hướng tải đọc bằng luật từ khóa (Anh/Việt) - câu lạ bị từ
  chối thay vì đoán; mô-men "bending moment of ... about the x axis" (không ký hiệu) bị từ chối vì quy ước Mx/My dễ
  nhầm; các bộ đề cũ đã dùng để tìm lỗi nên không còn là đề mù; 16 đề mới do tôi tự viết.

## Mục tiêu 1 - Agent LLM → ML → MATLAB → LLM: XONG
Lỗi tìm thấy trong llm.py gốc (v1):
1. Với Hugging Face, prompt không đưa cấu trúc JSON → gpt-oss-120b đặt Nx, Ny... ở ngoài `"loads"` →
   `_fix_units` âm thầm điền 0 → CLT chạy với **tải = 0** và báo "an toàn". Xảy ra ở **27/28** đề thử (đề còn lại T4: HF trả về nội dung rỗng → crash).
2. Prompt giải thích yêu cầu so sánh σ2 với độ bền ngang nhưng không đưa độ bền vào prompt.
3. gpt-oss là model suy luận: `max_tokens` nhỏ → `content = None`.

Thiết kế mới (v3, "LLM đọc, Python tính và kiểm tra"):
- LLM chỉ CHÉP số + đơn vị như trong đề (JSON schema bị ép cho cả HF lẫn Ollama).
- Python: khai triển xếp lớp (`layup.py`, [0/90]2s → 8 lớp), đổi đơn vị, và đối chiếu với văn bản đề:
  loại sợi theo từ khóa; ký hiệu [..] trong đề thắng; mỗi giá trị SI phải tạo được từ 1 số + 1 đơn vị có
  trong đề; tải viết dạng "Nx = 5 kN/m" được Python đọc trực tiếp; số lớp ghi trong đề phải khớp;
  độ dày lớp × số lớp phải khớp tổng chiều dày. Lỗi nghiêm trọng → hỏi lại LLM 1 lần kèm danh sách lỗi;
  vẫn sai → báo lỗi rõ ràng (không âm thầm tính sai).
- HF: provider Cerebras (~1 s/lần), lỗi → provider auto → Ollama; backend lỗi bị bỏ qua 5 phút.
- Bước giải thích nhận độ bền + tóm tắt tính sẵn (lớp tới hạn, thành phần ứng suất quyết định, hệ số an
  toàn); guardrail dò số lạ trong lời giải thích.

Benchmark trích số liệu (28 đề viết tay, đáp án kiểm tra chéo bằng layup.py; file trong deliverables/benchmark/):

| bộ đề | v1 HF | v1 Ollama | v3 HF (LLM một mình) | v3 Ollama (LLM một mình) |
|---|---|---|---|---|
| dev 10 (dùng để chỉnh prompt) | 0/10 | 4/10 | 10/10 (10/10) | 10/10 (4/10) |
| holdout 6 (lần đầu, mù, code giữa chừng) | 0/6 | 2/6 | 6/6 | 4/6 |
| holdout2 6 (lần đầu, mù, code giữa chừng) | 0/6 | 0/6 | 6/6 | 3/6 |
| holdout3 6 (lần đầu, mù, code cuối) | 0/6 | 1/6 | **6/6 (6/6)** | **5/6 (2/6)** |
| code cuối trên cả 28 đề | 0/28 | 7/28 | **28/28** | **24/28** |

Ollama 4 ca sai với code cuối: 3 ca agent từ chối + báo lỗi (H6, N5, T5), 1 ca sai âm thầm (N4: tải viết
bằng lời "force of 2 N/mm in the x direction" bị đặt vào Nxy).
→ **Mặc định: HF gpt-oss-120b. Dự phòng khi mất mạng: Ollama gemma3:4b** (đã thử: proxy hỏng → tự chuyển).
Thời gian (sau khi sửa localhost → 127.0.0.1): HF ~1-2 s/lần gọi, gemma3:4b ~3-4 s/đề (lần đầu lâu hơn do nạp
model vào GPU). Benchmark Ollama chạy lại sau khi sửa: độ chính xác không đổi (24/28, LLM một mình 10/28).

## Mục tiêu 2 - RAG: XONG (bản Python); pgvector: BỎ QUA
- Docker chưa cài, WSL chưa cài ("Windows Subsystem for Linux is not installed") → Docker Desktop cần cài WSL
  và khởi động lại máy → tạm bỏ qua PostgreSQL + pgvector, giữ bản chạy ổn định.
- rag.py: embedding nomic-embed-text (Ollama, 768 chiều) + cosine + cộng điểm khớp tên vật liệu; câu hỏi
  "cao nhất / thấp nhất" → Python xếp hạng; câu hỏi "tính chất X của vật liệu Y" → Python tra thẳng bảng
  (dòng [F]) và kiểm tra câu trả lời có khớp; guardrail dò số và số hiệu báo cáo NCP-RP không có trong ngữ cảnh;
  danh sách nguồn (báo cáo, trang, trạng thái kiểm chứng) luôn do Python in ra.
- Benchmark RAG: dev 12 câu: HF 12/12, Ollama 11/12 (trước khi sửa: Ollama 6/12 vì chép ví dụ trích dẫn
  trong prompt). Holdout 6 câu (mù): **HF 6/6, Ollama 5/6** (thiếu số hiệu báo cáo trong câu trả lời).
  Tìm đúng vật liệu: 18/18 cả hai.

## Mục tiêu 3 - run_demo.bat: XONG
Phần 0 kiểm tra môi trường → Phần 1 số kiểm chứng → Phần 2 agent 2 đề (đề 1 an toàn FI=0.00238; đề 2 tiếng Việt
quá tải FI=1.096 → FAILS) → Phần 3 RAG 4 câu. Đếm ngược 5-8 s giữa các phần (bấm phím để bỏ qua).
Đã chạy (không tính thời gian dừng): online 17 s; `--offline` 39 s; giả lập mất mạng → tự chuyển Ollama, 18 s.
Log trong logs\ (không commit); bản sao dự phòng: deliverables/demo_log_backup_online.txt, demo_log_backup_offline.txt.

## Mục tiêu 4 - Tài liệu: XONG
- deliverables/CompositeAgent_slides.pptx (bản đầu 15 slide tạo bằng make_slides.py; bản hiện tại 19 slide, xem mục
  "Tài liệu thuyết trình cập nhật" ở trên).
- deliverables/KICH_BAN_THUYET_TRINH.md + .docx (chuẩn bị, kịch bản từng slide, demo từng bước, xử lý sự cố,
  số liệu cần nhớ, bảng thuật ngữ, câu hỏi dự kiến).
## Mục tiêu 5 - Fine-tune: KHÔNG CẦN (HF mặc định đúng 28/28). Ghi vào "bước tiếp theo" cho model offline.

## Nhật ký
- 27/10 17:5x  git init, commit `2b15e21`; demo.py PASS.
- 27/10 18:04  v1 vs v2 trên HF (dev): 0/10 vs 10/10.
- 27/10 18:21  Ollama dev: v1 4/10, v2 4/10 → thêm đối chiếu với văn bản (v3) → 9/10 → thêm hỏi lại → 10/10.
- 27/10 18:30  holdout lần đầu: v3 HF 6/6, Ollama 4/6 → thêm luật số lớp / độ dày.
- 27/10 18:36  holdout2 lần đầu: v3 HF 6/6, Ollama 3/6 → thêm đối chiếu SI + đọc "Nx = ..." bằng regex.
- 27/10 18:43  holdout3 lần đầu (code cuối): HF 6/6, Ollama 5/6.
- 27/10 18:47-18:52  RAG v2 + benchmark; holdout RAG: HF 6/6, Ollama 5/6.
- 27/10 18:54  run_demo online/offline OK; giả lập mất mạng → tự chuyển Ollama OK.
- 27/10 18:58  evaluate_model.py chạy lại: số LOOCV không đổi (E1 R² 0.44, G12 0.302, Xt 0.305; E2 -0.023,
  nu12 -0.406, Xc -0.104, S -0.229; Yt 0.035, Yc 0.128).
- 27/10 19:0x  slide + kịch bản. Soát lại: v1+HF tải = 0 ở 27/28 đề (đề T4: trả lời rỗng → crash), đã sửa chữ "28/28".
- 27/10 19:18  Phát hiện Ollama qua "localhost" chậm ~2,1 s/lần gọi (Windows thử IPv6 trước) → đổi mặc định
  sang 127.0.0.1 (0,05 s). Demo online 23-81 s → 17 s; offline 61 s → 39 s. demo.py PASS.
- 28/10 12:1x  Khởi động lại máy: demo.py PASS, run_demo.bat (có mạng, --offline) OK, MATLAB tính lại 83/83 phương án tối ưu.
- 28/10 sau đó  Slide 19 trang + kịch bản (phần tối ưu); pytest module tối ưu 78/78.
