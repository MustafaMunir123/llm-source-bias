import json
from math import comb

PATH = "experiment-3/eval_results/paired_scores.json"

def exact_mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p_tail = sum(comb(n, i) for i in range(0, k + 1)) * (0.5 ** n)
    return min(2 * p_tail, 1.0)

def main():
    data = json.load(open(PATH))
    for model, d in data.items():
        rows = d["paired_analysis"]["rows"]
        a = b = c = e = 0
        for r in rows:
            nf = r["normal"] == "first"
            rf = r["reversed"] == "first"
            if nf and rf:
                a += 1
            elif nf and not rf:
                b += 1
            elif not nf and rf:
                c += 1
            else:
                e += 1
        p = exact_mcnemar(b, c)
        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
        print(f"{model:<28} n={a+b+c+e:<4} a={a} b={b} c={c} d={e}  p={p:.4f} {sig}")

if __name__ == "__main__":
    main()
