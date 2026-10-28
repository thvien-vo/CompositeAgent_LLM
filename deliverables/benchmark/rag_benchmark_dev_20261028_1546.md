# RAG benchmark (dev set, 12 questions)
Run: 2026-10-28 15:46. Embedding: nomic-embed-text (Ollama).

| backend | answer correct | right material retrieved | guardrail clean | fact-check agrees | mean s/question |
|---|---|---|---|---|---|
| ollama | **12/12** | 12/12 | 12/12 | 9/9 | 2.1 |

## Answers

- **ollama R1** OK - What is the longitudinal tensile strength Xt of IM7/8552?  
  The longitudinal tensile strength Xt of IM7/8552 is 2212 MPa (source: NCAMP NCP-RP-2009-028 Rev B, Table 3-3 p.37, RTD mean as-measured; status: verified_pdf). This value was retrieved from the database using a Python script. The database confirms this value as verified.
- **ollama R2** OK - Độ bền cắt S của AS4/8552 là bao nhiêu?  
  Độ bền cắt S của AS4/8552 là 91.6 MPa (source [F]: NCAMP NCP-RP-2010-008 Rev D, lamina summary table p.37, RTD mean as-measured; verification status: verified_pdf). This value was obtained from a database lookup.
- **ollama R3** OK - What is E1 of T1100G/3960 and which report is it from?  
  The longitudinal modulus (E1) of the T1100G/3960 material is 170.5 GPa (source: [1]: lamina summary table p.34, RTD mean as-measured). This value was obtained from the NCAMP NCP-RP-2023-002 Rev B report.
- **ollama R4** OK - Give the transverse compressive strength Yc of T650/5320-1.  
  Yc (transverse compressive strength) of T650/5320-1 = 274 MPa (source: NCAMP NCP-RP-2013-001 Rev A, Table 3-3 p.35, RTD mean as-measured; status: verified_pdf). Note: Checked visually on PDF page 35. S conflict resolved: 15.639 ksi was SBS, correct F12s(5%) = 13.501 ksi
- **ollama R5** OK - What is the Poisson's ratio nu12 of T40-800/5215? Is the value reliable?  
  The Poisson’s ratio nu12 of T40-800/5215 is 0.164 (source: NCAMP NCP-RP (Cycom 5215 T40-800 Unitape), lamina summary table p.36, RTD mean as-measured; status: verified_pdf). The value is doubtful because it is anomalously low compared to the value for the transverse Poisson’s ratio (nu12c = 0.366 in same table).
- **ollama R6** OK - Which NCAMP material has the highest Xt?  
  Ranking computed by Python from the whole database (NCAMP materials only, 15 materials with data), property Xt (longitudinal tensile strength), highest first: 1. T1100G/3960: 3645 MPa (source: NCAMP NCP-RP-2023-002 Rev B, lamina summary table p.34, RTD mean as-measured; status: verified_pdf); 2. T1100GC/TC380: 3277 MPa (source: NCAMP NCP-RP-2025-010 Rev -, lamina summary table p.38, RTD mean as-measured; status: verified_pdf); 3. IM7G/EP2202: 2967 MPa (source: NCAMP NCP-RP-2014-006 N/C, lamina summary table p.35, RTD mean as-measured; status: verified_pdf).
- **ollama R7** OK - Vật liệu sợi thủy tinh nào có mô đun dọc E1 lớn nhất?  
  Vật liệu sợi thủy tinh có mô đun dọc E1 lớn nhất là E-glass/LY556 với giá trị 53.48 GPa (source: Soden, Hinton & Kaddour (1998) Compos Sci Technol 58:1011-1022 (WWFE-I); status: needs_check). The E-glass/MY750 material has a longitudinal modulus of 45.6 GPa (source: Soden, Hinton & Kaddour (1998) Compos Sci Technol 58:1011-1022 (WWFE-I); status: needs_check), and the S2-glass/BT250E-6 material has a longitudinal modulus of 44.7 GPa (source: NCAMP NCP-RP-2015-021 N/C, lamina summary table p.31, RTD mean as-measured; status: verified_pdf).
- **ollama R8** OK - What is the tensile strength of titanium Ti-6Al-4V?  
  The database does not contain it.
- **ollama R9** OK - What is the in-plane shear strength S of T650/5250-5?  
  The in-plane shear strength S of T650/5250-5 is not reported in the database (source: NCAMP NCP-RP (Cycom 5250-5 T650 Unitape), lamina summary table p.36, RTD mean as-measured; status: verified_pdf).
- **ollama R10** OK - What is the fibre volume fraction of AS4/MTM45-1?  
  The fibre volume fraction of AS4/MTM45-1 is 0.58 (source: NCAMP NCP-RP-2008-004 Rev B, Table 3-3 p.35, RTD (75F) mean as-measured; status: verified_pdf). This value was looked up by Python from the database.
- **ollama R11** OK - What is Yc of Kevlar 49/epoxy?  
  The transverse compressive strength (Yc) of Kevlar 49/epoxy is 53 MPa (source: Tsai & Hahn (1980) Introduction to Composite Materials, Technomic; status: conflict). This value is doubtful due to a discrepancy with other sources. The database value was looked up by Python.
- **ollama R12** OK - Mô đun cắt G12 của IM7/BT250E-6 là bao nhiêu?  
  Mô đun cắt G12 của IM7/BT250E-6 là 4.34 GPa (source [F]: NCAMP NCP-RP-2015-019 N/C, lamina summary table p.31, RTD mean as-measured).
