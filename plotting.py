import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from engine import SimConfig


def _to_time_axis(t0: pd.Timestamp, t_min_series: pd.Series) -> pd.Series:
    return t0 + pd.to_timedelta(t_min_series, unit="m")

# =========================================================
# Plotting Colors
# =========================================================
STATION_COLORS = {
    "SSS (Kiosk)": "#f27527",  # Orange
    "Easypass": "#34d6ee",     # Cyan
    "EU": "#003399",           # Blau
    "TCN": "#94C11C",          # Grün
}

TERMINAL_COLORS = {
    "T1": "#9D9D9D", 
    "T2": "#00A8A1"
}

HEATMAP_COLORS = [
    '#0962A9',  # <= 10 min
    '#3F79A8',  # 11-20 min
    '#7F8B7A',  # 21-30 min
    '#C48A3F',  # 31-45 min
    '#EF7C00',  # > 45 min
]

def get_heatmap_colorscale(zmax_val: float = 60.0) -> list:
    """Creates the discrete colorscale for the wait time heatmap."""
    return [
        # Range 1: <= 10 min
        [0.0, HEATMAP_COLORS[0]],
        [10/zmax_val, HEATMAP_COLORS[0]],
        # Range 2: > 10 to <= 20 min
        [10/zmax_val, HEATMAP_COLORS[1]],
        [20/zmax_val, HEATMAP_COLORS[1]],
        # Range 3: > 20 to <= 30 min
        [20/zmax_val, HEATMAP_COLORS[2]],
        [30/zmax_val, HEATMAP_COLORS[2]],
        # Range 4: > 30 to <= 45 min
        [30/zmax_val, HEATMAP_COLORS[3]],
        [45/zmax_val, HEATMAP_COLORS[3]],
        # Range 5: > 45 min
        [45/zmax_val, HEATMAP_COLORS[4]],
        [1.0, HEATMAP_COLORS[4]],
    ]

def _build_rolling_mean_timeseries(
    df_data: pd.DataFrame,
    t0: pd.Timestamp,
    time_col: str,
    value_col: str,
    window_min: int = 15,
    step_min: int = 1,
) -> pd.DataFrame:
    """Calculates a rolling mean over a time series on a fixed time grid.

    This function implements an efficient two-pointer algorithm to calculate
    the rolling mean of a value column over a specified time window. The
    calculation is performed on a fixed time grid from 06:00 to 24:00 on the
    day of the simulation start time (t0).

    Args:
        df_data: The input DataFrame containing the time and value data.
        t0: The reference start time of the simulation (t=0), used to
            establish the absolute time grid.
        time_col: The name of the column in `df_data` with time values
            (in minutes relative to t0).
        value_col: The name of the column in `df_data` with values to be
            averaged.
        window_min: The size of the rolling window in minutes. The mean is
            calculated for data points in the interval (t - window_min, t].
        step_min: The step size for the output time grid in minutes.

    Returns:
        A DataFrame with two columns: 't_min' for the time grid and
        'mean_value' for the calculated rolling mean at each grid point.
    """
    df = df_data[[time_col, value_col]].dropna().sort_values(time_col)

    # Define fixed time range: 06:00 to 24:00
    day_start = t0.normalize()
    t_start_fixed = day_start + pd.Timedelta(hours=6)
    t_end_fixed = day_start + pd.Timedelta(hours=24)
    min_rel_start = (t_start_fixed - t0).total_seconds() / 60.0
    min_rel_end = (t_end_fixed - t0).total_seconds() / 60.0

    t_start = min_rel_start
    t_end = min_rel_end

    grid = pd.DataFrame({
        "t_min": [t_start + i * step_min for i in range(int((t_end - t_start) / step_min) + 1)]
    })

    if df.empty:
        grid["mean_value"] = 0.0
        return grid

    t_vals = df[time_col].to_numpy()
    val_vals = df[value_col].to_numpy()
    n = len(df)

    means = []
    left = 0
    right = 0

    for t in grid["t_min"].to_numpy():
        while right < n and t_vals[right] <= t:
            right += 1
        while left < n and t_vals[left] < t - window_min:
            left += 1
        means.append(val_vals[left:right].mean() if right > left else 0.0)

    grid["mean_value"] = means
    return grid


def build_queue_timeseries_rolling(
    df_ts: pd.DataFrame,
    t0: pd.Timestamp,
    col: str,
    window_min: int = 15,
    step_min: int = 1,
) -> pd.DataFrame:
    
    # Rolling mean der Queue-Länge über (t-window, t] auf Zeitraster (step_min).
    # df_ts: enthält t_min und q_*
    
    grid = _build_rolling_mean_timeseries(
        df_data=df_ts,
        t0=t0,
        time_col="t_min",
        value_col=col,
        window_min=window_min,
        step_min=step_min,
    )
    return grid.rename(columns={"mean_value": "mean_q"})


def plot_queue_over_time_rolling(
    list_of_ts_data: list,
    t0: pd.Timestamp,
    window_min: int = 15,
    y_max: Optional[float] = None,
):
    fig = go.Figure()

    for ts, label in list_of_ts_data:
        if ts.empty:
            continue
        x = _to_time_axis(t0, ts["t_min"])
        fig.add_trace(go.Scatter(x=x, y=ts["mean_q"], mode="lines", name=label, line=dict(color=STATION_COLORS.get(label, "black"), width=2.5)))

    fig.update_layout(
        xaxis_title=None,
        yaxis_title="Ø wartende Passagiere",
        hovermode="x unified",
        legend_title_text="",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5
        ),
    )
    if y_max is not None:
        fig.update_yaxes(range=[0, y_max * 1.1])

    st.plotly_chart(fig, use_container_width=True)


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

    df_filtered = df_res[df_res[serv_col] > 0].copy()
    
    if df_filtered.empty:
        # Pass an empty dataframe to the helper to get a zero-filled grid
        df_prepared = pd.DataFrame(columns=["service_start_time", wait_col])
    else:
        df_filtered["service_start_time"] = df_filtered["arrival_min"] + df_filtered[wait_col]
        df_prepared = df_filtered

    grid = _build_rolling_mean_timeseries(
        df_data=df_prepared,
        t0=t0,
        time_col="service_start_time",
        value_col=wait_col,
        window_min=window_min,
        step_min=step_min,
    )
    return grid.rename(columns={"mean_value": "mean_wait"})


def plot_mean_wait_over_time_rolling(
    list_of_ts_data: list,
    t0: pd.Timestamp,
    window_min: int = 15,
    y_max: Optional[float] = None,
    cfg: Optional["SimConfig"] = None,
):
    # Check if TCN is in the subset to decide if we need a secondary axis
    has_tcn_secondary_axis = cfg is not None

    if has_tcn_secondary_axis:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
    else:
        fig = go.Figure()

    max_wait_from_data = 0
    for ts, label in list_of_ts_data:
        if ts.empty:
            continue
        if not ts['mean_wait'].empty:
            max_wait_from_data = max(max_wait_from_data, ts['mean_wait'].max())

        x = _to_time_axis(t0, ts["t_min"])
        trace = go.Scatter(x=x, y=ts["mean_wait"], mode="lines", name=label, line=dict(color=STATION_COLORS.get(label, "black"), width=2.5))
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
                line=dict(color='grey', dash='dot', shape='hv', width=2.5),
            ),
            secondary_y=True,
        )
    fig.update_layout(
        xaxis_title=None,
        hovermode="x unified",
        legend_title_text="",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5
        ),
    )
    # Set y-axis titles
    if has_tcn_secondary_axis:
        # Manuelle Skalierung der Achsen, um das 10:1-Verhältnis zu gewährleisten und sicherzustellen, dass alle Daten sichtbar sind.

        max_wait = y_max if y_max is not None else max_wait_from_data
        
        max_cap = max(cfg.cap_tcn_schedule.values()) if cfg and cfg.cap_tcn_schedule else 6

        # 2. Erforderliche obere Grenzen für die Achsen berechnen
        y1_max_required = max_wait * 1.1  # 10% Puffer für die Wartezeit-Achse
        y2_max_desired = max_cap + 1      # Puffer für die Kapazitäts-Achse (max. 7)

        # 3. Prüfen, ob die gewünschte Kapazitäts-Achse ausreicht, um die Wartezeit im 10:1-Verhältnis darzustellen
        if y1_max_required <= y2_max_desired * 10:
            # Ja, die Kapazitäts-Achse kann bei max. 7 bleiben und die Wartezeit-Achse wird entsprechend skaliert
            final_y2_range = [0, y2_max_desired]
            final_y1_range = [0, y2_max_desired * 10]
        else:
            # Nein, die Wartezeit ist zu hoch. Die Wartezeit-Achse bestimmt die Skalierung, und die Kapazitäts-Achse wird mitgezogen.
            final_y1_range = [0, y1_max_required]
            final_y2_range = [0, y1_max_required / 10]

        fig.update_yaxes(title_text="Ø Wartezeit [min]", secondary_y=False, range=final_y1_range)
        fig.update_yaxes(
            title_text=None,
            secondary_y=True,
            range=final_y2_range,
            showgrid=False,
            dtick=1,
        )
    else:
        max_wait = y_max if y_max is not None else max_wait_from_data
        fig.update_yaxes(title_text="Ø Wartezeit [min]", range=[0, max_wait * 1.1])

    st.plotly_chart(fig, use_container_width=True)


def _get_wait_heatmap_traces(
    df_res: pd.DataFrame,
    t0: pd.Timestamp,
    show_sss: bool = True,
    bin_min: int = 60,
    t_start_fixed: pd.Timestamp = None,
    t_end_fixed: pd.Timestamp = None,
):
    if df_res.empty:
        return [], []

    # Wir wollen Wartezeiten pro Zeitfenster (Ankunftszeit) aggregieren
    # Stationen definieren: (Spalte genutzt?, Spalte Wartezeit)
    stations_map = {
        "TCN": ("used_tcn", "wait_tcn"),
        "EU": ("used_eu", "wait_eu"),
        "Easypass": ("used_easypass", "wait_easypass"),
    }
    if show_sss:
        stations_map["SSS (Kiosk)"] = ("used_sss", "wait_sss")

    
    min_rel_start = (t_start_fixed - t0).total_seconds() / 60.0
    min_rel_end = (t_end_fixed - t0).total_seconds() / 60.0
    
    start_bin = int((min_rel_start // bin_min) * bin_min)
    end_bin = int((min_rel_end // bin_min) * bin_min)
    
    # Range bis end_bin (exklusiv), d.h. letzter Bin startet vor 24:00 (z.B. 23:45)
    full_idx = range(start_bin, end_bin, bin_min)
    
    # Ergebnis-Dict für Z-Werte
    z_data = {}
    
    # Aggregate for each station
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
    text_z = [[f'{val:.1f}' if val > 0 else '' for val in row] for row in z]
    
    # Definieren der diskreten Farbskala
    zmax_val = 60.0  # Set a new max for the colorscale to include the >45 range
    heatmap_colorscale = get_heatmap_colorscale(zmax_val)
    
    heatmap_trace = go.Heatmap( # Changed to return trace
        z=z, x=x, y=ordered_keys,
        text=text_z,
        texttemplate="%{text}",
        textfont={"size": 14},
        colorscale=heatmap_colorscale,
        ygap=3,
        zmin=0, zmax=zmax_val,
        colorbar=dict(
            title=dict(
                text="P95 Min",
                font=dict(size=14)
            ),
            tickvals=[5, 15, 25, 37.5, 52.5], # Midpoints for labels
            ticktext=['&le; 10', '11-20', '21-30', '31-45', '&gt; 45'],
            tickfont=dict(size=12)
        ),
        hovertemplate="<b>%{y}</b><br>Ankunft ab: %{x}<br>P95 Wartezeit: %{z:.1f} min<extra></extra>"
    )
    return [heatmap_trace], ordered_keys # Return traces and y-labels


def plot_pax_arrival_stacked_bar(df_res: pd.DataFrame, t0: pd.Timestamp, bin_minutes: int = 15): # This function is still used for the overall terminal overview
    """
    Zeigt das Passagieraufkommen pro Terminal als gestapeltes Balkendiagramm.
    """
    if df_res.empty:
        st.info("Keine Passagierdaten für das Aufkommensdiagramm vorhanden.")
        return

    # 1. Data prep
    df_res['arrival_bin'] = (df_res['arrival_min'] // bin_minutes) * bin_minutes
    pax_by_terminal_time = df_res.groupby(['arrival_bin', 'terminal']).size().unstack(fill_value=0)

    # Ensure all bins are present
    if pax_by_terminal_time.empty:
        st.info("Keine Passagierdaten für das Aufkommensdiagramm vorhanden.")
        return
        
    min_bin = pax_by_terminal_time.index.min()
    max_bin = pax_by_terminal_time.index.max()
    full_range = pd.RangeIndex(start=int(min_bin), stop=int(max_bin) + bin_minutes, step=bin_minutes)
    pax_by_terminal_time = pax_by_terminal_time.reindex(full_range, fill_value=0)

    # Convert bin to timestamp for plotting
    time_bins = _to_time_axis(t0, pax_by_terminal_time.index)

    # 2. Plotting
    fig = go.Figure()

    for term in ["T1", "T2"]:
        if term in pax_by_terminal_time.columns:
            fig.add_trace(go.Bar(
                x=time_bins,
                y=pax_by_terminal_time[term],
                name=f'Terminal {term.strip("T")}',
                marker_color=TERMINAL_COLORS.get(term)
            ))

    fig.update_layout(
        barmode='stack',
        title=f"Passagieraufkommen pro Terminal ({bin_minutes}-Minuten-Intervalle)",
        xaxis_title="Ankunftszeit an der Grenzkontrolle",
        yaxis_title="Anzahl Passagiere",
        legend_title_text="Terminal",
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)


def _get_pax_arrival_by_flight_stacked_bar_traces( # Renamed to helper function
    df_res: pd.DataFrame,
    t0: pd.Timestamp,
    terminal: str,
    bin_minutes: int = 60,
    t_start_fixed: pd.Timestamp = None, # Added fixed time range parameters
    t_end_fixed: pd.Timestamp = None,   # Added fixed time range parameters
):
    """
    Zeigt das Passagieraufkommen pro Flug als gestapeltes Balkendiagramm für ein bestimmtes Terminal.
    """
    df_terminal = df_res[df_res['terminal'] == terminal].copy()

    if df_terminal.empty:
        return [] # Return empty list of traces

    df_terminal['arrival_bin'] = (df_terminal['arrival_min'] // bin_minutes) * bin_minutes
    pax_by_fln_time = df_terminal.groupby(['arrival_bin', 'fln']).size().unstack(fill_value=0)

    if pax_by_fln_time.empty:
        return [] # Return empty list of traces
    
    min_rel_start = (t_start_fixed - t0).total_seconds() / 60.0
    min_rel_end = (t_end_fixed - t0).total_seconds() / 60.0
    
    start_bin = int(min_rel_start // bin_minutes) * bin_minutes
    end_bin = int(min_rel_end // bin_minutes) * bin_minutes
    
    full_range = pd.RangeIndex(start=start_bin, stop=end_bin + bin_minutes, step=bin_minutes)
    pax_by_fln_time = pax_by_fln_time.reindex(full_range, fill_value=0)

    # Ersetze 0 durch None, damit im Tooltip nur Werte > 0 erscheinen
    pax_by_fln_time.replace(0, None, inplace=True)

    time_bins = _to_time_axis(t0, pax_by_fln_time.index)

    fig = go.Figure()
    # Flüge nach Gesamtpassagierzahl sortieren für eine geordnete Legende
    flight_order = pax_by_fln_time.sum().sort_values(ascending=False).index

    bar_traces = [] # Collect traces
    for fln in flight_order:
        bar_traces.append(go.Bar(
            x=time_bins,
            y=pax_by_fln_time[fln],
            name=fln,
            showlegend=True, # Ensure legend is shown for each flight
            hovertemplate="<b>%{x|%H:%M}</b><br>Flug: %{customdata}<br>Passagiere: %{y}<extra></extra>", # Custom hover template
            customdata=[fln] * len(time_bins) # Add customdata for hover
        ))
    return bar_traces # Return list of traces


def plot_terminal_overview_combined( # New combined plotting function
    df_res: pd.DataFrame,
    t0: pd.Timestamp,
    terminal: str,
    cfg: "SimConfig",
    bin_minutes_bar: int = 60,
    bin_minutes_heatmap: int = 60,
):
    # Define fixed time range for consistent x-axis across all plots
    day_start = t0.normalize()
    t_start_fixed = day_start + pd.Timedelta(hours=6)
    t_end_fixed = day_start + pd.Timedelta(hours=24)

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05 # Adjust spacing between subplots
    )

    # Add stacked bar chart traces
    bar_traces = _get_pax_arrival_by_flight_stacked_bar_traces(
        df_res, t0, terminal, bin_minutes_bar, t_start_fixed, t_end_fixed
    )
    if bar_traces:
        for trace in bar_traces:
            fig.add_trace(trace, row=1, col=1)
    else:
        # Add a placeholder if no data for bar chart
        fig.add_annotation(
            text="Keine Passagierdaten für das Aufkommensdiagramm vorhanden.",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="gray"),
            row=1, col=1
        )

    # Add heatmap traces
    heatmap_traces, heatmap_y_labels = _get_wait_heatmap_traces(
        df_res[df_res["terminal"] == terminal], t0, cfg.sss_enabled, bin_minutes_heatmap, t_start_fixed, t_end_fixed
    )
    if heatmap_traces:
        for trace in heatmap_traces:
            fig.add_trace(trace, row=2, col=1)
        fig.update_yaxes(tickvals=heatmap_y_labels, ticktext=heatmap_y_labels, row=2, col=1) # Ensure y-labels are correct
    else:
        # Add a placeholder if no data for heatmap
        fig.add_annotation(
            text="Keine Passagierdaten für die Heatmap vorhanden.",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="gray"),
            row=2, col=1
        )

    # Update layout for combined figure
    fig.update_layout(
        barmode='stack',
        title_text=f"Terminal {terminal.strip('T')}: Passagieraufkommen pro Flug & P95 Wartezeit",
        hovermode="x unified",
        height=750, # Total height for the combined plot
        xaxis=dict(range=[t_start_fixed, t_end_fixed]), # Fixed x-axis range for top plot
        xaxis2=dict(rangeslider_visible=False, range=[t_start_fixed, t_end_fixed]), # Fixed x-axis range and rangeslider for bottom plot
        legend_title_text="Flugnummer",
        margin=dict(l=0, r=0, t=60, b=0) # Adjust margins for overall figure
    )
    
    # After layout is defined, we can get the domain of the second y-axis
    # The domain is calculated by make_subplots and is available in the layout object.
    # We need to update the colorbar of the heatmap trace to align with its subplot.
    if heatmap_traces:
        yaxis2_domain = fig.layout.yaxis2.domain
        fig.update_traces(
            selector=dict(type='heatmap'),
            colorbar_y=yaxis2_domain[0],
            colorbar_len=yaxis2_domain[1] - yaxis2_domain[0]
        )
    
    fig.update_yaxes(title_text="Anzahl Passagiere", row=1, col=1)
    fig.update_yaxes(title_text="Prozessstelle", row=2, col=1)
    st.plotly_chart(fig, use_container_width=True)
