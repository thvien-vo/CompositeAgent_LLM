import pytest

from optimization.material import NCAMP_IM7_8552_CPT, Material, get_material, material_from_dict


def test_im7_8552_measured_values(im7):
    assert im7.name == "IM7/8552" and im7.source.startswith("measured: NCAMP")
    assert im7.E1 == pytest.approx(162.1e9) and im7.Xt == pytest.approx(2212e6) and im7.S == pytest.approx(91.1e6)
    assert im7.warnings == ()
    assert NCAMP_IM7_8552_CPT == pytest.approx(0.18288e-3)


def test_unknown_name_uses_ml_group_with_warning():
    m = get_material("Unobtainium/9999", group="CFRP", verbose=False)
    assert "ML prediction" in m.source and m.warnings


def test_missing_strength_filled_by_ml_with_warning(capsys):
    m = material_from_dict({"E1": 1.6e11, "E2": 9e9, "G12": 5e9, "nu12": 0.3, "Xt": 2e9, "Xc": 1.5e9},
                           name="partial", verbose=True)
    out = capsys.readouterr().out
    for k in ("Yt", "Yc", "S"):
        assert f"{k} of partial not given" in out
        assert getattr(m, k) > 0
    assert m.Xt == 2e9


def test_csv_row_with_missing_strength_uses_ml():
    m = get_material("T650/5250-5", verbose=False)
    assert any("S of T650/5250-5" in w for w in m.warnings)


def test_elastic_constants_required():
    with pytest.raises(ValueError):
        material_from_dict({"E1": 1.6e11, "Xt": 2e9}, verbose=False)
    with pytest.raises(ValueError):
        Material(E1=-1, E2=1, G12=1, nu12=0.3, Xt=1, Xc=1, Yt=1, Yc=1, S=1)
