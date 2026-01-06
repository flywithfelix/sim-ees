from __future__ import annotations
import streamlit as st
from passenger_data import DEFAULT_MIX, MEAN_EASYPASS_S, SD_EASYPASS_S, MEAN_EU_S, SD_EU_S
from passenger_data import (
    MEAN_SSS_VH_REG_S, SD_SSS_VH_REG_S, MEAN_SSS_VH_UNREG_S, SD_SSS_VH_UNREG_S,
    MEAN_SSS_VE_REG_S, SD_SSS_VE_REG_S, MEAN_SSS_VE_UNREG_S, SD_SSS_VE_UNREG_S,
    MEAN_TCN_VH_REG_S_SSS_ENABLED, SD_TCN_VH_REG_S_SSS_ENABLED, MEAN_TCN_VH_UNREG_S_SSS_ENABLED, SD_TCN_VH_UNREG_S_SSS_ENABLED,
    MEAN_TCN_VH_REG_S_SSS_DISABLED, SD_TCN_VH_REG_S_SSS_DISABLED, MEAN_TCN_VH_UNREG_S_SSS_DISABLED, SD_TCN_VH_UNREG_S_SSS_DISABLED,
    MEAN_TCN_VE_REG_S_SSS_ENABLED, SD_TCN_VE_REG_S_SSS_ENABLED, MEAN_TCN_VE_UNREG_S_SSS_ENABLED, SD_TCN_VE_UNREG_S_SSS_ENABLED,
    MEAN_TCN_VE_REG_S_SSS_DISABLED, SD_TCN_VE_REG_S_SSS_DISABLED, MEAN_TCN_VE_UNREG_S_SSS_DISABLED, SD_TCN_VE_UNREG_S_SSS_DISABLED,
)
from session_state_init import init_session_state, save_session_settings, load_session_settings


def _reset_passenger_mix():
    """Callback to reset passenger mix to defaults."""
    for key, val in DEFAULT_MIX.items():
        st.session_state[key] = val
    st.toast("Passagiermix auf Default gesetzt.", icon="✅")


def _reset_all_settings():
    """Callback to reset all settings to defaults."""
    for key, val in DEFAULT_MIX.items():
        st.session_state[key] = val

    defaults = {
        "ees_choice": "0:100",
        "deboard_offset_min": 5, "deboard_window_min": 10,
        "walk_speed_mean_mps": 1.25, "walk_speed_sd_mps": 0.25, "walk_speed_floor_mps": 0.5,
        "sss_enabled_t1": True,
        "sss_enabled_t2": True,
        "cap_sss": 6, "cap_easypass": 6, "cap_eu": 2, "cap_tcn": 2,
        "cap_sss_t1": 4, "cap_easypass_t1": 6, "cap_eu_t1": 2, "cap_tcn_t1": 2,
        "mean_easypass_s": MEAN_EASYPASS_S, "sd_easypass_s": SD_EASYPASS_S,
        "mean_eu_s": MEAN_EU_S, "sd_eu_s": SD_EU_S,
        "process_time_scale_pct": 100,
        "tcn_at_policy": "load",
        "seed": 42,
        "sim_runs": 5,
        "threshold_pax_length_t1": 50, "threshold_pax_length_t2": 50,
        "threshold_wait_s_t1": 60, "threshold_wait_s_t2": 60,
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
        st.session_state[k] = v
    st.toast("Alle Einstellungen wurden auf Standardwerte zurückgesetzt.", icon="✅")


def _load_tcn_defaults_sss_active():
    """Load TCN times for SSS enabled."""
    st.session_state.mean_tcn_vh_reg_s = MEAN_TCN_VH_REG_S_SSS_ENABLED
    st.session_state.sd_tcn_vh_reg_s = SD_TCN_VH_REG_S_SSS_ENABLED
    st.session_state.mean_tcn_vh_unreg_s = MEAN_TCN_VH_UNREG_S_SSS_ENABLED
    st.session_state.sd_tcn_vh_unreg_s = SD_TCN_VH_UNREG_S_SSS_ENABLED
    st.session_state.mean_tcn_ve_reg_s = MEAN_TCN_VE_REG_S_SSS_ENABLED
    st.session_state.sd_tcn_ve_reg_s = SD_TCN_VE_REG_S_SSS_ENABLED
    st.session_state.mean_tcn_ve_unreg_s = MEAN_TCN_VE_UNREG_S_SSS_ENABLED
    st.session_state.sd_tcn_ve_unreg_s = SD_TCN_VE_UNREG_S_SSS_ENABLED
    st.toast("TCN-Zeiten für SSS=aktiv geladen.", icon="⚡")


def _load_tcn_defaults_sss_inactive():
    """Load TCN times for SSS disabled."""
    st.session_state.mean_tcn_vh_reg_s = MEAN_TCN_VH_REG_S_SSS_DISABLED
    st.session_state.sd_tcn_vh_reg_s = SD_TCN_VH_REG_S_SSS_DISABLED
    st.session_state.mean_tcn_vh_unreg_s = MEAN_TCN_VH_UNREG_S_SSS_DISABLED
    st.session_state.sd_tcn_vh_unreg_s = SD_TCN_VH_UNREG_S_SSS_DISABLED
    st.session_state.mean_tcn_ve_reg_s = MEAN_TCN_VE_REG_S_SSS_DISABLED
    st.session_state.sd_tcn_ve_reg_s = SD_TCN_VE_REG_S_SSS_DISABLED
    st.session_state.mean_tcn_ve_unreg_s = MEAN_TCN_VE_UNREG_S_SSS_DISABLED
    st.session_state.sd_tcn_ve_unreg_s = SD_TCN_VE_UNREG_S_SSS_DISABLED
    st.toast("TCN-Zeiten für SSS=inaktiv geladen.", icon="🐢")


def render_settings_sidebar(show_sim_button: bool = False):
    """Renders the full settings UI in the Streamlit sidebar with collapsible sections.
    
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
            st.session_state["mix_tcn_vh"] +
            st.session_state["mix_tcn_ve"]
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
        st.slider("TCN-VH [%]", 0, 100, key="mix_tcn_vh")
        st.slider("TCN-VE [%]", 0, 100, key="mix_tcn_ve")

        st.button("Reset Mix", on_click=_reset_passenger_mix)

        mix_sum = (
            st.session_state["mix_easypass"] +
            st.session_state["mix_eu_manual"] +
            st.session_state["mix_tcn_at"] +
            st.session_state["mix_tcn_vh"] +
            st.session_state["mix_tcn_ve"]
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
        st.slider("Start nach SIBT [min] (Türen öffnen)", 0, 15, key="deboard_offset_min")
        st.slider("Deboarding-Fenster [min]", 1, 30, key="deboard_window_min")

    # Walk speed
    with st.sidebar.expander("Gehgeschwindigkeit"):
        st.number_input("Ø Gehgeschwindigkeit [m/s]", min_value=0.3, step=0.05, key="walk_speed_mean_mps")
        st.number_input("Stdabw. Gehgeschwindigkeit [m/s]", min_value=0.0, step=0.05, key="walk_speed_sd_mps")
        st.number_input("Min. Gehgeschwindigkeit [m/s]", min_value=0.1, step=0.05, key="walk_speed_floor_mps")

    # SSS and Capacities
    with st.sidebar.expander("SSS (Kiosk)"):
        st.checkbox("SSS (Kiosk) T1 aktiv", key="sss_enabled_t1")
        st.checkbox("SSS (Kiosk) T2 aktiv", key="sss_enabled_t2")
        
        st.markdown("---")
        st.caption("Standardwerte für TCN-Prozesszeiten laden:")
        st.button("Werte für SSS=aktiv laden", on_click=_load_tcn_defaults_sss_active, width="stretch")
        st.button("Werte für SSS=inaktiv laden", on_click=_load_tcn_defaults_sss_inactive, width="stretch")

    with st.sidebar.expander("Kapazitäten"):
        st.markdown("**Terminal 1**")
        st.slider("SSS T1", min_value=1, max_value=4, key="cap_sss_t1")
        st.slider("Easypass T1", min_value=1, max_value=6, key="cap_easypass_t1")
        st.slider("EU T1", min_value=1, max_value=4, key="cap_eu_t1")
        st.slider("TCN T1", min_value=1, max_value=6, key="cap_tcn_t1")

        st.markdown("**Terminal 2**")
        st.slider("SSS T2", min_value=1, max_value=6, key="cap_sss")
        st.slider("Easypass T2", min_value=1, max_value=6, key="cap_easypass")
        st.slider("EU T2", min_value=1, max_value=2, key="cap_eu")
        st.slider("TCN T2", min_value=1, max_value=6, key="cap_tcn")

    # Process times (grouped in expanders)
    with st.sidebar.expander("Prozesszeiten (Easypass / EU)"):
        st.number_input("Easypass Ø", min_value=1.0, step=1.0, key="mean_easypass_s")
        st.number_input("Easypass Stdabw.", min_value=0.0, step=1.0, key="sd_easypass_s")
        st.number_input("EU Ø", min_value=1.0, step=1.0, key="mean_eu_s")
        st.number_input("EU Stdabw.", min_value=0.0, step=1.0, key="sd_eu_s")

    with st.sidebar.expander("Prozesszeiten (SSS)"):
        st.markdown("**TCN-VH**")
        st.number_input("SSS VH reg Ø", min_value=1.0, step=1.0, key="mean_sss_vh_reg_s")
        st.number_input("SSS VH reg Stdabw.", min_value=0.0, step=1.0, key="sd_sss_vh_reg_s")
        st.number_input("SSS VH unreg Ø", min_value=1.0, step=1.0, key="mean_sss_vh_unreg_s")
        st.number_input("SSS VH unreg Stdabw.", min_value=0.0, step=1.0, key="sd_sss_vh_unreg_s")
        st.markdown("**TCN-VE**")
        st.number_input("SSS VE reg Ø", min_value=1.0, step=1.0, key="mean_sss_ve_reg_s")
        st.number_input("SSS VE reg Stdabw.", min_value=0.0, step=1.0, key="sd_sss_ve_reg_s")
        st.number_input("SSS VE unreg Ø", min_value=1.0, step=1.0, key="mean_sss_ve_unreg_s")
        st.number_input("SSS VE unreg Stdabw.", min_value=0.0, step=1.0, key="sd_sss_ve_unreg_s")

    with st.sidebar.expander("Prozesszeiten (TCN)"):
        st.markdown("**TCN-VH**")
        st.number_input("TCN VH reg Ø", min_value=1.0, step=1.0, key="mean_tcn_vh_reg_s")
        st.number_input("TCN VH reg Stdabw.", min_value=0.0, step=1.0, key="sd_tcn_vh_reg_s")
        st.number_input("TCN VH unreg Ø", min_value=1.0, step=1.0, key="mean_tcn_vh_unreg_s")
        st.number_input("TCN VH unreg Stdabw.", min_value=0.0, step=1.0, key="sd_tcn_vh_unreg_s")
        st.markdown("**TCN-VE**")
        st.number_input("TCN VE reg Ø", min_value=1.0, step=1.0, key="mean_tcn_ve_reg_s")
        st.number_input("TCN VE reg Stdabw.", min_value=0.0, step=1.0, key="sd_tcn_ve_reg_s")
        st.number_input("TCN VE unreg Ø", min_value=1.0, step=1.0, key="mean_tcn_ve_unreg_s")
        st.number_input("TCN VE unreg Stdabw.", min_value=0.0, step=1.0, key="sd_tcn_ve_unreg_s")

    # Scaling and misc
    with st.sidebar.expander("Skalierung & Sonstiges"):
        st.slider("Prozesszeit-Skalierung [%]", 100, 200, key="process_time_scale_pct", help="Multipliziert alle Prozesszeiten.")
        st.selectbox("TCN-AT Routing", ["load", "queue"], key="tcn_at_policy")
        st.number_input("Random Seed", min_value=0, step=1, key="seed")
        st.slider("Anzahl Simulationsläufe (Monte-Carlo)", min_value=1, max_value=50, key="sim_runs", help="Mehrere Durchläufe erhöhen die statistische Genauigkeit.")

    with st.sidebar.expander("Referenzlinien (für Plots)"):
        st.markdown("**Terminal 1**")
        st.slider("Warteschlange T1", 20, 300, key="threshold_pax_length_t1")
        st.slider("Ø Wartezeit T1 [s]", 0, 120, key="threshold_wait_s_t1")
        st.markdown("**Terminal 2**")
        st.slider("Warteschlange T2", 20, 300, key="threshold_pax_length_t2")
        st.slider("Ø Wartezeit T2 [s]", 0, 120, key="threshold_wait_s_t2")

    st.sidebar.markdown("---")

    # Save / Load buttons at the bottom
    st.sidebar.markdown("**Einstellungen verwalten**")
    c1, c2 = st.sidebar.columns([1, 1])
    with c1:
        if st.sidebar.button("💾 Speichern"):
            keys_to_save = list(DEFAULT_MIX.keys()) + [
                "ees_choice", "deboard_offset_min", "deboard_window_min",
                "walk_speed_mean_mps", "walk_speed_sd_mps", "walk_speed_floor_mps",
                "sss_enabled_t1", "sss_enabled_t2",
                "cap_sss", "cap_easypass", "cap_eu", "cap_tcn",
                "cap_sss_t1", "cap_easypass_t1", "cap_eu_t1", "cap_tcn_t1",
                "mean_easypass_s", "sd_easypass_s", "mean_eu_s", "sd_eu_s",
                "process_time_scale_pct", "tcn_at_policy", "seed", "sim_runs",
                "threshold_pax_length_t1", "threshold_pax_length_t2",
                "threshold_wait_s_t1", "threshold_wait_s_t2",
                "mean_sss_vh_reg_s", "sd_sss_vh_reg_s",
                "mean_sss_vh_unreg_s", "sd_sss_vh_unreg_s",
                "mean_sss_ve_reg_s", "sd_sss_ve_reg_s",
                "mean_sss_ve_unreg_s", "sd_sss_ve_unreg_s",
                "mean_tcn_vh_reg_s", "sd_tcn_vh_reg_s",
                "mean_tcn_vh_unreg_s", "sd_tcn_vh_unreg_s",
                "mean_tcn_ve_reg_s", "sd_tcn_ve_reg_s",
                "mean_tcn_ve_unreg_s", "sd_tcn_ve_unreg_s",
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
