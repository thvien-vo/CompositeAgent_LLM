import os
import matlab.engine

# Thư mục chứa clt_engine.m — tự tính từ vị trí file này, không phụ thuộc
# vào việc bạn chạy "python main.py" từ đâu
MATLAB_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "matlab")

_eng = None  # giữ 1 phiên MATLAB chạy nền, dùng lại cho mọi lần gọi


def _get_engine():
    global _eng
    if _eng is None:
        print("Starting MATLAB engine (this takes 10-30 seconds)...")
        _eng = matlab.engine.start_matlab()
        _eng.cd(MATLAB_FOLDER, nargout=0)  # bao MATLAB biet clt_engine.m nam o dau
        print("MATLAB engine is ready.")
    return _eng


def run_clt(problem, material):
    eng = _get_engine()
    result = eng.clt_engine(problem.model_dump(), material, nargout=1)
    return result


def close_engine():
    global _eng
    if _eng is not None:
        _eng.quit()
        _eng = None