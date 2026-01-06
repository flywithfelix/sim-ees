from __future__ import annotations

import streamlit as st

from passenger_data import (
    DEFAULT_MIX,
    MEAN_SSS_VH_REG_S, SD_SSS_VH_REG_S, MEAN_SSS_VH_UNREG_S, SD_SSS_VH_UNREG_S,
    MEAN_SSS_VE_REG_S, SD_SSS_VE_REG_S, MEAN_SSS_VE_UNREG_S, SD_SSS_VE_UNREG_S,
    MEAN_TCN_VH_REG_S_SSS_ENABLED, SD_TCN_VH_REG_S_SSS_ENABLED, MEAN_TCN_VH_UNREG_S_SSS_ENABLED, SD_TCN_VH_UNREG_S_SSS_ENABLED,
    MEAN_TCN_VH_REG_S_SSS_DISABLED, SD_TCN_VH_REG_S_SSS_DISABLED, MEAN_TCN_VH_UNREG_S_SSS_DISABLED, SD_TCN_VH_UNREG_S_SSS_DISABLED,
    MEAN_TCN_VE_REG_S_SSS_ENABLED, SD_TCN_VE_REG_S_SSS_ENABLED, MEAN_TCN_VE_UNREG_S_SSS_ENABLED, SD_TCN_VE_UNREG_S_SSS_ENABLED,
    MEAN_TCN_VE_REG_S_SSS_DISABLED, SD_TCN_VE_REG_S_SSS_DISABLED, MEAN_TCN_VE_UNREG_S_SSS_DISABLED, SD_TCN_VE_UNREG_S_SSS_DISABLED,
    MEAN_EASYPASS_S, SD_EASYPASS_S, MEAN_EU_S, SD_EU_S,
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
        "cap_sss": 6, "cap_easypass": 6, "cap_eu": 2, "cap_tcn": 2,
        "cap_sss_t1": 6, "cap_easypass_t1": 6, "cap_eu_t1": 2, "cap_tcn_t1": 2,
        "mean_easypass_s": MEAN_EASYPASS_S, "sd_easypass_s": SD_EASYPASS_S,
        "mean_eu_s": MEAN_EU_S, "sd_eu_s": SD_EU_S,
        "process_time_scale_pct": 150,
        "tcn_at_policy": "load",
        "seed": 42,
        "sim_runs": 10,
        "threshold_pax_length_t1": 50, "threshold_pax_length_t2": 50,
        "threshold_wait_s_t1": 60, "threshold_wait_s_t2": 60,
        # SSS/TCN Zeiten (Initialwerte)
        "mean_sss_vh_reg_s": MEAN_SSS_VH_REG_S, "sd_sss_vh_reg_s": SD_SSS_VH_REG_S,
        "mean_sss_vh_unreg_s": MEAN_SSS_VH_UNREG_S, "sd_sss_vh_unreg_s": SD_SSS_VH_UNREG_S,
        "mean_sss_ve_reg_s": MEAN_SSS_VE_REG_S, "sd_sss_ve_reg_s": SD_SSS_VE_REG_S,
        "mean_sss_ve_unreg_s": MEAN_SSS_VE_UNREG_S, "sd_sss_ve_unreg_s": SD_SSS_VE_UNREG_S,
        "mean_tcn_vh_reg_s": MEAN_TCN_VH_REG_S_SSS_ENABLED, "sd_tcn_vh_reg_s": SD_TCN_VH_REG_S_SSS_ENABLED,
        "mean_tcn_vh_unreg_s": MEAN_TCN_VH_UNREG_S_SSS_ENABLED, "sd_tcn_vh_unreg_s": SD_TCN_VH_UNREG_S_SSS_ENABLED,
        "mean_tcn_ve_reg_s": MEAN_TCN_VE_REG_S_SSS_ENABLED, "sd_tcn_ve_reg_s": SD_TCN_VE_REG_S_SSS_ENABLED,
        "mean_tcn_ve_unreg_s": MEAN_TCN_VE_UNREG_S_SSS_ENABLED, "sd_tcn_ve_unreg_s": SD_TCN_VE_UNREG_S_SSS_ENABLED,
    }

    for k, v in defaults.items():
        if k not in st.session_state:
            # Use saved value if present, otherwise use default
            st.session_state[k] = saved.get(k, v)


def save_session_settings(keys: list[str] | None = None) -> None:
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
