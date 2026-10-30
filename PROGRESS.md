# PROGRESS - CompositeAgent

Repo: https://github.com/thvien-vo/CompositeAgent_LLM (chuyển sang repo này ngày 28/10/2026; slide và kịch bản
thuyết trình lưu ngoài repo).
Hạn: thuyết trình dời sang **01/11/2026**; hoàn tất trước hết ngày 31/10/2026; nhánh main luôn chạy được.
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

## Việc 3 - thiết kế tấm composite bằng lời (30/10): XONG
Mốc: tag `before-design-agent` (= c799a34). Làm trên nhánh `design-agent` (worktree `D:\CompositeAgent_da`), gộp vào
main sau khi mọi kiểm tra đạt.
- **Bộ đề viết trước khi code** (commit 3a979fd): `python/design_cases.py`, 21 yêu cầu (Anh/Việt; vật liệu có tên và
  theo nhóm; kéo, nén, cắt, tổ hợp; hai mục tiêu; đề thiếu thông tin dùng mặc định; 6 đề phải từ chối; 1 đề không
  khả thi).
- **Phân loại** (`router.py`): quy tắc Python; LLM chỉ xác nhận câu viết yếu ("I need a laminate that can carry ...");
  mơ hồ thì từ chối kèm hướng dẫn. 44/44 đề phân tích cũ, 18/18 câu RAG cũ, 20/20 đề thiết kế (+ DS20 cần LLM: đúng).
- **Đọc yêu cầu** (`design.py`): LLM chép số + đơn vị; Python đọc lại từ văn bản (tải dùng chung `llm.read_loads`:
  kN/m, N/mm, số bằng chữ, tiếng Việt, "nén" -> âm), giá trị LLM chỉ được dùng khi có trong văn bản và hợp lý; mặc định
  in rõ (hệ số an toàn 1,5; tấm 0,5 × 0,5 m; lớp 0,125 mm; góc 0/±45/90; 4 luật; 8-64 lớp). Từ chối: mô-men, mục
  tiêu khác, góc khác, không có vật liệu, tải không rõ hướng, tấm không đối xứng / không cân bằng, vừa cho xếp lớp vừa
  đòi thiết kế. Vật liệu ML: cảnh báo "kết quả chỉ mang tính tham khảo".
- **Tối ưu** (`optimization.api.design_search`): tìm kiếm chính xác (giới hạn 30 s) -> "tối ưu đã chứng minh"; không
  xong thì GA + tìm kiếm cục bộ seed 0 -> "tốt nhất tìm được" + cận dưới số lớp (nếu cận = số lớp tìm được thì số lớp
  đã chứng minh). Lưu ý: việc tìm kiếm chính xác xong trong 30 s hay không (và cận dưới) có thể phụ thuộc tải máy; phương
  án GA thì không.
- **Kiểm tra lại**: MATLAB `clt_engine.m` (độ bền, cả hai chiều cắt), Ritz đa thức độc lập (chênh in ra, cảnh báo nếu
  > 2 %), hệ số dự trữ từng tiêu chuẩn, so với tấm tựa đẳng hướng nhỏ nhất cùng ràng buộc (kể cả số lớp tối thiểu).
- **Giải thích**: dữ kiện có tên/đơn vị/ý nghĩa; bộ kiểm tra ý nghĩa mở rộng (số lớp, hệ số dự trữ, hệ số tải mất ổn
  định, %); kiểm tra thêm: khả thi hay không, "đã chứng minh" hay không, tiêu chuẩn quyết định, chiều lực cắt, chiều
  so sánh với tựa đẳng hướng, biên của phương án bị gán cho tấm tựa đẳng hướng. `test_design_checks.py`: ALL PASS.
- **Lực cắt đổi chiều**: tùy chọn `shear_both_signs` trong module tối ưu (mặc định tắt; agent bật khi có Nxy trừ khi đề
  nói một chiều). pytest 102/102 (+11). Kết quả Lớp 1 và Le Riche & Haftka KHÔNG đổi khi tắt (chạy lại toàn bộ 960 lần
  chạy + tìm kiếm chính xác + Le Riche & Haftka, so với file đã công bố bỏ qua cột thời gian: 0 khác biệt;
  `logs\da_rerun_compare.txt`). Bảng một / hai chiều (BAO_CAO_LOP1 mục 4.8): cắt thuần 42 -> 46 lớp (0,125 mm), 28 -> 32
  lớp (0,18288 mm), số lớp chứng minh được; nén + cắt cùng số lớp, biên 1,751 -> 1,688; kéo + cắt, tải rất lớn không
  đổi; MATLAB 8/8.
- **Bộ đề thiết kế** (`benchmark_design.py`, kết quả trong `deliverables/benchmark/design_benchmark_*`):

  | | gemma3 (lần cuối) | HF gpt-oss-120b |
  |---|---|---|
  | phân loại đúng (đề thiết kế) | 15/15 | 15/15 |
  | đọc đề đúng | 15/15 | 15/15 |
  | kết quả = gọi trực tiếp optimize(...) | 15/15 | 15/15 |
  | MATLAB kiểm tra lại | 15/15 | 15/15 |
  | từ chối đúng | 6/6 | 6/6 |
  | hoàn toàn đúng | **21/21** | **21/21** |
  | giải thích LLM / hỏi lại / dựng sẵn | 13 / 1 / 1 (2 lỗi thật bị bắt) | 11 / 0 / 4 (báo nhầm -> đã sửa) |

  gemma3 lần 1: 20/21 (DS11 đọc sai "at most 24 plies" -> sửa thuật toán). Các lỗi ý nghĩa tìm được khi đọc tay lời giải
  thích đều đã thành luật kiểm tra + test (so sánh ngược chiều, "shear not checked", biên gán cho tựa đẳng hướng...).
- **Không giảm**: 44 đề gemma3 28/28 + 16/16; RAG gemma3 12/12 + 6/6.
- **Demo**: `run_demo.bat` phần 4 "Design" (2 yêu cầu, đều tối ưu đã chứng minh): (1) IM7/8552, Nxy = 40 kN/m, hai chiều
  -> [-45/45_2/-45/45/-45_2/45/90/0_2/90]s, 24 lớp, biên 1,699 (mất ổn định), tựa đẳng hướng 32 lớp (-25 %);
  (2) carbon/epoxy (ML), Nx = -20 kN/m -> 26 lớp, biên 1,658, tựa đẳng hướng 32 lớp (-18,8 %). Thời gian phần 4:
  7,9 s có mạng, 17,7 s offline (giới hạn 2 / 4 phút). `--interactive`: mục 3 = yêu cầu thiết kế, a = tự phân loại.
- **Gộp vào main** (commit 722086e) sau khi mọi kiểm tra trên nhánh đạt; kiểm tra lại trên main: pytest 102/102,
  demo.py PASS (0,002381 / lớp 4), test_checks / test_explain_checks / test_design_checks ALL PASS, không
  SyntaxWarning, `run_demo.bat --offline` OK (65 s, phần 4: 17,1 s) và có mạng OK (28 s, phần 4: 8,9 s). Log dự phòng
  cập nhật: `deliverables/demo_log_backup_online.txt`, `demo_log_backup_offline.txt`.
- **Hugging Face trong đợt này: 72 lần gọi** (giới hạn 100; dòng 147-218 của `logs\hf_calls.log`): 40 bộ đề thiết kế,
  16 demo có mạng trên nhánh, 16 demo có mạng trên main.
- Slide và kịch bản (ngoài repo, 30/10): slide 21 trang - thêm slide 17 (thiết kế bằng lời: 4 bước) và 18 (kiểm
  chứng + bảng lực cắt một / hai chiều), slide 10 có ô "Part 4", cập nhật hạn chế / bước tiếp theo / lệnh; kịch bản .md và
  .docx: lời nói slide 17-18, demo phần 4 từng bước, câu hỏi dự kiến (lực cắt đổi chiều, vật liệu ML, LLM tự chọn xếp
  lớp, yêu cầu không rõ), thuật ngữ. Bố cục kiểm tra bằng ảnh xuất từ PowerPoint. Bản sao lưu trước khi sửa:
  `D:\CompositeAgent_slide_backups\before_design_20261030\`.

## Đợt "mất ổn định do cắt + sửa demo" (28/10 chiều - 30/10): XONG
Mốc trước khi làm: tag `before-shear-buckling`. Việc 1 làm trên nhánh `shear-buckling` (worktree `D:\CompositeAgent_sb`),
gộp vào main (commit 62885cb) sau khi mọi kiểm chứng đạt; Việc 2 làm trực tiếp trên main.

**Việc 1 - mất ổn định do cắt trong tối ưu** (chỉ sửa / thêm trong `python/optimization/`, `deliverables/optimization/`):
- Mô hình `buckling.RitzModel`: Rayleigh-Ritz chuỗi sin kép có D16, D26, Nx, Ny, Nxy; trị riêng tổng quát, hệ số tải tới
  hạn = trị riêng dương nhỏ nhất, kéo làm tăng ổn định, không có trị riêng dương -> RF = inf; dùng đúng dấu Nxy đề cho.
  Áp dụng khi có nén hoặc cắt; ràng buộc RF >= 1.5. Tích phân tính sẵn, trị riêng theo lô, cache theo D, chỉ tính cho
  phương án đã đạt độ bền (GA, vét cạn). Báo cáo ghi rõ: chuỗi sin không thỏa điều kiện mô-men khi D16, D26 != 0 ->
  cận trên, hội tụ chậm.
- Kiểm chứng trước khi dùng (`verify_buckling.py`, `tests/test_buckling_full.py`): nén thuần trực hướng trùng công thức
  đóng (<= 6.2e-16); k_s tấm vuông 9.328 so với 9.34 (0.13 %, Stein & Neff 1947; Timoshenko & Gere 1961); tấm dài
  a/b = 10: 5.389 (0.73 %), a/b = 20: 5.351 (0.02 %) so với 5.35 (Southwell & Skan 1924); so với lời giải Ritz đa thức
  độc lập <= 0.62 %; Nemeth 1992 (NASA TP-3195, chỉ có đồ thị + số "khoảng" trong lời văn): -50 % / +44 %, ±7.8 %, ±3.9 %
  so với "khoảng 48 %, 7 %, 3.5 %", cùng chiều. Hội tụ: mọi ca 8 x 8 số hạng (tăng lên 10 x 10 đổi <= 0.49 %).
- Tìm kiếm chính xác mới (nhánh-cận, cận Rayleigh chứng minh được), <= 10 s mỗi bài: chứng minh tối ưu 15/16 bài; cắt thuần
  lớp 0.125 mm chỉ chứng minh n* = 42 (biên là tốt nhất đã biết) - phạm vi bị thu hẹp (bộ số lượng > 3 triệu cách xếp
  không liệt kê), đã ghi rõ trong báo cáo.
- Thuật toán so với tối ưu đã chứng minh (15 bài x 20 seed): **GA + tìm kiếm cục bộ 300/300**, GA 294/300, **NSGA-II
  213/300** (kém ở các ca có D16, D26; vẫn đúng số lớp 298/300, biên thấp hơn <= 2.5 %). Cắt thuần 0.125 mm: GA+LS 9/20
  tới phương án tốt nhất đã biết, 20/20 ở 42 lớp. Một lần chạy 2-20 s; cả 960 lần chạy + tìm kiếm chính xác 29.5 phút
  (3 tiến trình).
- % giảm khối lượng so với tựa đẳng hướng (cùng mô hình mất ổn định), trước -> sau (* = bản trước chưa xét cắt, không hợp lệ):

  | ca | lớp 0.125 mm | lớp 0.18288 mm |
  |---|---|---|
  | C1 kéo một phương | -50 % -> -50 % (24/48) | -50 % -> -50 % (16/32) |
  | C2 kéo hai phương | -37.5 % -> -37.5 % (20/32) | -41.7 % -> -41.7 % (14/24) |
  | C3 nén một phương | -16.7 % -> -16.7 % (20/24) | -12.5 % -> -12.5 % (14/16) |
  | C4 nén hai phương | -8.3 % -> -8.3 % (22/24) | -33.3 % -> -33.3 % (16/24) |
  | C5 cắt thuần | -25 %* (12/16) -> **-25 % (42/56)** | -25 %* (12/16) -> **-30 % (28/40)** |
  | C6 kéo + cắt | -25 %* -> -25 % (24/32) | -33.3 %* -> -33.3 % (16/24) |
  | C7 nén + cắt | -16.7 %* -> -16.7 % (20/24) | -12.5 %* -> -12.5 % (14/16) |
  | C8 tải rất lớn | không khả thi -> **không khả thi <= 64 lớp** (tựa đẳng hướng 104) | -11.1 %* -> -11.1 % (64/72) |

  Phương án cắt thuần 12 lớp cũ chỉ chịu 2.6 % tải (0.125 mm). Cảnh báo: tối ưu dùng chiều Nxy đề cho; Nxy đổi chiều
  -> biên cắt thuần 1.59 -> 0.56 (0.125 mm), 1.52 -> 0.51 (0.18288 mm); nén + cắt 1.75 -> 1.49.
- Le Riche & Haftka giữ giả định gốc (công thức đóng, bỏ qua D16/D26): chạy lại, mọi giá trị trùng bản trước (3973.01,
  9998.19, 13518.66; bài 1995 n* = 48). MATLAB tính lại 51/51 phương án tối ưu mới đạt (ABD <= 1.7e-15, ứng suất
  <= 3.1e-15). pytest 91/91 (78 cũ + 13 mới). Bảng / hình cũ giữ trong `results/before_ritz/`, `figures/before_ritz/`.

**Việc 2 - lỗi nhỏ của demo** (trên main):
- `run_demo.py`: docstring raw, hết `SyntaxWarning: invalid escape sequence '\l'`.
- Lời giải thích CLT: LLM nhận từng đại lượng kèm tên, đơn vị, ý nghĩa; `llm.check_meaning` kiểm tra mỗi con số được
  gọi đúng loại đại lượng (Anh + Việt; ABD(1,1) là độ cứng, không đi với load/capacity/tải/sức chịu), kết luận an toàn
  và so sánh với 1 khớp chỉ số phá hủy; sai -> hỏi lại 1 lần -> bản dựng sẵn bằng Python (có ghi chú).
  30/10: sửa thêm 1 báo nhầm ("the reciprocal of the failure index ... is below 1" bị coi là nói về chỉ số phá hủy);
  bản cũ còn bỏ sót 2 câu sai cùng kiểu. `test_explain_checks.py` 73/73.
- RAG: `rag.check_citations` - mỗi số hiệu báo cáo phải là nguồn của vật liệu trong cùng câu / mệnh đề; sai -> hỏi lại
  1 lần -> câu trả lời dựng sẵn từ dữ liệu.
- Kết quả gemma3: 44 đề **28/28 + 16/16** (không đổi); RAG **12/12 + 6/6** (trước 11/12 + 5/6). Giải thích gemma3
  (30/10): 42 đề tiếng Anh 39 đạt ngay + 3 dựng sẵn (cả 3 là lỗi thật: gọi hệ số an toàn là "a load of 480.6", ghi
  "unsafe"); 8 đề tiếng Việt 4 + 2 hỏi lại + 2 dựng sẵn (lỗi thật: chỉ số 0.01273 "lớn hơn 1"; gọi chỉ số phá hủy là
  "hệ số suy giảm"). Không còn câu gán sai ý nghĩa hay trích sai nguồn được in ra.
- `run_demo.bat --offline`: 6 lần ngày 28/10 + 2 lần ngày 30/10, đều OK (lần đầu sau khi khởi động máy chậm: nạp gemma3
  46 s); có mạng: 3 lần, OK.

**Hugging Face trong đợt này: 39 lần gọi** (giới hạn 100; dòng 108-146 của `logs\hf_calls.log`): 24 lần ngày 28/10
(2 lần run_demo có mạng, 12 lần mỗi lần), 3 lần ngày 30/10 thử lời giải thích đề 2, 12 lần demo có mạng cuối cùng.

## Tài liệu thuyết trình (cập nhật 30/10): XONG - lưu ngoài repo
- Slide (19 trang, song ngữ, phần tối ưu Lớp 1 ở slide 13-16) và kịch bản thuyết trình (.md và .docx khớp nhau) được
  giữ trên máy người trình bày, không đưa vào repo (`.gitignore` chặn *.pptx, KICH_BAN_THUYET_TRINH.*, *.pdf).
- 30/10: ngày 01/11/2026; slide 13-16 có mất ổn định do cắt (Ritz, D16, D26), kiểm chứng k_s, % giảm khối lượng cho cả
  8 ca (hai độ dày lớp), cảnh báo chiều lực cắt; slide 17-18 cập nhật hạn chế / bước tiếp theo. Bố cục kiểm tra bằng
  ảnh xuất từ PowerPoint.

## Lớp 1 - Tối ưu thứ tự xếp lớp (28/10): XONG
Mốc trước khi làm: tag `before-optimization`. Chỉ THÊM file trong `python/optimization/` và
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
- (Bản 28/10 sáng, công thức đóng - đã được thay bằng mục "Đợt mất ổn định do cắt" ở trên.) Giảm khối lượng so với
  tựa đẳng hướng (lớp 0.125 mm, ca không có lực cắt): -50 % kéo một phương, -37.5 % kéo hai phương, -16.7 % nén một
  phương, -8.3 % nén hai phương; tải rất lớn: không khả thi <= 64 lớp. Ca có lực cắt: bản này chưa có mất ổn định do cắt.
- Hạn chế của bản 28/10 sáng (nay đã xử lý): công thức đóng không có mất ổn định do cắt, bỏ qua D16/D26. Còn lại: bài
  LC3 1995 "đánh lừa GA" chỉ 3/20.
- Sửa trong lúc làm: NSGA-II của pymoo làm mất tối ưu khi nhiều thiết kế cùng (số lớp, biên) -> khoảng cách chen chúc
  tính trên vector mục tiêu khác nhau (test hồi quy); GA thêm tìm kiếm cục bộ + bước bớt lớp (LC2 1995: 6/20 -> 20/20).
- Sự cố máy (28/10 ~02:10-02:18, ĐÃ XỬ LÝ): sau một lần chạy song song 16 tiến trình bị lỗi cấp phát bộ nhớ OpenBLAS,
  dịch vụ WMI của Windows treo (`tasklist`, `platform.platform()` của Python, `import matlab.engine` đều treo). Sau khi
  khởi động lại máy đã kiểm tra: `demo.py` PASS (0.00238 / 4); `run_demo.bat` có mạng và `--offline` chạy đúng;
  `matlab_recheck` 83/83 đạt; pytest 78/78. Module tối ưu tự tránh WMI (`optimization/__init__.py`, `run_tests.py`).

## Việc 1 + 2 (27/10 tối): XONG - chi tiết trong deliverables/benchmark/KET_QUA_VIEC_1_2.md
Mốc trước khi sửa: tag `before-task12`. Demo gốc: online 25 s, offline 39 s, demo.py PASS (log trong
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
- Slide song ngữ có ghi chú người nói và kịch bản thuyết trình (chuẩn bị, kịch bản từng slide, demo từng bước, xử lý
  sự cố, số liệu cần nhớ, bảng thuật ngữ, câu hỏi dự kiến): lưu ngoài repo (xem mục "Tài liệu thuyết trình" ở trên).
## Mục tiêu 5 - Fine-tune: KHÔNG CẦN (HF mặc định đúng 28/28). Ghi vào "bước tiếp theo" cho model offline.

## Nhật ký
- 27/10 17:5x  git init, commit đầu tiên; demo.py PASS.
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
- 28/10 13:3x  Chuyển sang repo CompositeAgent_LLM: lịch sử không còn slide / kịch bản thuyết trình; demo.py PASS,
  pytest 78/78 trước khi push.
- 28/10 15:08  Tag `before-shear-buckling`. Việc 2 (SyntaxWarning, kiểm tra ý nghĩa, kiểm tra trích dẫn) trên main;
  nhánh `shear-buckling` cho Việc 1.
- 28/10 15:58  Kiểm chứng mô hình Ritz có D16, D26: tất cả đạt (k_s 9.328, tấm dài 5.351, Nemeth 1992 cùng xu hướng).
- 28/10 16:09  Commit Việc 2 trên main (44 đề gemma3 28/28 + 16/16, RAG 12/12 + 6/6).
- 28/10 16:00-16:30  Chạy lại thí nghiệm Lớp 1 (3 tiến trình, 29.5 phút), MATLAB 51/51, Le Riche & Haftka chạy lại trùng.
- 28/10 16:39  pytest 91/91 trên nhánh -> gộp `shear-buckling` vào main; trên main: pytest 91/91, demo.py PASS,
  run_demo --offline và có mạng OK.
- 28/10 16:42  Dừng giữa chừng (hết quota) khi đang sửa slide 13-18.
- 30/10 09:0x  Máy đã khởi động lại (29/10 17:57); không có tiến trình Python sót. Sửa 1 báo nhầm của bộ kiểm tra so
  sánh với 1; đánh giá lại gemma3 (42 + 8 đề) không giảm; test_explain_checks 73/73.
- 30/10 09:1x-09:3x  Slide 13-18 và kịch bản (.md / .docx) cập nhật theo kết quả mới, ngày thuyết trình 01/11.
- 30/10 09:3x  Kiểm tra cuối trên main: pytest 91/91, demo.py PASS (0.002381 / 4), test_checks ALL PASS, không còn
  SyntaxWarning, run_demo.bat --offline OK (47 s) và có mạng OK (20 s, cả 3 lời giải thích của HF qua kiểm tra);
  HF đợt này 39 lần.
