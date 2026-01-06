from __future__ import annotations

import pandas as pd
import streamlit as st

from engine import SimConfig, run_simulation
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
from typ4_defaults import DEFAULT_EPAX_BY_TYP4
from flight_allocation import FLIGHT_ALLOCATION


# =========================================================
# Session State Init (Defaults)
# =========================================================
from session_state_init import init_session_state


# =========================================================
# CSV Parsing
# =========================================================
def read_csv_auto(uploaded) -> pd.DataFrame:
    # Liest eine hochgeladene Tabellendatei ein.
    # Erkennt XLSX/XLS anhand des Dateinamens oder Content-Type und nutzt
    # `pd.read_excel`. Für CSV wird versucht, verschiedene Trennzeichen zu verwenden.
    # `uploaded` ist das von Streamlit hochgeladene File-like-Objekt; wir setzen den
    # Stream vor jedem Versuch zurück (seek), falls verfügbar.
    name = getattr(uploaded, "name", "") or ""
    ctype = getattr(uploaded, "type", "") or ""

    # Excel-Erkennung
    if name.lower().endswith((".xlsx", ".xls")) or "excel" in ctype.lower():
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
    needed = ["SIBT", "FLN", "PPOS", "PK", "EPAX", "Typ4", "T"]
    missing = set(needed) - set(df.columns)
    if missing:
        raise ValueError(f"CSV fehlt Spalten: {missing}")

    out = df[needed].copy()
    out["SIBT"] = pd.to_datetime(out["SIBT"], dayfirst=True, errors="coerce")
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

    return out.sort_values("SIBT")

# Liste alle Flüge für die Simulation auf, basierend auf ausgewählten FLN
def flights_to_sim_input(df: pd.DataFrame, fln_selected: list[str]):
    df2 = df[df["FLN"].isin(fln_selected)].copy()
    if df2.empty:
        return [], None, df2, 0

    t0 = df2["SIBT"].min()
    df2["t_arr_min"] = (df2["SIBT"] - t0).dt.total_seconds() / 60.0

    flights = []
    # Default-Dictionary: aus externem Mapping (falls Typ4 nicht in Mapping: Fallback 100)
    default_epax_by_typ4 = DEFAULT_EPAX_BY_TYP4

    # Ermitteln, wie viele Zeilen weder APAX noch EPAX haben -> Fallback
    if "APAX" in df2.columns:
        fallback_mask = df2["APAX"].isna() & df2["EPAX"].isna()
    else:
        fallback_mask = df2["EPAX"].isna()
    fallback_count = int(fallback_mask.sum())

    assigned_terminals = []
    for idx, r in df2.iterrows():
        # SPAX direkt aus der Spalte verwenden (bereits in parse_flights_csv_fixed berechnet)
        spax = int(r["SPAX"]) if pd.notna(r.get("SPAX")) else 100

        # Terminal-Zuteilung
        # Flüge mit bekanntem PPOS: T1 oder T2 basierend auf FLIGHT_ALLOCATION
        # Flüge mit unbekanntem PPOS (nicht im Dictionary): immer T2
        term = "T2"  # Default für unbekannte PPOS
        ppos_val = str(r["PPOS"])
        if ppos_val in FLIGHT_ALLOCATION["T1"]["ppos"]:
            term = "T1"
        elif ppos_val in FLIGHT_ALLOCATION["T2"]["ppos"]:
            term = "T2"
        # else: PPOS nicht im Dictionary oder "unbekannt" -> T2 (default bleibt)
        assigned_terminals.append(term)

        flights.append({
            "flight_key": f"{r['SIBT']:%Y%m%d-%H%M}_{r['PPOS']}_{r['FLN']}_{idx}",
            "fln": r["FLN"],
            "ppos": r["PPOS"],
            "spax": spax,
            "acft": r["Typ4"],
            "t_arr_min": float(r["t_arr_min"]),
            "terminal": term,
        })

    df2["GKS"] = assigned_terminals
    return flights, t0, df2, fallback_count


# =========================================================
# App Start
# =========================================================
st.set_page_config(page_title="SIM EES", layout="wide", initial_sidebar_state="expanded")
st.title("Simulation des EES-Prozesses am Flughafen")

# Initialisiere Defaults (wichtig, falls User Settings noch nicht besucht hat)
init_session_state()
# Render settings in the sidebar (migrated from pages/2_Einstellungen.py)
from settings_sidebar import render_settings_sidebar
render_settings_sidebar(show_sim_button=True)
# Ensure Einstellungen page reloads saved settings when arriving from Home
st.session_state["_settings_loaded"] = False


def clear_results():
    keys = ["last_df_res_t1", "last_df_res_t2", "last_t0", "last_df_selected", "last_cfg_t1", "last_cfg_t2"]
    for k in keys:
        st.session_state.pop(k, None)

# Visual frame for upload section using expander (always expanded)
with st.expander("📋 Flugplan importieren", expanded=True):
    uploaded = st.file_uploader(
        "Flugplan hochladen (CSV oder XLSX, Pflichtspalten: SIBT, FLN, ADEP3, PPOS, Typ4, PK, EPAX, APAX, T, PK )",
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

# Spaltenreihenfolge robust setzen: gewünschte Reihenfolge zuerst, übrige Spalten anhängen
desired_cols = ["SIBT", "FLN", "ADEP3", "Typ4", "EPAX", "APAX", "SPAX", "PPOS", "T", "PK"]
new_order = [c for c in desired_cols if c in df_all.columns] + [c for c in df_all.columns if c not in desired_cols]
df_all = df_all[new_order]

fln_all = sorted(df_all["FLN"].unique().tolist())
if not fln_all:
    st.warning("Keine Flüge nach PK-Filter vorhanden.")
    st.stop()


# =========================================================
# Main Page Controls (FLN & Start)
# =========================================================

# FLN Auswahl direkt auf der Startseite (da datenabhängig)
st.subheader("Simulation konfigurieren")
fln_selected = st.multiselect("Flugnummern (FLN) auswählen", options=fln_all, default=fln_all)

st.info("Um die Simulation zu starten, klicke auf den Button **▶️ Simulation starten** in der Seitenleiste.")

# Check the _run_simulation flag from sidebar button
run_btn = st.session_state.get("_run_simulation", False)


# =========================================================
# Relevante Flüge nach FLN
# =========================================================
flights, t0, df_selected, fallback_count = flights_to_sim_input(df_all, fln_selected)
st.subheader("In die Simulation eingehende Flüge (nach FLN-Auswahl)")
# Formatiere SIBT für Anzeige (europäisches Format TT.MM.YYYY HH:MM)
df_selected_display = df_selected.copy()
df_selected_display["SIBT"] = df_selected_display["SIBT"].dt.strftime("%d.%m.%Y %H:%M")
st.dataframe(df_selected_display, width="stretch")

# Warnen, wenn für einige Zeilen weder APAX noch EPAX vorhanden waren und Default verwendet wurde
if fallback_count > 0:
    st.warning(f"{fallback_count} Flüge ohne APAX/EPAX — Standardwert verwendet.")

if not flights:
    st.warning("Keine Flüge nach FLN-Auswahl.")
    st.stop()


# =========================================================
# Simulation (nur Submit) + Persistenz
# =========================================================
if run_btn:
    # Reset the flag so it doesn't persist across reruns
    st.session_state["_run_simulation"] = False
    
    mix_sum = (
        st.session_state["mix_easypass"] +
        st.session_state["mix_eu_manual"] +
        st.session_state["mix_tcn_at"] +
        st.session_state["mix_tcn_vh"] +
        st.session_state["mix_tcn_ve"]
    )
    if mix_sum != 100:
        st.error("Passagiermix muss exakt 100% ergeben.")
        st.stop()

    # Werte aus Session State lesen
    process_time_scale = st.session_state["process_time_scale_pct"] / 100.0
    ees_choice = st.session_state["ees_choice"]
    ees_registered_share = {"100:0": 1.0, "75:25": 0.75, "50:50": 0.5, "0:100": 0.0}[ees_choice]

    # Gemeinsame Parameter für beide Terminals
    sim_params = dict(
        deboard_offset_min=st.session_state["deboard_offset_min"],
        deboard_window_min=st.session_state["deboard_window_min"],
        walk_speed_mean_mps=st.session_state["walk_speed_mean_mps"],
        walk_speed_sd_mps=st.session_state["walk_speed_sd_mps"],
        walk_speed_floor_mps=st.session_state["walk_speed_floor_mps"],
        share_easypass=st.session_state["mix_easypass"] / 100.0,
        share_eu_manual=st.session_state["mix_eu_manual"] / 100.0,
        share_tcn_at=st.session_state["mix_tcn_at"] / 100.0,
        share_tcn_vh=st.session_state["mix_tcn_vh"] / 100.0,
        share_tcn_ve=st.session_state["mix_tcn_ve"] / 100.0,
        tcn_at_policy=st.session_state["tcn_at_policy"],
        ees_registered_share=ees_registered_share,
        mean_easypass_s=st.session_state["mean_easypass_s"] * process_time_scale,
        sd_easypass_s=st.session_state["sd_easypass_s"] * process_time_scale,
        mean_eu_s=st.session_state["mean_eu_s"] * process_time_scale,
        sd_eu_s=st.session_state["sd_eu_s"] * process_time_scale,
        mean_sss_vh_reg_s=st.session_state["mean_sss_vh_reg_s"] * process_time_scale,
        sd_sss_vh_reg_s=st.session_state["sd_sss_vh_reg_s"] * process_time_scale,
        mean_sss_vh_unreg_s=st.session_state["mean_sss_vh_unreg_s"] * process_time_scale,
        sd_sss_vh_unreg_s=st.session_state["sd_sss_vh_unreg_s"] * process_time_scale,
        mean_sss_ve_reg_s=st.session_state["mean_sss_ve_reg_s"] * process_time_scale,
        sd_sss_ve_reg_s=st.session_state["sd_sss_ve_reg_s"] * process_time_scale,
        mean_sss_ve_unreg_s=st.session_state["mean_sss_ve_unreg_s"] * process_time_scale,
        sd_sss_ve_unreg_s=st.session_state["sd_sss_ve_unreg_s"] * process_time_scale,
        mean_tcn_vh_reg_s=st.session_state["mean_tcn_vh_reg_s"] * process_time_scale,
        sd_tcn_vh_reg_s=st.session_state["sd_tcn_vh_reg_s"] * process_time_scale,
        mean_tcn_vh_unreg_s=st.session_state["mean_tcn_vh_unreg_s"] * process_time_scale,
        sd_tcn_vh_unreg_s=st.session_state["sd_tcn_vh_unreg_s"] * process_time_scale,
        mean_tcn_ve_reg_s=st.session_state["mean_tcn_ve_reg_s"] * process_time_scale,
        sd_tcn_ve_reg_s=st.session_state["sd_tcn_ve_reg_s"] * process_time_scale,
        mean_tcn_ve_unreg_s=st.session_state["mean_tcn_ve_unreg_s"] * process_time_scale,
        sd_tcn_ve_unreg_s=st.session_state["sd_tcn_ve_unreg_s"] * process_time_scale,
    )

    # Konfiguration T1
    cfg_t1 = SimConfig(
        cap_sss=(st.session_state["cap_sss_t1"] if st.session_state["sss_enabled_t1"] else 0),
        cap_easypass=st.session_state["cap_easypass_t1"],
        cap_eu=st.session_state["cap_eu_t1"],
        cap_tcn=st.session_state["cap_tcn_t1"],
        sss_enabled=st.session_state["sss_enabled_t1"],
        **sim_params
    )

    # Konfiguration T2
    cfg_t2 = SimConfig(
        cap_sss=(st.session_state["cap_sss"] if st.session_state["sss_enabled_t2"] else 0),
        cap_easypass=st.session_state["cap_easypass"],
        cap_eu=st.session_state["cap_eu"],
        cap_tcn=st.session_state["cap_tcn"],
        sss_enabled=st.session_state["sss_enabled_t2"],
        **sim_params
    )

    # Flüge aufteilen
    flights_t1 = [f for f in flights if f["terminal"] == "T1"]
    flights_t2 = [f for f in flights if f["terminal"] == "T2"]

    # Simulationen ausführen (Schleife über Anzahl der Runs)
    n_runs = st.session_state.get("sim_runs", 1)
    base_seed = int(st.session_state["seed"])
    
    results_t1_list = []
    ts_t1_list = []
    results_t2_list = []
    ts_t2_list = []
    
    progress_bar = st.progress(0)
    
    for i in range(n_runs):
        run_seed = base_seed + i
        
        # Run T1
        m1 = run_simulation(flights_t1, cfg_t1, seed=run_seed)
        results_t1_list.extend([r.__dict__ for r in m1.results])
        ts_t1_list.extend(m1.queue_ts)
        
        # Run T2
        m2 = run_simulation(flights_t2, cfg_t2, seed=run_seed)
        results_t2_list.extend([r.__dict__ for r in m2.results])
        ts_t2_list.extend(m2.queue_ts)
        
        progress_bar.progress((i + 1) / n_runs)
    
    progress_bar.empty()

    # Ergebnisse speichern (als DataFrames)
    st.session_state["last_df_res_t1"] = pd.DataFrame(results_t1_list)
    st.session_state["last_df_ts_t1"] = pd.DataFrame(ts_t1_list)
    st.session_state["last_df_res_t2"] = pd.DataFrame(results_t2_list)
    st.session_state["last_df_ts_t2"] = pd.DataFrame(ts_t2_list)
    
    # Config speichern (Referenz für Plots/Einstellungen)
    st.session_state["last_cfg_t1"] = cfg_t1
    st.session_state["last_cfg_t2"] = cfg_t2
    st.session_state["last_t0"] = t0
    st.session_state["last_df_selected"] = df_selected
    
    st.success("✅ Simulation abgeschlossen!")

# =========================================================
# Ergebnisse anzeigen, wenn verfügbar (unabhängig vom Button)
# =========================================================
if "last_df_res_t1" in st.session_state and "last_df_res_t2" in st.session_state:
    st.markdown("---")
    st.subheader("📊 Simulationsergebnisse")
    
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
        
        # Slider optisch über der entsprechenden Metrik (3. Spalte) platzieren
        cs1, cs2, cs3, cs4 = st.columns(4)
        with cs3:
            kpi_thresh = st.select_slider("Schwellwert [min]", options=[10, 15, 20, 30], value=15)

        p95_wait = df_res["wait_total"].quantile(0.95)
        mean_wait = df_res["wait_total"].mean()

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
        
        pct_over = (df_res["wait_total"] > kpi_thresh).mean() * 100.0

        t_start = df_res["arrival_min"].min()
        t_end = df_res["exit_min"].max()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("P95 Wartezeit", f"{p95_wait:.1f} min")
        c2.metric("Ø Wartezeit", f"{mean_wait:.1f} min")
        c3.metric(f"% > {kpi_thresh} min", f"{pct_over:.1f} %")
        c4.metric("Passagiere gesamt", f"{len(df_res):,}".replace(",", "."))
        
        # Peaks je Terminal
        st.caption("Details: Peaks je Terminal")
        cp1, cp2, _, _, _ = st.columns(5)
        cp1.metric("Max Queue T1", f"{mq_t1} Pax", delta=f"um {t_t1} ({s_t1})", delta_color="off")
        cp2.metric("Max Queue T2", f"{mq_t2} Pax", delta=f"um {t_t2} ({s_t2})", delta_color="off")
        st.markdown("---")

        # Optional: 4er-Gruppe (VH/VE × EES) sichtbar machen
        if "ees_status" in df_res.columns:
            df_res["group_4"] = df_res["group"]
            mask = df_res["group"].isin(["TCN_VH", "TCN_VE"])
            df_res.loc[mask, "group_4"] = (
                df_res.loc[mask, "group"] + "_" + df_res.loc[mask, "ees_status"].fillna("NA")
            )
        else:
            df_res["group_4"] = df_res["group"]
        
        total = int(len(df_res))
        
        # Plots
        from plotting import plot_queue_over_time_rolling, plot_mean_wait_over_time_rolling, plot_wait_heatmap
        st.subheader("Diagramme (Warteschlangen & Wartezeiten)")
        
        tab_t1, tab_t2 = st.tabs(["Terminal 1", "Terminal 2"])
        
        with tab_t1:
            st.markdown("#### Terminal 1")
            show_sss_t1 = bool(cfg_t1.sss_enabled) if cfg_t1 else False
            thresh_q_t1 = st.session_state["threshold_pax_length_t1"]
            thresh_w_t1 = st.session_state["threshold_wait_s_t1"]
            df_ts_t1 = st.session_state["last_df_ts_t1"]
            if not df_ts_t1.empty:
                plot_wait_heatmap(df_res[df_res["terminal"]=="T1"], t0, show_sss=show_sss_t1)
                plot_queue_over_time_rolling(df_ts_t1, t0, threshold=thresh_q_t1, window_min=15, step_min=1, show_sss=show_sss_t1, subset=["EU", "Easypass"])
                plot_mean_wait_over_time_rolling(df_res[df_res["terminal"]=="T1"], t0, threshold=thresh_w_t1, window_min=15, step_min=1, show_sss=show_sss_t1, subset=["EU", "Easypass"])
                plot_queue_over_time_rolling(df_ts_t1, t0, threshold=thresh_q_t1, window_min=15, step_min=1, show_sss=show_sss_t1, subset=["TCN", "SSS (Kiosk)"])
                plot_mean_wait_over_time_rolling(df_res[df_res["terminal"]=="T1"], t0, threshold=thresh_w_t1, window_min=15, step_min=1, show_sss=show_sss_t1, subset=["TCN", "SSS (Kiosk)"])
            else:
                st.info("Keine Daten für Terminal 1.")
        
        with tab_t2:
            st.markdown("#### Terminal 2")
            show_sss_t2 = bool(cfg_t2.sss_enabled) if cfg_t2 else False
            thresh_q_t2 = st.session_state["threshold_pax_length_t2"]
            thresh_w_t2 = st.session_state["threshold_wait_s_t2"]
            df_ts_t2 = st.session_state["last_df_ts_t2"]
            if not df_ts_t2.empty:
                plot_wait_heatmap(df_res[df_res["terminal"]=="T2"], t0, show_sss=show_sss_t2)
                plot_queue_over_time_rolling(df_ts_t2, t0, threshold=thresh_q_t2, window_min=15, step_min=1, show_sss=show_sss_t2, subset=["EU", "Easypass"])
                plot_mean_wait_over_time_rolling(df_res[df_res["terminal"]=="T2"], t0, threshold=thresh_w_t2, window_min=15, step_min=1, show_sss=show_sss_t2, subset=["EU", "Easypass"])
                plot_queue_over_time_rolling(df_ts_t2, t0, threshold=thresh_q_t2, window_min=15, step_min=1, show_sss=show_sss_t2, subset=["TCN", "SSS (Kiosk)"])
                plot_mean_wait_over_time_rolling(df_res[df_res["terminal"]=="T2"], t0, threshold=thresh_w_t2, window_min=15, step_min=1, show_sss=show_sss_t2, subset=["TCN", "SSS (Kiosk)"])
            else:
                st.info("Keine Daten für Terminal 2.")
        
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