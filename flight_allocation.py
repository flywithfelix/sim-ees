# Zuteilung der Flüge auf Terminals (T1 vs T2)
# PPOS-Werte für T1 und T2. Fallback auf Spalte 'T' (1 -> T1, 2/Null -> T2)
FLIGHT_ALLOCATION = {
    "T1": {
        "ppos": ["01", "01A", "01B", "02", "02A", "02B"],
    },
    "T2": {
        "ppos": ["05", "05A", "05B", "06", "06A", "06B", "07", "07A", "07B", "08"],
    }
}
