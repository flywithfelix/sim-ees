"""
Definition der festen Wegstrecken von den Parkpositionen zur Grenzkontrolle.

Dieses Modul enthält ein Dictionary, das für jede Parkposition (PPOS) die
entsprechende Gehdistanz in Metern zur Grenzkontrollstelle speichert.
"""

PPOS_DISTANCE_M = {
    "01": 165.0,
    "01A": 200.0,
    "01B": 165.0,
    "02": 110.0,
    "02A": 110.0,
    "02B": 70.0,
    "05": 110.0,
    "05A": 110.0,
    "05B": 70.0,
    "06": 120.0,
    "06A": 150.0,
    "06B": 120.0,
    "07": 240.0,
    "07A": 240.0,
    "07B": 220.0,
    "08": 290.0,
    
    # Falls PPOS ohne führende Null kommt:
    "1": 165.0,
    "1A": 200.0,
    "1B": 165.0,
    "2": 110.0,
    "2A": 110.0,
    "2B": 70.0,
    "5": 110.0,
    "5A": 110.0,
    "5B": 70.0,
    "6": 120.0,
    "6A": 150.0,
    "6B": 120.0,
    "7": 240.0,
    "7A": 240.0,
    "7B": 220.0,
    "8": 290.0,
}
