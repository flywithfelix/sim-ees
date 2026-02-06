from __future__ import annotations

"""
Initialisierung und Verwaltung des Streamlit Session State.

Dieses Modul stellt Funktionen zur Verfügung, um den `st.session_state`
mit Standardwerten zu initialisieren, Einstellungen in eine JSON-Datei zu
speichern und von dort zu laden.
"""
from typing import Optional
import streamlit as st

from passenger_data import (
    DEFAULT_MIX,
    MEAN_SSS_S, SD_SSS_S,
    MU_TCN_V_REG_S_SSS_ENABLED, SIGMA_TCN_V_REG_S_SSS_ENABLED, MU_TCN_V_UNREG_S_SSS_ENABLED,
    SIGMA_TCN_V_UNREG_S_SSS_ENABLED, MU_TCN_V_REG_S_SSS_DISABLED, SIGMA_TCN_V_REG_S_SSS_DISABLED,
    MU_TCN_V_UNREG_S_SSS_DISABLED, SIGMA_TCN_V_UNREG_S_SSS_DISABLED, MAX_TCN_V_S,
    MU_EASYPASS_S, SIGMA_EASYPASS_S, MAX_EASYPASS_S, MU_EU_S, SIGMA_EU_S, MAX_EU_S,
    DEBOARD_DELAY_MIN_S, DEBOARD_DELAY_MAX_S, TCN_SERVICE_LEVELS,
    MAX_TCN_CAPACITY_T1, MAX_TCN_CAPACITY_T2, MIN_EU_CAPACITY, MAX_EU_CAPACITY,
    BUS_CAPACITY, BUS_FILL_TIME_MIN, BUS_TRAVEL_TIME_MIN,
)
import json
from pathlib import Path

SETTINGS_FILE = Path(".streamlit_settings.json")


def init_session_state():
    """
    Initialisiert den `st.session_state` mit Standardwerten.

    Stellt sicher, dass alle für die Anwendung notwendigen Schlüssel im
    Session State vorhanden sind. Falls ein Schlüssel fehlt, wird er entweder
    aus einer gespeicherten Einstellungsdatei (`.streamlit_settings.json`) oder
    aus den hartcodierten Standardwerten geladen.
    """
    # 1. Load saved settings (as fallback for hard defaults)
    saved = load_session_settings()
    
    # 2. Passagiermix-Defaults
    for key, val in DEFAULT_MIX.items():
        if key not in st.session_state:
            st.session_state[key] = saved.get(key, val)

    # 3. Allgemeine Simulationsparameter-Defaults
    defaults = {
        "ees_choice": "0:100",
        "deboard_offset_min": 5,
        "deboard_delay_min_s": DEBOARD_DELAY_MIN_S, "deboard_delay_max_s": DEBOARD_DELAY_MAX_S,
        "walk_speed_mean_mps": 1.25, "walk_speed_sd_mps": 0.25, "walk_speed_floor_mps": 0.5,
        "sss_enabled_t1": True,
        "sss_enabled_t2": True,
        "bus_capacity": BUS_CAPACITY,
        "bus_fill_time_min": BUS_FILL_TIME_MIN,
        "bus_travel_time_min": BUS_TRAVEL_TIME_MIN,
        "cap_sss": 6, "cap_easypass": 6,
        "cap_sss_t1": 4, "cap_easypass_t1": 4,
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
    defaults.update({
        "tcn_service_level_key": list(TCN_SERVICE_LEVELS.keys())[0],
        "tcn_min_capacity": 1,
        "max_iterations": 10,
        "max_tcn_capacity_t1": MAX_TCN_CAPACITY_T1,
        "max_tcn_capacity_t2": MAX_TCN_CAPACITY_T2,
        "min_eu_capacity": MIN_EU_CAPACITY,
        "max_eu_capacity": MAX_EU_CAPACITY,
    })

    for k, v in defaults.items():
        if k not in st.session_state:
            # Use saved value if present, otherwise use default
            st.session_state[k] = saved.get(k, v)


def save_session_settings(keys: Optional[list[str]] = None) -> None:
    """
    Speichert ausgewählte Schlüssel aus dem `st.session_state` in eine JSON-Datei.

    Serialisiert die Werte der angegebenen Schlüssel in die Datei `.streamlit_settings.json`.
    Große oder nicht serialisierbare Objekte werden übersprungen.

    Args:
        keys: Eine optionale Liste von Schlüsseln, die gespeichert werden sollen.
              Wenn `None`, werden alle einfachen Datentypen gespeichert.
    """
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
    """
    Lädt gespeicherte Einstellungen aus der JSON-Datei.

    Returns:
        Ein Dictionary mit den geladenen Einstellungen oder ein leeres Dictionary bei Fehlern.
    """
    if not SETTINGS_FILE.exists():
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
