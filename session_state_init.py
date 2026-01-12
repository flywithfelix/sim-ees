from __future__ import annotations

from typing import Optional
import streamlit as st

from passenger_data import (
    DEFAULT_MIX,
    MEAN_SSS_S, SD_SSS_S,
    MU_TCN_V_REG_S_SSS_ENABLED, SIGMA_TCN_V_REG_S_SSS_ENABLED, MU_TCN_V_UNREG_S_SSS_ENABLED,
    SIGMA_TCN_V_UNREG_S_SSS_ENABLED, MU_TCN_V_REG_S_SSS_DISABLED, SIGMA_TCN_V_REG_S_SSS_DISABLED,
    MU_TCN_V_UNREG_S_SSS_DISABLED, SIGMA_TCN_V_UNREG_S_SSS_DISABLED, MAX_TCN_V_S,
    MU_EASYPASS_S, SIGMA_EASYPASS_S, MAX_EASYPASS_S, MU_EU_S, SIGMA_EU_S, MAX_EU_S,
    BUS_CAPACITY, BUS_FILL_TIME_MIN, BUS_TRAVEL_TIME_MIN,
)
import json
from pathlib import Path

SETTINGS_FILE = Path(".streamlit_settings.json")


def init_session_state():
    """Setzt alle Default-Werte im Session State, falls noch nicht vorhanden.
    
    Lädt die Defaults aus Hard-Defaults oder aus der JSON-Datei (gespeicherte Einstellungen).
    Diese Funktion wird auf allen Seiten aufgerufen und füllt fehlende Schlüssel auf.
    """
    # 1. Load saved settings (as fallback for hard defaults)
    saved = load_session_settings()
    
    # 2. Mix Defaults (use saved if present, otherwise defaults)
    for key, val in DEFAULT_MIX.items():
        if key not in st.session_state:
            st.session_state[key] = saved.get(key, val)

    # 3. Allgemeine Parameter Defaults (use saved if present, otherwise defaults)
    defaults = {
        "ees_choice": "0:100",
        "deboard_offset_min": 5, "deboard_window_min": 10,
        "walk_speed_mean_mps": 1.25, "walk_speed_sd_mps": 0.25, "walk_speed_floor_mps": 0.5,
        "sss_enabled_t1": True,
        "sss_enabled_t2": True,
        "bus_capacity": BUS_CAPACITY,
        "bus_fill_time_min": BUS_FILL_TIME_MIN,
        "bus_travel_time_min": BUS_TRAVEL_TIME_MIN,
        "cap_sss": 6, "cap_easypass": 6, "cap_eu": 2, "cap_tcn": 2,
        "cap_sss_t1": 4, "cap_easypass_t1": 4, "cap_eu_t1": 2,
        "mu_easypass_s": MU_EASYPASS_S, "sigma_easypass_s": SIGMA_EASYPASS_S, "max_easypass_s": MAX_EASYPASS_S,
        "mu_eu_s": MU_EU_S, "sigma_eu_s": SIGMA_EU_S, "max_eu_s": MAX_EU_S,
        "process_time_scale_pct": 150,
        "tcn_at_target": "EASYPASS",
        "changeover_s": 0.0,
        "seed": 42,
        # SSS/TCN Zeiten (Initialwerte)
        "mean_sss_s": MEAN_SSS_S, "sd_sss_s": SD_SSS_S,
        "mu_tcn_v_reg_s": MU_TCN_V_REG_S_SSS_ENABLED, "sigma_tcn_v_reg_s": SIGMA_TCN_V_REG_S_SSS_ENABLED,
        "mu_tcn_v_unreg_s": MU_TCN_V_UNREG_S_SSS_ENABLED, "sigma_tcn_v_unreg_s": SIGMA_TCN_V_UNREG_S_SSS_ENABLED,
        "max_tcn_v_s": MAX_TCN_V_S,
    }
    
    intervals = ["06-09", "09-12", "12-15", "15-18", "18-21", "21-00"]
    for interval in intervals:
        defaults[f"cap_tcn_t1_{interval}"] = 2
    for interval in intervals:
        defaults[f"cap_tcn_t2_{interval}"] = 2

    for k, v in defaults.items():
        if k not in st.session_state:
            # Use saved value if present, otherwise use default
            st.session_state[k] = saved.get(k, v)


def save_session_settings(keys: Optional[list[str]] = None) -> None:
    """Save specified keys from session_state to a JSON file. If keys is None, save all simple keys."""
    out: dict = {}
    if keys is None:
        for k, v in st.session_state.items():
            # skip large or unserializable objects
            if isinstance(v, (str, int, float, bool, list, dict)):
                out[k] = v
    else:
        for k in keys:
            v = st.session_state.get(k)
            if isinstance(v, (str, int, float, bool, list, dict)):
                out[k] = v
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_session_settings() -> dict:
    """Return saved settings dict (or empty) without applying them."""
    if not SETTINGS_FILE.exists():
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
