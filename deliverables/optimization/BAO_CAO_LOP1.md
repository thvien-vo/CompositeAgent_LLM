# BÁO CÁO LỚP 1 — TỐI ƯU HÓA THỨ TỰ XẾP LỚP VẬT LIỆU COMPOSITE

*Module `python/optimization` của dự án CompositeAgent — Lớp 1 (nền tảng, không dùng LLM). Ngày 28/10/2026.*

> **Đọc nhanh:** xem mục 0 (tóm tắt) và mục 9 (trang tóm tắt tiếng Anh cho GS. Nishikawa).
> Mọi con số trong báo cáo được sinh tự động từ các tệp kết quả trong `deliverables/optimization/results/`
> (bảng `results/tables.md` do `make_tables.py` tạo) — không có số nào gõ tay.

<!-- RESULTS_SUMMARY -->

---

## 1. Bài toán

### 1.1 Composite nhiều lớp là gì, vì sao thứ tự xếp lớp quan trọng
Một **tấm composite nhiều lớp (laminate)** được ghép từ nhiều **lớp (ply)** mỏng; mỗi lớp là sợi carbon song song
trong nhựa epoxy, rất cứng và bền theo phương sợi (phương 1), yếu theo phương ngang (phương 2). Người thiết kế chọn
**góc sợi** của từng lớp (ở đây chỉ 0°, +45°, −45°, 90° như thông lệ ngành hàng không) và **thứ tự xếp lớp**
(stacking sequence), ví dụ `[0/45/−45/90]s` (chữ `s` = đối xứng qua mặt giữa: nửa còn lại là ảnh gương).

* **Số lớp** quyết định khối lượng (cùng vật liệu, cùng độ dày lớp → khối lượng tỉ lệ số lớp).
* **Số lượng lớp mỗi góc** quyết định độ cứng màng **A** (kéo – nén – cắt trong mặt phẳng) → quyết định độ bền.
* **Thứ tự** quyết định độ cứng uốn **D** (lớp càng xa mặt giữa càng góp nhiều) → quyết định **mất ổn định
  (buckling)** khi tấm chịu nén hoặc cắt.

### 1.2 Mục tiêu của Lớp 1
Tìm thứ tự xếp lớp **có ít lớp nhất** (nhẹ nhất) sao cho **biên an toàn ≥ hệ số an toàn** (mặc định 1.5) và
thỏa mọi **luật thiết kế**; nếu nhiều phương án cùng số lớp thì chọn phương án có biên an toàn lớn nhất. Ngoài ra
xây dựng **đường Pareto** (đánh đổi giữa số lớp và biên an toàn) và tái tạo bài kiểm tra kinh điển của
Le Riche & Haftka.

---

## 2. Giả định và quy ước

| Hạng mục | Lựa chọn trong Lớp 1 |
|---|---|
| Tải | Lực màng trong mặt phẳng Nx, Ny, Nxy (N/m); **kéo dương, nén âm**. **Không xét mô-men** (Mx = My = Mxy = 0; hàm `optimize` từ chối nếu có mô-men). |
| Nhiệt, ẩm | Bỏ qua ứng suất nhiệt và độ ẩm. |
| Tiêu chí phá hủy | **Lớp gãy đầu tiên** (first-ply failure): tấm coi như hỏng khi lớp đầu tiên đạt tiêu chuẩn bền. |
| Đơn vị | SI trong mọi tính toán (Pa, m, N/m). Riêng bài Le Riche & Haftka đổi từ psi, in, lb/in bằng hệ số chính xác. |
| Độ dày lớp | Tham số; mặc định **0.125 mm** (nhất quán với demo). Bộ thứ hai: **0.18288 mm = 0.0072 in**, độ dày lớp danh định của Hexcel 8552/IM7 (190 g/m²) theo NCAMP NCP-RP-2009-028 Rev B — giá trị lấy từ cột `Vf_note` của dòng IM7/8552 trong `composite_lamina_dataset_v4.csv` (“FAW 190 gsm / (rho_f 1.78 g/cc x tply 0.0072 in)”). |
| Tấm | Chữ nhật a × b, **tựa đơn bốn cạnh**; mặc định a = b = 0.5 m. |
| Vật liệu | Mặc định **IM7/8552**, số đo thật NCAMP (E1 = 162.1 GPa, E2 = 8.96 GPa, G12 = 4.69 GPa, ν12 = 0.316, Xt = 2212, Xc = 1731, Yt = 64.1, Yc = 286, S = 91.1 MPa), lấy qua cơ chế sẵn có `materials.py`. |
| Thước đo chung | **Hệ số dự trữ RF** (reserve factor) = số lần có thể nhân **toàn bộ** tải lên trước khi đạt tới hạn. **Biên an toàn** của phương án = min RF qua mọi lớp và mọi tiêu chuẩn. Ràng buộc: biên an toàn ≥ hệ số an toàn (mặc định 1.5, đổi được). |
| Tsai-Wu | F12 = F12\*·√(F11·F22) với **F12\* = −0.5** (giá trị khuyến nghị thường được trích từ Tsai & Hahn 1980); tham số đổi được. |
| Mất ổn định | Chỉ xét khi có nén (Nx < 0 hoặc Ny < 0); công thức đóng cho tấm **trực hướng đặc biệt**, **bỏ qua D16, D26**; tỉ số \|D16\|/D11, \|D26\|/D22 được in cho mọi phương án tối ưu. **Nxy không có trong công thức đóng** (không tự chế công thức mất ổn định do cắt). Phần bổ sung dùng phương pháp Ritz có nguồn (mục 3.3). |
| Góc lớp | {0, +45, −45, 90}. Hai cách mã hóa: theo **từng lớp** (mặc định, mịn nhất: số lớp bước 2) và theo **cặp lớp** 0₂ / ±45 / 90₂ như Le Riche & Haftka (số lớp bước 4). |
| Luật thiết kế (bật/tắt từng luật) | **Đối xứng**; **cân bằng** (#+45 = #−45); **mỗi họ hướng 0, ±45, 90 ≥ 10 % số lớp** (±45 tính chung một họ); **không quá 4 lớp cùng góc liền nhau**, tính trên cả tấm (kể cả hai lớp kề mặt giữa khi đối xứng). Số lớp 8–64. |

---

## 3. Phương pháp

### 3.1 Bộ tính CLT bằng Python (`clt.py`, `evaluate.py`)
**Lý thuyết tấm nhiều lớp cổ điển (CLT)**: từ E1, E2, G12, ν12 tính ma trận độ cứng lớp **Q**, xoay theo góc lớp
thành **Q̄**, cộng theo chiều dày được ma trận **ABD** (A: màng, B: ghép màng–uốn, D: uốn). Giải
[N; M] = ABD·[ε⁰; κ] được biến dạng mặt giữa ε⁰ và độ cong κ, rồi biến dạng/ứng suất từng lớp theo trục vật liệu.
**Cùng quy ước với `matlab/clt_engine.m`**: lớp 1 ở đáy (z = −h/2), cùng công thức Q̄ (m⁴, m²n²…), biến dạng kỹ
thuật, ứng suất lấy ở **giữa chiều dày lớp**, cùng chỉ số Max Stress. Hàm `cosd/sind` tái tạo cách rút gọn góc của
MATLAB nên 90° cho đúng 0.

**Vector hóa**: với tấm đối xứng chỉ chịu lực màng, B = 0 và biến dạng đều theo chiều dày (ε⁰ = A⁻¹N); A chỉ phụ
thuộc **số lớp mỗi góc**, nên ứng suất mỗi lớp chỉ phụ thuộc góc của nó; D = Σ Q̄(góc)·trọng số vị trí. Nhờ vậy
đánh giá được hàng triệu phương án/giây theo lô. Đường tính tổng quát (A, B, D, độ cong) dùng cho tấm không đối xứng
và để đối chiếu với MATLAB; hai đường khớp nhau tới 3·10⁻¹⁵ (test `test_fast_symmetric_path_equals_general_path`).

### 3.2 Tiêu chuẩn bền và hệ số dự trữ (`failure.py`)
* **Max Stress**: chỉ số FI = max(σ1/Xt hoặc −σ1/Xc, σ2/Yt hoặc −σ2/Yc, |τ12|/S) — đúng như MATLAB.
  Ứng suất tỉ lệ tuyến tính với tải nên **RF = 1/FI**.
* **Tsai-Wu**: F1σ1 + F2σ2 + F11σ1² + F22σ2² + F66τ12² + 2F12σ1σ2 = 1. Nhân tải với RF thì ứng suất nhân RF:
  a·RF² + b·RF − 1 = 0 (a: phần bậc hai, b: phần bậc nhất). Với |F12\*| < 1 phần bậc hai xác định dương nên có
  đúng một nghiệm dương; dùng công thức nghiệm ổn định số (không trừ hai số gần bằng nhau).
* **Max Strain** (chỉ cho bài Le Riche & Haftka): RF = min(ε1u/|ε1|, ε2u/|ε2|, γ12u/|γ12|).
* **Thiếu giới hạn bền**: nếu vật liệu thiếu giá trị nào (ô trống trong CSV, hoặc người dùng không cho), giá trị đó
  được thay bằng **dự đoán ML theo nhóm** của cơ chế sẵn có và **in cảnh báo** ghi rõ tên đại lượng
  (`material.py`, test `test_missing_strength_filled_by_ml_with_warning`).

### 3.3 Mất ổn định (`buckling.py`)
**Công thức đóng** (tấm trực hướng đặc biệt tựa đơn, nén hai phương; Whitney 1987; đúng phương trình (3.1) của
Le Riche 1994):

λ(m, n) = π²·[D11(m/a)⁴ + 2(D12 + 2D66)(m/a)²(n/b)² + D22(n/b)⁴] / [(m/a)²·(−Nx) + (n/b)²·(−Ny)],

chỉ các mode có mẫu dương mới mất ổn định được; **λ_cr = min theo (m, n)** = hệ số tải tới hạn = RF_buckling.
**Dò mode có chứng minh đủ**: đặt μ = (m/a)², ν = (n/b)²; vì D12 + 2D66 ≥ 0 nên tử ≥ min(D11, D22)·(μ+ν)²/2 và mẫu
≤ Nmax·(μ+ν), do đó λ(m,n) ≥ π²·min(D11,D22)·(μ+ν)/(2Nmax). Sau khi có ước lượng λ0 từ các mode nhỏ, mọi mode có
μ+ν > 2·Nmax·λ0/(π²·Dmin) chắc chắn kém hơn λ0, nên chỉ cần dò m ≤ a√R, n ≤ b√R. Test so với dò thô 60×60 mode trên
200 trường hợp ngẫu nhiên (kể cả kéo ngang): khớp tới 10⁻¹².

**Bổ sung có nguồn — Ritz có lực cắt Nxy**: chuỗi sin kép w = ΣΣ A_mn sin(mπx/a) sin(nπy/b) (phương pháp năng lượng
kinh điển cho mất ổn định do cắt của tấm tựa đơn: Timoshenko & Gere 1961 §9.7; Stein & Neff 1947; Whitney 1987 cho
tấm trực hướng), vẫn bỏ qua D16, D26. Kiểm chứng: (i) khi Nxy = 0 trùng công thức đóng tới 10⁻¹²; (ii) tấm vuông
đẳng hướng chịu cắt thuần hội tụ đơn điệu từ trên xuống k_s = 9.3245 (24×24 số hạng), sát giá trị 9.34 trong
Timoshenko & Gere (chênh 0.17 %, đúng chiều vì nghiệm Ritz là cận trên và giá trị sách tính với ít số hạng hơn);
(iii) a/b = 2 cho 6.546. Trong tối ưu dùng 10×10 số hạng (sai lệch ≤ 1.2·10⁻⁵ so với 20×20), kiểm tra cuối dùng
20×20. **Ritz chỉ là phần bổ sung**: kết quả chính theo đúng đặc tả (công thức đóng, Nxy không gây mất ổn định).

### 3.4 Biến thiết kế, luật thiết kế và cơ chế sửa (`rules.py`)
Một phương án là một **chuỗi ký hiệu** = nửa tấm từ mặt ngoài vào mặt giữa (khi đối xứng). Ký hiệu “rỗng” cho phép
số lớp thay đổi; chuỗi được **chuẩn hóa** (dồn về phía mặt giữa) nên mỗi tấm có đúng một chuỗi. `check_rules()` là
phép kiểm tra gốc trên tấm đầy đủ. **Cơ chế sửa (repair)** biến chuỗi bất kỳ thành chuỗi hợp lệ: chỉnh số lớp →
cân bằng ±45 → tối thiểu 10 % mỗi họ (lấy từ họ dư nhiều nhất) → bảo đảm số lượng xếp được trong giới hạn 4 lớp liền
→ đổi chỗ các lớp vi phạm; nếu không được thì dựng lại tham lam từ mặt giữa ra. Kiểm thử ngẫu nhiên: 1 500 chuỗi ×
20 tổ hợp luật/mã hóa, **không lần nào** trả về phương án vi phạm.

### 3.5 Vét cạn và cận chứng minh được (`exhaustive.py`)
* **Vét cạn theo “họ góc”**: với luật đối xứng + cân bằng, biên an toàn chỉ phụ thuộc số lớp mỗi góc (độ bền) và
  D11, D12, D22, D66 (mất ổn định) — các đại lượng này **như nhau cho +45 và −45**. Vì vậy chỉ cần liệt kê chuỗi họ
  {0, ±45, 90} (3^L thay vì 4^L); mỗi chuỗi có số lớp ±45 chẵn được đổi thành lớp thật bằng cách xen kẽ +45/−45 —
  luôn cân bằng và không tạo dãy cùng góc. Test so với liệt kê đầy đủ 4^L (bộ kiểm tra luật gốc) trên 3 tải: trùng
  tới 10⁻¹². Tốc độ ≈ 0.4–0.8 triệu phương án/giây; giới hạn 10 phút/bài (tự ước lượng và dừng, ghi “unknown”).
* **Vét cạn theo số lượng** (khi không có mất ổn định): biên an toàn chỉ phụ thuộc bộ số lượng (n0, n+45, n−45,
  n90). Liệt kê mọi bộ số lượng + **quy hoạch động chính xác** kiểm tra có xếp được trong giới hạn 4 lớp liền →
  **tối ưu chính xác cho mọi số lớp tới 64** trong < 1 s.
* **Cận dưới chứng minh được của số lớp**: với mỗi bộ số lượng, độ bền tính chính xác, còn mất ổn định bị chặn trên
  bằng D “lạc quan” (mỗi thành phần D11, D22, D12+2D66 được cực đại riêng bằng cách đặt lớp có giá trị lớn nhất ra
  ngoài — bất đẳng thức sắp xếp lại); λ tăng theo các thành phần này nên λ(D) ≤ λ(D lạc quan). Nếu mọi bộ số lượng
  của một số lớp có cận < hệ số an toàn thì số lớp đó **chắc chắn không khả thi**. Cận này được nâng thêm qua các
  số lớp mà vét cạn đã chứng minh không khả thi (“cận dưới hiệu lực”).

### 3.6 Thuật toán di truyền và NSGA-II (`ga.py`, `nsga2.py`)
* **GA đơn mục tiêu**: quần thể 30, chọn lọc giải đấu nhị phân theo **thứ tự từ điển** (khả thi trước; khả thi thì
  ít lớp hơn rồi biên lớn hơn; không khả thi thì vi phạm nhỏ hơn — quy tắc Deb 2000), giữ 2 phương án tốt nhất
  (elitism), lai ghép hai điểm (xác suất 1) trên chuỗi canh theo mặt giữa, đột biến từng lớp (1/L), thêm/bớt lớp
  (0.10/0.10), **hoán vị hai lớp** (0.7, toán tử “stack swap” của Le Riche & Haftka), sửa sau mỗi phép biến đổi.
* **GA + tìm kiếm cục bộ (memetic)**: mỗi khi phương án tốt nhất được cải thiện, leo đồi dốc nhất trên mọi hoán vị
  hai lớp khác góc, mọi đổi góc một lớp và (bài ít lớp nhất) mọi bỏ một lớp; tính trong cùng ngân sách. **Biến thể
  này được thêm sau khi GA cơ bản trượt tối ưu ở các bài “đánh lừa GA” của Le Riche & Haftka 1995** (mục 4.6); cả
  hai biến thể được báo cáo trên mọi bài.
* **NSGA-II** (pymoo 0.6.2, Deb et al. 2002): hai mục tiêu (số lớp ↓, −biên an toàn ↓); dùng **cùng** khởi tạo, lai
  ghép, đột biến và **repair** như GA (mọi phương án luôn thỏa luật), loại trùng lặp trên chuỗi chuẩn hóa; quần thể
  40. Đáp án “ít lớp nhất” lấy từ quần thể cuối: phương án khả thi ít lớp nhất, hòa thì biên lớn nhất.
* **Ngân sách** = số **phương án khác nhau** được phân tích (phương án lặp lại lấy từ bộ nhớ đệm), 10 000 cho mỗi
  lần chạy; dừng sớm nếu 100 thế hệ liền không có phương án mới. **20 seed cố định** (0–19) cho mỗi bài × mỗi thuật
  toán (10 seed cho phần bổ sung Ritz). **Thành công** = phương án cuối có **đúng số lớp tối ưu và biên an toàn bằng
  tối ưu toàn cục** (sai số tương đối 10⁻⁹) trong ngân sách; ghi số lần đánh giá lúc lần đầu đạt và thời gian chạy.
* Tham số GA/NSGA-II chọn trước, **không** tinh chỉnh trên 8 ca tải kiểm tra.

### 3.7 Kiểm chứng
1. **Python ↔ MATLAB** trên ≥ 50 tấm ngẫu nhiên (`verify_matlab.py`): ABD, ứng suất từng lớp, chỉ số Max Stress;
   sai số tương đối ≤ 10⁻⁹ (định nghĩa sai số ở đầu `matlab_check.py`; B chuẩn hóa theo A·h vì B = 0 với tấm đối xứng).
2. **GA, GA+LS, NSGA-II ↔ vét cạn** trên 8 ca tải × 2 độ dày lớp.
3. **Le Riche & Haftka** (chế độ riêng, tối đa tải phá hủy với số lớp cố định).
4. **Mọi phương án tối ưu cuối** được tính lại bằng `clt_engine.m` (`matlab_recheck.py`).
5. **pytest** cho bộ tính CLT, từng tiêu chuẩn, mất ổn định, từng luật, repair, từng thuật toán, vật liệu, MATLAB.

<!-- RESULTS_BODY -->
