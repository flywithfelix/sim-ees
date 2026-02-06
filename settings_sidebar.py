from __future__ import annotations
"""
Modul zur Darstellung der Einstellungs-Seitenleiste in Streamlit.

Diese Datei enthält die Logik zum Rendern aller UI-Elemente (Slider,
Checkboxen, etc.) in der Seitenleiste, die zur Konfiguration der
Simulation dienen.
"""
import streamlit as st
from passenger_data import (
    DEFAULT_MIX,
    MEAN_SSS_S, SD_SSS_S,
    MU_TCN_V_REG_S_SSS_ENABLED, SIGMA_TCN_V_REG_S_SSS_ENABLED, MU_TCN_V_UNREG_S_SSS_ENABLED, SIGMA_TCN_V_UNREG_S_SSS_ENABLED,
    MU_TCN_V_REG_S_SSS_DISABLED, SIGMA_TCN_V_REG_S_SSS_DISABLED, MU_TCN_V_UNREG_S_SSS_DISABLED,
    SIGMA_TCN_V_UNREG_S_SSS_DISABLED, MAX_TCN_V_S,
    MU_EASYPASS_S, SIGMA_EASYPASS_S, MAX_EASYPASS_S, MU_EU_S, SIGMA_EU_S, MAX_EU_S,
)
from passenger_data import (
    BUS_CAPACITY, BUS_FILL_TIME_MIN, BUS_TRAVEL_TIME_MIN, DEBOARD_DELAY_MIN_S, DEBOARD_DELAY_MAX_S,
    TCN_SERVICE_LEVELS, MAX_TCN_CAPACITY_T1, MAX_TCN_CAPACITY_T2,
    MIN_EU_CAPACITY, MAX_EU_CAPACITY
)
from session_state_init import init_session_state, save_session_settings, load_session_settings


# =========================================================
# Callback-Funktionen für UI-Elemente
# =========================================================

def _reset_passenger_mix():
    """Callback-Funktion, um den Passagiermix auf Standardwerte zurückzusetzen."""
    for key, val in DEFAULT_MIX.items():
        st.session_state[key] = val
    st.toast("Passagiermix auf Default gesetzt.", icon="✅")


def _reset_all_settings():
    """Callback-Funktion, um alle Einstellungen auf ihre Standardwerte zurückzusetzen."""
    for key, val in DEFAULT_MIX.items():
        st.session_state[key] = val

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
        "process_time_scale_pct": 100,
        "tcn_at_target": "EASYPASS",
        "changeover_s": 0.0,
        "seed": 42,
        "mean_sss_s": MEAN_SSS_S,
        "sd_sss_s": SD_SSS_S,
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
        st.session_state[k] = v
    st.toast("Alle Einstellungen wurden auf Standardwerte zurückgesetzt.", icon="✅")


def _load_tcn_defaults_sss_active():
    """Lädt die Standard-Prozesszeiten für TCN, wenn SSS aktiviert ist."""
    st.session_state.mu_tcn_v_reg_s = MU_TCN_V_REG_S_SSS_ENABLED
    st.session_state.sigma_tcn_v_reg_s = SIGMA_TCN_V_REG_S_SSS_ENABLED
    st.session_state.mu_tcn_v_unreg_s = MU_TCN_V_UNREG_S_SSS_ENABLED
    st.session_state.sigma_tcn_v_unreg_s = SIGMA_TCN_V_UNREG_S_SSS_ENABLED
    st.toast("TCN-Zeiten für SSS=aktiv geladen.", icon="⚡")


def _load_tcn_defaults_sss_inactive():
    """Lädt die Standard-Prozesszeiten für TCN, wenn SSS deaktiviert ist."""
    st.session_state.mu_tcn_v_reg_s = MU_TCN_V_REG_S_SSS_DISABLED
    st.session_state.sigma_tcn_v_reg_s = SIGMA_TCN_V_REG_S_SSS_DISABLED
    st.session_state.mu_tcn_v_unreg_s = MU_TCN_V_UNREG_S_SSS_DISABLED
    st.session_state.sigma_tcn_v_unreg_s = SIGMA_TCN_V_UNREG_S_SSS_DISABLED
    st.toast("TCN-Zeiten für SSS=inaktiv geladen.", icon="🐢")

# =========================================================
# Haupt-Rendering-Funktion
# =========================================================

def render_settings_sidebar(show_sim_button: bool = False):
    """
    Rendert die komplette Einstellungs-Seitenleiste.

    Die Funktion stellt alle Konfigurationsoptionen in thematisch gruppierten
    `st.expander`-Elementen in der Seitenleiste dar.
    
    Args:
        show_sim_button: If True, shows a "Simulation starten" button in the sidebar.
    
    This is a refactor of `pages/2_Einstellungen.py` so settings appear on every page.
    """
    # Ensure defaults exist
    init_session_state()

    st.sidebar.title("Einstellungen")
    
    # Simulation button at the top (if show_sim_button is True)
    if show_sim_button:
        mix_sum = (
            st.session_state["mix_easypass"] +
            st.session_state["mix_eu_manual"] +
            st.session_state["mix_tcn_at"] +
            st.session_state["mix_tcn_v"]
        )
        sim_button_disabled = mix_sum != 100
        if st.sidebar.button(
            "▶️ Simulation starten",
            type="primary",
            disabled=sim_button_disabled,
            width="stretch",
        ):
            st.session_state["_run_simulation"] = True
        
        if sim_button_disabled:
            st.sidebar.warning(f"Passagiermix muss 100% ergeben (aktuell {mix_sum}%)")
        
        st.sidebar.markdown("---")

    # Passenger mix
    with st.sidebar.expander("Passagiermix", expanded=False):
        st.slider("Easypass [%]", 0, 100, key="mix_easypass")
        st.slider("EU-manual [%]", 0, 100, key="mix_eu_manual")
        st.slider("TCN-AT [%]", 0, 100, key="mix_tcn_at")
        st.slider("TCN-V [%]", 0, 100, key="mix_tcn_v")

        st.button("Reset Mix", on_click=_reset_passenger_mix)

        mix_sum = (
            st.session_state["mix_easypass"] +
            st.session_state["mix_eu_manual"] +
            st.session_state["mix_tcn_at"] +
            st.session_state["mix_tcn_v"]
        )
        if mix_sum == 100:
            st.success(f"Summe: {mix_sum}% ✅")
        elif mix_sum < 100:
            st.warning(f"Summe: {mix_sum}% (unter 100%)")
        else:
            st.error(f"Summe: {mix_sum}% ❌ (über 100%)")

    # EES distribution
    with st.sidebar.expander("EES-Verteilung"):
        st.selectbox("EES_registered : EES_unregistered", options=["100:0", "75:25", "50:50", "0:100"], key="ees_choice")

    # Deboarding
    with st.sidebar.expander("Deboarding"):
        st.slider("Start nach BIBT [min] (Türen öffnen)", 0, 15, key="deboard_offset_min")
        st.number_input("Min. Verzögerung pro Pax [s]", min_value=0, step=1, key="deboard_delay_min_s")
        st.number_input("Max. Verzögerung pro Pax [s]", min_value=0, step=1, key="deboard_delay_max_s")
    # Walk speed
    with st.sidebar.expander("Gehgeschwindigkeit"):
        st.number_input("Ø Gehgeschwindigkeit [m/s]", min_value=0.3, step=0.05, key="walk_speed_mean_mps")
        st.number_input("Stdabw. Gehgeschwindigkeit [m/s]", min_value=0.0, step=0.05, key="walk_speed_sd_mps")
        st.number_input("Min. Gehgeschwindigkeit [m/s]", min_value=0.1, step=0.05, key="walk_speed_floor_mps")

    # Bus transport for unknown PPOS
    with st.sidebar.expander("Bus-Transport (unbek. PPOS)"):
        st.number_input("Bus Kapazität [Pax]", min_value=1, step=1, key="bus_capacity")
        st.number_input("Bus Füllzeit [min]", min_value=0.0, step=0.5, key="bus_fill_time_min")
        st.number_input("Bus Fahrzeit [min]", min_value=0.0, step=0.5, key="bus_travel_time_min")

    # SSS and Capacities
    with st.sidebar.expander("SSS (Kiosk)"):
        st.markdown("**Terminal 1**")
        st.checkbox("SSS T1 aktiv", key="sss_enabled_t1")
        st.slider("Anzahl SSS T1", min_value=1, max_value=4, key="cap_sss_t1")
        st.markdown("**Terminal 2**")
        st.checkbox("SSS (Kiosk) T2 aktiv", key="sss_enabled_t2")
        st.slider("Anzahl SSS T2", min_value=1, max_value=6, key="cap_sss")
        st.markdown("---")
        st.caption("Standardwerte für TCN-Prozesszeiten laden:")
        st.button("Werte für SSS=aktiv laden", on_click=_load_tcn_defaults_sss_active, width="stretch")
        st.button("Werte für SSS=inaktiv laden", on_click=_load_tcn_defaults_sss_inactive, width="stretch")

    with st.sidebar.expander("Easypass"):
        st.markdown("**Terminal 1**")
        st.slider("Anzahl Easypass T1", min_value=1, max_value=4, key="cap_easypass_t1")
        st.markdown("**Terminal 2**")
        st.slider("Anzahl Easypass T2", min_value=1, max_value=6, key="cap_easypass")

    with st.sidebar.expander("Service Level"):
        st.selectbox(
            "Service Level (TCN & EU)",
            options=list(TCN_SERVICE_LEVELS.keys()),
            key="tcn_service_level_key",
            help="Die Simulation erhöht iterativ die Schalteranzahl für TCN und EU, bis die mittlere Wartezeit der jeweiligen Passagiergruppe in jedem 15-Minuten-Intervall unter diesem Wert liegt."
        )

    with st.sidebar.expander("Passbox"):
        st.markdown("**Automatische Kapazitätsanpassung**")
        st.markdown("**TCN**")
        st.number_input("Max. TCN-Schalter T1", min_value=1, step=1, key="max_tcn_capacity_t1")
        st.number_input("Max. TCN-Schalter T2", min_value=1, step=1, key="max_tcn_capacity_t2")
        st.markdown("**EU**")
        st.number_input("Max. EU-Schalter", min_value=1, step=1, key="max_eu_capacity")

    with st.sidebar.expander("Prozesszeiten (Easypass / EU)"):
        st.markdown("**Easypass**")
        st.number_input("Easypass (Lognormal μ)", min_value=0.0, step=0.01, format="%.2f", key="mu_easypass_s")
        st.number_input("Easypass (Lognormal σ)", min_value=0.0, step=0.01, format="%.2f", key="sigma_easypass_s")
        st.number_input("Easypass Max-Wert [s]", min_value=1.0, step=1.0, key="max_easypass_s")
        st.markdown("---")
        st.markdown("**EU**")
        st.number_input("EU (Lognormal μ)", min_value=0.0, step=0.01, format="%.2f", key="mu_eu_s")
        st.number_input("EU (Lognormal σ)", min_value=0.0, step=0.01, format="%.2f", key="sigma_eu_s")
        st.number_input("EU Max-Wert [s]", min_value=1.0, step=1.0, key="max_eu_s")

    with st.sidebar.expander("Prozesszeiten (SSS)"):
        st.number_input("SSS Ø", min_value=1.0, step=1.0, key="mean_sss_s")
        st.number_input("SSS Stdabw.", min_value=0.0, step=1.0, key="sd_sss_s")

    with st.sidebar.expander("Prozesszeiten (TCN)"):
        st.markdown("**TCN-V**")
        st.number_input("TCN V reg (Lognormal μ)", min_value=0.0, step=0.01, format="%.2f", key="mu_tcn_v_reg_s")
        st.number_input("TCN V reg (Lognormal σ)", min_value=0.0, step=0.01, format="%.2f", key="sigma_tcn_v_reg_s")
        st.number_input("TCN V unreg (Lognormal μ)", min_value=0.0, step=0.01, format="%.2f", key="mu_tcn_v_unreg_s")
        st.number_input("TCN V unreg (Lognormal σ)", min_value=0.0, step=0.01, format="%.2f", key="sigma_tcn_v_unreg_s")
        st.number_input("TCN V Max-Wert [s]", min_value=1.0, step=1.0, key="max_tcn_v_s", help="Verhindert extreme Ausreißer der Lognormalverteilung.")

    # Scaling and misc
    with st.sidebar.expander("Skalierung & Sonstiges"):
        st.slider("Prozesszeit-Skalierung [%]", 100, 200, key="process_time_scale_pct", help="Multipliziert alle Prozesszeiten.")
        st.selectbox("TCN-AT Ziel", ["EASYPASS", "EU", "TCN"], key="tcn_at_target", help="Leitet TCN-AT Passagiere fest an eine Prozessstelle.")
        st.number_input("Schalter-Wechselzeit [s]", min_value=0.0, step=0.5, key="changeover_s", help="Zeitlücke zwischen Passagieren an einem Schalter.")
        st.number_input("Max. Simulations-Durchläufe", min_value=1, max_value=10, step=1, key="max_iterations")
        st.number_input("Random Seed", min_value=0, step=1, key="seed")

    st.sidebar.markdown("---")

    # Save / Load buttons at the bottom
    st.sidebar.markdown("**Einstellungen verwalten**")
    c1, c2 = st.sidebar.columns([1, 1])
    with c1:
        if st.sidebar.button("💾 Speichern"):
            keys_to_save = list(DEFAULT_MIX.keys()) + [ "ees_choice", "deboard_offset_min",
                "deboard_delay_min_s", "deboard_delay_max_s",
                "walk_speed_mean_mps", "walk_speed_sd_mps", "walk_speed_floor_mps",
                "bus_capacity", "bus_fill_time_min", "bus_travel_time_min",
                "sss_enabled_t1", "sss_enabled_t2",
                "cap_sss", "cap_easypass",
                "cap_sss_t1", "cap_easypass_t1",
                "mu_easypass_s", "sigma_easypass_s", "max_easypass_s",
                "mu_eu_s", "sigma_eu_s", "max_eu_s",
                "process_time_scale_pct", "tcn_at_target", "changeover_s", "seed",
                "mean_sss_s", "sd_sss_s",
                "mu_tcn_v_reg_s", "sigma_tcn_v_reg_s",
                "mu_tcn_v_unreg_s", "sigma_tcn_v_unreg_s",
                "max_tcn_v_s",
                "tcn_service_level_key", "max_iterations",
                "max_tcn_capacity_t1", "max_tcn_capacity_t2",
                "max_eu_capacity",
            ]
            save_session_settings(keys_to_save)
            st.sidebar.success("✅ Einstellungen gespeichert.")
    with c2:
        if st.sidebar.button("📂 Laden"):
            data = load_session_settings()
            for k, v in data.items():
                if k not in st.session_state:
                    st.session_state[k] = v
            try:
                st.experimental_rerun()
            except Exception:
                pass

    st.sidebar.button("🔄 Zurücksetzen", on_click=_reset_all_settings, type="secondary", width="stretch")
