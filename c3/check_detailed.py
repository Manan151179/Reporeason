import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rankers import rank_detailed

d = json.load(open(os.path.join(HERE, "data", "repos.json"), encoding="utf-8"))
q = d["q1"]
det = rank_detailed(q["query"], q["repos"])

print("query:", q["query"])
print("candidates ranked:", len(det))
for i, r in enumerate(det[:5]):
    print(f"{i+1}. {r['repo']['full_name']:35s} "
          f"score={r['score']:.4f} sum_contrib={sum(r['contributions'].values()):.4f}")
    print("     signals:", {k: round(v, 3) for k, v in r["signals"].items()})

assert all(det[i]["score"] >= det[i+1]["score"] for i in range(len(det)-1)), \
    "FAIL: not sorted best-first"
assert all(abs(r["score"] - sum(r["contributions"].values())) < 1e-6 for r in det), \
    "FAIL: contributions don't sum to score"
print("OK: ranked best-first and contributions sum to score")
