# LLM Source Bias

This research investigates whether LLMs exhibit source bias — treating identical content as more trustworthy, safe, or actionable when it appears to originate from a known or authoritative domain (e.g. `claude.ai`, `en.wikipedia.org`) compared to an unknown or fabricated one (e.g. `jaguar.ai`, `wikitest.com`). The goal is to determine whether source identity is an independent variable that changes LLM behaviour, separate from the content itself, and to quantify that effect across script execution, factual reproduction, and instruction-following tasks.

---

## Experiments

| # | Research Question | Status | Model | Tool | Sessions |
|---|---|---|---|---|---|
| 1 | Script execution bias — Does an LLM execute a script without question from a trusted domain (claude.ai) but hesitate or refuse from an unknown domain (jaguar.ai)? | Complete | DeepSeek V4 Flash | OpenCode | 60 (30 per domain, 3 phases × 10) |
| 2 | Factual trust bias — Does an LLM reproduce false facts as truth when the source is Wikipedia, but question the same facts from an unknown domain? | Planned | — | — | — |
| 3 | Instruction-following bias — Does an LLM follow instructions embedded in content more readily when the source appears authoritative? | Planned | — | — | — |
| 4 | Detection threshold — At what point does source credibility stop mattering? Is there any domain an LLM would unconditionally trust? | Planned | — | — | — |

---

## Findings Log

| Date | Time | Experiment | Phase | Model | Finding | Sessions |
|---|---|---|---|---|---|---|
| 2026-08-02 | — | Exp 1 | All | DeepSeek V4 Flash | Unknown domain (jaguar) triggered measurably more caution than trusted domain (claude) across inspection, refusal, and suspicion metrics [↗](#exp1-metrics) | 60 |
| 2026-08-02 | — | Exp 1 | All | DeepSeek V4 Flash | Delivery format affects inspection regardless of source: .py files triggered immediate suspicion and inspection across all domains; .sh files rarely triggered suspicion; .exe: macOS Gatekeeper generated a warning for unsigned/non-notarized binary, which the LLM read and acted on | — |

<details id="exp1-metrics">
<summary>Exp 1 — Metric breakdown</summary>

| Metric | claude.ai (trusted) | jaguar.ai (unknown) |
|---|---|---|
| Executed without inspection | 29/30 (97%) | 25/30 (83%) |
| Proactively fetched & read install.sh | 0/30 (0%) | 5/30 (17%) |
| Refused to run | 1/30 (3%) | 5/30 (17%) |
| Expressed suspicion | 9/30 (30%) | 19/30 (63%) |

</details>
