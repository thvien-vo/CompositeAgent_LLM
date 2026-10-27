# RAG benchmark (holdout set, 6 questions)
Run: 2026-10-27 18:53. Embedding: nomic-embed-text (Ollama).

| backend | answer correct | right material retrieved | guardrail clean | fact-check agrees | mean s/question |
|---|---|---|---|---|---|
| hf | **6/6** | 6/6 | 6/6 | 4/4 | 4.2 |
| ollama | **5/6** | 6/6 | 6/6 | 4/4 | 6.6 |

## Answers

- **hf Q1** OK - What is the transverse tensile strength Yt of AS4/MTM45-1?  
  The transverse tensile strength Yt of AS4/MTM45-1 is 47.7 MPa (source [F]: NCAMP NCP‑RP‑2008‑004 Rev B, Table 3‑3 p.35, RTD (75F) mean as‑measured; status: verified_pdf).
- **hf Q2** OK - Cho biết mô đun ngang E2 của vật liệu T700GC/TC1225.  
  Mô đun ngang E2 của vật liệu T700GC/TC1225 là 9.09 GPa (source [F]: E2 (transverse modulus) of T700GC/TC1225 = 9.09 GPa (source: NCAMP NCP‑RP‑2019‑011 Rev A, lamina summary table p.33, RTD mean as-measured; status: verified_pdf)).
- **hf Q3** OK - Which glass fibre material has the lowest Xc?  
  E‑glass/LY556 has the lowest longitudinal compressive strength, Xc = 570 MPa (source [R]: “E‑glass/LY556: 570 MPa … status: needs_check”). This value is not yet verified.
- **hf Q4** OK - What is the in-plane shear strength of IM7/8552 and how is it defined?  
  The in‑plane shear strength of IM7/8552 is 91.1 MPa (source [F]: Database value looked up by Python: S (in‑plane shear strength) of IM7/8552 = 91.1 MPa (source: NCAMP NCP‑RP‑2009‑028 Rev B, Table 3‑3 p.37, RTD mean as‑measured; status: verified_pdf)). It is defined as the shear stress F₁₂s at 5 % strain (source [1]: S definition: F12s at 5% strain).
- **hf Q5** OK - Xt của T300/5208 là bao nhiêu và lấy từ nguồn nào?  
  Xt của T300/5208 là 1500 MPa (source [F]: Database value looked up by Python: Xt (longitudinal tensile strength) of T300/5208 = 1500 MPa (source: Tsai & Hahn (1980) Introduction to Composite Materials, Technomic; status: verified_online)). No page information is provided.
- **hf Q6** OK - What is the density of IM7/8552?  
  The database does not contain the density of IM7/8552.
- **ollama Q1** OK - What is the transverse tensile strength Yt of AS4/MTM45-1?  
  The transverse tensile strength Yt of AS4/MTM45-1 is 47.7 MPa (source: NCAMP NCP-RP-2008-004 Rev B, Table 3-3 p.35, RTD (75F) mean as-measured; verification status: verified_pdf). This value was obtained from the database lookup. The AS4/MTM45-1 material consists of AS4 fibre (carbon) in Cytec MTM45-1 matrix (epoxy) with a fibre volume fraction of 0.58 (source: NCAMP NCP-RP-2008-004 Rev B, Table 3-3 p.35, RTD (75F) mean as-measured).
- **ollama Q2** OK - Cho biết mô đun ngang E2 của vật liệu T700GC/TC1225.  
  The transverse modulus E2 of the T700GC/TC1225 material is 9.09 GPa (source: NCAMP NCP-RP-2019-011 Rev A, lamina summary table p.33, RTD mean as-measured; verification status: verified_pdf). This value was obtained from the database lookup.
- **ollama Q3** OK - Which glass fibre material has the lowest Xc?  
  The E-glass/LY556 material has a longitudinal compressive strength (Xc) of 570 MPa (source [1]: Soden, Hinton & Kaddour (1998) Compos Sci Technol 58:1011-1022 (WWFE-I)). Scotchply 1002 has a value of 610 MPa (source [2]: Tsai & Hahn (1980) Introduction to Composite Materials, Technomic; status: needs_check), and E-glass/MY750 has a value of 800 MPa (source [3]: Soden, Hinton & Kaddour (1998) Compos Sci Technol 58:1011-1022 (WWFE-I); status: needs_check). According to the ranking [R], E-glass/LY556 has the lowest Xc value.
- **ollama Q4** FAIL - What is the in-plane shear strength of IM7/8552 and how is it defined?  
  The in-plane shear strength of IM7/8552 is 91.1 MPa (source: [1]: Table 3-3 p.37, RTD mean as-measured; status: verified_pdf). This value is defined as F12s at 5% strain (source: [1]: Table 3-3 p.37, RTD mean as-measured; status: verified_pdf).  
  missing: [['NCP-RP-2009-028']]; suspicious numbers: []
- **ollama Q5** OK - Xt của T300/5208 là bao nhiêu và lấy từ nguồn nào?  
  The longitudinal tensile strength (Xt) of T300/5208 is 1500 MPa (source: Tsai & Hahn (1980) Introduction to Composite Materials, Technomic; status: verified_online).
- **ollama Q6** OK - What is the density of IM7/8552?  
  The database does not contain the density of IM7/8552.
