import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine import SimConfig


def _to_time_axis(t0: pd.Timestamp, t_min_series: pd.Series) -> pd.Series:
    return t0 + pd.to_timedelta(t_min_series, unit="m")

# Farbschema für die Prozessstellen
STATION_COLORS = {
    "SSS (Kiosk)": "#f27527",  # Orange
    "Easypass": "#34d6ee",     # Cyan
    "EU": "#003399",           # Blau
    "TCN": "#d62728",          # Rot
}

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
    fig.add_trace(go.Scatter(x=x, y=df_plot["q_sss"], mode="lines", name="SSS (Kiosk)", line=dict(color=STATION_COLORS["SSS (Kiosk)"])))
    fig.add_trace(go.Scatter(x=x, y=df_plot["q_easypass"], mode="lines", name="Easypass", line=dict(color=STATION_COLORS["Easypass"])))
    fig.add_trace(go.Scatter(x=x, y=df_plot["q_eu"], mode="lines", name="EU", line=dict(color=STATION_COLORS["EU"])))
    fig.add_trace(go.Scatter(x=x, y=df_plot["q_tcn"], mode="lines", name="TCN", line=dict(color=STATION_COLORS["TCN"])))


    fig.update_layout(
        title=title,
        xaxis_title="Uhrzeit",
        yaxis_title="Wartende Passagiere",
        hovermode="x unified",
        legend_title_text="Prozessstelle",
    )
    st.plotly_chart(fig, width="stretch")


def build_queue_timeseries_rolling(
    df_ts: pd.DataFrame,
    t0: pd.Timestamp,
    col: str,
    window_min: int = 15,
    step_min: int = 1,
) -> pd.DataFrame:
    
    # Rolling mean der Queue-Länge über (t-window, t] auf Zeitraster (step_min).
    # df_ts: enthält t_min und q_*
    
    # WICHTIG: drop_duplicates("t_min") entfernt, damit Daten aus mehreren Runs (mit gleichen Zeitstempeln) erhalten bleiben
    df = df_ts[["t_min", col]].dropna().sort_values("t_min")

    # Zeitbereich bestimmen: Fix 06:00 bis 24:00
    day_start = t0.normalize()
    t_start_fixed = day_start + pd.Timedelta(hours=6)
    t_end_fixed = day_start + pd.Timedelta(hours=24)
    min_rel_start = (t_start_fixed - t0).total_seconds() / 60.0
    min_rel_end = (t_end_fixed - t0).total_seconds() / 60.0

    t_start = min_rel_start
    t_end = min_rel_end

    if df.empty:
        grid = pd.DataFrame({"t_min": [t_start + i * step_min for i in range(int((t_end - t_start) / step_min) + 1)]})
        grid["mean_q"] = 0.0
        return grid

    t_vals = df["t_min"].to_numpy()
    q_vals = df[col].to_numpy()
    n = len(df)

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

        means.append(q_vals[left:right].mean() if right > left else 0.0)

    grid["mean_q"] = means
    return grid


def plot_queue_over_time_rolling(
    df_ts: pd.DataFrame,
    t0: pd.Timestamp,
    threshold: float,
    window_min: int = 15,
    step_min: int = 1,
    show_sss: bool = True,
    subset: list[str] | None = None,
):
    fig = go.Figure()

    cols = [
        ("q_sss", "SSS (Kiosk)"),
        ("q_easypass", "Easypass"),
        ("q_eu", "EU"),
        ("q_tcn", "TCN"),
    ]

    if subset:
        cols = [c for c in cols if c[1] in subset]

    if not show_sss:
        cols = [c for c in cols if c[0] != "q_sss"]

    for col, label in cols:
        ts = build_queue_timeseries_rolling(df_ts, t0, col, window_min=window_min, step_min=step_min)
        if ts.empty:
            continue
        x = _to_time_axis(t0, ts["t_min"])
        fig.add_trace(go.Scatter(x=x, y=ts["mean_q"], mode="lines", name=label, line=dict(color=STATION_COLORS.get(label, "black"))))

    fig.add_hline(y=threshold, line_dash="dash", annotation_text=f"Schwellwert = {threshold}")

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

    title = f"Warteschlangen je Prozessstelle (rollierend {window_min} min)"
    if subset:
        title += f" ({', '.join(subset)})"

    fig.update_layout(
        title=title,
        xaxis_title="Uhrzeit",
        yaxis_title="Ø wartende Passagiere",
        hovermode="x unified",
        legend_title_text="Prozessstelle",
    )
    st.plotly_chart(fig, width="stretch")


def build_wait_time_timeseries_rolling(
    df_res: pd.DataFrame,
    t0: pd.Timestamp,
    station: str,
    window_min: int = 15,
    step_min: int = 1,
) -> pd.DataFrame:
    
    # Rolling mean der Wartezeit über Passagiere, die in (t-window, t] ihren Service an der Station starten.
    # t = arrival_min + wait_station
    
    wait_col = f"wait_{station}"
    serv_col = f"serv_{station}"

    df = df_res[df_res[serv_col] > 0].copy()

    # Zeitbereich bestimmen: Fix 06:00 bis 24:00
    day_start = t0.normalize()
    t_start_fixed = day_start + pd.Timedelta(hours=6)
    t_end_fixed = day_start + pd.Timedelta(hours=24)
    min_rel_start = (t_start_fixed - t0).total_seconds() / 60.0
    min_rel_end = (t_end_fixed - t0).total_seconds() / 60.0

    t_start = min_rel_start
    t_end = min_rel_end

    if df.empty:
        grid = pd.DataFrame({"t_min": [t_start + i * step_min for i in range(int((t_end - t_start) / step_min) + 1)]})
        grid["mean_wait"] = 0.0
        return grid

    df["t_min"] = df["arrival_min"] + df[wait_col]
    df = df.sort_values("t_min")

    t_vals = df["t_min"].to_numpy()
    w_vals = df[wait_col].to_numpy()
    n = len(df)

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
        means.append(w_vals[left:right].mean() if right > left else 0.0)

    grid["mean_wait"] = means
    return grid


def plot_mean_wait_over_time_rolling(
    df_res: pd.DataFrame,
    df_ts: pd.DataFrame,
    cfg: "SimConfig",
    t0: pd.Timestamp,
    threshold: float,
    window_min: int = 15,
    step_min: int = 1,
    show_sss: bool = True,
    subset: list[str] | None = None,
):
    # Check if TCN is in the subset to decide if we need a secondary axis
    has_tcn_secondary_axis = subset and "TCN" in subset

    if has_tcn_secondary_axis:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
    else:
        fig = go.Figure()

    def _stations_iter(show_sss: bool = True):
        stations = [
            ("sss", "SSS (Kiosk)"),
            ("easypass", "Easypass"),
            ("eu", "EU"),
            ("tcn", "TCN"),
        ]
        if subset:
            stations = [s for s in stations if s[1] in subset]
        if not show_sss:
            stations = [s for s in stations if s[0] != "sss"]
        return stations

    for station, label in _stations_iter(show_sss=show_sss):
        ts = build_wait_time_timeseries_rolling(df_res, t0, station, window_min=window_min, step_min=step_min)
        if ts.empty:
            continue
        x = _to_time_axis(t0, ts["t_min"])
        trace = go.Scatter(x=x, y=ts["mean_wait"], mode="lines", name=label, line=dict(color=STATION_COLORS.get(label, "black")))
        if has_tcn_secondary_axis:
            fig.add_trace(trace, secondary_y=False)
        else:
            fig.add_trace(trace)

    # Add the secondary axis for TCN usage
    if has_tcn_secondary_axis:
        schedule = cfg.cap_tcn_schedule
        x_points = []
        y_points = []
        
        day_start = t0.normalize()

        points = []
        for key, cap in schedule.items():
            start_h = int(key.split('-')[0])
            points.append((start_h, cap))
        points.sort()

        for start_h, cap in points:
            x_points.append(day_start + pd.Timedelta(hours=start_h))
            y_points.append(cap)
        
        x_points.append(day_start + pd.Timedelta(hours=24))
        y_points.append(y_points[-1])

        fig.add_trace(
            go.Scatter(
                x=x_points,
                y=y_points,
                name="Verfügbare TCN-Schalter",
                mode='lines',
                line=dict(color='grey', dash='dot', shape='hv'),
            ),
            secondary_y=True,
        )

    if has_tcn_secondary_axis:
        fig.add_hline(y=threshold, line_dash="dash", annotation_text=f"Schwellwert = {threshold}", annotation_position="left", secondary_y=False)
    else:
        fig.add_hline(y=threshold, line_dash="dash", annotation_text=f"Schwellwert = {threshold}", annotation_position="left")

    title = f"Ø Wartezeit je Prozessstelle (rollierend {window_min} min)"
    if subset:
        title += f" ({', '.join(subset)})"

    fig.update_layout(
        title=title,
        xaxis_title="Uhrzeit",
        hovermode="x unified",
        legend_title_text="Prozessstelle",
    )
    # Set y-axis titles
    if has_tcn_secondary_axis:
        # Manuelle Skalierung der Achsen, um das 10:1-Verhältnis zu gewährleisten
        
        # 1. Max-Werte für beide Achsen ermitteln
        max_wait = 0
        for trace in fig.data:
            if (trace.yaxis is None or trace.yaxis == 'y1') and trace.y is not None and len(trace.y) > 0:
                max_wait = max(max_wait, max(trace.y))
        
        max_cap = max(cfg.cap_tcn_schedule.values()) if cfg and cfg.cap_tcn_schedule else 6

        # 2. Zielbereiche bestimmen
        y1_range_target = max_wait * 1.1 # Auto-Range mit 10% Puffer
        y2_range_target = max_cap + 1    # Kapazität + 1 Puffer

        # 3. Bereiche anpassen, um das 10:1-Verhältnis zu erzwingen
        if y1_range_target / y2_range_target > 10:
            # Wartezeit ist dominant, passe Schalter-Achse an
            final_y1_range = [0, y1_range_target]
            final_y2_range = [0, y1_range_target / 10]
        else:
            # Kapazität ist dominant, passe Wartezeit-Achse an
            final_y2_range = [0, y2_range_target]
            final_y1_range = [0, y2_range_target * 10]

        fig.update_yaxes(title_text="Ø Wartezeit [min]", secondary_y=False, range=final_y1_range)
        fig.update_yaxes(
            title_text="Anzahl Schalter", 
            secondary_y=True,
            range=final_y2_range,
            showgrid=False,
            dtick=1,
        )
    else:
        fig.update_yaxes(title_text="Ø Wartezeit [min]")

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
    st.plotly_chart(fig, width="stretch")


def plot_wait_heatmap(
    df_res: pd.DataFrame,
    t0: pd.Timestamp,
    show_sss: bool = True,
    bin_min: int = 60,
):
    if df_res.empty:
        return

    # Wir wollen Wartezeiten pro Zeitfenster (Ankunftszeit) aggregieren
    # Stationen definieren: (Spalte genutzt?, Spalte Wartezeit)
    stations_map = {
        "TCN": ("used_tcn", "wait_tcn"),
        "EU": ("used_eu", "wait_eu"),
        "Easypass": ("used_easypass", "wait_easypass"),
    }
    if show_sss:
        stations_map["SSS (Kiosk)"] = ("used_sss", "wait_sss")

    # Zeitbereich bestimmen: Fix 06:00 bis 24:00
    day_start = t0.normalize()
    t_start_fixed = day_start + pd.Timedelta(hours=6)
    t_end_fixed = day_start + pd.Timedelta(hours=24)
    
    min_rel_start = (t_start_fixed - t0).total_seconds() / 60.0
    min_rel_end = (t_end_fixed - t0).total_seconds() / 60.0
    
    start_bin = int((min_rel_start // bin_min) * bin_min)
    end_bin = int((min_rel_end // bin_min) * bin_min)
    
    # Range bis end_bin (exklusiv), d.h. letzter Bin startet vor 24:00 (z.B. 23:45)
    full_idx = range(start_bin, end_bin, bin_min)
    
    # Ergebnis-Dict für Z-Werte
    z_data = {}
    
    # Für jede Station aggregieren
    for label, (col_used, col_wait) in stations_map.items():
        # Filtern auf Passagiere, die die Station genutzt haben
        mask = df_res[col_used] == True
        df_sub = df_res[mask].copy()
        
        if df_sub.empty:
            z_data[label] = pd.Series(0, index=full_idx)
        else:
            df_sub["t_bin"] = (df_sub["arrival_min"] // bin_min).astype(int) * bin_min
            # Mean wait per bin
            grouped = df_sub.groupby("t_bin")[col_wait].quantile(0.95)
            z_data[label] = grouped.reindex(full_idx, fill_value=0)
    
    x = _to_time_axis(t0, pd.Series(full_idx))
    
    # Y-Achse und Z-Daten vorbereiten (Reihenfolge für Anzeige)
    # Plotly Y-Achse ist Bottom-to-Top.
    # Gewünscht (Oben nach Unten): SSS, TCN, EU, Easypass
    # Also Liste (Unten nach Oben): Easypass, EU, TCN, SSS
    ordered_keys = ["Easypass", "EU", "TCN"]
    if show_sss:
        ordered_keys.append("SSS (Kiosk)")
        
    z = [z_data[k].values for k in ordered_keys]
    
    fig = go.Figure(data=go.Heatmap(
        z=z, x=x, y=ordered_keys,
        colorscale="RdYlGn_r",
        ygap=3,
        zmin=0, zmax=45,
        colorbar=dict(
            title=dict(
                text="P95 Min",
                font=dict(size=14)
            ),
            tickfont=dict(size=12)
        ),
        hovertemplate="<b>%{y}</b><br>Ankunft ab: %{x}<br>P95 Wartezeit: %{z:.1f} min<extra></extra>"
    ))
    
    fig.update_layout(
        title=f"Heatmap: P95 Wartezeit (Minuten) - {bin_min} min Raster",
        xaxis_title="Ankunftszeit",
        yaxis_title=None,
        yaxis=dict(tickfont=dict(size=14)),
        title_font_size=18,
        height=300,
        margin=dict(l=0, r=0, t=40, b=0)
    )
    st.plotly_chart(fig, width="stretch")
