from cycler import cycler
import matplotlib.pyplot as plt
# plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Inter"]

COLORS = [
    '#E6194B',
    '#3CB44B',
    '#4363D8',
    '#008080',
    '#911EB4',
    '#42D4F4',
    '#FABEBE',
    '#F58231',
    '#BFEF45',
    '#F032E6', 
]
plt.rcParams['axes.prop_cycle'] = cycler(color=COLORS)