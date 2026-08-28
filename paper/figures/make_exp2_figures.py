import matplotlib.pyplot as plt

BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
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

MODELS = ["Qwen3-4B", "DeepSeek-R1-Distill-7B", "Mistral-7B-Instruct"]
COLORS = [BLUE, ORANGE, AQUA]
DOMAINS = ["Space/\nAstro.", "Medicine/\nBio.", "Climate\nSci.", "Particle\nPhys."]

BY_DOMAIN = {
    "Qwen3-4B": [0.45, 1.00, 0.05, 0.00],
    "DeepSeek-R1-Distill-7B": [0.19, 0.65, 0.41, 0.40],
    "Mistral-7B-Instruct": [0.45, 0.32, 0.90, 0.45],
}
OVERALL = {"Qwen3-4B": 0.375, "DeepSeek-R1-Distill-7B": 0.415, "Mistral-7B-Instruct": 0.333}
ORDER = {
    "Qwen3-4B": (0.35, 0.60),
    "DeepSeek-R1-Distill-7B": (0.469, 0.636),
    "Mistral-7B-Instruct": (0.184, 0.525),
}


def style_axes(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(BASELINE)
    ax.spines["bottom"].set_color(BASELINE)
    ax.tick_params(length=0)


# ---- Figure: source-level bias by domain + overall ----
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.5, 3.6), gridspec_kw={"width_ratios": [2.2, 1]})

x = list(range(len(DOMAINS)))
width = 0.26
for i, model in enumerate(MODELS):
    offs = (i - 1) * width
    vals = BY_DOMAIN[model]
    bars = ax1.bar([xi + offs for xi in x], vals, width, color=COLORS[i], label=model,
                   edgecolor="white", linewidth=0.8)
    for rect, val in zip(bars, vals):
        ax1.text(rect.get_x() + rect.get_width() / 2, val + 0.02, f"{val:.2f}",
                  ha="center", va="bottom", fontsize=10, color=INK,
                  bbox=dict(facecolor="white", edgecolor="none", pad=0.5))

ax1.axhline(0.5, color=MUTED, linewidth=1, linestyle="--", alpha=0.6)
ax1.text(len(DOMAINS) - 0.55, 0.52, "chance (0.50)", fontsize=9.5, color=MUTED)
ax1.set_xticks(x)
ax1.set_xticklabels(DOMAINS, fontsize=11)
ax1.set_ylim(0, 1.12)
ax1.set_ylabel("Source-level bias rate", fontsize=11.5)
ax1.set_title("By domain", fontsize=13, fontweight="bold", pad=8)
ax1.yaxis.grid(True, color=GRID, linewidth=0.9, zorder=0)
ax1.set_axisbelow(True)
style_axes(ax1)

xo = list(range(len(MODELS)))
bars = ax2.bar(xo, [OVERALL[m] for m in MODELS], 0.55, color=COLORS, edgecolor="white", linewidth=0.8)
for rect, m in zip(bars, MODELS):
    val = OVERALL[m]
    ax2.text(rect.get_x() + rect.get_width() / 2, val + 0.02, f"{val:.2f}",
              ha="center", va="bottom", fontsize=10, color=INK, fontweight="bold")
ax2.axhline(0.5, color=MUTED, linewidth=1, linestyle="--", alpha=0.6)
ax2.set_xticks(xo)
ax2.set_xticklabels(["Qwen3-4B", "DeepSeek-\nR1-Distill-7B", "Mistral-7B-\nInstruct"], fontsize=10)
ax2.set_ylim(0, 1.12)
ax2.set_title("Overall", fontsize=13, fontweight="bold", pad=8)
ax2.yaxis.grid(True, color=GRID, linewidth=0.9, zorder=0)
ax2.set_axisbelow(True)
style_axes(ax2)

handles, labels = ax1.get_legend_handles_labels()
fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False,
           bbox_to_anchor=(0.5, 1.06), fontsize=11)

plt.tight_layout(rect=[0, 0, 1, 0.88])
plt.savefig("/Users/mustafa.munir/Personal/llm-source-bias/plans/paper/figures/source_level_bias.pdf", dpi=300, bbox_inches="tight")
plt.savefig("/Users/mustafa.munir/Personal/llm-source-bias/plans/paper/figures/source_level_bias.png", dpi=200, bbox_inches="tight")
plt.close(fig)


# ---- Figure: position-level bias, normal vs reversed ----
fig, ax = plt.subplots(figsize=(6.2, 3.2))

y = list(range(len(MODELS)))
for i, model in enumerate(MODELS):
    normal, reversed_ = ORDER[model]
    ax.plot([normal, reversed_], [i, i], color=COLORS[i], linewidth=2.2, zorder=1)
    ax.scatter([normal], [i], color=COLORS[i], s=90, zorder=2)
    ax.scatter([reversed_], [i], facecolors="white", edgecolors=COLORS[i], linewidths=2.2, s=90, zorder=2)
    ax.text(normal, i + 0.18, f"{normal:.2f}", ha="center", fontsize=10, color=INK, fontweight="bold")
    ax.text(reversed_, i + 0.18, f"{reversed_:.2f}", ha="center", fontsize=10, color=INK, fontweight="bold")

ax.axvline(0.5, color=MUTED, linewidth=1, linestyle="--", alpha=0.6)
ax.set_ylim(-0.5, len(MODELS) - 0.5)
ax.text(0.5, len(MODELS) - 0.62, "chance (50%)", ha="center", fontsize=9.5, color=MUTED)

ax.set_yticks(y)
ax.set_yticklabels(MODELS, fontsize=11)
ax.set_xlim(0, 1.0)
ax.set_xlabel("Rate of picking the first-listed org", fontsize=11.5)
ax.set_title("Position-level bias: normal vs. reversed order", fontsize=13, fontweight="bold", pad=10)
ax.xaxis.grid(True, color=GRID, linewidth=0.9, zorder=0)
ax.set_axisbelow(True)
style_axes(ax)

from matplotlib.lines import Line2D
legend_elems = [
    Line2D([0], [0], marker="o", color="none", markerfacecolor=MUTED, markersize=9, label="normal order"),
    Line2D([0], [0], marker="o", color="none", markerfacecolor="white", markeredgecolor=MUTED, markeredgewidth=2, markersize=9, label="reversed order"),
]
ax.legend(handles=legend_elems, loc="lower right", frameon=False, fontsize=11)

plt.tight_layout()
plt.savefig("/Users/mustafa.munir/Personal/llm-source-bias/plans/paper/figures/position_level_bias.pdf", dpi=300, bbox_inches="tight")
plt.savefig("/Users/mustafa.munir/Personal/llm-source-bias/plans/paper/figures/position_level_bias.png", dpi=200, bbox_inches="tight")
plt.close(fig)

print("saved source_level_bias.pdf/png and position_level_bias.pdf/png")
