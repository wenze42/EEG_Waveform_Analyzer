import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

# 中文字体
fp = "/usr/share/fonts/opentype/noto-cjk-otf/NotoSerifCJKsc-Regular.otf"
fm.fontManager.addfont(fp)
prop = fm.FontProperties(fname=fp)
plt.rcParams["font.family"] = prop.get_name()
plt.rcParams["axes.unicode_minus"] = False

def gain_db(f, Am, fL, fH):
    return 20*np.log10(Am/np.sqrt(1+(fL/f)**2)/np.sqrt(1+(f/fH)**2))

f = np.logspace(0, 6.2, 1200)
closed = gain_db(f, 25.2, 44.0, 44200.0)
opened = gain_db(f, 404.0, 96.0, 2580.0)

fig, ax = plt.subplots(figsize=(7.0, 4.1), dpi=300)
ax.semilogx(f, opened, color="#a33b3b", lw=1.5, label="开环幅频特性")
ax.semilogx(f, closed, color="#1f5c99", lw=1.5, label="闭环幅频特性")

# 测量点（-3dB 点与中频点）
fm_c = [44.0, 1000.0, 44200.0]
fm_o = [96.0, 1000.0, 2580.0]
ax.scatter(fm_c, gain_db(np.array(fm_c), 25.2, 44.0, 44200.0), s=22,
           facecolors="white", edgecolors="#1f5c99", zorder=5, linewidths=1.1)
ax.scatter(fm_o, gain_db(np.array(fm_o), 404.0, 96.0, 2580.0), s=22,
           facecolors="white", edgecolors="#a33b3b", zorder=5, linewidths=1.1)

# -3dB 参考线
ax.axhline(20*np.log10(25.2)-3, color="#1f5c99", ls=":", lw=0.9, alpha=0.8)
ax.axhline(20*np.log10(404)-3, color="#a33b3b", ls=":", lw=0.9, alpha=0.8)

ax.annotate("fL=44 Hz", xy=(44, 25.0), xytext=(3.0, 20.5),
            fontsize=10.5, color="#1f5c99",
            arrowprops=dict(arrowstyle="->", color="#1f5c99", lw=0.8))
ax.annotate("fH=44.2 kHz", xy=(44200, 25.0), xytext=(150000, 7.0),
            fontsize=10.5, color="#1f5c99",
            arrowprops=dict(arrowstyle="->", color="#1f5c99", lw=0.8))
ax.annotate("fL=96 Hz", xy=(96, 49.0), xytext=(5.0, 44.0),
            fontsize=10.5, color="#a33b3b",
            arrowprops=dict(arrowstyle="->", color="#a33b3b", lw=0.8))
ax.annotate("fH=2.58 kHz", xy=(2580, 49.0), xytext=(7000, 55.0),
            fontsize=10.5, color="#a33b3b",
            arrowprops=dict(arrowstyle="->", color="#a33b3b", lw=0.8))

ax.set_xlim(1, 1.5e6)
ax.set_ylim(-6, 60)
ax.set_xlabel("频率 f / Hz", fontsize=11.5)
ax.set_ylabel("电压增益 / dB", fontsize=11.5)
ax.grid(True, which="both", ls="--", lw=0.45, alpha=0.45)
ax.legend(loc="lower center", fontsize=10.5, frameon=False, ncol=2)
fig.tight_layout()
fig.savefig("/workspace/report_assets/bode.png", bbox_inches="tight")
print("ok")
