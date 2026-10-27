"""
run_demo.py - one-command demo for the presentation (started by ..\run_demo.bat).
  Part 0  environment check: Hugging Face (internet + token), Ollama + models
  Part 1  reference check, ML + MATLAB only: max FI 0.00238, critical ply 4, ABD(1,1) 5.94e7 N/m
  Part 2  agent: problems written in words -> LLM -> ML -> MATLAB -> LLM
  Part 3  RAG: questions about the material database, answers with report number and page
  Part 4  (only with --interactive) the audience types its own problem or question
Options: --offline (only Ollama, no internet)  --no-wait  --lang vi  --parts 1,2,3  --interactive
Everything printed is also saved in ..\logs\demo_YYYYMMDD_HHMMSS.log
"""
import argparse
import datetime
import json
import os
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

PROBLEMS = [
    ("English, symmetric 8-ply carbon laminate (same case as the reference check)",
     "Carbon/epoxy laminate [0/45/-45/90]s, each ply 0.125 mm thick. "
     "In-plane loads: Nx = 1000 N/m, Ny = 500 N/m, Nxy = 100 N/m."),
    ("Vietnamese, glass fibre, kN/m, decimal comma, bending moment - high load, failure expected",
     "Tấm composite sợi thủy tinh/epoxy, xếp lớp [0/±45]s, mỗi lớp dày 0,15 mm. "
     "Tải trọng: Nx = 150 kN/m, Nxy = 40 kN/m, mô-men uốn My = 10 N.m/m."),
]
QUESTIONS = [
    "What is the longitudinal tensile strength Xt of IM7/8552?",
    "Độ bền cắt S của AS4/8552 là bao nhiêu?",
    "Which NCAMP material has the highest Xt?",
    "What is the tensile strength of titanium Ti-6Al-4V?",
]


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)
            st.flush()

    def flush(self):
        for st in self.streams:
            st.flush()


def banner(title):
    print("\n" + "=" * 78 + f"\n  {title}\n" + "=" * 78, flush=True)


WAITED = [0.0]  # seconds spent in countdowns (not counted in the part times)


def wait(seconds, no_wait):
    """Countdown; any key skips it (Windows)."""
    if no_wait or seconds <= 0:
        return
    t0 = time.time()
    try:
        _countdown(seconds)
    finally:
        WAITED[0] += time.time() - t0


def _countdown(seconds):
    try:
        import msvcrt
    except ImportError:
        time.sleep(seconds)
        return
    end = time.time() + seconds
    while time.time() < end:
        sys.__stdout__.write(f"\r  ... next part in {int(end - time.time()) + 1:2d} s (press any key to continue now) ")
        sys.__stdout__.flush()
        if msvcrt.kbhit():
            msvcrt.getwch()
            break
        time.sleep(0.2)
    sys.__stdout__.write("\r" + " " * 78 + "\r")
    sys.__stdout__.flush()


def check_env(offline):
    import llm
    status = {}
    banner("PART 0 - Environment check")
    if offline:
        print("  [--offline] Hugging Face skipped: only the local model (Ollama) is used")
        status["hf"] = False
    elif not os.environ.get("HF_TOKEN"):
        print("  [WARN] HF_TOKEN is not set -> only Ollama can be used")
        status["hf"] = False
    else:
        try:
            req = urllib.request.Request("https://huggingface.co/api/whoami-v2",
                                         headers={"Authorization": f"Bearer {os.environ['HF_TOKEN']}"})
            with urllib.request.urlopen(req, timeout=8) as r:
                json.loads(r.read().decode())
            print(f"  [OK]   Hugging Face reachable, token valid -> main LLM: {llm.HF_MODEL}")
            status["hf"] = True
        except Exception as e:
            print(f"  [WARN] Hugging Face not reachable ({type(e).__name__}) -> the agent will use Ollama")
            status["hf"] = False
    try:
        with urllib.request.urlopen(llm.OLLAMA_URL + "/api/tags", timeout=5) as r:
            names = [m["name"] for m in json.loads(r.read().decode())["models"]]
        print(f"  [OK]   Ollama running at {llm.OLLAMA_URL}")
        for need in (llm.MODEL, "nomic-embed-text"):
            have = any(n == need or n.split(":")[0] == need for n in names)
            print(f"  [{'OK' if have else 'FAIL'}]{'  ' if have else ''} model {need}"
                  + ("" if have else f"   -> run: ollama pull {need}"))
            status[need] = have
        status["ollama"] = True

        def warm():  # load gemma3 + embedding model into memory now, so they answer fast later
            try:
                llm._post("/api/generate", {"model": llm.MODEL, "prompt": "", "keep_alive": "30m"}, timeout=180)
                llm._post("/api/embed", {"model": "nomic-embed-text", "input": ["warm up"], "keep_alive": "30m"},
                          timeout=120)
            except Exception:
                pass
        threading.Thread(target=warm, daemon=True).start()
    except Exception:
        print("  [WARN] Ollama is not running -> start the Ollama app (needed offline and for RAG search)")
        status["ollama"] = False
    if not status["hf"] and not status["ollama"]:
        print("  [FAIL] no LLM available: connect to the internet or start Ollama")
    return status


def part1():
    from schemas import CLTInput
    from ml import predict_material
    from matlab_clt import run_clt
    banner("PART 1 - Reference check (ML + MATLAB, no LLM)")
    problem = CLTInput.model_validate({
        "material": "CFRP",
        "plies": [{"angle": a, "thickness": 0.000125} for a in [0, 45, -45, 90, 90, -45, 45, 0]],
        "loads": {"Nx": 1000, "Ny": 500, "Nxy": 100, "Mx": 0, "My": 0, "Mxy": 0},
    })
    print("  CFRP [0/45/-45/90]s, 8 x 0.125 mm, Nx=1000, Ny=500, Nxy=100 N/m")
    result = run_clt(problem, predict_material("CFRP"))
    fi, ply, a11 = result["max_failure_index"], int(result["critical_ply"]), result["ABD"][0][0]
    ok = abs(fi - 0.00238) < 5e-6 and ply == 4 and abs(a11 - 5.94e7) / 5.94e7 < 1e-3
    print(f"  max_failure_index = {fi:.6f}   (reference 0.00238)")
    print(f"  critical_ply      = {ply}          (reference 4)")
    print(f"  ABD(1,1)          = {a11:.5g} N/m (reference 5.94e7)")
    print(f"  -> {'PASS' if ok else 'FAIL'}")
    return ok


def part2(lang, no_wait):
    import main as agent
    banner("PART 2 - Agent: text -> LLM -> ML -> MATLAB -> LLM")
    results = []
    for i, (title, text) in enumerate(PROBLEMS, 1):
        print(f"\n----- Problem {i}/{len(PROBLEMS)}: {title}")
        print(f"  \"{text}\"")
        try:
            out = agent.main(text, lang=lang)
            agent.print_explanation(out)
            results.append(True)
        except Exception as e:
            print(f"  [FAIL] {type(e).__name__}: {e}")
            results.append(False)
        if i < len(PROBLEMS):
            wait(8, no_wait)
    return all(results)


def part3(no_wait):
    import rag
    banner("PART 3 - RAG: questions about the material database (with sources)")
    ok = True
    for i, q in enumerate(QUESTIONS, 1):
        print(f"\n----- Question {i}/{len(QUESTIONS)}: {q}")
        try:
            rag.print_answer(rag.answer(q))
        except Exception as e:
            print(f"  [FAIL] {type(e).__name__}: {e}")
            ok = False
        if i < len(QUESTIONS):
            wait(6, no_wait)
    return ok


def part4(lang):
    import main as agent
    import rag
    banner("PART 4 - Try your own (Enter on an empty line = quit)")
    while True:
        kind = input("\n  1 = laminate problem (CLT), 2 = material question (RAG), Enter = quit: ").strip()
        if kind not in ("1", "2"):
            return
        text = input("  Type it on one line: ").strip()
        if not text:
            continue
        try:
            if kind == "1":
                agent.print_explanation(agent.main(text, lang=lang))
            else:
                rag.print_answer(rag.answer(text))
        except Exception as e:
            print(f"  [FAIL] {type(e).__name__}: {e}")


def run():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="use only Ollama (no internet)")
    ap.add_argument("--no-wait", action="store_true")
    ap.add_argument("--lang", default="en", choices=["en", "vi"])
    ap.add_argument("--parts", default="1,2,3")
    ap.add_argument("--interactive", action="store_true")
    args = ap.parse_args()
    if args.offline:
        os.environ["LLM_BACKEND"] = "ollama"

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
    log_path = os.path.join(ROOT, "logs", f"demo_{datetime.datetime.now():%Y%m%d_%H%M%S}.log")
    log = open(log_path, "w", encoding="utf-8")
    sys.stdout = Tee(sys.__stdout__, log)

    import llm
    if args.offline:
        llm.BACKEND = "ollama"
    t0 = time.time()
    print(f"COMPOSITE AGENT DEMO  -  {datetime.datetime.now():%Y-%m-%d %H:%M}  -  log: {log_path}")
    status = check_env(args.offline)
    if not status["hf"]:
        llm.BACKEND = "ollama"
    parts = args.parts.split(",")
    summary = {}  # name -> (ok, seconds without the countdowns)

    def timed(name, fn, *a):
        t, w = time.time(), WAITED[0]
        summary[name] = (fn(*a), time.time() - t - (WAITED[0] - w))

    if "1" in parts:
        timed("Part 1 reference check", part1)
        wait(5, args.no_wait)
    if "2" in parts:
        timed("Part 2 agent", part2, args.lang, args.no_wait)
        wait(8, args.no_wait)
    if "3" in parts:
        timed("Part 3 RAG", part3, args.no_wait)
    if args.interactive:
        part4(args.lang)

    banner("SUMMARY")
    for k, (ok, sec) in summary.items():
        print(f"  {k:28} {'OK' if ok else 'FAILED':7} {sec:5.1f} s")
    print(f"  LLM used last: {llm.LAST_BACKEND}")
    print(f"  total time: {time.time() - t0:.0f} s   log: {log_path}")
    try:
        from matlab_clt import close_engine
        close_engine()
    except Exception:
        pass
    log.close()
    sys.stdout = sys.__stdout__


if __name__ == "__main__":
    run()
