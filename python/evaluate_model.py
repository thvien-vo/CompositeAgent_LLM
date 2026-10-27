"""
evaluate_model.py - Danh gia do chinh xac model trong ml.py bang Leave-One-Out Cross-Validation.
Moi lan: train tren tat ca tru 1 mau, du doan mau con lai; lap lai cho moi mau.
Chay: python evaluate_model.py   -> in bang ket qua va ghi model/loocv_results.json
"""
import json
import os

import numpy as np
from sklearn.base import clone
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import LeaveOneOut

from ml import MODEL_DIR, TARGETS, load_training_data, make_pipeline, training_rows


def main():
    df = load_training_data()
    results = {}
    for col in TARGETS:
        X, y = training_rows(df, col)
        preds = np.empty(len(y))
        for tr, te in LeaveOneOut().split(X):
            pipe = clone(make_pipeline())
            pipe.fit(X.iloc[tr], y.iloc[tr])
            preds[te[0]] = pipe.predict(X.iloc[te])[0]
        baseline = np.array([y.drop(i).mean() for i in range(len(y))])  # du doan bang trung binh
        results[col] = {
            "n": int(len(y)),
            "MAE": round(float(mean_absolute_error(y, preds)), 4),
            "MAE_baseline_mean": round(float(mean_absolute_error(y, baseline)), 4),
            "R2": round(float(r2_score(y, preds)), 3),
            "MAPE_pct": round(float(np.mean(np.abs((y - preds) / y)) * 100), 1),
        }
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(os.path.join(MODEL_DIR, "loocv_results.json"), "w") as f:
        json.dump(results, f, indent=2)
    print(f"{'property':9} {'n':>3} {'MAE':>9} {'MAE(mean)':>10} {'R2':>7} {'MAPE%':>6}")
    for col, r in results.items():
        print(f"{col:9} {r['n']:>3} {r['MAE']:>9} {r['MAE_baseline_mean']:>10} {r['R2']:>7} {r['MAPE_pct']:>6}")


if __name__ == "__main__":
    main()
