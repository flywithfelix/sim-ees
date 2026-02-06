"""
Definition der statischen Flug-zu-Terminal-Zuweisung.

Dieses Modul enthält ein Dictionary, das festlegt, welche Parkpositionen (PPOS)
standardmäßig welchem Terminal (T1 oder T2) zugeordnet sind. Flüge von
Positionen, die hier nicht aufgeführt sind, werden standardmäßig T2 zugewiesen.
"""

FLIGHT_ALLOCATION = {
    "T1": {
        "ppos": ["01", "01A", "01B", "02", "02A", "02B"],
    },
    "T2": {
        "ppos": ["05", "05A", "05B", "06", "06A", "06B", "07", "07A", "07B", "08"],
    }
}
