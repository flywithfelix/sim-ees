from __future__ import annotations
"""
Modul zur Darstellung der Einstellungs-Seitenleiste in Streamlit.

Diese Datei enthält die Logik zum Rendern aller UI-Elemente (Slider,
Checkboxen, etc.) in der Seitenleiste, die zur Konfiguration der
Simulation dienen.
"""
import streamlit as st
from parameter import (
    DEFAULT_MIX,
    DEFAULT_SESSION_STATE,
    MEAN_SSS_S, SD_SSS_S,
    MU_TCN_V_S_SSS_ENABLED, SIGMA_TCN_V_S_SSS_ENABLED, MU_TCN_V_S_SSS_DISABLED, SIGMA_TCN_V_S_SSS_DISABLED, MAX_TCN_V_S,
    MU_EASYPASS_S, SIGMA_EASYPASS_S, MAX_EASYPASS_S, MU_EU_S, SIGMA_EU_S, MAX_EU_S,
    BUS_CAPACITY, BUS_FILL_TIME_MIN, BUS_TRAVEL_TIME_MIN, DEBOARD_DELAY_MIN_S, DEBOARD_DELAY_MAX_S,
    TCN_SERVICE_LEVELS, MAX_TCN_CAPACITY_T1, MAX_TCN_CAPACITY_T2,
    MIN_EU_CAPACITY, MAX_EU_CAPACITY
)


# =========================================================
# Callback-Funktionen für UI-Elemente
# =========================================================

def _reset_all_settings():
    """Callback-Funktion, um alle Einstellungen auf ihre Standardwerte zurückzusetzen."""
    for k, v in DEFAULT_SESSION_STATE.items():
        st.session_state[k] = v
    st.toast("Alle Einstellungen wurden auf Standardwerte zurückgesetzt.", icon="✅")

# =========================================================
# Haupt-Rendering-Funktion
# =========================================================

def render_settings_sidebar(show_sim_button: bool = False):
    """
    Rendert die komplette Einstellungs-Seitenleiste.

    Die Funktion stellt alle für den Benutzer änderbaren Konfigurationsoptionen
    in thematisch gruppierten `st.expander`-Elementen dar. Diese Funktion wurde
    aus der ehemaligen Seite "Einstellungen" extrahiert, damit die Parameter
    auf jeder Seite verfügbar sind.

    Args:
        show_sim_button: Wenn True, wird der "Simulation starten"-Button
            in der Seitenleiste angezeigt.
    """
    st.sidebar.title("Einstellungen")
    
    # Simulation button at the top (if show_sim_button is True)
    if show_sim_button:
        if st.sidebar.button(
            "▶️ Simulation starten",
            type="primary",
            width="stretch",
        ):
            st.session_state["_run_simulation"] = True
        
        st.sidebar.markdown("---")
 
    # Service-Level für die iterative Kapazitätsanpassung
    with st.sidebar.expander("Service Level"):
        st.selectbox(
            "Service Level (TCN & EU)",
            options=list(TCN_SERVICE_LEVELS.keys()),
            key="tcn_service_level_key",
            help="Die Simulation erhöht iterativ die Schalteranzahl für TCN und EU, bis die mittlere Wartezeit der jeweiligen Passagiergruppe in jedem 15-Minuten-Intervall unter diesem Wert liegt."
        )

    # Maximale Kapazitäten für die automatische Anpassung (Passbox)
    with st.sidebar.expander("Passbox"):
        st.markdown("**Maximale Schalterkapazitäten**")
        st.markdown("**TCN**")
        st.number_input("Max. TCN-Schalter T1", min_value=1, step=1, key="max_tcn_capacity_t1", help="Obergrenze für die automatische Anpassung der TCN-Schalter in Terminal 1.")
        st.number_input("Max. TCN-Schalter T2", min_value=1, step=1, key="max_tcn_capacity_t2", help="Obergrenze für die automatische Anpassung der TCN-Schalter in Terminal 2.")
        st.markdown("**EU**")
        st.number_input("Max. EU-Schalter", min_value=1, step=1, key="max_eu_capacity", help="Obergrenze für die automatische Anpassung der EU-Schalter (gilt für beide Terminals).")

    # Aktivierung der SSS-Kioske pro Terminal
    with st.sidebar.expander("SSS (Kiosk)"):
        st.markdown("**Terminal 1**")
        st.checkbox("SSS T1 aktiv", key="sss_enabled_t1", help="Aktiviert/Deaktiviert die SSS-Kioske für Terminal 1. Die Anzahl wird in der `parameter.py` festgelegt.")
        st.markdown("**Terminal 2**")
        st.checkbox("SSS T2 aktiv", key="sss_enabled_t2", help="Aktiviert/Deaktiviert die SSS-Kioske für Terminal 2. Die Anzahl wird in der `parameter.py` festgelegt.")

    # Globale Skalierungs- und Steuerungsparameter
    with st.sidebar.expander("Skalierung & Sonstiges"):
        st.slider("Prozesszeit-Skalierung [%]", 100, 200, key="process_time_scale_pct", help="Globaler Multiplikator für alle Prozesszeiten. Nützlich für Was-wäre-wenn-Analysen.")
        st.selectbox("TCN-AT Ziel", ["EASYPASS", "EU", "TCN"], key="tcn_at_target", help="Leitet TCN-AT Passagiere fest an eine Prozessstelle.")
        st.number_input("Max. Simulations-Durchläufe", min_value=1, max_value=10, step=1, key="max_iterations", help="Maximale Anzahl an Iterationen für die automatische Kapazitätsanpassung, um Endlosschleifen zu verhindern.")

    st.sidebar.markdown("---")

    # Button zum Zurücksetzen aller Einstellungen auf die Standardwerte
    st.sidebar.button("🔄 Alle Einstellungen zurücksetzen", on_click=_reset_all_settings, type="secondary", width="stretch")
