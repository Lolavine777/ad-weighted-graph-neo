# Sinh va hieu chinh xac suat co dieu kien q_i tu bang chung thuc nghiem (#237)

## 1. Tom tat dieu hanh va cac quyet dinh kien truc

Tai lieu nay thuc hien Master Issue [#237](https://github.com/nairyuuu/ad-weighted-graph/issues/237) ve viec nghien cuu, sinh va hieu chinh xac suat thanh cong co dieu kien $q_i$ tu bang chung thuc nghiem (empirical evidence).
Nguoi phu trach: TTS A (@Lolavine777).
Nguoi ra soat giao dien va ngu nghia: TTS B (@nairyuuu).
Baseline ma nguon duoc pin: `develop@32ffd62ce9e65c20ccb032143bb8c8cb3dae259a` (bao gom AS-REP #234).
Tai lieu tham chieu: ADR-0013, Issue #204, #206, #207, #208, #192, #219, #228, #229; NIST Handbook PRC 2.4.1; Ur et al. (USENIX Security 2015).

He thong tuan thu nghiem ngat cac nguyen tac cap cao da duoc phe chuan:
1.
Giu nguyen kien truc tinh toan xac suat toan duong $P(\text{path}) = \prod q_i$ voi dieu kien hoa tren toan bo lich su thanh cong truoc do (full-history conditioning).
2.
Tuyet doi khong anh xa cac chi so dinh tinh (Low/Medium/High, CVSS) hoac do tu tin cua mo hinh ngon ngu lon (LLM confidence) thanh xac suat so hoc.
3.
Ap dung chinh sach fail-closed doi voi du lieu thieu hoac khong dai dien: neu thieu can cu thuc nghiem, bat buoc giu trang thai `unrated`.
4.
Khong tu y dien cac gia tri mac dinh nhu 0, 0.5, 1 hay khoang $[0, 1]$, va khong dung diem phat (penalty) de bien ung vien chua co bang chung thanh ung vien da xep hang.
5.
Phan dinh ro rang giua co gia dinh re nhanh kiem thu phan mem (`recovery_success=true`), fixture mo phong prototype, va quan sat thuc nghiem do luong thuc te.
6.
Thi diem hep truoc tren don vi cong viec phuc hoi bi mat ngoai tuyen (`recover_asrep_secret` / `recover_ticket_secret`) do da co cac thong so rang buoc ve phuong phap (`method`), ngan sach doan (`budget`), va thoi han (`horizon`).
7.
Giu nguyen ven bang chung lich su va 21 tham so da duoc chap thuan cua Week 3 (digest `sha256:20f67e8604f6399b5b360e412bb30bf898f4d788f13b69c08c78ef2df73d3358`).
8.
Minh bach ve trang thai nghiem thu: Bo du lieu `lab_benchmark_dataset.json` hien tai la mot benchmark prototype fixture phuc vu kiem chung phan mem cho bo uoc luong va quy trinh danh gia holdout, chua phai mot chien dich do luong thuc te tren ha tang Active Directory duoc audit doc lap.
Do do, cac hang muc do luong quy mo lon duoc ghi nhan la deferred theo dung chi dao tai Muc 5 cua Issue #237; tuyet doi khong tu dong dong master issue duoi nhan da hieu chuan hoan tat.

## 2. Chang 1: Audit du lieu, Literature va Chon thi diem

### 2.1. Audit implementation tai pinned revision (`develop@32ffd62`)
He thong hien tai xu ly xac suat tai `src/engine/ranking/assessment.py` (dong 85-115).
Dong co xep hang nhan `conditional_bounds_table` duoi dang tu dien anh xa tu tien to chuoi cong viec (`prefix`) sang cap khoang xac suat `(lower, upper)`.
Cac can xac suat duoc nhan tich luy bang so hoc phan so chinh xac (`fractions.Fraction`) de triet tieu hoan toan sai so dau phay dong.
Neu bat ky tien to nao trong chuoi cong viec cua ung vien bi thieu trong bang, trang thai xep hang chuyen sang `likelihood_status = "unrated"` va khoang xac suat bi thu hoi (`likelihood_interval = None`).

Ranh gioi du kien trong kien truc hien tai gom ba tang:
- Tang 1 (`observed_facts`): Cac thuoc tinh cau hinh duoc trich xuat truc tiep tu snapshot Active Directory tinh, vi du `owner_enabled`, `dontreqpreauth` tu `SnapshotFacts`.
Day la thuoc tinh cau hinh/chinh sach tai mot thoi diem, khong phai la xac suat hay tan suat quan sat.
- Tang 3 (`assumed_facts`): Cac gia dinh kich ban runtime do nguoi goi query khai bao, vi du `network_kdc_reachable`, `asrep_request_accepted`, `recovery_success`, `authentication_accepted`.
Trong cac ca synthetic (#216, #228) va kich ban Week 3, cac cong nay duoc gan gia tri boolean de phuc vu viec re nhanh thuat toan tim kiem, hoan toan chua co nhat ky telemetry do luong thuc te.
- Bang xac suat hien hanh:
  - Trong Week 3: 11 khoang likelihood duoc gan nhan `basis_category = "scenario_assumption"` tu nhan dinh chuyen gia co AI ho tro (`human_reviewed_ai_assisted_ratings`), vi du khoang $[3/5, 19/20]$ cho thao tac `reset_password`.
  - Trong Week 4 (#216, #228): Ban giao ky thuat Kerberoasting va AS-REP roasting giu nguyen bang rong `conditional_bounds_table: []` va nhan `missing_basis_reasons: ["no_numeric_basis"]`.
Khong co baseline nhan dinh so hoc nao tung duoc phe duyet cho thao tac `recover_asrep_secret` trong Week 3 hay Week 4.

### 2.2. Ma tran nguon du lieu 5 chieu
De danh gia tinh kha thi cua viec do luong, ma tran sau day kiem ke 5 chieu thong tin doi voi cac nguon du lieu co the tiep can:

| Nguon du lieu | Cau hinh (Config) | Moi truong chay (Runtime) | Bien phap kiem soat (Controls) | Thoi han (Horizon) | Thuc nghiem Lab (Empirical Lab) | Danh gia kha nang ap dung sang SEAMLESS |
| --- | --- | --- | --- | --- | --- | --- |
| SEAMLESS Snapshot | Day du: do thi BloodHound, ACLs, UAC, SPN, DontReqPreauth | Hoan toan thieu: khong co telemetry mang, khong co log xac thuc Kerberos | Mot phan: GPO password policy chung, thieu cau hinh EDR chi tiet | Co dinh theo snapshot | Khong co: khong co hash mat khau that, khong co lan be khoa nao duoc ghi nhan | **Khong the ap dung**: Thieu mau so (denominator) cho cac bien co dong; suy doan xac suat tu do thi tinh la vo can cu. |
| Synthetic Fixtures (#216, #228) | Day du cho do thi gia dinh nho | Co boolean nhan tao (`value: true/false`) | Khai bao gia dinh | Khai bao co dinh | Khong co | **Khong the ap dung**: Fixture chi phuc vu kiem thu phan mem; cam dung lam bang chung xac suat. |
| Controlled Lab Benchmark Prototype | Kiem soat chinh xac: dinh dang hash Kerberos etype 23/18 | Ghi nhan day du: thoi gian chay, so luong, GPU hash rate | Xac dinh ro rang: khong co co che khoa tai khoan ngoai tuyen | Gioi han cung: $3600$ giay ($1$ gio) | 100 luot thu nghiem prototype voi tu dien va rule co dinh | **Chi ap dung trong pham vi Lab Prototype**: Co mau so va tu so xac dinh; giu SEAMLESS bat buoc la `unrated`. |

### 2.3. Doi chieu cac huong kha thi va khuyen nghi thi diem
Ba huong tiep can chinh duoc phan tich doi chieu:
- Huong 1 - Anh xa Heuristic (CVSS, do phuc tap do thi, in/out-degree):
  Uu diem la de tinh toan va co the phu kin toan bo do thi.
  Nhuoc diem la vi pham nghiem trong Nguyen tac 2 cua du an, khong co ngu nghia xac suat va tao ra do chinh xac gia tao.
  Huong nay bi loai bo.
- Huong 2 - Su dung Machine Learning / LLM Elicitation:
  Uu diem la co the sinh ra con so nhanh chong cho nhieu kich ban phuc tap.
  Nhuoc diem la khong kiem toan duoc nguon du lieu, do tu tin cua mo hinh ngon ngu khong phan anh tan suat thanh cong thuc te trong mang noi bo.
  Huong nay bi loai bo.
- Huong 3 - Estimator Thong ke dua tren Bang chung Thuc nghiem (NIST Binomial Proportion):
  Uu diem la co co so toan hoc chat che (NIST Handbook PRC 2.4.1), kiem toan duoc mau so va tu so, cong bo ro rang khoang tin cay thong ke va co co che fail-closed khi thieu du lieu.
  Nhuoc diem la pham vi ap dung hep, doi hoi phai co du lieu thuc nghiem tuong thich.
  **Khuyen nghi**: Chon Huong 3 lam thi diem.
  Don vi cong viec duoc chon la `recover_asrep_secret` (va `recover_ticket_secret`) vi day la thao tac ngoai tuyen duy nhat trong mo hinh hien hanh da chuan hoa day du bo ba rang buoc `method`, `budget`, va `horizon`.

## 3. Chang 2: Estimator Thuc nghiem Doc lap

### 3.1. Mo hinh toan hoc va khoang tin cay Wilson
Cho mot tap hop cac cuoc thu nghiem phuc hoi mat khau ngoai tuyen doc lap trong cung mot lop kich ban.
Goi $n$ la tong so tai khoan/bam mat khau duoc thu nghiem doc lap trong cung ngan sach doan $B$ va thoi han $H$.
Goi $k$ la so tai khoan be khoa thanh cong trong ngan sach va thoi han do ($0 \le k \le n$).
Ty le thanh cong quan sat duoc la $\hat{p} = k / n$.

Theo khuyen nghi cua NIST (Handbook PRC Section 2.4.1), khoang tin cay Wilson score interval cap $1 - \alpha = 0.95$ ($z \approx 1.95996$) duoc tinh nhu sau:
$$\tilde{n} = n + z^2, \quad \tilde{p} = \frac{k + \frac{z^2}{2}}{\tilde{n}}$$
$$\text{CI}_{\text{Wilson}} = \left[ \max\left(0, \tilde{p} - \frac{z}{\tilde{n}} \sqrt{\frac{k(n-k)}{n} + \frac{z^2}{4}}\right), \min\left(1, \tilde{p} + \frac{z}{\tilde{n}} \sqrt{\frac{k(n-k)}{n} + \frac{z^2}{4}}\right) \right]$$

Khi $k = 0$, can duoi duoc xac dinh chinh xac bang $0.0$.
Khi $k = n$, can tren duoc xac dinh chinh xac bang $1.0$.

### 3.2. Thuat toan lam tron bao thu ra ngoai (Outer Conservative Rationalization)
De dua khoang tin cay vao giao dien `conditional_bounds_table` cua engine ma khong gay sai so dau phay dong, cac can so thuc $[l, u]$ duoc chuyen doi sang phan so toi gian `Fraction` voi mau so toi da $M = 1000$.
De bao toan do bao phu thong ke cua khoang tin cay 95%, thuat toan lam tron bao thu ra ngoai:
$$l_{\text{frac}} = \frac{\lfloor l \times M \rfloor}{M}, \quad u_{\text{frac}} = \frac{\lceil u \times M \rceil}{M}$$
Quy tac nay dam bao bat bien:
$$0 \le l_{\text{frac}} \le l \le u \le u_{\text{frac}} \le 1$$
Khoang phan so $[l_{\text{frac}}, u_{\text{frac}}]$ bao trum toan bo khoang tin cay thong ke, triet tieu nguy co thu hep khoang nhan tao.

### 3.3. Co che tu choi Fail-Closed (Refusal Behavior)
Bo uoc luong `EmpiricalQiEstimator` tai `scripts/research/empirical_qi_estimator.py` cai dat cac quy tac tu choi nghiem ngat va tra ve `status = "unrated"` kem danh sach ma ly do khi:
1.
Chuyen giao khong dai dien sang SEAMLESS (`unrepresentative_domain_transfer_seamless`):
Kiem tra khong phan biet hoa thuong (case-insensitive); bat ky yeu cau nao co `scenario_id` chua `seamless` deu bi tu choi do snapshot BloodHound khong chua telemetry hay phan phoi mat khau quan sat.
2.
Moi truong hoac kich ban nam ngoai pham vi bang chung (`unsupported_domain_or_scenario`):
Cac kich ban khong thuoc danh sach kich ban lab duoc xac minh trong manifest (bao gom ca cac kich ban bat dau bang tien to lab khong xac dinh nhu `lab-unseen-production-bank-ad` hoac alias kiem thu `lab-scenario`) deu bi tu choi fail-closed.
Tuyet doi khong gop (union) danh sach kich ban cua manifest voi tap alias mac dinh cua phan mem kiem thu.
3.
Su dung fixture kiem thu tong hop (`synthetic_test_fixture_rejected_as_evidence`):
Cac co kich ban nhan tao khong duoc phep dung lam bang chung xac suat.
4.
Thieu metadata phuong phap (`missing_method_specification`):
Khai bao phuong phap phuc hoi bi trong hoac khong duoc xac dinh.
5.
Thieu metadata ngan sach (`missing_budget_specification`):
Ngan sach thu doan bi thieu hoac nho hon hoac bang 0.
6.
Thieu hoac khong hop le ve thoi han (`missing_horizon_specification`):
Thoi han phuc hoi bi thieu, nho hon hoac bang 0, hoac chua gia tri khong huu han nhu NaN hoac Inf.
7.
Ky thuat nam ngoai pham vi thi diem (`out_of_scope_technique`):
Ky thuat danh gia khong thuoc danh muc phuc hoi bi mat ngoai tuyen duoc ho tro.
8.
Thieu thong tin phan lop do phuc tap muc tieu (`missing_target_complexity_class_specification`):
Thieu hoac de trong phan lop do phuc tap mat khau (`target_complexity_class`), vi pham gia dinh dong nhat quan the (i.i.d. population conditioning).
9.
Thieu hoac khong ho tro nang luc tac nhan (`missing_actor_capability_specification` / `unsupported_actor_capability`):
Khi duoc rang buoc boi evidence manifest, ngu canh bat buoc phai khai bao tuong minh nang luc tac nhan (`actor_capability`).
Neu de trong (`None`), bo uoc luong lap tuc tu choi fail-closed voi ly do thieu dac ta nang luc.
Neu khai bao nang luc khong nam trong danh muc thiet bi va nang luc da duoc do luong trong manifest (`supported_actor_capabilities`), yeu cau bi tu choi fail-closed.
10.
Dinh danh buoc tien to khong hop le (`invalid_prefix_step_identifier`):
Tien to chua dinh danh buoc rong, chi chua khoang trang hoac khong phai kieu chuoi hop le.
11.
Lich su tien to khong duoc ho tro (`unsupported_prefix_history`):
Theo nguyen ly dieu kien hoa toan bo lich su (full-history conditioning), $q_i = P(\text{step}_i \mid \text{history})$.
Neu tien to chua cac buoc can thiep lam thay doi phan phoi mat khau (vi du `reset_password`), yeu cau bi tu choi do bang chung lab chi do luong chuoi thu thap nguyen ban `["asrep_request", "recover_asrep_secret"]`.
Ngoai ra, bo uoc luong thuc thi nghiem ngat danh muc chuoi tien to duoc phep (`supported_prefix_sequences`) tu manifest.
Kich ban phuc hoi dung mot minh voi `initial_material_present=True` nhung thieu buoc thu thap tien quyet cung bi tu choi neu manifest khong ho tro chuoi don le do.
12.
Thieu dieu kien tien quyet trong lich su (`missing_prerequisite_in_history`):
Thao tac phuc hoi bi mat ngoai tuyen doi hoi bien co thu thap material (`asrep_request`) phai nam trong lich su neu ngu canh ban dau chua co material.
13.
Hanh dong dich khong khop ky thuat (`prefix_action_mismatch`):
Buoc cong viec o duoi tien to khong khop voi ky thuat ngu canh can danh gia.
14.
Tien to rong (`empty_prefix`):
Chuoi tien to cong viec rong bi tu choi do vi pham nguyen tac dieu kien hoa toan bo lich su.
15.
Ket qua thu nghiem bi censored hoac khong hop le (`censored_or_invalid_trial_outcome`):
Quan sat co outcome khong nam trong `{"success", "failure"}` (vi du `censored`, `aborted`, `invalid`) bi tu choi nghiem ngat; tuyet doi khong ep quan sat censored thanh failure.
16.
Thieu dinh danh hoac provenance tren quan sat (`missing_provenance_metadata`):
Quan sat co `provenance_reference`, `trial_id` hoac `target_hash_id` rong bi tu choi fail-closed de dam bao kha nang truy xuat nguon goc va kiem tra giao thoa du lieu.
17.
Thu nghiem lap lai co ket qua mau thuan (`contradictory_repeated_trials`):
Neu cung mot ma bam muc tieu duoc ghi nhan ca `success` va `failure` trong cung mot dieu kien, bo uoc luong tu choi fail-closed doc lap voi thu tu truyen vao cua du lieu.
18.
Co mau khong du (`insufficient_sample_size`):
So luong quan sat doc lap sau khi khu trung lap cac ma bam hop le nho hon nguong toi thieu ($n < 20$).

### 3.4. Phan loai bang chung va Cach ly Prototype khoi Production Ranking
Nham ngan chan viec bien fixture prototype thanh can cu thuc nghiem de xep hang duong tan cong tren moi truong van hanh, kien truc thuc thi co che cach ly:
1.
Tiep nhan va bao toan nguyen ven phan loai du lieu:
Bo du lieu duoc khai bao la `dataset_classification = "controlled_lab_benchmark_prototype"`.
Bo uoc luong `EmpiricalQiEstimator` luu giu phan loai nay va xuat ra `basis_category = "controlled_lab_benchmark_prototype"` kem theo `evidence_disposition = "quarantined_prototype_not_for_production_ranking"`.
2.
Cong chan xuat ban sang Production Ranking:
Giao dien `export_bounds_table_entry(..., for_production_ranking=True)` hoan toan khoa chat va tra ve `None` trong pham vi prototype cua Issue #237.
Cac phep do luong thuc nghiem tren ha tang Active Directory thuc te tiep tuc duoc hoan lai (deferred).
Do do, cong xuat ban production ranking bi vo hieu hoa de dam bao khong bat ky du lieu prototype hoac caller override nao co the lot vao bang xep hang van hanh.
Bao cao `evidence-qi-calibration-237.json` ghi nhan ro rang `production_ranking_bounds_table_entry: null` de kiem toan truc quan co che cong chan nay.
Ngoai ra, bo uoc luong kiem tra su ton tai cua khoa trong manifest thay vi chi kiem tra gia tri boolean, dam bao cac danh sach rong (`[]`) cho kich ban, nang luc tac nhan, hoac chuoi tien to deu bi tu choi fail-closed thay vi roi ve cac hang so mat dinh.
3.
Siet chat ranh gioi thang hang bang chung (Production Promotion Boundary):
Manifest la nguon chan ly duy nhat va bat bien cho phan loai du lieu.
Cac tham so chuoi do caller cung cap qua constructor hoac `fit()` khong duoc phep ghi de hoac thay doi phan loai cua manifest.
Moi truong hop caller truyen phan loai mau thuan voi manifest deu bi tu choi fail-closed (`conflicting_dataset_classification`).
Truong hop caller yeu cau `empirical_measurement` ma khong cung cap manifest hoac manifest chua qua review hop le deu bi tu choi fail-closed (`missing_evidence_manifest` hoac `unreviewed_evidence_manifest`).
Dong thoi, cac quan sat mang nguon goc prototype (`lab://`) bi chan tuyet doi, khong the thang hang len empirical measurement (`unverified_prototype_provenance`).
Co che xuat ban empirical production ranking tiep tuc o trang thai deferred/disabled cho den khi co goi du lieu thuc nghiem van hanh duoc phe chuan.

## 4. Chang 3: Doi chung chat luong va Thuc nghiem Holdout

### 4.1. Thiet ke tap du lieu Lab Benchmark Prototype
Tap du lieu chuan hoa gom $100$ quan sat tai `tests/fixtures/empirical_calibration/lab_benchmark_dataset.json` (ma bam `sha256:b67c02f1d088f6a43d865981e43f91f25d9c7f6aa31e27b93b99301b009a4575`).
Tap du lieu duoc phan loai ro rang la `dataset_classification: "controlled_lab_benchmark_prototype"` kem theo `evidence_manifest` day du (cong cu `hashcat v6.2.6`, tu dien `rockyou.txt`, tap luat `best64.rule`, moi truong 1x RTX 4090 GPU).
Moi ban ghi quan sat deu duoc gan kem ma bam `artifact_digest` xac thuc.
Du lieu duoc chia tach chat che:
- Tap huan luyen (Training Set): $60$ quan sat doc lap voi $22$ lan thanh cong ($p_{\text{train}} = 22 / 60 \approx 36.67\%$).
- Tap kiem chung giu lai (Holdout Set): $40$ quan sat doc lap voi $14$ lan thanh cong ($p_{\text{holdout}} = 14 / 40 = 35.00\%$).

Co che chan ro ri du lieu (Data Leakage Interception):
Ham `evaluate_holdout_quality` thuc hien kiem tra giao thoa toan dien giua tap holdout va tap huan luyen da fit cua estimator.
Kiem tra bao gom danh tinh on dinh (`target_hash_id`, `trial_id`, `provenance_reference`) va ma bam noi dung ban ghi quan sat `artifact_digest`.
Moi ban ghi trong tap holdout cung duoc xac thuc day du ve dinh dang va provenance truoc khi danh gia.
Neu phat hien bat ky su trung lap ve danh tinh, ma bam ban ghi hoac du lieu khong hop le nao, ham lap tuc tu choi danh gia va tra ve `status = "leakage_detected"` hoac `status = "invalid_holdout_data"`, triet tieu nguy co danh gia sai lech khi du lieu bi ro ri.

Bao cao tu choi Holdout an toan (Safe Holdout Refusal Reporting):
Khi tap holdout bi tu choi danh gia do censored, ro ri du lieu hoac tap holdout rong, ham `run_full_evaluation` khong truy cap cac chi so danh gia de tranh loi `KeyError: 'holdout_sample_size'`.
Bao cao luu giu trang thai tu choi, ma chan doan, va dat cac chi so danh gia (Brier score, log loss, empirical rate) ve `None`.

### 4.2. Ket qua do luong tren Prototype Fixture
Chay giao thuc danh gia hoan chinh (`scripts/research/empirical_qi_estimator.py`):
- Khoang tin cay Wilson 95% tu tap huan luyen: $[0.256209, 0.493170]$.
- Can phan so bao thu toi gian: $[32/125, 247/500]$ (tuong duong $[0.2560, 0.4940]$).
- Ty le thanh cong quan sat duoc tren tap holdout: $35.00\%$ ($14/40$).
- Chan doan tinh tuong thich tren 1 split don le (`holdout_rate_in_interval_diagnostic`): **TRUE** ($35.00\%$ nam ben trong khoang $[25.62\%, 49.32\%]$).
  Luu y khoa hoc: Day chi la mot phep kiem tra tuong thich (single-split consistency diagnostic), KHONG PHAI la do luong do bao phu lay mau lap lai (repeated-sampling coverage) hay xac nhan hieu chuan xac suat toan dien.
- Do rong khoang tin cay: $0.2370$.
- Brier Score tren tap holdout (su dung posterior mean shrinkage): $0.2279$.
- Log Loss tren tap holdout: $0.6484$.
- Ty le tu choi tren tap 19 ca kiem thu fail-closed (`tests/fixtures/empirical_calibration/refusal_cases.json`): **$100\%$ ($19/19$ ca deu bi tu choi dung quy cach)**.

### 4.3. Danh gia Baseline va Doi chung Ngu canh

Doi chieu voi cac cong bo truoc day cua du an:
- Trong dot phat hanh Week 3: Chi co 11 tham so duoc tiep nhan dua tren nhan dinh chuyen gia co AI ho tro (`human_reviewed_ai_assisted_ratings`), vi du khoang $[3/5, 19/20]$ cho thao tac dat lai mat khau truc tuyen (`reset_password`).
- Trong dot phat hanh Week 4 (#228 / #234): Ky thuat AS-REP roasting duoc dua vao mo hinh nhung giu nguyen `conditional_bounds_table: []` voi nhan `missing_basis_reasons: ["no_numeric_basis"]`.
- Do do, **khong ton tai mot baseline nhan dinh chuyen gia so hoc nao duoc phe duyet cho ky thuat `recover_asrep_secret`**.

Ket luan doi chung:
- `baseline_comparison`: Duoc ghi nhan chinh thuc la **`unavailable`** (`reason: "no_reviewed_baseline_for_technique"`).
- Viec lay khoang $[3/5, 19/20]$ cua `reset_password` de so sanh voi `recover_asrep_secret` la khong dung phuong phap luan vi day la hai bien co hoan toan khac nhau ve ban chat, chinh sach va co che tan cong (online LDAP password reset vs offline GPU hash cracking).
- Khoang tin cay hep hon khong tu dong chung minh mo hinh tot hon.
- Bo hoan toan cac tuyen bo ve "do tin cay vuot troi" so voi baseline cu vi khong co phep so sanh tuong duong hop le.
- Doi voi kịch ban SEAMLESS: Do hoan toan thieu telemetry va phan phoi mat khau quan sat, he thong tiep tuc duy tri trang thai `unrated` fail-closed.

## 5. Chang 4: Tich hop tuy chon va Hop dong Engine

### 5.1. Ranh gioi so huu va Giao dien tich hop
Tuan thu ranh gioi so huu giua TTS A va TTS B:
- TTS A chiu trach nhiem ve mo hinh thong ke, bo uoc luong, goi du lieu thuc nghiem prototype, va cung cap ket qua qua cau truc du lieu chuan `conditional_bounds_table`.
- TTS B duy tri toan bo engine xep hang (`src/engine/ranking/`), khong bi ep buoc phai thay doi thuat toan tim kiem hay cau truc noi bo cua engine.

### 5.2. Kiem chung tinh dung dan voi Engine hien hanh
Hop dong giao dien da duoc kiem chung bang kiem thu tich hop tu dong (`tests/test_empirical_qi_estimator.py`):
1. Kich ban Lab Benchmark Prototype:
   Can xac suat cua `recover_asrep_secret` ($[32/125, 247/500]$) voi chuoi tien to dieu kien day du (`["asrep_request", "recover_asrep_secret"]` hoac qua bi danh hanh dong `["w-req", "w-rec"]`) duoc nap vao `conditional_bounds_table`.
   Ham `assess_candidate_program` trong `src/engine/ranking/assessment.py` thuc hien nhan don phan so:
   $$P_{\text{path}} = [9/10 \times 32/125, 19/20 \times 247/500] = [144/625, 4693/10000]$$
   Ket qua tra ve dat trang thai `likelihood_status = "rated"` voi gia tri khop chinh xac tuyet doi voi Fraction oracle doc lap cua A.
2. Kich ban SEAMLESS:
   Do bo uoc luong tu choi chuyen giao, tien to `recover_asrep_secret` khong xuat hien trong `conditional_bounds_table`.
   Ham `assess_candidate_program` thuc thi chinh sach fail-closed:
   Ket qua tra ve `likelihood_status = "unrated"`, `likelihood_interval = None`, va ghi nhan ma chan doan `diagnostic_reasons = ["likelihood_unrated"]`.
3. Kiem tra tinh toan ven cua Week 3:
   Bo tham so 21 gia tri cua kich ban Week 3 (`reviewed-release.json`) va ma bam chuan `sha256:20f67e8604f6399b5b360e412bb30bf898f4d788f13b69c08c78ef2df73d3358` duoc giu nguyen ven khong bi sua doi.

## 6. Nghiem thu Master Checklist theo Muc 5 cua Issue #237

- [x] **Tieu chi 1: Chang 1 co recommendation, evidence/data inventory va gioi han; khong claim novelty chi vi repo dang thieu.**
  Da hoan thanh: Muc 2 da kiem ke ma tran 5 chieu, phan tich ranh gioi facts/assumptions, va khuyen nghi pilot hep cho phuc hoi mat khau ngoai tuyen.
- [x] **Tieu chi 2: It nhat mot event/context co estimator tai lap, provenance va refusal behavior dung.**
  Da hoan thanh: `scripts/research/empirical_qi_estimator.py` cai dat bo uoc luong Wilson 95% cho `recover_asrep_secret` voi day du kiem tra provenance, ma bam artifact_digest, loai bo lo hong wildcard prefix, bao toan phan loai prototype va cach ly khoi production ranking, thuc thi ranh gioi evidence manifest nghiem ngat, va 19 ca kiem thu tu choi fail-closed (chan domain shift, mixed-case SEAMLESS, unseen history, censored runs, missing complexity, unsupported/missing actor capabilities, unsupported prefix sequences, scenario ngoai manifest, va contradictory duplicates).
- [ ] **Tieu chi 3: Co ket qua do/danh gia doc lap voi du lieu dung xay estimator, cong bo bat dinh va sampling limits.**
  GHI NHAN DEFERRED: Hien tai phep kiem tra holdout chi la chan doan tinh tuong thich tren 1 split don le tren benchmark prototype fixture.
  Chua co chien dich thuc nghiem do luong tren ha tang that duoc kiem toan doc lap, va chua do luong do bao phu lay mau lap lai; do do hang muc nay duoc danh dau la DEFERRED theo dung dieu kien dung cua Master #237.
- [x] **Tieu chi 4: Doi chung neu cai thien, khong cai thien hoac chua du bang chung mot cach trung thuc; khong bat ket qua phai thang expert.**
  Da hoan thanh: Doi chung tai Muc 4.3 ghi nhan ro `baseline_comparison: unavailable` do Week 3 khong co baseline cho AS-REP recovery, khong so sanh khap khieng voi `reset_password`, va khong claim vuot troi vo can cu.
- [x] **Tieu chi 5: Co disposition tich hop hoac defer voi ly do, ownership va scope; neu tich hop thi engine conformance/ranking regression duoc kiem.**
  Da hoan thanh: Giao dien tich hop qua `conditional_bounds_table` da duoc kiem chung khop hoan toan voi `assessment.py`, SEAMLESS giu nguyen unrated fail-closed, va bao toan nguyen ban release Week 3.
- [x] **Tieu chi 6: Ket luan tieng Viet ro dieu gi da do, ap dung o dau va phan nao tiep tuc unrated.**
  Da hoan thanh: Ket luan neu ro da do ty le be khoa trong bối canh lab benchmark prototype, chi ap dung cho bối canh lab co cung dieu kien, va tiep tuc giu SEAMLESS la `unrated`.

Dieu kien dung:
Khong tu merge PR va khong tuyen bo hoan tat master issue #237 duoi nhan da hieu chuan.
Phan khao sat, bo uoc luong prototype va giao dien tich hop da hoan thanh; cac chien dich do luong thuc nghiem tren moi truong san xuat duoc ghi nhan la deferred cho cac giai doan tiep theo khi co nguon du lieu telemetry thuc te.
