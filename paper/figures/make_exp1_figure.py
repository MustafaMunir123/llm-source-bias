import matplotlib.pyplot as plt

BLUE = "#2a78d6"
ORANGE = "#eb6834"
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Times New Roman", "Times", "DejaVu Serif"]
plt.rcParams["text.color"] = INK
plt.rcParams["axes.edgecolor"] = BASELINE
plt.rcParams["axes.labelcolor"] = INK
plt.rcParams["xtick.color"] = MUTED
plt.rcParams["ytick.color"] = MUTED

MODELS = ["DeepSeek V4 Flash", "GPT-5.6 Luna", "MiMo V2.5", "GLM-5.3"]
METRICS = ["Executed", "Fetched\nscript", "Refused", "Suspicion"]

DATA = {
    "DeepSeek V4 Flash": {
        "claude": [54 / 60, 2 / 60, 1 / 60, 4 / 60],
        "jaguar": [45 / 60, 14 / 60, 10 / 60, 27 / 60],
        "p": [0.0528, 0.0022, 0.0084, 1.89e-06],
    },
    "GPT-5.6 Luna": {
        "claude": [60 / 60, 0 / 60, 0 / 60, 0 / 60],
        "jaguar": [60 / 60, 0 / 60, 0 / 60, 6 / 60],
        "p": [1.0, 1.0, 1.0, 0.0274],
    },
    "MiMo V2.5": {
        "claude": [55 / 59, 1 / 59, 4 / 59, 6 / 59],
        "jaguar": [36 / 60, 14 / 60, 24 / 60, 25 / 60],
        "p": [2.21e-05, 0.0005, 2.21e-05, 0.0001],
    },
    "GLM-5.3": {
        "claude": [58 / 60, 0 / 60, 1 / 60, 0 / 60],
        "jaguar": [52 / 60, 10 / 60, 10 / 60, 15 / 60],
        "p": [0.0946, 0.0013, 0.0084, 2.25e-05],
    },
}


def sig_stars(p):
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


fig, axes = plt.subplots(2, 2, figsize=(8.5, 7.8), sharey=True)
x = list(range(len(METRICS)))
width = 0.32

for ax, model in zip(axes.flat, MODELS):
    d = DATA[model]
    claude_vals = [v * 100 for v in d["claude"]]
    jaguar_vals = [v * 100 for v in d["jaguar"]]

    bars_c = ax.bar([i - width / 2 for i in x], claude_vals, width,
                     color=BLUE, label="claude.ai (trusted)",
                     edgecolor="white", linewidth=0.8)
    bars_j = ax.bar([i + width / 2 for i in x], jaguar_vals, width,
                     color=ORANGE, label="jaguar.ai (unknown)",
                     edgecolor="white", linewidth=0.8)

    for rect, val in zip(bars_c, claude_vals):
        ax.text(rect.get_x() + rect.get_width() / 2, val + 2.5, f"{val:.0f}",
                ha="center", va="bottom", fontsize=10, color=INK)
    for rect, val in zip(bars_j, jaguar_vals):
        ax.text(rect.get_x() + rect.get_width() / 2, val + 2.5, f"{val:.0f}",
                ha="center", va="bottom", fontsize=10, color=INK)

    for i, p in enumerate(d["p"]):
        star = sig_stars(p)
        top = max(claude_vals[i], jaguar_vals[i])
        if star != "ns":
            ax.text(i, top + 12, star, ha="center", va="bottom",
                     fontsize=12, color=INK, fontweight="bold")

    ax.set_title(model, fontsize=13, color=INK, pad=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(METRICS, fontsize=11)
    ax.set_ylim(0, 120)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.tick_params(axis="y", labelsize=11)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(BASELINE)
    ax.spines["bottom"].set_color(BASELINE)
    ax.yaxis.grid(True, color=GRID, linewidth=0.9, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)

axes[0, 0].set_ylabel("% of sessions", fontsize=11.5, color=INK)
axes[1, 0].set_ylabel("% of sessions", fontsize=11.5, color=INK)

handles, labels = axes[0, 0].get_legend_handles_labels()
fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False,
           bbox_to_anchor=(0.5, 1.02), fontsize=11)

fig.text(0.5, -0.015,
          "Stars mark Fisher-exact significance vs. claude.ai baseline "
          "(* p<.05, ** p<.01, *** p<.001); \"ns\" = not significant.",
          ha="center", fontsize=9.5, color=MUTED)

plt.tight_layout(rect=[0, 0.02, 1, 0.94])
plt.savefig("/Users/mustafa.munir/Personal/llm-source-bias/plans/paper/figures/exp1_metrics.pdf", dpi=300, bbox_inches="tight")
plt.savefig("/Users/mustafa.munir/Personal/llm-source-bias/plans/paper/figures/exp1_metrics.png", dpi=200, bbox_inches="tight")
print("saved exp1_metrics.pdf/png")
