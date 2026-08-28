import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

BLUE = "#2a78d6"
RED = "#e34948"
NEUTRAL = "#f0efec"
INK = "#0b0b0b"
MUTED = "#52514e"

plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Times New Roman", "Times", "DejaVu Serif"]
plt.rcParams["text.color"] = INK

MODELS = ["DeepSeek V4 Flash", "GPT-5.6 Luna", "MiMo V2.5", "GLM-5.3"]
METRICS = ["Executed", "Fetched script", "Refused", "Suspicion"]

# (claude_rate, jaguar_rate, p) per model x metric, values in [0,1]
DATA = {
    "DeepSeek V4 Flash": [(54/60, 45/60, 0.0528), (2/60, 14/60, 0.0022), (1/60, 10/60, 0.0084), (4/60, 27/60, 1.89e-06)],
    "GPT-5.6 Luna":       [(60/60, 60/60, 1.0),    (0/60, 0/60, 1.0),    (0/60, 0/60, 1.0),      (0/60, 6/60, 0.0274)],
    "MiMo V2.5":          [(55/59, 36/60, 2.21e-05), (1/59, 14/60, 0.0005), (4/59, 24/60, 2.21e-05), (6/59, 25/60, 0.0001)],
    "GLM-5.3":            [(58/60, 52/60, 0.0946), (0/60, 10/60, 0.0013), (1/60, 10/60, 0.0084), (0/60, 15/60, 2.25e-05)],
}


def sig_stars(p):
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


diff = np.array([[ (j - c) * 100 for (c, j, p) in DATA[m]] for m in MODELS])
pvals = np.array([[p for (c, j, p) in DATA[m]] for m in MODELS])

cmap = LinearSegmentedColormap.from_list("div", [BLUE, NEUTRAL, RED], N=256)
vmax = 60

fig, ax = plt.subplots(figsize=(6.0, 4.4))
im = ax.imshow(diff, cmap=cmap, vmin=-vmax, vmax=vmax, aspect="auto")

ax.set_xticks(range(len(METRICS)))
ax.set_xticklabels(METRICS, fontsize=11)
ax.set_yticks(range(len(MODELS)))
ax.set_yticklabels(MODELS, fontsize=11)
ax.tick_params(length=0)
for spine in ax.spines.values():
    spine.set_visible(False)

for i in range(len(MODELS)):
    for j in range(len(METRICS)):
        val = diff[i, j]
        star = sig_stars(pvals[i, j])
        text_color = "white" if abs(val) > 35 else INK
        label = f"{val:+.0f}"
        if star:
            label += f"\n{star}"
        ax.text(j, i, label, ha="center", va="center", fontsize=10,
                color=text_color, fontweight="bold" if star else "normal")

# gridlines between cells
ax.set_xticks(np.arange(-0.5, len(METRICS)), minor=True)
ax.set_yticks(np.arange(-0.5, len(MODELS)), minor=True)
ax.grid(which="minor", color="white", linewidth=2)
ax.tick_params(which="minor", length=0)

cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
cbar.set_label("jaguar.ai $-$ claude.ai (pp)", fontsize=10, color=MUTED)
cbar.ax.tick_params(labelsize=9.5, length=0)
cbar.outline.set_visible(False)

ax.set_title("Domain effect on session outcomes",
             fontsize=13, color=INK, pad=9, fontweight="bold")

fig.text(0.5, -0.03,
          "Red = higher on the unknown domain; blue = higher on the trusted domain. "
          "Stars mark significance (* p<.05, ** p<.01, *** p<.001).",
          ha="center", fontsize=9.5, color=MUTED)

plt.tight_layout(rect=[0, 0.04, 1, 1])
plt.savefig("/Users/mustafa.munir/Personal/llm-source-bias/plans/paper/figures/exp1_matrix.pdf", dpi=300, bbox_inches="tight")
plt.savefig("/Users/mustafa.munir/Personal/llm-source-bias/plans/paper/figures/exp1_matrix.png", dpi=200, bbox_inches="tight")
print("saved exp1_matrix.pdf/png")
