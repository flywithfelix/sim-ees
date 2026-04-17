"""
Zentrale Konfigurationsdatei für Simulationsparameter.

Diese Datei enthält Standardwerte für Prozesszeiten, Kapazitäten,
Passagiermixe, Flug-zu-Terminal-Zuweisungen und andere grundlegende Daten,
die von der Simulation verwendet werden.
"""

# =========================================================
# Prozesszeiten (Standardwerte in Sekunden)
# =========================================================

# --- SSS (Kiosk) ---
# Prozesszeit am SSS-Kiosk (Normalverteilung)
MEAN_SSS_S = 34.0  # Mittelwert der Prozesszeit in Sekunden
SD_SSS_S = 20.4    # Standardabweichung der Prozesszeit in Sekunden

# --- TCN (Manuelle Grenzkontrolle für Drittstaatsangehörige) ---
# Prozesszeiten für TCN-V Passagiere (Lognormalverteilung)
# Die Parameter sind abhängig davon, ob SSS-Kioske genutzt werden oder nicht.

# Fall 1: SSS-Kioske sind aktiviert
MU_TCN_V_S_SSS_ENABLED = 3.92      # Lognormal-Parameter μ für TCN-V Passagiere
SIGMA_TCN_V_S_SSS_ENABLED = 0.54   # Lognormal-Parameter σ für TCN-V Passagiere

# Fall 2: SSS-Kioske sind deaktiviert
MU_TCN_V_S_SSS_DISABLED = 3.92      # Lognormal-Parameter μ für TCN-V Passagiere
SIGMA_TCN_V_S_SSS_DISABLED = 0.54   # Lognormal-Parameter σ für TCN-V Passagiere

# Maximale Prozesszeit für TCN-V, um extreme Ausreißer zu verhindern
MAX_TCN_V_S = 180.0

# --- Easypass (Automatisierte Grenzkontrolle) ---
# Prozesszeit am Easypass (Lognormalverteilung)
MU_EASYPASS_S = 2.76      # Lognormal-Parameter μ in Sekunden
SIGMA_EASYPASS_S = 0.34   # Lognormal-Parameter σ in Sekunden
MAX_EASYPASS_S = 90.0     # Maximale Prozesszeit in Sekunden

# --- EU (Manuelle Grenzkontrolle für EU-Bürger) ---
# Prozesszeit am EU-Schalter (Lognormalverteilung)
MU_EU_S = 3.76      # Lognormal-Parameter μ in Sekunden
SIGMA_EU_S = 0.5    # Lognormal-Parameter σ in Sekunden
MAX_EU_S = 180.0    # Maximale Prozesszeit in Sekunden

# =========================================================
# Deboarding
# =========================================================
# Zeitliche Verzögerung zwischen zwei aufeinanderfolgenden Passagieren beim Deboarding
DEBOARD_DELAY_MIN_S = 2  # Minimale Verzögerung in Sekunden
DEBOARD_DELAY_MAX_S = 8  # Maximale Verzögerung in Sekunden

# =========================================================
# Service Level & Kapazitäten
# =========================================================

# --- TCN Service Level & Kapazität ---
# Definition der Service-Level-Ziele (maximale durchschnittliche Wartezeit in Minuten)
TCN_SERVICE_LEVELS = {
    "SL 1 (<10 min)": 10.0,
    "SL 2 (<20 min)": 20.0,
    "SL 3 (<30 min)": 30.0,
    "SL 4 (<45 min)": 45.0,
}
# Maximale Anzahl an TCN-Schaltern, die die iterative Anpassung öffnen kann
MAX_TCN_CAPACITY_T1 = 6  # Für Terminal 1
MAX_TCN_CAPACITY_T2 = 8  # Für Terminal 2

# --- EU Service Level & Kapazität ---
# Minimale und maximale Anzahl an EU-Schaltern für die iterative Anpassung
MIN_EU_CAPACITY = 1
MAX_EU_CAPACITY = 2

# =========================================================
# Bus-Transport
# =========================================================
# Parameter für den Bustransport von Vorfeldpositionen ohne feste PPOS-Zuweisung
BUS_CAPACITY = 80          # Maximale Anzahl Passagiere pro Bus
BUS_FILL_TIME_MIN = 7.0    # Zeit in Minuten, um einen vollen Bus zu füllen
BUS_TRAVEL_TIME_MIN = 2.5  # Fahrzeit des Busses zur Grenzkontrolle in Minuten

# =========================================================
# Passagiermix (Standardaufteilung in Prozent)
# =========================================================
DEFAULT_MIX = {
    "mix_easypass": 49,   # Anteil der Passagiere, die Easypass nutzen
    "mix_eu_manual": 21,  # Anteil der EU-Bürger, die manuelle Schalter nutzen
    "mix_tcn_at": 15,     # Anteil der TCN-Passagiere (Anhang III), die zu Easypass/EU/TCN geleitet werden
    "mix_tcn_v": 15,      # Anteil der TCN-Passagiere (Visa), die zu SSS/TCN/EU geleitet werden
}

# =========================================================
# Flug-zu-Terminal-Zuweisung
# =========================================================
FLIGHT_ALLOCATION = {
    "T1": {
        "ppos": ["01", "01A", "01B", "02", "02A", "02B"],
    },
    "T2": {
        "ppos": ["05", "05A", "05B", "06", "06A", "06B", "07", "07A", "07B", "08"],
    }
}

# =========================================================
# Gehdistanzen (PPOS -> Grenzkontrolle)
# =========================================================
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

AVG_PPOS_DISTANCE_M = sum(PPOS_DISTANCE_M.values()) / len(PPOS_DISTANCE_M)
API_TERMINAL_PPOS = {
    1: "API_T1",
    2: "API_T2",
}

PPOS_DISTANCE_M.update({
    "API_T1": AVG_PPOS_DISTANCE_M,
    "API_T2": AVG_PPOS_DISTANCE_M,
})

# =========================================================
# Gesamte Session-State Defaults (Zentral)
# =========================================================
DEFAULT_SESSION_STATE = {
    "import_mode": "API-Import",
    **DEFAULT_MIX,
    "deboard_offset_min": 5,
    "deboard_delay_min_s": DEBOARD_DELAY_MIN_S,
    "deboard_delay_max_s": DEBOARD_DELAY_MAX_S,
    "walk_speed_mean_mps": 1.25,
    "walk_speed_sd_mps": 0.25,
    "walk_speed_floor_mps": 0.5,
    "sss_enabled_t1": False,
    "sss_enabled_t2": False,
    "bus_capacity": BUS_CAPACITY,
    "bus_fill_time_min": BUS_FILL_TIME_MIN,
    "bus_travel_time_min": BUS_TRAVEL_TIME_MIN,
    "cap_sss": 6,
    "cap_easypass": 6,
    "cap_sss_t1": 4,
    "cap_easypass_t1": 4,
    "mu_easypass_s": MU_EASYPASS_S,
    "sigma_easypass_s": SIGMA_EASYPASS_S,
    "max_easypass_s": MAX_EASYPASS_S,
    "mu_eu_s": MU_EU_S,
    "sigma_eu_s": SIGMA_EU_S,
    "max_eu_s": MAX_EU_S,
    "process_time_scale_pct": 100,
    "tcn_at_target": "TCN",
    "changeover_s": 8.0,
    "seed": 42,
    "mean_sss_s": MEAN_SSS_S,
    "sd_sss_s": SD_SSS_S,
    "mu_tcn_v_s": MU_TCN_V_S_SSS_ENABLED,
    "sigma_tcn_v_s": SIGMA_TCN_V_S_SSS_ENABLED,
    "max_tcn_v_s": MAX_TCN_V_S,
    "tcn_service_level_key": list(TCN_SERVICE_LEVELS.keys())[2],
    "tcn_min_capacity": 1,
    "max_iterations": 10,
    "max_tcn_capacity_t1": MAX_TCN_CAPACITY_T1,
    "max_tcn_capacity_t2": MAX_TCN_CAPACITY_T2,
    "min_eu_capacity": MIN_EU_CAPACITY,
    "max_eu_capacity": MAX_EU_CAPACITY,
}
