# RAG benchmark (dev set, 12 questions)
Run: 2026-10-27 18:50. Embedding: nomic-embed-text (Ollama).

| backend | answer correct | right material retrieved | guardrail clean | fact-check agrees | mean s/question |
|---|---|---|---|---|---|
| hf | **11/12** | 12/12 | 12/12 | 9/9 | 2.8 |
| ollama | **11/12** | 12/12 | 12/12 | 9/9 | 6.0 |

## Answers

- **hf R1** OK - What is the longitudinal tensile strength Xt of IM7/8552?  
  The longitudinal tensile strength Xt of IM7/8552 is 2212 MPa (source [F]: NCAMP NCP‑RP‑2009‑028 Rev B, Table 3‑3 p. 37, RTD mean as‑measured).
- **hf R2** OK - Độ bền cắt S của AS4/8552 là bao nhiêu?  
  Độ bền cắt S của AS4/8552 là 91.6 MPa (source [F]: Database value looked up by Python: S (in-plane shear strength) of AS4/8552 = 91.6 MPa (source: NCAMP NCP‑RP‑2010‑008 Rev D, lamina summary table p.37, RTD mean as-measured; status: verified_pdf)).
- **hf R3** OK - What is E1 of T1100G/3960 and which report is it from?  
  E1 = 170.5 GPa (source [F]: Database value looked up by Python: E1 (longitudinal modulus) of T1100G/3960 = 170.5 GPa (source: NCAMP NCP‑RP‑2023‑002 Rev B, lamina summary table p.34, RTD mean as‑measured; status: verified_pdf)).
- **hf R4** OK - Give the transverse compressive strength Yc of T650/5320-1.  
  The transverse compressive strength Yc of T650/5320-1 is 274 MPa (source [F]: Database value looked up by Python: Yc (transverse compressive strength) of T650/5320-1 = 274 MPa (source: NCAMP NCP‑RP‑2013‑001 Rev A, Table 3‑3 p.35, RTD mean as‑measured; status: verified_pdf)).
- **hf R5** OK - What is the Poisson's ratio nu12 of T40-800/5215? Is the value reliable?  
  The Poisson’s ratio ν12 for T40‑800/5215 is 0.164 (source [F]: Database value looked up by Python: nu12 (Poisson's ratio) of T40-800/5215 = 0.164 (source: NCAMP NCP‑RP (Cycom 5215 T40‑800 Unitape), lamina summary table p.36, RTD mean as‑measured; status: verified_pdf)). The entry is marked as verified, but the original table notes that ν12t = 0.164 is anomalously low compared with ν12c = 0.366, so the value should be treated with caution (source [1]: nu12t = 0.164 is anomalously low (nu12c = 0.366 in same table) - consider excluding nu12 for this row).
- **hf R6** FAIL - Which NCAMP material has the highest Xt?  
  The NCAMP material with the highest longitudinal tensile strength (Xt) is **T1100G/3960**, with Xt = 3645 MPa (source [R]: Ranking computed by Python from the whole database (NCAMP materials only, 15 materials with data), property Xt (longitudinal tensile strength), highest first: 1. T1100G/3960: 3645 MPa …).  
  missing: [['NCP-RP-2023-002']]; suspicious numbers: []
- **hf R7** OK - Vật liệu sợi thủy tinh nào có mô đun dọc E1 lớn nhất?  
  Vật liệu E‑glass/LY556 có mô đun dọc E1 lớn nhất, bằng 53.48 GPa (chưa được xác thực). (source [1]: Material E-glass/LY556: … E1 (longitudinal modulus) = 53.48 GPa.)
- **hf R8** OK - What is the tensile strength of titanium Ti-6Al-4V?  
  The database does not contain the tensile strength of titanium Ti‑6Al‑4V.
- **hf R9** OK - What is the in-plane shear strength S of T650/5250-5?  
  The in‑plane shear strength S of T650/5250‑5 is not reported. (source [1]: “S (in‑plane shear strength): not reported. … Source: NCAMP NCP‑RP (Cycom 5250‑5 T650 Unitape), lamina summary table p.36, RTD mean as‑measured.”)
- **hf R10** OK - What is the fibre volume fraction of AS4/MTM45-1?  
  The fibre volume fraction of AS4/MTM45-1 is 0.58 (source [F]: NCAMP NCP‑RP‑2008‑004 Rev B, Table 3‑3 p.35, RTD (75F) mean as‑measured; status: verified_pdf).
- **hf R11** OK - What is Yc of Kevlar 49/epoxy?  
  The transverse compressive strength Yc of Kevlar 49/epoxy is 53 MPa, but this value is not yet verified (conflict). (source [F]: Database value looked up by Python: Yc (transverse compressive strength) of Kevlar 49/epoxy = 53 MPa (source: Tsai & Hahn (1980) Introduction to Composite Materials, Technomic; status: conflict))
- **hf R12** OK - Mô đun cắt G12 của IM7/BT250E-6 là bao nhiêu?  
  Mô đun cắt G12 của IM7/BT250E-6 là 4.34 GPa (source [1]: NCAMP NCP-RP-2015-019 N/C, lamina summary table p.31, RTD mean as-measured).
- **ollama R1** OK - What is the longitudinal tensile strength Xt of IM7/8552?  
  The longitudinal tensile strength Xt of IM7/8552 is 2212 MPa (source: NCAMP NCP-RP-2009-028 Rev B, Table 3-3 p.37, RTD mean as-measured; status: verified_pdf). This value was retrieved directly from the database. The material is IM7 fibre in Hexcel 8552 matrix with a fibre volume fraction of 0.584.
- **ollama R2** OK - Độ bền cắt S của AS4/8552 là bao nhiêu?  
  Độ bền cắt S của AS4/8552 là 91.6 MPa (source [1]: lamina summary table p.37, RTD mean as-measured). This value was verified from the NCAMP NCP-RP-2010-008 Rev D document. The database contains this information as a verified value.
- **ollama R3** OK - What is E1 of T1100G/3960 and which report is it from?  
  The longitudinal modulus (E1) of T1100G/3960 is 170.5 GPa (source: [1]: lamina summary table p.34, RTD mean as-measured). This value was obtained from the NCAMP NCP-RP-2023-002 Rev B report. The verification status of this data is verified_pdf.
- **ollama R4** OK - Give the transverse compressive strength Yc of T650/5320-1.  
  The transverse compressive strength Yc of T650/5320-1 is 274 MPa (source [F]: NCAMP NCP-RP-2013-001 Rev A, Table 3-3 p.35, RTD mean as-measured; status: verified_pdf). This value was obtained directly from the database. The material consists of T650 fibre (carbon) in Cytec Cycom 5320-1 matrix (epoxy) with a fibre volume fraction of 0.586.
- **ollama R5** FAIL - What is the Poisson's ratio nu12 of T40-800/5215? Is the value reliable?  
  The Poisson’s ratio nu12 of T40-800/5215 is 0.164 (source: [1]: «nu12 (Poisson's ratio) = 0.164»). This value is verified as part of the NCAMP NCP-RP (Cycom 5215 T40-800 Unitape) lamina summary table p.36, RTD mean as-measured (verified_pdf). Note: Read visually on PDF page 36. The database value is reliable.  
  missing: [['anomal', 'low', 'unreliable', 'not reliable', 'caution', 'question']]; suspicious numbers: []
- **ollama R6** OK - Which NCAMP material has the highest Xt?  
  The NCAMP material with the highest longitudinal tensile strength (Xt) is T1100G/3960, with a value of 3645 MPa (source: NCAMP NCP-RP-2023-002 Rev B, lamina summary table p.34, RTD mean as-measured; status: verified_pdf). T1100GC/TC380 has 3277 MPa (source: NCAMP NCP-RP-2025-010 Rev -, lamina summary table p.38, RTD mean as-measured; status: verified_pdf), and IM7G/EP2202 has 2967 MPa (source: NCAMP NCP-RP-2014-006 N/C, lamina summary table p.35, RTD mean as-measured; status: verified_pdf).
- **ollama R7** OK - Vật liệu sợi thủy tinh nào có mô đun dọc E1 lớn nhất?  
  Vật liệu sợi thủy tinh E-glass/LY556 có mô đun dọc E1 lớn nhất, với giá trị là 53.48 GPa (source: Soden, Hinton & Kaddour (1998) Compos Sci Technol 58:1011-1022 (WWFE-I); status: needs_check). E-glass/MY750 có mô đun dọc E1 là 45.6 GPa (source: Soden, Hinton & Kaddour (1998) Compos Sci Technol 58:1011-1022 (WWFE-I); status: needs_check). S2-glass/BT250E-6 có mô đun dọc E1 là 44.7 GPa (source: NCAMP NCP-RP-2015-021 N/C, lamina summary table p.31, RTD mean as-measured; status: verified_pdf).
- **ollama R8** OK - What is the tensile strength of titanium Ti-6Al-4V?  
  The database does not contain it.
- **ollama R9** OK - What is the in-plane shear strength S of T650/5250-5?  
  The in-plane shear strength S of T650/5250-5 is not reported in the database (source [F]: NCAMP NCP-RP (Cycom 5250-5 T650 Unitape), lamina summary table p.36, RTD mean as-measured; status: verified_pdf). The database does not contain this value.
- **ollama R10** OK - What is the fibre volume fraction of AS4/MTM45-1?  
  The fibre volume fraction of AS4/MTM45-1 is 0.58 (source: NCAMP NCP-RP-2008-004 Rev B, Table 3-3 p.35, RTD (75F) mean as-measured; status: verified_pdf). This value was retrieved from the database using a Python script. The database confirms this value as verified.
- **ollama R11** OK - What is Yc of Kevlar 49/epoxy?  
  The transverse compressive strength (Yc) of Kevlar 49/epoxy is 53 MPa (source: Tsai & Hahn (1980) Introduction to Composite Materials, Technomic; status: conflict). This value was obtained from the database. However, it is noted that this value is in conflict with other sources.
- **ollama R12** OK - Mô đun cắt G12 của IM7/BT250E-6 là bao nhiêu?  
  Mô đun cắt G12 của IM7/BT250E-6 là 4.34 GPa (source [F]: NCAMP NCP-RP-2015-019 N/C, lamina summary table p.31, RTD mean as-measured). The longitudinal modulus E1 is 155.8 GPa (source [1]: NCAMP NCP-RP-2015-019 N/C, lamina summary table p.31, RTD mean as-measured). The transverse modulus E2 is 8.6 GPa (source [1]: NCAMP NCP-RP-2015-019 N/C, lamina summary table p.31, RTD mean as-measured).
