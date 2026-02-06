"""
Modul für alle Plotting-Funktionen der Anwendung.

Dieses Modul enthält Funktionen zur Erstellung verschiedener Diagramme
mittels Plotly, wie z.B. Zeitreihen, Heatmaps und Balkendiagramme,
um die Simulationsergebnisse zu visualisieren.
"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from engine import SimConfig


def _to_time_axis(t0: pd.Timestamp, t_min_series: pd.Series) -> pd.Series:
    """Konvertiert eine Serie von relativen Minuten in absolute Zeitstempel."""
    return t0 + pd.to_timedelta(t_min_series, unit="m")

# =========================================================
# Farbdefinitionen für Diagramme
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

QUEUE_HEATMAP_COLORS = [
    '#0962A9',  # <= 10 pax
    '#3F79A8',  # 11-25 pax
    '#7F8B7A',  # 26-50 pax
    '#C48A3F',  # 51-100 pax
    '#EF7C00',  # > 100 pax
]

HEATMAP_COLORS = [
    '#0962A9',  # <= 10 min
    '#3F79A8',  # 11-20 min
    '#7F8B7A',  # 21-30 min
    '#C48A3F',  # 31-45 min
    '#EF7C00',  # > 45 min
]

def get_queue_heatmap_colorscale(zmax_val: float = 150.0) -> list:
    """Erstellt eine diskrete Farbskala für die Heatmap der Warteschlangenlänge."""
    return [
        # Range 1: <= 10 pax
        [0.0, QUEUE_HEATMAP_COLORS[0]],
        [10/zmax_val, QUEUE_HEATMAP_COLORS[0]],
        # Range 2: > 10 to <= 25 pax
        [10/zmax_val, QUEUE_HEATMAP_COLORS[1]],
        [25/zmax_val, QUEUE_HEATMAP_COLORS[1]],
        # Range 3: > 25 to <= 50 pax
        [25/zmax_val, QUEUE_HEATMAP_COLORS[2]],
        [50/zmax_val, QUEUE_HEATMAP_COLORS[2]],
        # Range 4: > 50 to <= 100 pax
        [50/zmax_val, QUEUE_HEATMAP_COLORS[3]],
        [100/zmax_val, QUEUE_HEATMAP_COLORS[3]],
        # Range 5: > 100 pax
        [100/zmax_val, QUEUE_HEATMAP_COLORS[4]],
        [1.0, QUEUE_HEATMAP_COLORS[4]],
    ]

def get_heatmap_colorscale(zmax_val: float = 60.0) -> list:
    """Erstellt eine diskrete Farbskala für die Heatmap der Wartezeit."""
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

# =========================================================
# Datenaufbereitungs-Funktionen für Diagramme
# =========================================================

def _build_rolling_mean_timeseries(
    df_data: pd.DataFrame,
    t0: pd.Timestamp,
    time_col: str,
    value_col: str,
    window_min: int = 15,
    step_min: int = 1,
) -> pd.DataFrame:
    """
    Berechnet einen gleitenden Mittelwert über eine Zeitreihe auf einem festen Zeitraster.

    Diese Funktion verwendet einen effizienten Zwei-Zeiger-Algorithmus, um den
    gleitenden Mittelwert einer Wertespalte über ein definiertes Zeitfenster zu
    berechnen. Die Berechnung erfolgt auf einem festen Zeitraster von 06:00 bis 24:00 Uhr
    am Tag des Simulationsstarts (t0).

    Args:
        df_data: DataFrame mit den Zeit- und Wertedaten.
        t0: Referenz-Startzeit der Simulation (t=0), um das absolute Zeitraster zu erstellen.
        time_col: Name der Spalte mit den Zeitwerten (in Minuten relativ zu t0).
        value_col: Name der Spalte mit den zu mittelnden Werten.
        window_min: Größe des gleitenden Fensters in Minuten. Der Mittelwert wird
            für Datenpunkte im Intervall (t - window_min, t] berechnet.
        step_min: Schrittweite des Ausgabe-Zeitrasters in Minuten.

    Returns:
        Ein DataFrame mit den Spalten 't_min' (Zeit-Raster) und 'mean_value'
        (berechneter gleitender Mittelwert).
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
    """
    Berechnet die gleitende mittlere Warteschlangenlänge.

    Nutzt `_build_rolling_mean_timeseries`, um die mittlere Länge einer Warteschlange (`q_*`) zu berechnen.
    """
    grid = _build_rolling_mean_timeseries(
        df_data=df_ts,
        t0=t0,
        time_col="t_min",
        value_col=col,
        window_min=window_min,
        step_min=step_min,
    )
    return grid.rename(columns={"mean_value": "mean_q"})


# =========================================================
# Plotting-Funktionen
# =========================================================

def plot_queue_over_time_rolling(
    list_of_ts_data: list,
    t0: pd.Timestamp,
    window_min: int = 15,
    y_max: Optional[float] = None,
):
    """
    Plottet eine oder mehrere Zeitreihen von Warteschlangenlängen.

    Args:
        list_of_ts_data: Eine Liste von Tupeln, wobei jedes Tupel (DataFrame, Label) enthält.
        t0: Startzeitpunkt der Simulation.
        window_min: Fenstergröße für die Darstellung (nur im Titel verwendet).
        y_max: Optionaler Maximalwert für die Y-Achse.
    """
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
    """
    Berechnet die gleitende mittlere Wartezeit an einer spezifischen Station.

    Der Mittelwert wird über Passagiere gebildet, die ihren Service an der Station
    innerhalb des gleitenden Zeitfensters (t-window, t] beginnen.

    Args:
        df_res: DataFrame mit den Passagierergebnissen.
        t0: Startzeitpunkt der Simulation.
        station: Name der Station (z.B. "sss", "tcn").
        window_min: Größe des Fensters in Minuten.
        step_min: Schrittweite des Zeitrasters in Minuten.
    """
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

def build_wait_time_timeseries_by_group_rolling(
    df_res: pd.DataFrame,
    t0: pd.Timestamp,
    groups: list[str],
    window_min: int = 15,
    step_min: int = 1,
) -> pd.DataFrame:
    """
    Berechnet die gleitende mittlere Gesamtwartezeit für spezifische Passagiergruppen.

    Der Mittelwert wird über Passagiere gebildet, die innerhalb des gleitenden
    Zeitfensters (t-window, t] an der Grenzkontrolle ankommen.

    Args:
        df_res: DataFrame mit den Passagierergebnissen.
        t0: Startzeitpunkt der Simulation.
        groups: Eine Liste von Passagiergruppen (z.B. ["TCN_V", "TCN_AT"]).
        window_min: Größe des Fensters in Minuten.
        step_min: Schrittweite des Zeitrasters in Minuten.
    """
    df_filtered = df_res[df_res["group"].isin(groups)].copy()
    
    if df_filtered.empty:
        # Pass an empty dataframe to the helper to get a zero-filled grid
        df_prepared = pd.DataFrame(columns=["arrival_min", "wait_total"])
    else:
        # wait_total is already calculated in the main script
        df_prepared = df_filtered

    grid = _build_rolling_mean_timeseries(
        df_data=df_prepared,
        t0=t0,
        time_col="arrival_min",
        value_col="wait_total",
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
    secondary_axis_type: Optional[str] = None,
):
    """
    Plottet eine oder mehrere Zeitreihen von mittleren Wartezeiten.

    Kann optional eine zweite Y-Achse für die verfügbare Kapazität (TCN oder EU) anzeigen.

    Args:
        list_of_ts_data: Liste von (DataFrame, Label)-Tupeln.
        t0: Startzeitpunkt der Simulation.
        y_max: Optionaler Maximalwert für die primäre Y-Achse.
        cfg: Die `SimConfig` des Laufs, wird für die Kapazitätsachse benötigt.
        secondary_axis_type: "TCN" oder "EU", um die entsprechende Kapazität anzuzeigen.
    """
    # Check if we need a secondary axis
    has_secondary_axis = cfg is not None and secondary_axis_type is not None

    if has_secondary_axis:
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
        if has_secondary_axis:
            fig.add_trace(trace, secondary_y=False)
        else:
            fig.add_trace(trace)

    # Add the secondary axis for TCN or EU usage
    if has_secondary_axis:
        if secondary_axis_type == 'TCN':
            schedule = cfg.cap_tcn_schedule
            axis_label = "Verfügbare TCN-Schalter"
        elif secondary_axis_type == 'EU':
            schedule = cfg.cap_eu_schedule
            axis_label = "Verfügbare EU-Schalter"
        else:
            schedule = {}
            axis_label = ""
        
        x_points = []
        y_points = []
        
        day_start = t0.normalize()

        points = []
        if schedule:
            for key, cap in schedule.items():
                start_str, _ = key.split('-')
                if ':' in start_str:
                    start_h, start_m = map(int, start_str.split(':'))
                else:
                    start_h = int(start_str)
                    start_m = 0
                points.append((pd.Timedelta(hours=start_h, minutes=start_m), cap))
            points.sort()

            for time_delta, cap in points:
                x_points.append(day_start + time_delta)
                y_points.append(cap)
            
            if x_points:
                x_points.append(day_start + pd.Timedelta(hours=24))
                y_points.append(y_points[-1])

        fig.add_trace(
            go.Scatter(
                x=x_points,
                y=y_points,
                name=axis_label,
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
    if has_secondary_axis:
        # Manuelle Skalierung der Achsen, um das 10:1-Verhältnis zu gewährleisten und sicherzustellen, dass alle Daten sichtbar sind.

        max_wait = y_max if y_max is not None else max_wait_from_data
        
        if secondary_axis_type == 'TCN':
            max_cap = max(cfg.cap_tcn_schedule.values()) if cfg and cfg.cap_tcn_schedule else 6
        elif secondary_axis_type == 'EU':
            max_cap = max(cfg.cap_eu_schedule.values()) if cfg and cfg.cap_eu_schedule else 4
        else:
            max_cap = 1

        # 2. Erforderliche obere Grenzen für die Achsen berechnen
        y1_max_required = max_wait * 1.1  # 10% Puffer für die Wartezeit-Achse
        y2_max_desired = max_cap + 1      # Puffer für die Kapazitäts-Achse

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


def _get_queue_heatmap_traces(
    df_ts: pd.DataFrame,
    t0: pd.Timestamp,
    show_sss: bool = True,
    bin_min: int = 60,
    t_start_fixed: pd.Timestamp = None,
    t_end_fixed: pd.Timestamp = None,
):
    """
    Bereitet die Daten für die Heatmap der Warteschlangenlänge vor.

    Aggregiert die maximale Warteschlangenlänge pro Zeitintervall (`bin_min`)
    für jede relevante Station.

    Args:
        df_ts: DataFrame mit den Zeitreihendaten der Warteschlangen.
        t0: Startzeitpunkt der Simulation.
        show_sss: Ob die SSS-Station berücksichtigt werden soll.
        bin_min: Breite der Zeitintervalle in Minuten.
        t_start_fixed, t_end_fixed: Fester Zeitbereich für die X-Achse.
    """
    if df_ts.empty:
        return [], []

    stations_map = {"TCN": "q_tcn", "EU": "q_eu", "Easypass": "q_easypass"}
    if show_sss:
        stations_map["SSS (Kiosk)"] = "q_sss"

    min_rel_start = (t_start_fixed - t0).total_seconds() / 60.0
    min_rel_end = (t_end_fixed - t0).total_seconds() / 60.0
    start_bin = int((min_rel_start // bin_min) * bin_min)
    end_bin = int((min_rel_end // bin_min) * bin_min)
    full_idx = range(start_bin, end_bin, bin_min)
    
    z_data = {}
    df_ts_binned = df_ts.copy()
    df_ts_binned["t_bin"] = (df_ts_binned["t_min"] // bin_min).astype(int) * bin_min
    
    for label, col_q in stations_map.items():
        if col_q not in df_ts_binned.columns:
            z_data[label] = pd.Series(0, index=full_idx)
            continue
        grouped = df_ts_binned.groupby("t_bin")[col_q].max()
        z_data[label] = grouped.reindex(full_idx, fill_value=0)
    
    x = _to_time_axis(t0, pd.Series(full_idx))
    ordered_keys = ["Easypass", "EU", "TCN"]
    if show_sss:
        ordered_keys.append("SSS (Kiosk)")
        
    z = [z_data[k].values for k in ordered_keys]
    text_z = [[f'{int(val)}' if val > 0 else '' for val in row] for row in z]
    zmax_val = 150.0
    heatmap_colorscale = get_queue_heatmap_colorscale(zmax_val)
    
    heatmap_trace = go.Heatmap(
        z=z, x=x, y=ordered_keys, text=text_z, texttemplate="%{text}", textfont={"size": 14},
        colorscale=heatmap_colorscale, ygap=3, zmin=0, zmax=zmax_val,
        showscale=False,
        hovertemplate="<b>%{y}</b><br>Zeitfenster ab: %{x}<br>Max. Warteschlange: %{z:.0f} Pax<extra></extra>"
    )
    return [heatmap_trace], ordered_keys


def plot_queue_heatmap(
    df_ts: pd.DataFrame,
    t0: pd.Timestamp,
    terminal: str,
    cfg: "SimConfig",
    bin_minutes: int = 60,
):
    """
    Plottet eine Heatmap der maximalen Warteschlangenlänge pro Stunde.

    Args:
        df_ts: DataFrame mit den Zeitreihendaten der Warteschlangen.
        t0: Startzeitpunkt der Simulation.
        terminal: Name des Terminals (für Titel).
        cfg: Die `SimConfig` des Laufs.
    """
    day_start = t0.normalize()
    t_start_fixed = day_start + pd.Timedelta(hours=6)
    t_end_fixed = day_start + pd.Timedelta(hours=24)

    fig = go.Figure()

    heatmap_traces, heatmap_y_labels = _get_queue_heatmap_traces(
        df_ts, t0, cfg.sss_enabled, bin_minutes, t_start_fixed, t_end_fixed
    )

    if heatmap_traces:
        for trace in heatmap_traces:
            fig.add_trace(trace)
        fig.update_yaxes(tickvals=heatmap_y_labels, ticktext=heatmap_y_labels)
    else:
        fig.add_annotation(
            text="Keine Daten für Heatmap vorhanden.",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, font=dict(size=16, color="gray"),
        )

    fig.update_layout(
        xaxis=dict(range=[t_start_fixed, t_end_fixed]),
        yaxis_title="Prozessstelle",
        height=175,
        margin=dict(l=0, r=0, t=10, b=0)
    )
    st.plotly_chart(fig, use_container_width=True)

def _get_wait_heatmap_traces(
    df_res: pd.DataFrame,
    t0: pd.Timestamp,
    show_sss: bool = True,
    bin_min: int = 60,
    t_start_fixed: pd.Timestamp = None,
    t_end_fixed: pd.Timestamp = None,
):
    """
    Bereitet die Daten für die Heatmap der P95-Wartezeit vor.

    Aggregiert die 95%-Perzentil-Wartezeit pro Zeitintervall (`bin_min`)
    für jede relevante Station, basierend auf der Ankunftszeit der Passagiere.

    Args:
        df_res: DataFrame mit den Passagierergebnissen.
        t0: Startzeitpunkt der Simulation.
        show_sss: Ob die SSS-Station berücksichtigt werden soll.
        bin_min: Breite der Zeitintervalle in Minuten.
        t_start_fixed, t_end_fixed: Fester Zeitbereich für die X-Achse.
    """
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
        showscale=False,
        hovertemplate="<b>%{y}</b><br>Ankunft ab: %{x}<br>P95 Wartezeit: %{z:.1f} min<extra></extra>"
    )
    return [heatmap_trace], ordered_keys # Return traces and y-labels


def plot_pax_arrival_stacked_bar(df_res: pd.DataFrame, t0: pd.Timestamp, bin_minutes: int = 15):
    """Plottet das Passagieraufkommen als gestapeltes Balkendiagramm.

    Args:
        df_res: DataFrame mit den Passagierergebnissen.
        t0: Startzeitpunkt der Simulation.
        bin_minutes: Breite der Zeitintervalle in Minuten.
    """
    # Define fixed time range first, as it's needed even for empty data
    day_start = t0.normalize()
    t_start_fixed = day_start + pd.Timedelta(hours=6)
    t_end_fixed = day_start + pd.Timedelta(hours=23)

    if df_res.empty:
        # Create an empty dataframe to show an empty plot with the correct range
        pax_by_terminal_time = pd.DataFrame()
    else:
        # 1. Data prep
        df_res_copy = df_res.copy() # Avoid SettingWithCopyWarning
        df_res_copy['arrival_bin'] = (df_res_copy['arrival_min'] // bin_minutes) * bin_minutes
        pax_by_terminal_time = df_res_copy.groupby(['arrival_bin', 'terminal']).size().unstack(fill_value=0)

    # Ensure all bins within the fixed range are present
    min_rel_start = (t_start_fixed - t0).total_seconds() / 60.0
    min_rel_end = (t_end_fixed - t0).total_seconds() / 60.0
    start_bin = int(min_rel_start // bin_minutes) * bin_minutes
    end_bin = int(min_rel_end // bin_minutes) * bin_minutes
    
    full_range = pd.RangeIndex(start=start_bin, stop=end_bin + bin_minutes, step=bin_minutes)
    
    # Reindex to the full fixed range
    pax_by_terminal_time = pax_by_terminal_time.reindex(full_range, fill_value=0)

    # Convert bin to timestamp for plotting
    time_bins = _to_time_axis(t0, pax_by_terminal_time.index)

    # 2. Plotting
    fig = go.Figure()
    terminals_in_data = [c for c in ["T1", "T2"] if c in pax_by_terminal_time.columns]
    for term in terminals_in_data:
        fig.add_trace(go.Bar(x=time_bins, y=pax_by_terminal_time[term], name=f'Terminal {term.strip("T")}', marker_color=TERMINAL_COLORS.get(term)))
    fig.update_layout(
        barmode='stack',
        xaxis_title=None,
        yaxis_title="Anzahl Passagiere",
        hovermode="x unified",
        xaxis=dict(range=[t_start_fixed, t_end_fixed]),
        showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0)
    )
    st.plotly_chart(fig, use_container_width=True)


def plot_terminal_overview_combined(
    df_res: pd.DataFrame,
    t0: pd.Timestamp,
    terminal: str,
    cfg: "SimConfig",
    bin_minutes_heatmap: int = 60,
):
    """
    Plottet die Heatmap der P95-Wartezeit für ein Terminal.

    Args:
        df_res: DataFrame mit den Passagierergebnissen.
        t0: Startzeitpunkt der Simulation.
        terminal: Name des Terminals.
        cfg: Die `SimConfig` des Laufs.
    """
    # Define fixed time range for consistent x-axis across all plots
    day_start = t0.normalize()
    t_start_fixed = day_start + pd.Timedelta(hours=6)
    t_end_fixed = day_start + pd.Timedelta(hours=24)

    fig = go.Figure()

    # Add heatmap traces
    heatmap_traces, heatmap_y_labels = _get_wait_heatmap_traces(
        df_res[df_res["terminal"] == terminal], t0, cfg.sss_enabled, bin_minutes_heatmap, t_start_fixed, t_end_fixed
    )
    if heatmap_traces:
        for trace in heatmap_traces:
            fig.add_trace(trace)
        fig.update_yaxes(tickvals=heatmap_y_labels, ticktext=heatmap_y_labels)
    else:
        # Add a placeholder if no data for heatmap
        fig.add_annotation(
            text="Keine Passagierdaten für die Heatmap vorhanden.",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="gray"),
        )

    # Update layout for combined figure
    fig.update_layout(
        hovermode="x unified",
        height=175,
        xaxis=dict(range=[t_start_fixed, t_end_fixed]),
        margin=dict(l=0, r=0, t=10, b=0)
    )
    
    fig.update_yaxes(title_text="Prozessstelle")
    st.plotly_chart(fig, use_container_width=True)
