# RAG benchmark (holdout set, 6 questions)
Run: 2026-10-30 10:40. Embedding: nomic-embed-text (Ollama).

| backend | answer correct | right material retrieved | guardrail clean | fact-check agrees | mean s/question |
|---|---|---|---|---|---|
| ollama | **6/6** | 6/6 | 6/6 | 4/4 | 2.2 |

## Answers

- **ollama Q1** OK - What is the transverse tensile strength Yt of AS4/MTM45-1?  
  The transverse tensile strength Yt of AS4/MTM45-1 is 47.7 MPa (source: NCAMP NCP-RP-2008-004 Rev B, Table 3-3 p.35, RTD (75F) mean as-measured; verification status: verified_pdf). This value was obtained from the database lookup. The AS4/MTM45-1 material consists of AS4 fibre (carbon) in Cytec MTM45-1 matrix (epoxy) with a fibre volume fraction of 0.58 (source: NCAMP NCP-RP-2008-004 Rev B, Table 3-3 p.35, RTD (75F) mean as-measured).
- **ollama Q2** OK - Cho biết mô đun ngang E2 của vật liệu T700GC/TC1225.  
  The transverse modulus E2 of the T700GC/TC1225 material is 9.09 GPa (source: NCAMP NCP-RP-2019-011 Rev A, lamina summary table p.33, RTD mean as-measured; verification status: verified_pdf). This value was obtained from the database lookup.
- **ollama Q3** OK - Which glass fibre material has the lowest Xc?  
  The E-glass/LY556 material has a longitudinal compressive strength (Xc) of 570 MPa (source [1]: Soden, Hinton & Kaddour (1998) Compos Sci Technol 58:1011-1022 (WWFE-I)). Scotchply 1002 has a value of 610 MPa (source [2]: Tsai & Hahn (1980) Introduction to Composite Materials, Technomic), and E-glass/MY750 has a value of 800 MPa (source [3]: Soden, Hinton & Kaddour (1998) Compos Sci Technol 58:1011-1022 (WWFE-I)). Therefore, E-glass/LY556 has the lowest Xc among these materials.
- **ollama Q4** OK - What is the in-plane shear strength of IM7/8552 and how is it defined?  
  S (in-plane shear strength) of IM7/8552 = 91.1 MPa (source: NCAMP NCP-RP-2009-028 Rev B, Table 3-3 p.37, RTD mean as-measured; status: verified_pdf). S definition: F12s at 5% strain. Note: Checked visually on PDF page 37. nu12 = tension
- **ollama Q5** OK - Xt của T300/5208 là bao nhiêu và lấy từ nguồn nào?  
  The longitudinal tensile strength (Xt) of T300/5208 is 1500 MPa (source: Tsai & Hahn (1980) Introduction to Composite Materials, Technomic; status: verified_online).
- **ollama Q6** OK - What is the density of IM7/8552?  
  The database does not contain the density of IM7/8552.
