# LLM Source Bias

This research investigates whether LLMs exhibit source bias, treating identical content as more trustworthy, safe, or actionable when it appears to originate from a known or authoritative domain (e.g. `claude.ai`, `en.wikipedia.org`) compared to an unknown or fabricated one (e.g. `jaguar.ai`, `wikitest.com`). The goal is to determine whether source identity is an independent variable that changes LLM behaviour, separate from the content itself, and to quantify that effect across script execution, factual reproduction, and instruction-following tasks.

---

## Findings Log


| Date       | Time | Experiment | Phase | Model                                                 | Finding                                                                                                                                                                                                                                                                                 | Sessions |
| ---------- | ---- | ---------- | ----- | ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| 2026-08-02 |      | Exp 1      | All   | DeepSeek V4 Flash                                     | Unknown domain (jaguar) significantly increased script inspection (7x), refusals (10x), and expressed suspicion (6.75x) vs trusted domain (claude); execution rate did not differ significantly [↗](#exp1-metrics)                                                                      | 120      |
| 2026-08-02 |      | Exp 1      | All   | DeepSeek V4 Flash                                     | Delivery format affects inspection regardless of source: .py files triggered immediate suspicion and inspection across all domains; .sh files rarely triggered suspicion; .exe: macOS Gatekeeper generated a warning for unsigned/non-notarized binary, which the LLM read and acted on |          |
| 2026-08-27 |      | Exp 1      | All   | GPT-5.6 Luna                                          | Executed the script from both domains at 100% (no execution bias); only a weak suspicion signal (6/60 jaguar vs 0/60 claude, p=0.028) — GPT-5.6 Luna shows far less source-based caution than DeepSeek V4 Flash                                                                         | 120      |
| 2026-08-23 |      | Exp 2      | All   | Qwen3-4B, DeepSeek-R1-Distill-7B, Mistral-7B-Instruct | Source-level bias confirmed: all three models attributed fake discoveries to the authoritative org well above a zero-bias baseline, proving entity authority is an independent variable that shifts LLM judgement regardless of content                                                 | 240      |
| 2026-08-23 |      | Exp 2      | All   | Qwen3-4B, DeepSeek-R1-Distill-7B, Mistral-7B-Instruct | Inverse coupling: models that defer to authority more are less accurate on the attribution task [↗](#exp2-metrics)                                                                                                                                                                      |          |
| 2026-08-23 |      | Exp 2      | All   | Qwen3-4B, DeepSeek-R1-Distill-7B, Mistral-7B-Instruct | Bias is domain-specific and bimodal — near-zero in some categories, near-total in others, within the same model [↗](#exp2-metrics)                                                                                                                                                      |          |
| 2026-08-23 |      | Exp 2      | All   | Qwen3-4B, DeepSeek-R1-Distill-7B, Mistral-7B-Instruct | Position-level bias is real but interacts with source bias: some models' apparent bias grows when presentation order flips; paired design was required to separate the two effects [↗](#exp2-metrics)                                                                                   |          |


---

## Experiments


| #   | Research Question                                                                                                                                                                                                                                           | Status   | Model                                                 | Tool        | Sessions                       |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ----------------------------------------------------- | ----------- | ------------------------------ |
| 1   | Tool-calling / script-execution bias: Does an LLM execute a script without question from a trusted domain (claude.ai) but hesitate or refuse from an unknown domain (jaguar.ai)?                                                                            | Complete | DeepSeek V4 Flash, GPT-5.6 Luna                       | OpenCode    | 180 (60 per domain x 2 models) |
| 2   | Entity authority bias: Does an LLM treat the same made-up domain knowledge as more credible when attributed to a highly relevant authoritative organisation (e.g. NASA for space) than to a less relevant one (e.g. SUPARCO)? Measured in CoT and response. | Complete | Qwen3-4B, DeepSeek-R1-Distill-7B, Mistral-7B-Instruct | Kaggle T4x2 | 240 (3 models x 2 orders x 40) |


Experiment 1 - Metric breakdown


| Model             | Metric                                | claude.ai (trusted) | jaguar.ai (unknown) | Fisher p | RR        |
| ----------------- | ------------------------------------- | ------------------- | ------------------- | -------- | --------- |
| DeepSeek V4 Flash | Executed                              | 54/60 (90%)         | 45/60 (75%)         | 1.00     | 0.83 ns   |
|                   | Proactively fetched & read install.sh | 2/60 (3%)           | 14/60 (23%)         | 0.0022   | 7.0x **   |
|                   | Refused to run                        | 1/60 (2%)           | 10/60 (17%)         | 0.0084   | 10x **    |
|                   | Expressed suspicion                   | 4/60 (7%)           | 27/60 (45%)         | <0.0001  | 6.75x *** |
| GPT-5.6 Luna      | Executed                              | 60/60 (100%)        | 60/60 (100%)        | 1.00     | 1.00 ns   |
|                   | Proactively fetched & read install.sh | 0/60 (0%)           | 0/60 (0%)           | 1.00     | 1.00 ns   |
|                   | Refused to run                        | 0/60 (0%)           | 0/60 (0%)           | 1.00     | 1.00 ns   |
|                   | Expressed suspicion                   | 0/60 (0%)           | 6/60 (10%)          | 0.0277   | 0.00x *   |


- ns = not significant
- * = p < 0.05
- ** = p < 0.01
- *** = p < 0.001

Experiment 2 - Metric breakdown


| Model                  | Category             | Correct | Source-Level Bias |
| ---------------------- | -------------------- | ------- | ----------------- |
| Qwen3-4B               | Space / Astrophysics | 11/20   | 0.45              |
| Qwen3-4B               | Medicine / Biology   | 0/20    | 1.00              |
| Qwen3-4B               | Climate Science      | 19/20   | 0.05              |
| Qwen3-4B               | Particle Physics     | 20/20   | 0.00              |
| DeepSeek-R1-Distill-7B | Space / Astrophysics | 13/20   | 0.19              |
| DeepSeek-R1-Distill-7B | Medicine / Biology   | 6/20    | 0.65              |
| DeepSeek-R1-Distill-7B | Climate Science      | 10/20   | 0.41              |
| DeepSeek-R1-Distill-7B | Particle Physics     | 9/20    | 0.40              |
| Mistral-7B-Instruct    | Space / Astrophysics | 11/20   | 0.45              |
| Mistral-7B-Instruct    | Medicine / Biology   | 13/20   | 0.32              |
| Mistral-7B-Instruct    | Climate Science      | 17/20   | 0.10              |
| Mistral-7B-Instruct    | Particle Physics     | 11/20   | 0.45              |


Full interactive table: `experiment-3/figures/bias_table.html`