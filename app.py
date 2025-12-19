from __future__ import annotations

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from simulation import SimConfig, run_simulation
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


# =========================================================
# Passagiermix – Defaults & Reset
# =========================================================
# Initialisiere den Session-State nur, wenn Keys fehlen
def init_mix_state():
    for key, val in DEFAULT_MIX.items():
        if key not in st.session_state:
            st.session_state[key] = val

# Callback: Setzt alle Slider-Werte zurück
def reset_passenger_mix():
    for key, val in DEFAULT_MIX.items():
        st.session_state[key] = val
    # optional: Flag setzen für Rückmeldung
    st.session_state["mix_reset_done"] = True


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
def parse_flights_csv_fixed(df: pd.DataFrame) -> pd.DataFrame:
    needed = ["SIBT", "FLN", "PPOS", "PK", "EPAX", "Typ4", "T"]
    missing = set(needed) - set(df.columns)
    if missing:
        raise ValueError(f"CSV fehlt Spalten: {missing}")

    out = df[needed].copy()
    out["SIBT"] = pd.to_datetime(out["SIBT"])
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

# Liste alle Flüge für die Simulation auf, basierend auf ausgewählten PPOS
def flights_to_sim_input(df: pd.DataFrame, ppos_selected: list[str]):
    df2 = df[df["PPOS"].isin(ppos_selected)].copy()
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

    for idx, r in df2.iterrows():
        # SPAX direkt aus der Spalte verwenden (bereits in parse_flights_csv_fixed berechnet)
        spax = int(r["SPAX"]) if pd.notna(r.get("SPAX")) else 100

        flights.append({
            "flight_key": f"{r['SIBT']:%Y%m%d-%H%M}_{r['PPOS']}_{r['FLN']}_{idx}",
            "fln": r["FLN"],
            "ppos": r["PPOS"],
            "spax": spax,
            "acft": r["Typ4"],
            "t_arr_min": float(r["t_arr_min"]),
        })
    return flights, t0, df2, fallback_count


# =========================================================
# Plot Helpers (Plotly)
# =========================================================
def _to_time_axis(t0: pd.Timestamp, t_min_series: pd.Series) -> pd.Series:
    return t0 + pd.to_timedelta(t_min_series, unit="m")


def plot_queue_over_time(df_ts: pd.DataFrame, t0: pd.Timestamp, title: str):
    df_plot = (
        df_ts.drop_duplicates(subset=["t_min"])
        .sort_values("t_min")
    )
    if df_plot.empty:
        st.info("Keine Queue-Zeitreihe verfügbar.")
        return

    x = _to_time_axis(t0, df_plot["t_min"])

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=df_plot["q_sss"], mode="lines", name="SSS (Kiosk)"))
    fig.add_trace(go.Scatter(x=x, y=df_plot["q_easypass"], mode="lines", name="Easypass"))
    fig.add_trace(go.Scatter(x=x, y=df_plot["q_eu"], mode="lines", name="EU"))
    fig.add_trace(go.Scatter(x=x, y=df_plot["q_tcn"], mode="lines", name="TCN"))


    fig.update_layout(
        title=title,
        xaxis_title="Uhrzeit",
        yaxis_title="Wartende Passagiere",
        hovermode="x unified",
        legend_title_text="Prozessstelle",
    )
    st.plotly_chart(fig, use_container_width=True)


def build_queue_timeseries_rolling(
    df_ts: pd.DataFrame,
    col: str,
    window_min: int = 15,
    step_min: int = 1,
) -> pd.DataFrame:
    
    # Rolling mean der Queue-Länge über (t-window, t] auf Zeitraster (step_min).
    # df_ts: enthält t_min und q_*
    
    df = df_ts[["t_min", col]].dropna().drop_duplicates("t_min").sort_values("t_min")
    if df.empty:
        return df

    t_vals = df["t_min"].to_numpy()
    q_vals = df[col].to_numpy()
    n = len(df)

    t_start = float(t_vals.min())
    t_end = float(t_vals.max())

    grid = pd.DataFrame({
        "t_min": [t_start + i * step_min for i in range(int((t_end - t_start) / step_min) + 1)]
    })

    means = []
    left = 0
    right = 0

    for t in grid["t_min"].to_numpy():
        while right < n and t_vals[right] <= t:
            right += 1
        while left < n and t_vals[left] < t - window_min:
            left += 1

        means.append(q_vals[left:right].mean() if right > left else float("nan"))

    grid["mean_q"] = means
    return grid


def plot_queue_over_time_rolling(
    df_ts: pd.DataFrame,
    t0: pd.Timestamp,
    window_min: int = 15,
    step_min: int = 1,
    show_sss: bool = True,
):
    fig = go.Figure()

    cols = [
        ("q_sss", "SSS (Kiosk)"),
        ("q_easypass", "Easypass"),
        ("q_eu", "EU"),
        ("q_tcn", "TCN"),
    ]

    if not show_sss:
        cols = [c for c in cols if c[0] != "q_sss"]

    for col, label in cols:
        ts = build_queue_timeseries_rolling(df_ts, col, window_min=window_min, step_min=step_min)
        if ts.empty:
            continue
        x = _to_time_axis(t0, ts["t_min"])
        fig.add_trace(go.Scatter(x=x, y=ts["mean_q"], mode="lines", name=label))

    fig.add_hline(y=threshold_pax_length, line_dash="dash", annotation_text=f"Schwellwert = {threshold_pax_length}")

    # Wenn SSS deaktiviert ist, einen klaren Hinweis in der Grafik anzeigen
    if not show_sss:
        fig.add_annotation(
            xref="paper",
            yref="paper",
            x=0.01,
            y=0.98,
            xanchor="left",
            yanchor="top",
            text="SSS deaktiviert",
            showarrow=False,
            bgcolor="rgba(255,200,200,0.6)",
            bordercolor="rgba(200,50,50,0.8)",
        )

    fig.update_layout(
        title=f"Warteschlangen je Prozessstelle (rollierend {window_min} min)",
        xaxis_title="Uhrzeit",
        yaxis_title="Ø wartende Passagiere",
        hovermode="x unified",
        legend_title_text="Prozessstelle",
    )
    st.plotly_chart(fig, use_container_width=True)


def build_wait_time_timeseries_rolling(
    df_res: pd.DataFrame,
    station: str,
    window_min: int = 15,
    step_min: int = 1,
) -> pd.DataFrame:
    
    # Rolling mean der Wartezeit über Passagiere, die in (t-window, t] ihren Service an der Station starten.
    # t = arrival_min + wait_station
    
    wait_col = f"wait_{station}"
    serv_col = f"serv_{station}"

    df = df_res[df_res[serv_col] > 0].copy()
    if df.empty:
        return df

    df["t_min"] = df["arrival_min"] + df[wait_col]
    df = df.sort_values("t_min")

    t_vals = df["t_min"].to_numpy()
    w_vals = df[wait_col].to_numpy()
    n = len(df)

    t_start = float(t_vals.min())
    t_end = float(t_vals.max())

    grid = pd.DataFrame({
        "t_min": [t_start + i * step_min for i in range(int((t_end - t_start) / step_min) + 1)]
    })

    means = []
    left = 0
    right = 0

    for t in grid["t_min"].to_numpy():
        while right < n and t_vals[right] <= t:
            right += 1
        while left < n and t_vals[left] < t - window_min:
            left += 1
        means.append(w_vals[left:right].mean() if right > left else float("nan"))

    grid["mean_wait"] = means
    return grid


def plot_mean_wait_over_time_rolling(
    df_res: pd.DataFrame,
    t0: pd.Timestamp,
    window_min: int = 15,
    step_min: int = 1,
    show_sss: bool = True,
):
    fig = go.Figure()

    def _stations_iter(show_sss: bool = True):
        stations = [
            ("sss", "SSS (Kiosk)"),
            ("easypass", "Easypass"),
            ("eu", "EU"),
            ("tcn", "TCN"),
        ]
        if not show_sss:
            stations = [s for s in stations if s[0] != "sss"]
        return stations

    for station, label in _stations_iter(show_sss=show_sss):
        ts = build_wait_time_timeseries_rolling(df_res, station, window_min=window_min, step_min=step_min)
        if ts.empty:
            continue
        x = _to_time_axis(t0, ts["t_min"])
        fig.add_trace(go.Scatter(x=x, y=ts["mean_wait"], mode="lines", name=label))

    fig.add_hline(y=threshold_wait_s, line_dash="dash", annotation_text=f"Schwellwert = {threshold_wait_s}", annotation_position="left")

    fig.update_layout(
        title=f"Ø Wartezeit je Prozessstelle (rollierend {window_min} min)",
        xaxis_title="Uhrzeit",
        yaxis_title="Ø Wartezeit [min]",
        hovermode="x unified",
        legend_title_text="Prozessstelle",
    )
    if not show_sss:
        fig.add_annotation(
            xref="paper",
            yref="paper",
            x=0.01,
            y=0.98,
            xanchor="left",
            yanchor="top",
            text="SSS deaktiviert",
            showarrow=False,
            bgcolor="rgba(255,200,200,0.6)",
            bordercolor="rgba(200,50,50,0.8)",
        )
    st.plotly_chart(fig, use_container_width=True)


# =========================================================
# App Start
# =========================================================
st.set_page_config(page_title="SIM EES", layout="wide")
st.title("Simulation des EES-Prozesses am Flughafen")

uploaded = st.file_uploader(
    "Flugplan hochladen (CSV oder XLSX, Pflichtspalten: SIBT, FLN, ADEP3, PPOS, Typ4, PK, EPAX, APAX, T, PK )",
    type=["csv", "xlsx"],
)
if uploaded is None:
    st.info("Bitte Datei (CSV oder XLSX) hochladen.")
    st.stop()

try:
    df_all = parse_flights_csv_fixed(read_csv_auto(uploaded))
except Exception as e:
    st.error(f"Datei konnte nicht verarbeitet werden: {e}")
    st.stop()

# Spaltenreihenfolge robust setzen: gewünschte Reihenfolge zuerst, übrige Spalten anhängen
desired_cols = ["SIBT", "FLN", "ADEP3", "Typ4", "EPAX", "APAX", "SPAX", "PPOS", "T", "PK"]
new_order = [c for c in desired_cols if c in df_all.columns] + [c for c in df_all.columns if c not in desired_cols]
df_all = df_all[new_order]

st.subheader("Gefundene Flüge mit Merkmal Passkontrolle")
# Formatiere SIBT für Anzeige (europäisches Format TT.MM.YYYY HH:MM)
df_display = df_all.copy()
df_display["SIBT"] = df_display["SIBT"].dt.strftime("%d.%m.%Y %H:%M")
st.dataframe(df_display, use_container_width=True)

ppos_all = sorted(df_all["PPOS"].unique().tolist())
if not ppos_all:
    st.warning("Keine Flüge nach PK-Filter vorhanden.")
    st.stop()


# =========================================================
# Sidebar
# =========================================================
with st.sidebar:
    st.subheader("Passagierdaten")

    init_mix_state()

    with st.expander("Passagiermix", expanded=False):
        # Wichtig: slider mit festen Keys, Werte kommen aus Session-State
        mix_easypass = st.slider("Easypass [%]", 0, 100, 
                                 value=st.session_state["mix_easypass"], 
                                 key="mix_easypass")
        mix_eu_manual = st.slider("EU-manual [%]", 0, 100, 
                                  value=st.session_state["mix_eu_manual"], 
                                  key="mix_eu_manual")
        mix_tcn_at = st.slider("TCN-AT [%]", 0, 100, 
                               value=st.session_state["mix_tcn_at"], 
                               key="mix_tcn_at")
        mix_tcn_vh = st.slider("TCN-VH [%]", 0, 100, 
                               value=st.session_state["mix_tcn_vh"], 
                               key="mix_tcn_vh")
        mix_tcn_ve = st.slider("TCN-VE [%]", 0, 100, 
                               value=st.session_state["mix_tcn_ve"], 
                               key="mix_tcn_ve")

        st.button("Reset Passagiermix", on_click=reset_passenger_mix, key="btn_reset_mix")

        mix_sum = (
            mix_easypass + mix_eu_manual + mix_tcn_at + mix_tcn_vh + mix_tcn_ve
        )
        if mix_sum == 100:
            st.success(f"Summe: {mix_sum}% ✅")
        elif mix_sum < 100:
            st.warning(f"Summe: {mix_sum}% (unter 100%)")
        else:
            st.error(f"Summe: {mix_sum}% ❌ (über 100%)")

    # optional: Rückmeldung beim Reset einblenden
    if st.session_state.get("mix_reset_done"):
        st.toast("Passagiermix auf Default gesetzt.", icon="✅")
        # Flag zurücksetzen, damit Toast nur einmal erscheint
        st.session_state["mix_reset_done"] = False


    with st.expander("EES-Verteilung", expanded=False):
        st.subheader("EES-Verteilung (nur TCN-VH/TCN-VE)")
        ees_choice = st.selectbox(
            "EES_registered : EES_unregistered",
            options=["100:0", "75:25", "50:50", "0:100"],
            index=3,
            )
        ees_registered_share = {"100:0": 1.0, "75:25": 0.75, "50:50": 0.5, "0:100": 0.0}[ees_choice]

    with st.expander("Deboarding", expanded=False):
        st.subheader("Deboarding")
        deboard_offset_min = st.slider("Start nach SIBT [min] (Türen öffnen)", 0, 15, 5)
        deboard_window_min = st.slider("Deboarding-Fenster [min]", 1, 30, 10)

    with st.expander("Gehgeschwindigkeit", expanded=False):
        st.subheader("Fußweg zur Grenzkontrolle")
        walk_speed_mean_mps = st.number_input("Ø Gehgeschwindigkeit [m/s]", min_value=0.3, value=1.25, step=0.05)
        walk_speed_sd_mps = st.number_input("Stdabw. Gehgeschwindigkeit [m/s]", min_value=0.0, value=0.25, step=0.05)
        walk_speed_floor_mps = st.number_input("Min. Gehgeschwindigkeit [m/s]", min_value=0.1, value=0.5, step=0.05)

    st.subheader("Simulationsparameter")

    with st.expander("SSS (Kiosk)", expanded=False):
        sss_enabled = st.checkbox("SSS (Kiosk) aktiv", value=True)
        
    with st.expander("Kapazitäten", expanded=False):
        # Defaults & Max wie gewünscht
        cap_sss = st.slider("SSS (Kiosk)", min_value=0, max_value=6, value=6)
        cap_easypass = st.slider("Easypass", min_value=0, max_value=6, value=6)
        cap_eu = st.slider("EU", min_value=0, max_value=2, value=2)
        cap_tcn = st.slider("TCN", min_value=0, max_value=6, value=2)
    
    with st.expander("Prozesszeit Easypass / EU-manual", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            mean_easypass_s = st.number_input("Easypass Ø", min_value=1.0, value=MEAN_EASYPASS_S, step=1.0)
            sd_easypass_s = st.number_input("Easypass Stdabw.", min_value=0.0, value=SD_EASYPASS_S, step=1.0)
        with c2:
            mean_eu_s = st.number_input("EU Ø", min_value=1.0, value=MEAN_EU_S, step=1.0)
            sd_eu_s = st.number_input("EU Stdabw.", min_value=0.0, value=SD_EU_S, step=1.0)

    with st.expander("Prozesszeit SSS (Kiosk)", expanded=False):
        c3, c4 = st.columns(2)
        with c3:
            st.markdown("**TCN-VH**")
            mean_sss_vh_reg_s = st.number_input("SSS VH reg Ø", min_value=1.0, value=MEAN_SSS_VH_REG_S, step=1.0)
            sd_sss_vh_reg_s = st.number_input("SSS VH reg Stdabw.", min_value=0.0, value=SD_SSS_VH_REG_S, step=1.0)
            mean_sss_vh_unreg_s = st.number_input("SSS VH unreg Ø", min_value=1.0, value=MEAN_SSS_VH_UNREG_S, step=1.0)
            sd_sss_vh_unreg_s = st.number_input("SSS VH unreg Stdabw.", min_value=0.0, value=SD_SSS_VH_UNREG_S, step=1.0)
        with c4:
            st.markdown("**TCN-VE**")
            mean_sss_ve_reg_s = st.number_input("SSS VE reg Ø", min_value=1.0, value=MEAN_SSS_VE_REG_S, step=1.0)
            sd_sss_ve_reg_s = st.number_input("SSS VE reg Stdabw.", min_value=0.0, value=SD_SSS_VE_REG_S, step=1.0)
            mean_sss_ve_unreg_s = st.number_input("SSS VE unreg Ø", min_value=1.0, value=MEAN_SSS_VE_UNREG_S, step=1.0)
            sd_sss_ve_unreg_s = st.number_input("SSS VE unreg Stdabw.", min_value=0.0, value=SD_SSS_VE_UNREG_S, step=1.0)

    with st.expander("Prozesszeit TCN-manual", expanded=False):
        c5, c6 = st.columns(2)
        with c5:
            st.markdown("**TCN-VH**")
            # Choose TCN defaults based on SSS enabled/disabled
            tcn_vh_reg_default = MEAN_TCN_VH_REG_S_SSS_ENABLED if sss_enabled else MEAN_TCN_VH_REG_S_SSS_DISABLED
            tcn_vh_reg_sd_default = SD_TCN_VH_REG_S_SSS_ENABLED if sss_enabled else SD_TCN_VH_REG_S_SSS_DISABLED
            tcn_vh_unreg_default = MEAN_TCN_VH_UNREG_S_SSS_ENABLED if sss_enabled else MEAN_TCN_VH_UNREG_S_SSS_DISABLED
            tcn_vh_unreg_sd_default = SD_TCN_VH_UNREG_S_SSS_ENABLED if sss_enabled else SD_TCN_VH_UNREG_S_SSS_DISABLED
            mean_tcn_vh_reg_s = st.number_input("TCN VH reg Ø", min_value=1.0, value=tcn_vh_reg_default, step=1.0)
            sd_tcn_vh_reg_s = st.number_input("TCN VH reg Stdabw.", min_value=0.0, value=tcn_vh_reg_sd_default, step=1.0)
            mean_tcn_vh_unreg_s = st.number_input("TCN VH unreg Ø", min_value=1.0, value=tcn_vh_unreg_default, step=1.0)
            sd_tcn_vh_unreg_s = st.number_input("TCN VH unreg Stdabw.", min_value=0.0, value=tcn_vh_unreg_sd_default, step=1.0)
        with c6:
            st.markdown("**TCN-VE**")
            # Choose TCN defaults based on SSS enabled/disabled
            tcn_ve_reg_default = MEAN_TCN_VE_REG_S_SSS_ENABLED if sss_enabled else MEAN_TCN_VE_REG_S_SSS_DISABLED
            tcn_ve_reg_sd_default = SD_TCN_VE_REG_S_SSS_ENABLED if sss_enabled else SD_TCN_VE_REG_S_SSS_DISABLED
            tcn_ve_unreg_default = MEAN_TCN_VE_UNREG_S_SSS_ENABLED if sss_enabled else MEAN_TCN_VE_UNREG_S_SSS_DISABLED
            tcn_ve_unreg_sd_default = SD_TCN_VE_UNREG_S_SSS_ENABLED if sss_enabled else SD_TCN_VE_UNREG_S_SSS_DISABLED
            mean_tcn_ve_reg_s = st.number_input("TCN VE reg Ø", min_value=1.0, value=tcn_ve_reg_default, step=1.0)
            sd_tcn_ve_reg_s = st.number_input("TCN VE reg Stdabw.", min_value=0.0, value=tcn_ve_reg_sd_default, step=1.0)
            mean_tcn_ve_unreg_s = st.number_input("TCN VE unreg Ø", min_value=1.0, value=tcn_ve_unreg_default, step=1.0)
            sd_tcn_ve_unreg_s = st.number_input("TCN VE unreg Stdabw.", min_value=0.0, value=tcn_ve_unreg_sd_default, step=1.0)

    # Prozesszeit-Skalierung (100%..200%) — multipliziert alle Prozesszeiten
    with st.expander("Prozesszeit-Skalierung", expanded=False):
        process_time_scale_pct = st.slider("Prozesszeit-Skalierung [%]", 100, 200, 150)
        process_time_scale = process_time_scale_pct / 100.0

    st.subheader("Sonstiges")

    with st.expander("Sonstiges", expanded=False):
        st.subheader("Routing")
        tcn_at_policy = st.selectbox("TCN-AT Routing", ["load", "queue"])
        seed = st.number_input("Random Seed", min_value=0, value=42, step=1)

        st.subheader("Datenfilter")
        ppos_selected = st.multiselect("Parkpositionen (PPOS)", options=ppos_all, default=ppos_all)

        st.subheader("Referenzlinien")
        threshold_pax_length = st.slider("Warteschlange", 20, 300, 50)
        threshold_wait_s = st.slider("Ø Wartezeit [s]", 0, 120, 60)

    with st.form("sim_form", clear_on_submit=False):
        run_btn = st.form_submit_button(
            "Simulation starten",
            type="primary",
            disabled=(mix_sum != 100),
        )


# =========================================================
# Relevante Flüge nach PPOS
# =========================================================
flights, t0, df_selected, fallback_count = flights_to_sim_input(df_all, ppos_selected)
st.subheader("In die Simulation eingehende Flüge (nach PPOS-Auswahl)")
# Formatiere SIBT für Anzeige (europäisches Format TT.MM.YYYY HH:MM)
df_selected_display = df_selected.copy()
df_selected_display["SIBT"] = df_selected_display["SIBT"].dt.strftime("%d.%m.%Y %H:%M")
st.dataframe(df_selected_display, use_container_width=True)

# Warnen, wenn für einige Zeilen weder APAX noch EPAX vorhanden waren und Default verwendet wurde
if fallback_count > 0:
    st.warning(f"{fallback_count} Flüge ohne APAX/EPAX — Standardwert verwendet.")

if not flights:
    st.warning("Keine Flüge nach PPOS-Auswahl.")
    st.stop()


# =========================================================
# Simulation (nur Submit) + Persistenz
# =========================================================
if run_btn:
    if mix_sum != 100:
        st.error("Passagiermix muss exakt 100% ergeben.")
        st.stop()

    cfg = SimConfig(
        # Kapazitäten
        cap_sss=(cap_sss if sss_enabled else 0),
        cap_easypass=cap_easypass,
        cap_eu=cap_eu,
        cap_tcn=cap_tcn,

        # Deboarding & Fußweg
        deboard_offset_min=deboard_offset_min,
        deboard_window_min=deboard_window_min,

        # SSS
        sss_enabled=sss_enabled,

        walk_speed_mean_mps=walk_speed_mean_mps,
        walk_speed_sd_mps=walk_speed_sd_mps,
        walk_speed_floor_mps=walk_speed_floor_mps,

        # Mix
        share_easypass=mix_easypass / 100.0,
        share_eu_manual=mix_eu_manual / 100.0,
        share_tcn_at=mix_tcn_at / 100.0,
        share_tcn_vh=mix_tcn_vh / 100.0,
        share_tcn_ve=mix_tcn_ve / 100.0,

        # Routing
        tcn_at_policy=tcn_at_policy,

        # EES
        ees_registered_share=ees_registered_share,

        # Servicezeiten (Easypass/EU) - skaliert
        mean_easypass_s=mean_easypass_s * process_time_scale,
        sd_easypass_s=sd_easypass_s * process_time_scale,
        mean_eu_s=mean_eu_s * process_time_scale,
        sd_eu_s=sd_eu_s * process_time_scale,

        # SSS: 4 Varianten - skaliert
        mean_sss_vh_reg_s=mean_sss_vh_reg_s * process_time_scale,
        sd_sss_vh_reg_s=sd_sss_vh_reg_s * process_time_scale,
        mean_sss_vh_unreg_s=mean_sss_vh_unreg_s * process_time_scale,
        sd_sss_vh_unreg_s=sd_sss_vh_unreg_s * process_time_scale,
        mean_sss_ve_reg_s=mean_sss_ve_reg_s * process_time_scale,
        sd_sss_ve_reg_s=sd_sss_ve_reg_s * process_time_scale,
        mean_sss_ve_unreg_s=mean_sss_ve_unreg_s * process_time_scale,
        sd_sss_ve_unreg_s=sd_sss_ve_unreg_s * process_time_scale,

        # TCN: 4 Varianten - skaliert
        mean_tcn_vh_reg_s=mean_tcn_vh_reg_s * process_time_scale,
        sd_tcn_vh_reg_s=sd_tcn_vh_reg_s * process_time_scale,
        mean_tcn_vh_unreg_s=mean_tcn_vh_unreg_s * process_time_scale,
        sd_tcn_vh_unreg_s=sd_tcn_vh_unreg_s * process_time_scale,
        mean_tcn_ve_reg_s=mean_tcn_ve_reg_s * process_time_scale,
        sd_tcn_ve_reg_s=sd_tcn_ve_reg_s * process_time_scale,
        mean_tcn_ve_unreg_s=mean_tcn_ve_unreg_s * process_time_scale,
        sd_tcn_ve_unreg_s=sd_tcn_ve_unreg_s * process_time_scale,
    )

    model = run_simulation(flights, cfg, seed=int(seed))

    st.session_state["last_model"] = model
    st.session_state["last_cfg"] = cfg
    st.session_state["last_t0"] = t0
    st.session_state["last_df_selected"] = df_selected
    
    summary = model.control_summary()


# =========================================================
# Ergebnisse anzeigen (falls vorhanden)
# =========================================================
if "last_model" not in st.session_state:
    st.info("Parameter einstellen und „Simulation starten“ klicken.")
    st.stop()

model = st.session_state["last_model"]
t0 = st.session_state["last_t0"]

df_res = pd.DataFrame([r.__dict__ for r in model.results])
df_ts = pd.DataFrame(model.queue_ts).drop_duplicates(subset=["t_min"]).sort_values("t_min")

if df_res.empty:
    st.warning("Keine Passagiere simuliert.")
    st.stop()

# Gesamtwartezeit
df_res["wait_total"] = df_res["wait_sss"] + df_res["wait_easypass"] + df_res["wait_eu"] + df_res["wait_tcn"]

# Optional: 4er-Gruppe (VH/VE × EES) sichtbar machen
if "ees_status" in df_res.columns:
    df_res["group_4"] = df_res["group"]
    mask = df_res["group"].isin(["TCN_VH", "TCN_VE"])
    df_res.loc[mask, "group_4"] = (
        df_res.loc[mask, "group"] + "_" + df_res.loc[mask, "ees_status"].fillna("NA")
    )
else:
    df_res["group_4"] = df_res["group"]


# =========================
# Kontrollwerte – Passagierverteilung
# =========================

total = int(len(df_res))

# =========================
# KPIs Gesamt
# =========================
st.subheader("KPIs Gesamt")
kpi = pd.DataFrame([{
    "Passagiere": int(len(df_res)),
    "Ø Wartezeit gesamt [min]": float(df_res["wait_total"].mean()),
    "P95 Wartezeit gesamt [min]": float(df_res["wait_total"].quantile(0.95)),
    "Ø Systemzeit [min]": float(df_res["system_min"].mean()),
    "P95 Systemzeit [min]": float(df_res["system_min"].quantile(0.95)),
}])
st.dataframe(kpi, use_container_width=True)


# =========================
# Plots
# =========================
#st.subheader("Warteschlangen (Zeitverlauf)")
#plot_queue_over_time(df_ts, t0, title="Warteschlangen je Prozessstelle")

st.subheader("Warteschlangen (rollierend 15 min)")
# Honor SSS enabled/disabled: hide SSS plot when SSS disabled in the model
show_sss = bool(getattr(model, "cfg", None) and getattr(model.cfg, "sss_enabled", True))
plot_queue_over_time_rolling(df_ts, t0, window_min=15, step_min=1, show_sss=show_sss)

st.subheader("Ø Wartezeit je Prozessstelle (rollierend 15 min)")
plot_mean_wait_over_time_rolling(df_res, t0, window_min=15, step_min=1, show_sss=show_sss)

# =========================
# Flight Summary
# =========================
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
st.dataframe(df_fsum, use_container_width=True)

# =========================
# Group Summary (inkl. VH/VE × EES)
# =========================
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
st.dataframe(df_gsum, use_container_width=True)

# =========================
# Passenger Detail
# =========================
st.subheader("Detaildaten (Passagiere)")
st.dataframe(df_res, use_container_width=True)

# Optional: CSV-Download der Passenger-Details
csv_bytes = df_res.to_csv(index=False).encode("utf-8")
st.download_button(
    "Passenger-Details als CSV herunterladen",
    data=csv_bytes,
    file_name="passenger_results.csv",
    mime="text/csv",
)
