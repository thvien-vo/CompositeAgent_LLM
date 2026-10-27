"""
ml.py - Du doan tinh chat vat lieu composite bang Machine Learning (Random Forest).

Thay the bang tra cuu co dinh (MATERIAL_DB cu) bang model duoc train tu du lieu that.
GIU NGUYEN cach goi cu de KHONG phai sua main.py / llm.py / clt_engine.m:
  - predict_material("CFRP") -> dict 9 so: E1, E2, G12, nu12, Xt, Xc, Yt, Yc, S
  - Don vi SI giong ban cu: E1/E2/G12 va Xt/Xc/Yt/Yc/S tinh bang Pa (VD E1 ~ 1.4e11)
  - Van co bien MATERIAL_DB va ALIASES (llm.py dang import MATERIAL_DB)

Du lieu train: composite_lamina_dataset_v4.csv (25 he vat lieu) - 15 dong tu bao cao NCAMP/NIAR
(Wichita State University, FAA cong nhan), da doi chieu truc tiep voi PDF goc; 10 dong tu
Tsai & Hahn (1980) va Soden, Hinton & Kaddour (1998, WWFE-I), CHUA doi chieu ban goc.

Input cua model: fiber_class (carbon/glass/aramid/boron), matrix_family (epoxy/bismaleimide/PAEK),
Vf (ty le the tich soi). Output: 9 tinh chat, moi tinh chat 1 model Random Forest rieng.

GIOI HAN (can noi ro khi bao cao):
  - Chi 25 mau -> do chinh xac con thap (xem loocv_results.json). Day la ban proof-of-concept.
  - Model khong phan biet duoc loai soi cu the (VD T300 vs IM7), chi phan biet nhom soi.
  - KEVLAR (aramid) chi co 1 mau trong du lieu -> du doan cho Kevlar rat kem tin cay.
"""
import json
import os

import joblib
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_CSV = os.path.join(HERE, "composite_lamina_dataset_v4.csv")
MODEL_DIR = os.path.join(HERE, "model")
META_PATH = os.path.join(MODEL_DIR, "meta.json")

FEATURES = ["fiber_class", "matrix_family", "Vf"]
TARGETS = {
    "E1_GPa": ("E1", 1e9), "E2_GPa": ("E2", 1e9), "G12_GPa": ("G12", 1e9), "nu12": ("nu12", 1.0),
    "Xt_MPa": ("Xt", 1e6), "Xc_MPa": ("Xc", 1e6), "Yt_MPa": ("Yt", 1e6), "Yc_MPa": ("Yc", 1e6),
    "S_MPa": ("S", 1e6),
}
EXCLUDE = {
    "nu12": [21],  
}

MATERIAL_DB = {
    "CFRP": ("carbon", "epoxy"),
    "GFRP": ("glass", "epoxy"),
    "KEVLAR": ("aramid", "epoxy"),
}

ALIASES = {
    "cfrp": "CFRP", "carbon": "CFRP", "carbon fiber": "CFRP", "carbon/epoxy": "CFRP",
    "gfrp": "GFRP", "glass": "GFRP", "glass fiber": "GFRP", "glass/epoxy": "GFRP", "fiberglass": "GFRP",
    "kevlar": "KEVLAR", "aramid": "KEVLAR", "kevlar/epoxy": "KEVLAR",
}

RF_PARAMS = dict(n_estimators=300, max_depth=4, random_state=0)


def make_pipeline():
    pre = ColumnTransformer(
        [("cat", OneHotEncoder(handle_unknown="ignore"), ["fiber_class", "matrix_family"])],
        remainder="passthrough",
    )
    return Pipeline([("pre", pre), ("rf", RandomForestRegressor(**RF_PARAMS))])


def load_training_data():
    df = pd.read_csv(DATA_CSV)
    df["Vf"] = df["Vf"].astype(float)
    return df


def training_rows(df, col):
    """Cac dong dung de train cho 1 tinh chat: bo o trong va cac dong bi loai (EXCLUDE)."""
    mask = df[col].notna() & ~df["id"].isin(EXCLUDE.get(col, []))
    return df.loc[mask, FEATURES].reset_index(drop=True), df.loc[mask, col].astype(float).reset_index(drop=True)


def train_models():
    """Train lai 9 model tu CSV va luu vao thu muc model/. Tu dong goi khi can."""
    df = load_training_data()
    os.makedirs(MODEL_DIR, exist_ok=True)
    models = {}
    for col in TARGETS:
        X, y = training_rows(df, col)
        pipe = clone(make_pipeline())
        pipe.fit(X, y)
        models[col] = pipe
        joblib.dump(pipe, os.path.join(MODEL_DIR, f"rf_{col}.joblib"))

    default_vf = {}
    for name, (fc, mf) in MATERIAL_DB.items():
        sub = df[(df["fiber_class"] == fc) & (df["matrix_family"] == mf)]
        default_vf[name] = round(float(sub["Vf"].mean()), 3)
    meta = {"sklearn_version": sklearn.__version__, "default_vf": default_vf, "n_rows": int(len(df))}
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)
    return models, meta


_models = None
_meta = None


def _load():
    """Nap model da luu. Neu thieu file hoac khac phien ban scikit-learn -> train lai (vai giay)."""
    global _models, _meta
    if _models is not None:
        return _models, _meta
    try:
        with open(META_PATH) as f:
            meta = json.load(f)
        if meta.get("sklearn_version") != sklearn.__version__:
            raise RuntimeError("scikit-learn version changed")
        models = {col: joblib.load(os.path.join(MODEL_DIR, f"rf_{col}.joblib")) for col in TARGETS}
    except Exception:
        print("ml.py: training material models from dataset (first run only, a few seconds)...")
        models, meta = train_models()
    _models, _meta = models, meta
    return _models, _meta


def predict_material(material_name: str) -> dict:
    """Nhan ten vat lieu ("CFRP", "GFRP", "KEVLAR" hoac ten tuong duong trong ALIASES),
    tra ve dict 9 tinh chat theo don vi SI (Pa) - dung dinh dang clt_engine.m can."""
    if not isinstance(material_name, str):
        raise TypeError(
            "predict_material() can ten vat lieu dang chuoi, vd predict_material(problem.material), "
            f"nhung nhan duoc {type(material_name).__name__}."
        )
    key = ALIASES.get(material_name.strip().lower(), material_name.strip().upper())
    if key not in MATERIAL_DB:
        raise ValueError(
            f"Khong co du lieu cho vat lieu '{material_name}'. "
            f"Cac vat lieu da ho tro: {', '.join(MATERIAL_DB)}."
        )

    models, meta = _load()
    fiber_class, matrix_family = MATERIAL_DB[key]
    X = pd.DataFrame([{"fiber_class": fiber_class, "matrix_family": matrix_family,
                       "Vf": meta["default_vf"][key]}])

    result = {}
    for col, (out_key, scale) in TARGETS.items():
        result[out_key] = float(f"{float(models[col].predict(X)[0]) * scale:.6g}")

    for k, v in result.items():
        if not v > 0:
            raise ValueError(f"Gia tri du doan khong hop ly: {k} = {v}")
    if not 0 < result["nu12"] < 0.5:
        raise ValueError(f"nu12 du doan ngoai khoang hop ly (0, 0.5): {result['nu12']}")
    return result


if __name__ == "__main__":
    for name in ["CFRP", "carbon fiber", "GFRP", "fiberglass", "Kevlar"]:
        print(name, "->", predict_material(name))
