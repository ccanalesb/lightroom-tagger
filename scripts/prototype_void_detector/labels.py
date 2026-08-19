"""PROTOTYPE — THROWAWAY. Ticket #277. The labelled probe set."""

# The four motivating frames from map #275 (ranks 15/16 and two one score lower).
CLASS_B_SEED = [
    "2020-12-14__DSF1511",
    "2020-12-14__DSF1521",
    "2020-12-14__DSF1528",
    "2020-12-14__DSF1534",
]

# Hard negatives that must survive, from #277's acceptance criteria.
HARD_NEGATIVES = [
    "2023-02-08_L1007467",  # Statue of Liberty isolated against darkness
    "2023-02-08_L1007465",
    "2023-02-08_L1007432",
    "2023-02-08_L1007424",
    "2018-02-18__CC12947",  # crescent moon in a grainy night sky
    "2023-01-15_L1007051",  # single leaf on still grey water
]

STAT_COLS = [
    "luma_mean", "luma_std", "luma_p50", "luma_p98", "luma_p999", "luma_max",
    "photosi_contrast", "black_frac_25", "black_frac_38", "lit_frac_25",
    "lit_frac_51", "blown_frac_235", "entropy", "lap_var", "lap_var_norm",
    "tile_max", "tile_std", "tile_lit_frac",
]
