from __future__ import annotations

__doc__ = """
Hauptanwendung der EES-Simulations-App.

Diese Datei ist der Haupteinstiegspunkt für die Streamlit-Anwendung. Sie
behandelt das Hochladen und Parsen von Flugplänen, die Interaktion mit dem
Benutzer zur Auswahl von Flügen, die Orchestrierung der Simulationsläufe und
die Darstellung der Ergebnisse in Form von Metriken, Tabellen und Diagrammen.
"""
import pandas as pd
import streamlit as st

from engine import SimConfig, run_simulation
from passenger_data import (
    DEFAULT_MIX,
    MEAN_SSS_S, SD_SSS_S,
    MU_TCN_V_REG_S_SSS_ENABLED, SIGMA_TCN_V_REG_S_SSS_ENABLED, MU_TCN_V_UNREG_S_SSS_ENABLED,
    SIGMA_TCN_V_UNREG_S_SSS_ENABLED,
    MU_TCN_V_REG_S_SSS_DISABLED, SIGMA_TCN_V_REG_S_SSS_DISABLED, MU_TCN_V_UNREG_S_SSS_DISABLED,
    SIGMA_TCN_V_UNREG_S_SSS_DISABLED, MAX_TCN_V_S,
    MU_EASYPASS_S, SIGMA_EASYPASS_S, MAX_EASYPASS_S, MU_EU_S, SIGMA_EU_S, MAX_EU_S,
)
from passenger_data import (
    TCN_SERVICE_LEVELS
)
from typ4_defaults import DEFAULT_EPAX_BY_TYP4
from flight_allocation import FLIGHT_ALLOCATION


# =========================================================
# Initialisierung
# =========================================================
from session_state_init import init_session_state
from plotting import build_wait_time_timeseries_rolling, build_wait_time_timeseries_by_group_rolling


# =========================================================
# Datenverarbeitung und Parsing
# =========================================================
def read_csv_auto(uploaded) -> pd.DataFrame:
    """
    Liest eine hochgeladene CSV- oder XLSX-Datei robust ein.

    Erkennt das Dateiformat am Namen und versucht bei CSV-Dateien
    automatisch verschiedene Trennzeichen (;, ,).

    Args:
        uploaded: Das von `st.file_uploader` zurückgegebene File-Objekt.

    Returns:
        Ein pandas DataFrame mit den eingelesenen Daten.
    """
    name = getattr(uploaded, "name", "") or ""

    # Excel-Erkennung
    if name.lower().endswith(".xlsx"):
        if hasattr(uploaded, "seek"):
            uploaded.seek(0)
        return pd.read_excel(uploaded)

    # CSV: Reihenfolge: pandas' automatische Erkennung (sep=None, engine='python'),
    # dann explizit ';' und ','.
    for sep in (None, ';', ','):
        try:
            if hasattr(uploaded, "seek"):
                uploaded.seek(0)
            if sep is None:
                df = pd.read_csv(uploaded, sep=None, engine="python")
            else:
                df = pd.read_csv(uploaded, sep=sep)
            return df
        except Exception:
            continue
    # Fallback: einfache read_csv (lässt Ausnahme durch)
    if hasattr(uploaded, "seek"):
        uploaded.seek(0)
    return pd.read_csv(uploaded)

# Liste alle gefundenen Flüge auf, bei denen PK auf Ja gesetzt ist
@st.cache_data
def parse_flights_csv_fixed(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parst und validiert den Inhalt eines Flugplan-DataFrames.

    Diese Funktion extrahiert die benötigten Spalten, konvertiert Datentypen,
    behandelt fehlende Werte und berechnet die finale Passagierzahl (SPAX)
    basierend auf einer Prioritätenlogik (APAX > EPAX > Default).

    Args:
        df: Der rohe DataFrame, der aus der hochgeladenen Datei gelesen wurde.

    Returns:
        Ein bereinigter und sortierter DataFrame, der für die Simulation bereit ist.
    """
    needed = ["BIBT", "FLN", "PPOS", "PK", "EPAX", "Typ4", "T"]
    missing = set(needed) - set(df.columns)
    if missing:
        raise ValueError(f"CSV fehlt Spalten: {missing}")

    out = df[needed].copy()
    out["BIBT"] = pd.to_datetime(out["BIBT"], dayfirst=True, errors="coerce")
    out["FLN"] = out["FLN"].astype(str).str.strip()
    # Fehlende PPOS konsistent behandeln: NaN/Leer -> 'unbekannt'
    out["PPOS"] = out["PPOS"].fillna("unbekannt").astype(str).str.strip()
    out.loc[out["PPOS"] == "", "PPOS"] = "unbekannt"

    # EPAX robust einlesen (kann leer sein) — falls vorhanden, numeric, sonst NaN
    out["EPAX"] = pd.to_numeric(out["EPAX"], errors="coerce")

    # Optional: APAX falls vorhanden einlesen (kann leer sein)
    if "APAX" in df.columns:
        out["APAX"] = pd.to_numeric(df["APAX"], errors="coerce")
    else:
        out["APAX"] = pd.NA

    # Optional: ADEP3 falls vorhanden einlesen
    if "ADEP3" in df.columns:
        out["ADEP3"] = df["ADEP3"].astype(str).str.strip()
    else:
        out["ADEP3"] = pd.NA

    out["Typ4"] = out["Typ4"].astype(str).str.strip()

    # T (verpflichtend) - als Integer ohne Dezimalstelle
    out["T"] = pd.to_numeric(out["T"], errors="coerce").astype("Int64")

    out["PK"] = out["PK"].astype(str).str.strip().str.upper()
    out = out[out["PK"].isin(["JA", "J", "YES", "Y", "TRUE", "1"])]

    # SPAX berechnen: Priorität APAX > EPAX > Dictionary-Fallback
    out["SPAX"] = None
    for idx, r in out.iterrows():
        spax_val = None
        # 1. APAX prüfen
        if "APAX" in r.index and pd.notna(r.get("APAX")):
            try:
                spax_val = int(r["APAX"])
            except Exception:
                spax_val = None
        # 2. EPAX prüfen
        if spax_val is None and pd.notna(r.get("EPAX")):
            try:
                spax_val = int(r["EPAX"])
            except Exception:
                spax_val = None
        # 3. Dictionary-Fallback
        if spax_val is None:
            spax_val = DEFAULT_EPAX_BY_TYP4.get(r["Typ4"], 100)
        out.at[idx, "SPAX"] = int(spax_val)

    return out.sort_values("BIBT")


def assign_gks(df: pd.DataFrame) -> pd.DataFrame:
    """
    Weist jedem Flug ein Terminal (T1/T2) zu.

    Die Zuweisung erfolgt primär basierend auf der Parkposition (PPOS) gemäß
    der Konfiguration in `flight_allocation.py`. Flüge ohne feste PPOS-Zuweisung
    werden standardmäßig T2 zugewiesen.
    """
    def get_terminal(ppos):
        ppos_val = str(ppos)
        if ppos_val in FLIGHT_ALLOCATION["T1"]["ppos"]:
            return "T1"
        # T2 ist der Standard für alles andere, einschließlich unbekannter PPOS
        return "T2"

    df['GKS'] = df['PPOS'].apply(get_terminal)
    return df

# Liste alle Flüge für die Simulation auf, basierend auf ausgewählten FLN
def flights_to_sim_input(df_selected: pd.DataFrame):
    """
    Konvertiert einen DataFrame ausgewählter Flüge in das für die Simulation benötigte Format.

    Args:
        df_selected: DataFrame mit den für die Simulation ausgewählten Flügen.

    Returns:
        Ein Tupel bestehend aus einer Liste von Flight-Dictionaries, dem
        Startzeitpunkt t0, dem DataFrame und der Anzahl der Flüge mit Fallback-Pax-Zahl.
    """
    df2 = df_selected.copy()
    if df2.empty:
        return [], None, df2, 0

    t0 = df2["BIBT"].min()
    df2["t_arr_min"] = (df2["BIBT"] - t0).dt.total_seconds() / 60.0

    flights = []
    # Default-Dictionary: aus externem Mapping (falls Typ4 nicht in Mapping: Fallback 100)
    default_epax_by_typ4 = DEFAULT_EPAX_BY_TYP4

    # Ermitteln, wie viele Zeilen weder APAX noch EPAX haben -> Fallback
    if "APAX" in df2.columns:
        fallback_mask = df2["APAX"].isna() & df2["EPAX"].isna()
    else:
        fallback_mask = df2["EPAX"].isna()
    fallback_count = int(fallback_mask.sum())

    for idx, r in df2.iterrows():
        # SPAX direkt aus der Spalte verwenden (bereits in parse_flights_csv_fixed berechnet)
        spax = int(r["SPAX"]) if pd.notna(r.get("SPAX")) else 100

        term = r["GKS"]

        flights.append({
            "flight_key": f"{r['BIBT']:%Y%m%d-%H%M}_{r['PPOS']}_{r['FLN']}_{idx}",
            "fln": r["FLN"],
            "ppos": r["PPOS"],
            "spax": spax,
            "acft": r["Typ4"],
            "t_arr_min": float(r["t_arr_min"]),
            "terminal": term,
        })

    return flights, t0, df2, fallback_count


# =========================================================
# App-Layout und UI-Logik
# =========================================================
st.set_page_config(page_title="SIM EES", layout="wide", initial_sidebar_state="expanded")
st.title("Simulation des EES-Prozesses am Flughafen")

# Initialisiere Defaults (wichtig, falls User Settings noch nicht besucht hat)
init_session_state()
# Render settings in the sidebar (migrated from pages/2_Einstellungen.py)
from settings_sidebar import render_settings_sidebar
render_settings_sidebar(show_sim_button=True)


def get_tcn_schedule_breaches(df_res, t0, service_level_min, window_min=15):
    """Analysiert TCN-Wartezeiten und identifiziert Service-Level-Verletzungen.

    Args:
        df_res: DataFrame mit den Ergebnissen eines Simulationslaufs.
        t0: Startzeitpunkt der Simulation.
        service_level_min: Die maximale erlaubte mittlere Wartezeit in Minuten.
        window_min: Die Fenstergröße für den gleitenden Mittelwert.

    Returns:
        Eine Liste von 15-Minuten-Intervallen (als Strings), in denen der Service Level verletzt wurde.
    """
    if df_res.empty:
        return []

    # Berechne die rollierende mittlere Wartezeit für die TCN-Passagiergruppe.
    # Dies berücksichtigt die gesamte Wartezeit (wait_total), egal an welchem Schalter.
    ts_wait_tcn_group = build_wait_time_timeseries_by_group_rolling(df_res, t0, ["TCN_V", "TCN_AT"], window_min=window_min, step_min=5)

    # Finde alle Zeitpunkte, an denen die mittlere Wartezeit den Schwellenwert überschreitet
    breached_times = ts_wait_tcn_group[ts_wait_tcn_group["mean_wait"] > service_level_min]

    if breached_times.empty:
        return []

    # Konvertiere die relativen Minuten in absolute Zeitstempel
    breached_timestamps = t0 + pd.to_timedelta(breached_times["t_min"], unit="m")

    # Finde die einzigartigen Stunden-Intervalle (z.B. "06-09"), die betroffen sind
    breached_intervals = set()

    for ts in breached_timestamps:
        # Runde auf das 15-Minuten-Intervall ab
        start_of_interval = ts.floor('15min')
        end_of_interval = start_of_interval + pd.Timedelta(minutes=15)
        
        # Formatieren des Schlüssels, z.B. "08:15-08:30"
        # Sonderfall für Mitternacht
        end_str = "00:00" if end_of_interval.time() == pd.Timestamp('00:00').time() and end_of_interval.date() > start_of_interval.date() else end_of_interval.strftime('%H:%M')
        interval_key = f"{start_of_interval.strftime('%H:%M')}-{end_str}"
        breached_intervals.add(interval_key)
    return list(breached_intervals)

def get_eu_schedule_breaches(df_res, t0, service_level_min, window_min=15):
    """Analysiert EU-Wartezeiten und identifiziert Service-Level-Verletzungen.

    Args:
        df_res: DataFrame mit den Ergebnissen eines Simulationslaufs.
        t0: Startzeitpunkt der Simulation.
        service_level_min: Die maximale erlaubte mittlere Wartezeit in Minuten.
        window_min: Die Fenstergröße für den gleitenden Mittelwert.

    Returns:
        Eine Liste von 15-Minuten-Intervallen (als Strings), in denen der Service Level verletzt wurde.
    """
    if df_res.empty:
        return []

    # Berechne die rollierende mittlere Wartezeit für die EU_MANUAL-Passagiergruppe.
    ts_wait_eu_group = build_wait_time_timeseries_by_group_rolling(df_res, t0, ["EU_MANUAL"], window_min=window_min, step_min=5)

    breached_times = ts_wait_eu_group[ts_wait_eu_group["mean_wait"] > service_level_min]

    if breached_times.empty:
        return []

    breached_timestamps = t0 + pd.to_timedelta(breached_times["t_min"], unit="m")
    breached_intervals = set()
    for ts in breached_timestamps:
        start_of_interval = ts.floor('15min')
        end_of_interval = start_of_interval + pd.Timedelta(minutes=15)
        end_str = "00:00" if end_of_interval.time() == pd.Timestamp('00:00').time() and end_of_interval.date() > start_of_interval.date() else end_of_interval.strftime('%H:%M')
        interval_key = f"{start_of_interval.strftime('%H:%M')}-{end_str}"
        breached_intervals.add(interval_key)
    return list(breached_intervals)
# Ensure Einstellungen page reloads saved settings when arriving from Home
st.session_state["_settings_loaded"] = False


def clear_results():
    """Löscht zwischengespeicherte Simulationsergebnisse aus dem Session State."""
    keys = ["last_df_res_t1", "last_df_res_t2", "last_t0", "last_df_selected", "last_cfg_t1", "last_cfg_t2", "edited_df"]
    for k in keys:
        st.session_state.pop(k, None)

# Visual frame for upload section using expander (always expanded)
with st.expander("📋 Flugplan importieren", expanded=True):
    # --- Sektion für den Datei-Upload ---
    uploaded = st.file_uploader(
        "Flugplan hochladen (CSV oder XLSX, Pflichtspalten: BIBT, FLN, ADEP3, PPOS, Typ4, EPAX, APAX, T, PK )",
        type=["csv", "xlsx"],
        key="flight_plan_uploader",
    )

if uploaded is not None:
    # Prüfen, ob sich die Datei geändert hat (anhand Name/Größe)
    # Bevor wir teures Parsing machen.
    file_id = f"{uploaded.name}_{uploaded.size}"
    if st.session_state.get("last_file_id") != file_id:
        try:
            df_new = parse_flights_csv_fixed(read_csv_auto(uploaded))
            st.session_state["last_file_id"] = file_id
            st.session_state["current_df"] = df_new
            clear_results()
        except Exception as e:
            st.error(f"Datei konnte nicht verarbeitet werden: {e}")
            st.stop()

if "current_df" in st.session_state:
    df_all = st.session_state["current_df"]
    if uploaded is None:
        st.info(f"Verwende geladene Daten ({len(df_all)} Flüge). Ziehen Sie eine neue Datei hierher, um zu aktualisieren.")
else:
    st.info("Bitte Datei (CSV oder XLSX) hochladen.")
    st.stop()

# GKS-Spalte hinzufügen
df_all = assign_gks(df_all)

# Spaltenreihenfolge robust setzen: gewünschte Reihenfolge zuerst, übrige Spalten anhängen
desired_cols = ["BIBT", "FLN", "ADEP3", "Typ4", "EPAX", "APAX", "SPAX", "PPOS", "GKS", "T", "PK"]
new_order = [c for c in desired_cols if c in df_all.columns] + [c for c in df_all.columns if c not in desired_cols]
df_all = df_all[new_order]

fln_all = sorted(df_all["FLN"].unique().tolist())
if not fln_all:
    st.warning("Keine Flüge nach PK-Filter vorhanden.")
    st.stop()


# =========================================================
# Hauptsteuerelemente (Flugauswahl)
# =========================================================
st.subheader("Flüge für Simulation auswählen")

# Warnen, wenn für einige Zeilen weder APAX noch EPAX vorhanden waren und Default verwendet wurde
if "APAX" in df_all.columns:
    fallback_mask_all = df_all["APAX"].isna() & df_all["EPAX"].isna()
else:
    fallback_mask_all = df_all["EPAX"].isna()
fallback_count_all = int(fallback_mask_all.sum())

if fallback_count_all > 0:
    st.warning(f"{fallback_count_all} Flüge ohne APAX/EPAX — Standardwert für Passagierzahl wird verwendet.")

# Prepare dataframe for editor. Add a 'select' column.
# Reset if the underlying file has changed (by checking if 'edited_df' is missing).
if "edited_df" not in st.session_state:
    df_editable = df_all.copy()
    df_editable.insert(0, "Aktiv", True)
    st.session_state["edited_df"] = df_editable

# Get a list of columns to disable, all except the selection and GKS columns
df_before_edit = st.session_state["edited_df"]
disabled_cols = [c for c in df_all.columns if c != 'GKS'] # Keep GKS editable

edited_df = st.data_editor(
    df_before_edit,
    disabled=disabled_cols,
    hide_index=True,
    column_config={
        "BIBT": st.column_config.DatetimeColumn(
            "BIBT",
            format="DD.MM.YYYY HH:mm",
        ),
        "Aktiv": st.column_config.CheckboxColumn(
            "Aktiv",
            default=True,
        ),
        "GKS": st.column_config.SelectboxColumn(
            "GKS",
            help="Manuelle Zuweisung zu Terminal 1 oder 2. Nur für Flüge ohne feste PPOS-Zuweisung änderbar.",
            options=["T1", "T2"],
            required=True,
        ),
    },
    width="stretch"
)

# --- Post-edit validation for GKS column ---
locked_ppos = set(FLIGHT_ALLOCATION["T1"]["ppos"]) | set(FLIGHT_ALLOCATION["T2"]["ppos"])
reverted_flights = []

# Find rows where GKS was changed by comparing with the state before the editor
gks_changed_mask = (df_before_edit['GKS'] != edited_df['GKS'])

if gks_changed_mask.any():
    changed_indices = edited_df[gks_changed_mask].index
    for idx in changed_indices:
        ppos = edited_df.loc[idx, 'PPOS']
        if str(ppos) in locked_ppos:
            original_gks = df_before_edit.loc[idx, 'GKS']
            edited_df.loc[idx, 'GKS'] = original_gks
            reverted_flights.append(edited_df.loc[idx, 'FLN'])

if reverted_flights:
    st.warning(f"Die GKS-Zuweisung für Flüge mit fester PPOS-Zuweisung ({', '.join(sorted(list(set(reverted_flights))))}) kann nicht geändert werden und wurde zurückgesetzt.")

st.session_state["edited_df"] = edited_df

# Get selected flights from the editor
df_selected_from_editor = edited_df[edited_df["Aktiv"]]

# Check the _run_simulation flag from sidebar button
run_btn = st.session_state.get("_run_simulation", False)

# =========================================================
# Relevante Flüge für die Simulation
# =========================================================
flights, t0, df_selected, fallback_count = flights_to_sim_input(df_selected_from_editor)

# Display count of selected flights
st.caption(f"{len(df_selected)} von {len(df_all)} Flügen für die Simulation ausgewählt.")

if not flights:
    st.warning("Keine Flüge nach FLN-Auswahl.")
    st.stop()


# =========================================================
# Simulationslogik und -orchestrierung
# =========================================================
if run_btn:
    # Reset the flag so it doesn't persist across reruns
    st.session_state["_run_simulation"] = False
    
    mix_sum = (
        st.session_state["mix_easypass"] +
        st.session_state["mix_eu_manual"] +
        st.session_state["mix_tcn_at"] +
        st.session_state["mix_tcn_v"]
    )
    if mix_sum != 100:
        st.error("Passagiermix muss exakt 100% ergeben.")
        st.stop()

    # Werte aus Session State lesen
    process_time_scale = st.session_state["process_time_scale_pct"] / 100.0
    ees_choice = st.session_state["ees_choice"]
    ees_registered_share = {"100:0": 1.0, "75:25": 0.75, "50:50": 0.5, "0:100": 0.0}.get(ees_choice, 0.0)
    sim_params = dict(
        deboard_offset_min=st.session_state["deboard_offset_min"],
        deboard_delay_min_s=st.session_state["deboard_delay_min_s"],
        deboard_delay_max_s=st.session_state["deboard_delay_max_s"],
        changeover_s=st.session_state["changeover_s"],
        walk_speed_mean_mps=st.session_state["walk_speed_mean_mps"],
        walk_speed_sd_mps=st.session_state["walk_speed_sd_mps"],
        walk_speed_floor_mps=st.session_state["walk_speed_floor_mps"],
        bus_capacity=st.session_state["bus_capacity"],
        bus_fill_time_min=st.session_state["bus_fill_time_min"],
        bus_travel_time_min=st.session_state["bus_travel_time_min"],
        share_easypass=st.session_state["mix_easypass"] / 100.0,
        share_eu_manual=st.session_state["mix_eu_manual"] / 100.0,
        share_tcn_at=st.session_state["mix_tcn_at"] / 100.0,
        share_tcn_v=st.session_state["mix_tcn_v"] / 100.0,
        tcn_at_target=st.session_state["tcn_at_target"],
        ees_registered_share=ees_registered_share,
        mu_easypass_s=st.session_state["mu_easypass_s"],
        sigma_easypass_s=st.session_state["sigma_easypass_s"],
        max_easypass_s=st.session_state["max_easypass_s"] * process_time_scale,
        mu_eu_s=st.session_state["mu_eu_s"],
        sigma_eu_s=st.session_state["sigma_eu_s"],
        max_eu_s=st.session_state["max_eu_s"] * process_time_scale,
        mean_sss_s=st.session_state["mean_sss_s"] * process_time_scale,
        sd_sss_s=st.session_state["sd_sss_s"] * process_time_scale,
        mu_tcn_v_reg_s=st.session_state["mu_tcn_v_reg_s"],
        sigma_tcn_v_reg_s=st.session_state["sigma_tcn_v_reg_s"],
        mu_tcn_v_unreg_s=st.session_state["mu_tcn_v_unreg_s"],
        sigma_tcn_v_unreg_s=st.session_state["sigma_tcn_v_unreg_s"],
        max_tcn_v_s=st.session_state["max_tcn_v_s"] * process_time_scale,
    )

    # Flüge aufteilen
    flights_t1 = [f for f in flights if f["terminal"] == "T1"]
    flights_t2 = [f for f in flights if f["terminal"] == "T2"]
    run_seed = int(st.session_state["seed"])

    # --- Iterative Simulation ---
    # Erzeuge 15-Minuten-Intervalle von 06:00 bis 23:45
    intervals = []
    for hour in range(6, 24):
        for minute in range(0, 60, 15):
            start_time = f"{hour:02d}:{minute:02d}"
            end_hour, end_minute = (hour, minute + 15)
            if end_minute == 60:
                end_hour += 1
                end_minute = 0
            end_time = "00:00" if end_hour == 24 else f"{end_hour:02d}:{end_minute:02d}"
            intervals.append(f"{start_time}-{end_time}")
    min_cap = st.session_state["tcn_min_capacity"]
    cap_tcn_schedule_t1 = {interval: min_cap for interval in intervals}
    cap_tcn_schedule_t2 = {interval: min_cap for interval in intervals}
    
    min_cap_eu = st.session_state["min_eu_capacity"]
    cap_eu_schedule_t1 = {interval: min_cap_eu for interval in intervals}
    cap_eu_schedule_t2 = {interval: min_cap_eu for interval in intervals}

    max_cap_tcn_t1 = st.session_state["max_tcn_capacity_t1"]
    max_cap_tcn_t2 = st.session_state["max_tcn_capacity_t2"]
    max_cap_eu = st.session_state["max_eu_capacity"]
    max_iterations = st.session_state["max_iterations"]
    service_level_key = st.session_state["tcn_service_level_key"]
    service_level_min = TCN_SERVICE_LEVELS[service_level_key]

    with st.status("Simulation läuft... (iterative Kapazitätsanpassung)", expanded=True) as status:
        for i in range(1, max_iterations + 1):
            status.update(label=f"Simulation läuft... Iteration {i}/{max_iterations}")

            # Konfiguration T1
            cfg_t1 = SimConfig(
                cap_tcn_schedule=cap_tcn_schedule_t1,
                cap_eu_schedule=cap_eu_schedule_t1,
                cap_sss=(st.session_state["cap_sss_t1"] if st.session_state["sss_enabled_t1"] else 0),
                cap_easypass=st.session_state["cap_easypass_t1"],
                sss_enabled=st.session_state["sss_enabled_t1"],
                **sim_params
            )
            # Konfiguration T2
            cfg_t2 = SimConfig(
                cap_tcn_schedule=cap_tcn_schedule_t2,
                cap_eu_schedule=cap_eu_schedule_t2,
                cap_sss=(st.session_state["cap_sss"] if st.session_state["sss_enabled_t2"] else 0),
                cap_easypass=st.session_state["cap_easypass"],
                sss_enabled=st.session_state["sss_enabled_t2"],
                **sim_params
            )

            # Simulationen ausführen
            m1 = run_simulation(flights_t1, cfg_t1, t0, seed=run_seed)
            df_res_t1 = pd.DataFrame([r.__dict__ for r in m1.results])
            if not df_res_t1.empty:
                df_res_t1["wait_total"] = df_res_t1["wait_sss"] + df_res_t1["wait_easypass"] + df_res_t1["wait_eu"] + df_res_t1["wait_tcn"]
            ts_t1 = m1.queue_ts

            m2 = run_simulation(flights_t2, cfg_t2, t0, seed=run_seed)
            df_res_t2 = pd.DataFrame([r.__dict__ for r in m2.results])
            if not df_res_t2.empty:
                df_res_t2["wait_total"] = df_res_t2["wait_sss"] + df_res_t2["wait_easypass"] + df_res_t2["wait_eu"] + df_res_t2["wait_tcn"]
            ts_t2 = m2.queue_ts

            # Ergebnisse analysieren und Kapazität anpassen
            breaches_t1 = get_tcn_schedule_breaches(df_res_t1, t0, service_level_min)
            breaches_eu_t1 = get_eu_schedule_breaches(df_res_t1, t0, service_level_min)
            breaches_t2 = get_tcn_schedule_breaches(df_res_t2, t0, service_level_min)
            breaches_eu_t2 = get_eu_schedule_breaches(df_res_t2, t0, service_level_min)

            capacity_changed = False
            for interval in breaches_t1:
                if interval in cap_tcn_schedule_t1 and cap_tcn_schedule_t1[interval] < max_cap_tcn_t1:
                    cap_tcn_schedule_t1[interval] += 1
                    capacity_changed = True
            for interval in breaches_eu_t1:
                if interval in cap_eu_schedule_t1 and cap_eu_schedule_t1[interval] < max_cap_eu:
                    cap_eu_schedule_t1[interval] += 1
                    capacity_changed = True
            for interval in breaches_t2:
                if interval in cap_tcn_schedule_t2 and cap_tcn_schedule_t2[interval] < max_cap_tcn_t2:
                    cap_tcn_schedule_t2[interval] += 1
                    capacity_changed = True
            for interval in breaches_eu_t2:
                if interval in cap_eu_schedule_t2 and cap_eu_schedule_t2[interval] < max_cap_eu:
                    cap_eu_schedule_t2[interval] += 1
                    capacity_changed = True

            # Abbruchbedingungen prüfen
            if not breaches_t1 and not breaches_t2 and not breaches_eu_t1 and not breaches_eu_t2:
                st.success(f"✅ Service Level in Iteration {i} erreicht!")
                status.update(label=f"Service Level in Iteration {i} erreicht!", state="complete")
                break
            if not capacity_changed:
                st.warning(f"⚠️ Service Level nicht erreicht. Die Kapazität konnte in Iteration {i} nicht weiter erhöht werden, da für alle verbleibenden Service-Level-Verletzungen bereits die jeweilige Maximalkapazität erreicht ist.")
                status.update(label=f"Maximale Kapazität für kritische Intervalle in Iteration {i} erreicht.", state="error")
                break
            if i == max_iterations:
                st.error(f"🛑 Simulation nach {max_iterations} Iterationen gestoppt. Service Level wurde nicht erreicht.")
                status.update(label=f"Maximale Iterationen erreicht.", state="error")

    # Ergebnisse speichern (als DataFrames)
    st.session_state["last_df_res_t1"] = df_res_t1
    st.session_state["last_df_ts_t1"] = pd.DataFrame(ts_t1)
    st.session_state["last_df_res_t2"] = df_res_t2
    st.session_state["last_df_ts_t2"] = pd.DataFrame(ts_t2)
    
    # Config speichern (Referenz für Plots/Einstellungen)
    st.session_state["last_cfg_t1"] = cfg_t1
    st.session_state["last_cfg_t2"] = cfg_t2
    st.session_state["last_t0"] = t0
    st.session_state["last_df_selected"] = df_selected
    
    st.success("✅ Simulation abgeschlossen!")

# =========================================================
# Anzeige der Simulationsergebnisse
# =========================================================
if "last_df_res_t1" in st.session_state and "last_df_res_t2" in st.session_state:
    st.markdown("---")
    st.header("Simulationsergebnisse")
    
    df_res_t1 = st.session_state["last_df_res_t1"]
    df_res_t2 = st.session_state["last_df_res_t2"]
    cfg_t1 = st.session_state.get("last_cfg_t1")
    cfg_t2 = st.session_state.get("last_cfg_t2")
    t0 = st.session_state.get("last_t0", 0)
    
    # Ergebnisse zusammenführen
    if not df_res_t1.empty:
        df_res_t1["terminal"] = "T1"
    if not df_res_t2.empty:
        df_res_t2["terminal"] = "T2"
    
    df_res = pd.concat([df_res_t1, df_res_t2], ignore_index=True)
    
    if df_res.empty:
        st.warning("Keine Passagiere simuliert.")
    else:
        # Gesamtwartezeit
        df_res["wait_total"] = df_res["wait_sss"] + df_res["wait_easypass"] + df_res["wait_eu"] + df_res["wait_tcn"]
        
        # --- KPIs Metrics ---
        st.subheader("KPIs (Metriken)")
        
        # Fester Schwellwert
        KPI_THRESH_MIN = 30

        # Berechnungen für KPIs
        df_res_t1_filtered = df_res[df_res['terminal'] == 'T1']
        df_res_t2_filtered = df_res[df_res['terminal'] == 'T2']
        
        p95_wait_t1 = df_res_t1_filtered["wait_total"].quantile(0.95) if not df_res_t1_filtered.empty else 0
        p95_wait_t2 = df_res_t2_filtered["wait_total"].quantile(0.95) if not df_res_t2_filtered.empty else 0
        pct_over_t1 = (df_res_t1_filtered["wait_total"] > KPI_THRESH_MIN).mean() * 100.0 if not df_res_t1_filtered.empty else 0.0
        pct_over_t2 = (df_res_t2_filtered["wait_total"] > KPI_THRESH_MIN).mean() * 100.0 if not df_res_t2_filtered.empty else 0.0

        # Max Queue Helper
        def _get_max_q_info(df_ts):
            if df_ts.empty: return 0, "-", "-"
            q_cols = [c for c in df_ts.columns if c.startswith("q_")]
            if not q_cols: return 0, "-", "-"
            
            max_val = df_ts[q_cols].max().max()
            if max_val == 0: return 0, "-", "-"
            
            # Zeitpunkt des Peaks finden (erste Zeile, in der das Max erreicht wird)
            idx = df_ts[q_cols].max(axis=1).idxmax()
            col = df_ts.loc[idx, q_cols].idxmax()
            
            t_min_val = df_ts.loc[idx, "t_min"]
            peak_time = t0 + pd.to_timedelta(t_min_val, unit="m")
            
            st_map = {"q_sss": "SSS", "q_easypass": "Easypass", "q_eu": "EU", "q_tcn": "TCN"}
            return int(max_val), peak_time.strftime("%H:%M"), st_map.get(col, col)

        mq_t1, t_t1, s_t1 = _get_max_q_info(st.session_state.get("last_df_ts_t1", pd.DataFrame()))
        mq_t2, t_t2, s_t2 = _get_max_q_info(st.session_state.get("last_df_ts_t2", pd.DataFrame()))
        
        # Anzeige der Haupt-KPIs
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("P95 Wartezeit T1", f"{p95_wait_t1:.1f} min")
        c2.metric(f"% > {KPI_THRESH_MIN} min T1", f"{pct_over_t1:.1f} %")
        c3.metric("P95 Wartezeit T2", f"{p95_wait_t2:.1f} min")
        c4.metric(f"% > {KPI_THRESH_MIN} min T2", f"{pct_over_t2:.1f} %")
        
        # Details je Terminal
        st.caption("Details: Aufkommen & Peaks je Terminal")
        pax_t1 = len(df_res[df_res['terminal'] == 'T1'])
        pax_t2 = len(df_res[df_res['terminal'] == 'T2'])
        cp1, cp2, cp3, cp4 = st.columns(4)
        cp1.metric("Passagiere T1", f"{pax_t1:,}".replace(",", "."))
        cp2.metric("Max Queue T1", f"{mq_t1} Pax", delta=f"um {t_t1} ({s_t1})", delta_color="off")
        cp3.metric("Passagiere T2", f"{pax_t2:,}".replace(",", "."))
        cp4.metric("Max Queue T2", f"{mq_t2} Pax", delta=f"um {t_t2} ({s_t2})", delta_color="off")
        
        st.markdown("---")

        # Optional: 4er-Gruppe (V × EES) sichtbar machen
        if "ees_status" in df_res.columns:
            df_res["group_4"] = df_res["group"]
            mask = df_res["group"].isin(["TCN_V"])
            df_res.loc[mask, "group_4"] = (
                df_res.loc[mask, "group"] + "_" + df_res.loc[mask, "ees_status"].fillna("NA")
            )
        else:
            df_res["group_4"] = df_res["group"]
        
        total = int(len(df_res))
        
        # Plots
        from plotting import build_queue_timeseries_rolling, plot_queue_over_time_rolling, plot_mean_wait_over_time_rolling, plot_pax_arrival_stacked_bar, plot_terminal_overview_combined, plot_queue_heatmap
        st.subheader("Diagramme (Warteschlangen & Wartezeiten)")
        
        selected_terminal_tab = st.radio(
            "Wählen Sie ein Terminal zur Detailansicht:",
            ["Terminal 1", "Terminal 2"],
            horizontal=True,
        )
        st.markdown("---")
        
        if selected_terminal_tab == "Terminal 1":
            show_sss_t1 = bool(cfg_t1.sss_enabled) if cfg_t1 else False
            df_ts_t1 = st.session_state["last_df_ts_t1"]
            if not df_ts_t1.empty:
                st.markdown("##### P95 Wartezeit pro Stunde")
                plot_terminal_overview_combined(df_res, t0, terminal="T1", cfg=cfg_t1, bin_minutes_heatmap=60)

                # --- Datenaufbereitung für synchronisierte Achsen ---
                df_res_t1 = df_res[df_res["terminal"]=="T1"]
                
                # Wartezeiten
                ts_w_tcn = build_wait_time_timeseries_by_group_rolling(df_res_t1, t0, ["TCN_V", "TCN_AT"], window_min=15, step_min=1)
                ts_w_eu = build_wait_time_timeseries_by_group_rolling(df_res_t1, t0, ["EU_MANUAL"], window_min=15, step_min=1)
                ts_w_ep = build_wait_time_timeseries_by_group_rolling(df_res_t1, t0, ["EASYPASS"], window_min=15, step_min=1)
                max_w = pd.concat([ts_w_tcn, ts_w_eu, ts_w_ep])['mean_wait'].max()

                # Warteschlangen
                ts_q_tcn = build_queue_timeseries_rolling(df_ts_t1, t0, "q_tcn", window_min=15, step_min=1)
                ts_q_sss = build_queue_timeseries_rolling(df_ts_t1, t0, "q_sss", window_min=15, step_min=1)
                ts_q_eu = build_queue_timeseries_rolling(df_ts_t1, t0, "q_eu", window_min=15, step_min=1)
                ts_q_ep = build_queue_timeseries_rolling(df_ts_t1, t0, "q_easypass", window_min=15, step_min=1)
                max_q = pd.concat([ts_q_tcn, ts_q_sss, ts_q_eu, ts_q_ep])['mean_q'].max()
                
                # --- Plotting ---
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("##### TCN-Gruppe")
                    data_w_tcn = [(ts_w_tcn, "TCN")]
                    st.markdown(f"###### Ø Wartezeit (rollierend 15 min)")
                    plot_mean_wait_over_time_rolling(data_w_tcn, t0, window_min=15, y_max=max_w, cfg=cfg_t1, secondary_axis_type='TCN')
                    data_q_tcn = [(ts_q_tcn, "TCN")] + ([ (ts_q_sss, "SSS (Kiosk)") ] if show_sss_t1 else [])
                    st.markdown(f"###### Warteschlangen (rollierend 15 min)")
                    plot_queue_over_time_rolling(data_q_tcn, t0, window_min=15, y_max=max_q)
                with col2:
                    st.markdown("##### EU/Easypass-Gruppen")
                    data_w_eu = [(ts_w_eu, "EU"), (ts_w_ep, "Easypass")]
                    st.markdown(f"###### Ø Wartezeit (rollierend 15 min)")
                    plot_mean_wait_over_time_rolling(data_w_eu, t0, window_min=15, y_max=max_w, cfg=cfg_t1, secondary_axis_type='EU')
                    data_q_eu = [(ts_q_eu, "EU"), (ts_q_ep, "Easypass")]
                    st.markdown(f"###### Warteschlangen (rollierend 15 min)")
                    plot_queue_over_time_rolling(data_q_eu, t0, window_min=15, y_max=max_q)

                st.markdown("##### Maximale Warteschlangenlänge pro Stunde")
                plot_queue_heatmap(df_ts_t1, t0, terminal="T1", cfg=cfg_t1, bin_minutes=60)

                st.markdown("##### Passagieraufkommen (15 min Intervalle)")
                plot_pax_arrival_stacked_bar(df_res_t1, t0, bin_minutes=15)
            else:
                st.info("Keine Daten für Terminal 1.")
        
        if selected_terminal_tab == "Terminal 2":
            show_sss_t2 = bool(cfg_t2.sss_enabled) if cfg_t2 else False
            df_ts_t2 = st.session_state["last_df_ts_t2"]
            if not df_ts_t2.empty:
                st.markdown("##### P95 Wartezeit pro Stunde")
                plot_terminal_overview_combined(df_res, t0, terminal="T2", cfg=cfg_t2, bin_minutes_heatmap=60)

                # --- Datenaufbereitung für synchronisierte Achsen ---
                df_res_t2 = df_res[df_res["terminal"]=="T2"]

                # Wartezeiten
                ts_w_tcn = build_wait_time_timeseries_by_group_rolling(df_res_t2, t0, ["TCN_V", "TCN_AT"], window_min=15, step_min=1)
                ts_w_eu = build_wait_time_timeseries_by_group_rolling(df_res_t2, t0, ["EU_MANUAL"], window_min=15, step_min=1)
                ts_w_ep = build_wait_time_timeseries_by_group_rolling(df_res_t2, t0, ["EASYPASS"], window_min=15, step_min=1)
                max_w = pd.concat([ts_w_tcn, ts_w_eu, ts_w_ep])['mean_wait'].max()

                # Warteschlangen
                ts_q_tcn = build_queue_timeseries_rolling(df_ts_t2, t0, "q_tcn", window_min=15, step_min=1)
                ts_q_sss = build_queue_timeseries_rolling(df_ts_t2, t0, "q_sss", window_min=15, step_min=1)
                ts_q_eu = build_queue_timeseries_rolling(df_ts_t2, t0, "q_eu", window_min=15, step_min=1)
                ts_q_ep = build_queue_timeseries_rolling(df_ts_t2, t0, "q_easypass", window_min=15, step_min=1)
                max_q = pd.concat([ts_q_tcn, ts_q_sss, ts_q_eu, ts_q_ep])['mean_q'].max()

                # --- Plotting ---
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("##### TCN-Gruppe")
                    data_w_tcn = [(ts_w_tcn, "TCN")]
                    st.markdown(f"###### Ø Wartezeit (rollierend 15 min)")
                    plot_mean_wait_over_time_rolling(data_w_tcn, t0, window_min=15, y_max=max_w, cfg=cfg_t2, secondary_axis_type='TCN')
                    data_q_tcn = [(ts_q_tcn, "TCN")] + ([ (ts_q_sss, "SSS (Kiosk)") ] if show_sss_t2 else [])
                    st.markdown(f"###### Warteschlangen (rollierend 15 min)")
                    plot_queue_over_time_rolling(data_q_tcn, t0, window_min=15, y_max=max_q)
                with col2:
                    st.markdown("##### EU/Easypass-Gruppen")
                    data_w_eu = [(ts_w_eu, "EU"), (ts_w_ep, "Easypass")]
                    st.markdown(f"###### Ø Wartezeit (rollierend 15 min)")
                    plot_mean_wait_over_time_rolling(data_w_eu, t0, window_min=15, y_max=max_w, cfg=cfg_t2, secondary_axis_type='EU')
                    data_q_eu = [(ts_q_eu, "EU"), (ts_q_ep, "Easypass")]
                    st.markdown(f"###### Warteschlangen (rollierend 15 min)")
                    plot_queue_over_time_rolling(data_q_eu, t0, window_min=15, y_max=max_q)

                st.markdown("##### Maximale Warteschlangenlänge pro Stunde")
                plot_queue_heatmap(df_ts_t2, t0, terminal="T2", cfg=cfg_t2, bin_minutes=60)

                st.markdown("##### Passagieraufkommen (15 min Intervalle)")
                plot_pax_arrival_stacked_bar(df_res_t2, t0, bin_minutes=15)
            else:
                st.info("Keine Daten für Terminal 2.")
        
        # Bus Arrivals Plot
        st.subheader("Bus-Ankünfte (Bulks)")
        # Nur anzeigen, wenn es Bus-Passagiere gibt
        if "Bus" in df_res["transport_mode"].unique():
            df_bus = df_res[df_res["transport_mode"] == "Bus"].copy()
            
            # Gruppiere nach Ankunftszeit, um die Bulks zu identifizieren
            bus_bulks = df_bus.groupby("arrival_min").agg(
                pax_count=("pax_id", "count"),
                fln=("fln", "first"),
                ppos=("ppos", "first"),
                terminal=("terminal", "first")
            ).reset_index()

            # Bus-Fahrzeit aus der Konfiguration holen
            bus_travel_time = cfg_t1.bus_travel_time_min if cfg_t1 else st.session_state.get("bus_travel_time_min", 2.5)
            bus_bulks["departure_min"] = bus_bulks["arrival_min"] - bus_travel_time

            # Zeitstempel für die Anzeige berechnen
            bus_bulks["arrival_time"] = t0 + pd.to_timedelta(bus_bulks["arrival_min"], unit="m")
            bus_bulks["departure_time"] = t0 + pd.to_timedelta(bus_bulks["departure_min"], unit="m")

            display_df = bus_bulks[[
                "fln", "pax_count", "ppos", "departure_time", "arrival_time", "terminal"
            ]].rename(columns={
                "terminal": "Terminal",
                "fln": "Flugnummer",
                "ppos": "PPOS",
                "pax_count": "Passagiere",
                "departure_time": "Bus Abfahrt",
                "arrival_time": "Bus Ankunft"
            }).sort_values(["Terminal", "Bus Ankunft"])
            st.dataframe(display_df.style.format({"Bus Abfahrt": "{:%H:%M:%S}", "Bus Ankunft": "{:%H:%M:%S}"}), width="stretch")
        else:
            st.info("Keine Flüge mit Bustransfer in dieser Simulation.")

        if cfg_t1 and cfg_t2:
            st.subheader("Ermittelte Kapazitäten")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("###### Terminal 1")
                tcn_schedule_t1 = cfg_t1.cap_tcn_schedule
                eu_schedule_t1 = cfg_t1.cap_eu_schedule
                sorted_intervals = sorted(tcn_schedule_t1.keys())
                df_cap_t1 = pd.DataFrame({
                    "Intervall": sorted_intervals,
                    "TCN Kapazität": [tcn_schedule_t1.get(k) for k in sorted_intervals],
                    "EU Kapazität": [eu_schedule_t1.get(k) for k in sorted_intervals]
                })
                st.dataframe(df_cap_t1, hide_index=True, use_container_width=True)
            with col2:
                st.markdown("###### Terminal 2")
                tcn_schedule_t2 = cfg_t2.cap_tcn_schedule
                eu_schedule_t2 = cfg_t2.cap_eu_schedule
                sorted_intervals = sorted(tcn_schedule_t2.keys())
                df_cap_t2 = pd.DataFrame({
                    "Intervall": sorted_intervals,
                    "TCN Kapazität": [tcn_schedule_t2.get(k) for k in sorted_intervals],
                    "EU Kapazität": [eu_schedule_t2.get(k) for k in sorted_intervals]
                })
                st.dataframe(df_cap_t2, hide_index=True, use_container_width=True)

        # Flight Summary
        st.subheader("Flugübersicht")
        df_fsum = (
            df_res.groupby("fln", as_index=False)
            .agg(
                spax=("pax_id", "count"),
                mean_wait=("wait_total", "mean"),
                p95_wait=("wait_total", lambda x: x.quantile(0.95)),
                mean_system=("system_min", "mean"),
                p95_system=("system_min", lambda x: x.quantile(0.95)),
            )
            .sort_values("spax", ascending=False)
        )
        st.dataframe(df_fsum, width="stretch")
        
        # Group Summary
        st.subheader("Gruppenübersicht")
        df_gsum = (
            df_res.groupby("group_4", as_index=False)
            .agg(
                spax=("pax_id", "count"),
                mean_wait=("wait_total", "mean"),
                p95_wait=("wait_total", lambda x: x.quantile(0.95)),
                mean_system=("system_min", "mean"),
            )
            .assign(share_pct=lambda d: (100.0 * d["spax"] / max(1, total)).round(1))
            .sort_values("spax", ascending=False)
        )
        st.dataframe(df_gsum, width="stretch")
        
        # Passenger Detail
        st.subheader("Detaildaten (Passagiere)")
        st.dataframe(df_res, width="stretch")
        
        # CSV-Download
        csv_bytes = df_res.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Passenger-Details als CSV herunterladen",
            data=csv_bytes,
            file_name="passenger_results.csv",
            mime="text/csv",
        )