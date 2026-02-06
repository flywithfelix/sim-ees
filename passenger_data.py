"""
Zentrale Konfigurationsdatei für Simulationsparameter.

Diese Datei enthält Standardwerte für Prozesszeiten, Kapazitäten,
Passagiermixe und andere grundlegende Daten, die von der Simulation
verwendet werden.
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
MU_TCN_V_REG_S_SSS_ENABLED = 3.92      # Lognormal-Parameter μ für registrierte TCN-V Passagiere
SIGMA_TCN_V_REG_S_SSS_ENABLED = 0.54   # Lognormal-Parameter σ für registrierte TCN-V Passagiere
MU_TCN_V_UNREG_S_SSS_ENABLED = 3.92    # Lognormal-Parameter μ für unregistrierte TCN-V Passagiere
SIGMA_TCN_V_UNREG_S_SSS_ENABLED = 0.54 # Lognormal-Parameter σ für unregistrierte TCN-V Passagiere

# Fall 2: SSS-Kioske sind deaktiviert
MU_TCN_V_REG_S_SSS_DISABLED = 3.92      # Lognormal-Parameter μ für registrierte TCN-V Passagiere
SIGMA_TCN_V_REG_S_SSS_DISABLED = 0.54   # Lognormal-Parameter σ für registrierte TCN-V Passagiere
MU_TCN_V_UNREG_S_SSS_DISABLED = 3.92    # Lognormal-Parameter μ für unregistrierte TCN-V Passagiere
SIGMA_TCN_V_UNREG_S_SSS_DISABLED = 0.54 # Lognormal-Parameter σ für unregistrierte TCN-V Passagiere

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