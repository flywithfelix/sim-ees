# Default process times (seconds) and standard deviations for stations

# SSS (Kiosk)
MEAN_SSS_S = 34.0
SD_SSS_S = 20.4

# TCN manual - TCN V (SSS enabled) - Lognormal parameters
MU_TCN_V_REG_S_SSS_ENABLED = 3.92
SIGMA_TCN_V_REG_S_SSS_ENABLED = 0.54
MU_TCN_V_UNREG_S_SSS_ENABLED = 3.92
SIGMA_TCN_V_UNREG_S_SSS_ENABLED = 0.54

# TCN manual - TCN V (SSS disabled) - Lognormal parameters
MU_TCN_V_REG_S_SSS_DISABLED = 3.92
SIGMA_TCN_V_REG_S_SSS_DISABLED = 0.54
MU_TCN_V_UNREG_S_SSS_DISABLED = 3.92
SIGMA_TCN_V_UNREG_S_SSS_DISABLED = 0.54

# TCN manual - TCN V - Max value cap
MAX_TCN_V_S = 180.0

# Easypass - Lognormal parameters
MU_EASYPASS_S = 2.76
SIGMA_EASYPASS_S = 0.34
MAX_EASYPASS_S = 90.0

# EU - Lognormal parameters
MU_EU_S = 3.76
SIGMA_EU_S = 0.5
MAX_EU_S = 180.0

# =========================================================
# Bus-Transport (für unbekannte PPOS)
# =========================================================
BUS_CAPACITY = 90
BUS_FILL_TIME_MIN = 7.0
BUS_TRAVEL_TIME_MIN = 2.5

# =========================================================
# Passagiermix – Defaults
# =========================================================
DEFAULT_MIX = {
    "mix_easypass": 49,
    "mix_eu_manual": 21,
    "mix_tcn_at": 15,
    "mix_tcn_v": 15,
}