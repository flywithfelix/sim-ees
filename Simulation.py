from __future__ import annotations

__doc__ = """
Hauptanwendung der EES-Simulations-App.

Diese Datei ist der Haupteinstiegspunkt für die Streamlit-Anwendung. Sie
behandelt das Hochladen und Parsen von Flugplänen, die Interaktion mit dem
Benutzer zur Auswahl von Flügen, die Orchestrierung der Simulationsläufe und
die Darstellung der Ergebnisse in Form von Metriken, Tabellen und Diagrammen.
"""
import pandas as pd
from dataclasses import asdict
import json
from datetime import date, datetime
import os
import re
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import streamlit as st
import plotly.graph_objects as go
from typing import Any, Dict, List, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from dotenv import load_dotenv

from engine import SimConfig, run_simulation
from parameter import (
    TCN_SERVICE_LEVELS,
    DEFAULT_SESSION_STATE,
    FLIGHT_ALLOCATION,
    API_TERMINAL_PPOS,
)
from typ4_defaults import DEFAULT_EPAX_BY_TYP4


# =========================================================
# Initialisierung
# =========================================================
from plotting import (
    build_wait_time_timeseries_rolling,
    build_wait_time_timeseries_by_group_rolling,
    plot_mean_wait_over_time_rolling,
    plot_queue_heatmap,
    plot_terminal_overview_combined,
    TERMINAL_COLORS
)

load_dotenv()

API_ARRIVALS_URL = "https://rest.api.hamburg-airport.de/v2/flights/arrivals"
API_SUBSCRIPTION_KEY = os.getenv("HAMBURG_AIRPORT_SUBSCRIPTION_KEY", "").strip()
HAMBURG_TZ = ZoneInfo("Europe/Berlin")
RUNS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs")
RUN_BASE_PATTERN = re.compile(
    r"^simulation_run_(?P<simulated_at>\d{8}_\d{6})(?:_seed_(?P<seed>[^_]+))?(?:_(?P<suffix>\d+))?$"
)

def init_session_state():
    """
    Initialisiert den `st.session_state` mit Standardwerten.
    """
    for k, v in DEFAULT_SESSION_STATE.items():
        if k not in st.session_state:
            st.session_state[k] = v


def build_results_export_dataframe(
    df_res_t1: pd.DataFrame,
    df_res_t2: pd.DataFrame,
    df_selected: pd.DataFrame | None,
) -> pd.DataFrame:
    """Bereitet die zusammengefuehrten Ergebnisdaten fuer Download und Persistenz auf."""
    _ = df_selected
    frames = []
    if not df_res_t1.empty:
        frames.append(df_res_t1.assign(terminal="T1"))
    if not df_res_t2.empty:
        frames.append(df_res_t2.assign(terminal="T2"))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _build_unique_run_base_path(run_seed: int | None) -> str:
    """Erzeugt einen eindeutigen Basis-Pfad fuer alle Dateien eines Simulationsruns."""
    os.makedirs(RUNS_DIR, exist_ok=True)

    timestamp = datetime.now(HAMBURG_TZ).strftime("%Y%m%d_%H%M%S")
    seed_part = f"_seed_{run_seed}" if run_seed is not None else ""
    base_name = f"simulation_run_{timestamp}{seed_part}"
    base_path = os.path.join(RUNS_DIR, base_name)
    suffix = 1

    while any(
        os.path.exists(f"{base_path}{extension}")
        for extension in (
            "_passengers.csv",
            "_flight_summary.csv",
            "_group_summary.csv",
            "_capacity_t1.csv",
            "_capacity_t2.csv",
        )
    ):
        base_path = os.path.join(RUNS_DIR, f"{base_name}_{suffix}")
        suffix += 1
    return base_path


def persist_run_results(
    df_res: pd.DataFrame,
    df_fsum: pd.DataFrame,
    df_gsum: pd.DataFrame,
    df_cap_t1: pd.DataFrame | None,
    df_cap_t2: pd.DataFrame | None,
    df_ts_t1: pd.DataFrame | None,
    df_ts_t2: pd.DataFrame | None,
    run_seed: int | None,
) -> str:
    """Schreibt einen Simulationslauf mit Detail-, Report- und Kapazitaetsdateien."""
    base_path = _build_unique_run_base_path(run_seed)

    exports: list[tuple[pd.DataFrame, str]] = [
        (df_res, "_passengers.csv"),
        (df_fsum, "_flight_summary.csv"),
        (df_gsum, "_group_summary.csv"),
    ]
    if df_cap_t1 is not None:
        exports.append((df_cap_t1, "_capacity_t1.csv"))
    if df_cap_t2 is not None:
        exports.append((df_cap_t2, "_capacity_t2.csv"))
    if df_ts_t1 is not None:
        exports.append((df_ts_t1, "_queue_ts_t1.csv"))
    if df_ts_t2 is not None:
        exports.append((df_ts_t2, "_queue_ts_t2.csv"))

    for dataframe, suffix in exports:
        dataframe.to_csv(f"{base_path}{suffix}", index=False, encoding="utf-8-sig")

    return os.path.abspath(base_path)


@st.cache_data(show_spinner=False)
def list_saved_runs() -> list[dict[str, Any]]:
    """Liest verfügbare gespeicherte Simulationsruns aus dem runs-Verzeichnis."""
    if not os.path.isdir(RUNS_DIR):
        return []

    runs: list[dict[str, Any]] = []
    for name in os.listdir(RUNS_DIR):
        if not name.endswith("_passengers.csv"):
            continue

        passenger_path = os.path.join(RUNS_DIR, name)
        base_name = name[: -len("_passengers.csv")]
        base_path = os.path.join(RUNS_DIR, base_name)
        match = RUN_BASE_PATTERN.match(base_name)

        simulated_at = None
        seed = None
        run_suffix = None
        if match:
            simulated_at = datetime.strptime(match.group("simulated_at"), "%Y%m%d_%H%M%S")
            seed = match.group("seed")
            run_suffix = match.group("suffix")

        try:
            df_meta = pd.read_csv(passenger_path, usecols=["BIBT", "terminal"], encoding="utf-8-sig")
        except ValueError:
            df_meta = pd.read_csv(passenger_path, encoding="utf-8-sig")
        except Exception:
            continue

        flight_dates = pd.to_datetime(df_meta.get("BIBT"), errors="coerce")
        flight_date = flight_dates.min().date() if flight_dates.notna().any() else None
        terminals = ", ".join(sorted(df_meta.get("terminal", pd.Series(dtype="string")).dropna().astype(str).unique().tolist()))
        passenger_count = int(len(df_meta.index))

        label_parts = []
        if simulated_at is not None:
            label_parts.append(f"Simuliert {simulated_at.strftime('%H:%M:%S')}")
        if seed:
            label_parts.append(f"Seed {seed}")
        if run_suffix:
            label_parts.append(f"Variante {run_suffix}")
        if terminals:
            label_parts.append(terminals)
        label_parts.append(f"{passenger_count:,} Pax".replace(",", "."))

        runs.append(
            {
                "base_path": base_path,
                "flight_date": flight_date,
                "simulated_at": simulated_at,
                "seed": seed,
                "label": " | ".join(label_parts),
                "has_queue_ts": os.path.exists(f"{base_path}_queue_ts_t1.csv") or os.path.exists(f"{base_path}_queue_ts_t2.csv"),
            }
        )

    runs.sort(
        key=lambda item: (
            item["flight_date"] or date.min,
            item["simulated_at"] or datetime.min,
        ),
        reverse=True,
    )
    return runs


def _read_csv_if_exists(path: str, parse_dates: list[str] | None = None) -> pd.DataFrame | None:
    """Liest eine CSV-Datei, falls sie existiert."""
    if not os.path.exists(path):
        return None
    return pd.read_csv(path, encoding="utf-8-sig", parse_dates=parse_dates)


def _schedule_from_capacity_df(df_cap: pd.DataFrame | None, column: str) -> dict[str, int]:
    """Baut ein Kapazitäts-Schedule aus der gespeicherten CSV auf."""
    if df_cap is None or df_cap.empty or "Intervall" not in df_cap.columns or column not in df_cap.columns:
        return {}
    values = pd.to_numeric(df_cap[column], errors="coerce").fillna(0).astype(int)
    return dict(zip(df_cap["Intervall"].astype(str), values))


def _build_plot_cfg(df_cap: pd.DataFrame | None, df_res_term: pd.DataFrame) -> SimpleNamespace:
    """Erzeugt eine minimale Plot-Konfiguration für geladene Runs."""
    sss_enabled = False
    if not df_res_term.empty:
        if "used_sss" in df_res_term.columns:
            sss_enabled = df_res_term["used_sss"].fillna(False).astype(bool).any()
        elif "wait_sss" in df_res_term.columns:
            sss_enabled = pd.to_numeric(df_res_term["wait_sss"], errors="coerce").fillna(0).gt(0).any()

    return SimpleNamespace(
        sss_enabled=bool(sss_enabled),
        cap_tcn_schedule=_schedule_from_capacity_df(df_cap, "TCN Kapazität"),
        cap_eu_schedule=_schedule_from_capacity_df(df_cap, "EU Kapazität"),
    )


@st.cache_data(show_spinner=False)
def load_saved_run(base_path: str) -> dict[str, Any]:
    """Lädt die gespeicherten Dateien eines Runs für die Read-only-Anzeige."""
    df_res = pd.read_csv(f"{base_path}_passengers.csv", encoding="utf-8-sig")
    if "BIBT" in df_res.columns:
        df_res["BIBT"] = pd.to_datetime(df_res["BIBT"], errors="coerce")
    if "wait_total" not in df_res.columns and {"wait_sss", "wait_easypass", "wait_eu", "wait_tcn"}.issubset(df_res.columns):
        df_res["wait_total"] = df_res["wait_sss"] + df_res["wait_easypass"] + df_res["wait_eu"] + df_res["wait_tcn"]

    df_cap_t1 = _read_csv_if_exists(f"{base_path}_capacity_t1.csv")
    df_cap_t2 = _read_csv_if_exists(f"{base_path}_capacity_t2.csv")
    df_ts_t1 = _read_csv_if_exists(f"{base_path}_queue_ts_t1.csv")
    df_ts_t2 = _read_csv_if_exists(f"{base_path}_queue_ts_t2.csv")

    if "terminal" in df_res.columns:
        df_res_t1 = df_res[df_res["terminal"] == "T1"].copy()
        df_res_t2 = df_res[df_res["terminal"] == "T2"].copy()
    else:
        df_res_t1 = df_res.copy()
        df_res_t2 = df_res.iloc[0:0].copy()

    cfg_t1 = _build_plot_cfg(df_cap_t1, df_res_t1)
    cfg_t2 = _build_plot_cfg(df_cap_t2, df_res_t2)

    if "BIBT" in df_res.columns and df_res["BIBT"].notna().any():
        t0 = df_res["BIBT"].min()
    else:
        t0 = pd.Timestamp.today().normalize()

    return {
        "df_res": df_res,
        "df_res_t1": df_res_t1,
        "df_res_t2": df_res_t2,
        "cfg_t1": cfg_t1,
        "cfg_t2": cfg_t2,
        "df_cap_t1": df_cap_t1,
        "df_cap_t2": df_cap_t2,
        "df_ts_t1": df_ts_t1 if df_ts_t1 is not None else pd.DataFrame(),
        "df_ts_t2": df_ts_t2 if df_ts_t2 is not None else pd.DataFrame(),
        "t0": t0,
    }

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


def _coalesce_columns(df: pd.DataFrame, candidates: List[str], default: Any = pd.NA) -> pd.Series:
    """
    Liefert die erste vorhandene Spalte aus `candidates` oder einen Default-Wert.
    """
    for col in candidates:
        if col in df.columns:
            return df[col]
    return pd.Series([default] * len(df), index=df.index)


def _coalesce_values(df: pd.DataFrame, candidates: List[str], default: Any = pd.NA) -> pd.Series:
    """
    Liefert pro Zeile den ersten nicht-leeren Wert aus `candidates`.
    """
    available = [col for col in candidates if col in df.columns]
    if not available:
        return pd.Series([default] * len(df), index=df.index)

    stacked = df[available].copy()
    stacked = stacked.replace({"": pd.NA, "<NA>": pd.NA, "nan": pd.NA, "None": pd.NA})
    return stacked.bfill(axis=1).iloc[:, 0].fillna(default)


def _coalesce_numeric_columns(df: pd.DataFrame, candidates: List[str], default: Any = pd.NA) -> pd.Series:
    """
    Liefert die erste vorhandene Spalte aus `candidates` als numerische Series.
    """
    for col in candidates:
        if col in df.columns:
            return pd.to_numeric(df[col], errors="coerce")
    return pd.Series([default] * len(df), index=df.index, dtype="Float64")


def _normalize_terminal_number(series: pd.Series) -> pd.Series:
    """
    Normalisiert unterschiedliche Terminal-Angaben auf ganzzahlige Werte 1/2.
    """
    cleaned = series.astype("string").str.upper().str.extract(r"(\d+)")[0]
    return pd.to_numeric(cleaned, errors="coerce").astype("Int64")


def _normalize_ppos(series: pd.Series) -> pd.Series:
    """
    Vereinheitlicht Parkpositionen; leere Werte werden als `unbekannt` markiert.
    """
    out = series.astype("string").str.strip().str.upper()
    out = out.replace({"<NA>": pd.NA, "NAN": pd.NA, "NONE": pd.NA, "": pd.NA})
    return out.fillna("unbekannt")


def _ppos_from_terminal_series(series: pd.Series) -> pd.Series:
    """
    Erzeugt API-Fallback-PPOS auf Basis des Ankunftsterminals.
    """
    terminal_numbers = _normalize_terminal_number(series)
    return terminal_numbers.map(API_TERMINAL_PPOS).fillna("unbekannt").astype("string")


def _parse_api_datetime_series(series: pd.Series) -> pd.Series:
    """
    Parst Zeitstempel der Hamburg-Airport-API robust.

    Die API kann Zeitzonen-Suffixe wie `[Europe/Berlin]` anhängen, die pandas
    nicht direkt verarbeitet. Diese werden vor dem Parsing entfernt.
    """
    cleaned = (
        series.astype("string")
        .str.replace(r"\[[^\]]+\]$", "", regex=True)
        .replace({"<NA>": pd.NA, "nan": pd.NA, "None": pd.NA})
    )
    parsed = pd.to_datetime(cleaned, errors="coerce", utc=True)
    return pd.Series(parsed, index=series.index).dt.tz_convert(HAMBURG_TZ).dt.tz_localize(None)


def _extract_records(payload: Any) -> List[Dict[str, Any]]:
    """
    Extrahiert eine Datensatzliste aus einer JSON-Antwort.
    """
    current = payload
    if isinstance(current, list):
        return [item for item in current if isinstance(item, dict)]
    if isinstance(current, dict):
        for key in ("flights", "arrivals", "items", "data", "results"):
            value = current.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [current]
    raise ValueError("API-Antwort enthält keine erkennbare Liste mit Flugdaten.")


def _build_api_headers() -> Dict[str, str]:
    """
    Baut die Header für die Hamburg-Airport-API.
    """
    if not API_SUBSCRIPTION_KEY:
        raise ValueError(
            "Subscription Key fehlt. Bitte `HAMBURG_AIRPORT_SUBSCRIPTION_KEY` in der `.env` setzen."
        )
    return {
        "Cache-Control": "no-cache",
        "Ocp-Apim-Subscription-Key": API_SUBSCRIPTION_KEY,
        "Accept": "application/json",
    }


def load_api_data() -> pd.DataFrame:
    """
    Lädt Flugdaten der festen Hamburg-Airport-API per HTTP-GET.
    """
    request = Request(API_ARRIVALS_URL, headers=_build_api_headers(), method="GET")
    try:
        with urlopen(request, timeout=30) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            payload = json.loads(response.read().decode(charset))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"API-Fehler {exc.code}: {detail[:300]}") from exc
    except URLError as exc:
        raise ValueError(f"API konnte nicht erreicht werden: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"API-Antwort ist kein gültiges JSON: {exc}") from exc

    records = _extract_records(payload)
    if not records:
        return pd.DataFrame()
    return pd.json_normalize(records, sep=".")


def normalize_api_flights(df_api_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Überführt eine generische API-Antwort in eine lesbare Flugtabelle.

    Die Daten werden bewusst nicht in das Simulationsformat überführt.
    """
    if df_api_raw.empty:
        return df_api_raw.copy()

    out = pd.DataFrame(index=df_api_raw.index)
    out["Flight"] = _coalesce_columns(df_api_raw, ["flightnumber", "flightNumber", "flight.number", "identifier", "iataNumber", "FLN"])
    out["Scheduled"] = _coalesce_columns(
        df_api_raw,
        ["scheduledTime.local", "scheduledTime", "times.scheduled", "scheduled", "scheduledArrivalTime", "BIBT"],
    )
    out["Estimated"] = _coalesce_columns(
        df_api_raw,
        ["estimatedTime.local", "estimatedTime", "times.estimated", "estimated", "estimatedArrivalTime"],
    )
    out["Origin"] = _coalesce_columns(df_api_raw, ["originAirport3LCode", "departure.airport.iata", "departure.airport.code", "origin", "ADEP3"])
    out["Status"] = _coalesce_columns(df_api_raw, ["flightStatusArrival", "status", "flightStatus", "publicStatus"])
    out["Terminal"] = _coalesce_columns(df_api_raw, ["gepTerminal", "arrivalTerminal", "terminal", "airportResources.terminal", "resources.terminal", "T"])
    out["Gate"] = _coalesce_columns(df_api_raw, ["gate", "airportResources.gate", "resources.gate"])
    out["Position"] = _coalesce_columns(df_api_raw, ["position", "parkingPosition", "PPOS"])
    out["Aircraft"] = _coalesce_columns(df_api_raw, ["aircraftType", "aircraft.model", "aircraft.type", "Typ4"])

    for col in ["Scheduled", "Estimated"]:
        out[col] = _parse_api_datetime_series(out[col])

    useful_cols = [col for col in out.columns if not out[col].isna().all()]
    if useful_cols:
        out = out[useful_cols]

    remaining_cols = [c for c in df_api_raw.columns if c not in out.columns]
    if remaining_cols:
        out = pd.concat([out, df_api_raw[remaining_cols]], axis=1)

    sort_col = "Scheduled" if "Scheduled" in out.columns else out.columns[0]
    return out.sort_values(sort_col, na_position="last").reset_index(drop=True)


def filter_api_flights_by_date(df_api_raw: pd.DataFrame, selected_date: date) -> pd.DataFrame:
    """
    Filtert API-Flüge auf einen Kalendertag anhand verfügbarer Zeitstempel.
    """
    if df_api_raw.empty:
        return df_api_raw.copy()

    timestamps = _parse_api_datetime_series(
        _coalesce_values(
            df_api_raw,
            [
                "expectedArrivalTime",
                "plannedArrivalTime",
                "estimatedTime.local",
                "estimatedTime",
                "scheduledTime.local",
                "scheduledTime",
                "times.estimated",
                "times.scheduled",
                "estimated",
                "scheduled",
                "plannedTime",
                "BIBT",
            ],
        )
    )

    if not timestamps.notna().any():
        return df_api_raw.iloc[0:0].copy()

    day_start = pd.Timestamp(selected_date)
    day_end = day_start + pd.Timedelta(days=1)
    mask = (timestamps >= day_start) & (timestamps < day_end)
    return df_api_raw.loc[mask].copy()


def normalize_api_flights_for_simulation(df_api_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Überführt API-Rohdaten in das Eingabeschema des CSV-Parsers.
    """
    if df_api_raw.empty:
        return pd.DataFrame(columns=["BIBT", "FLN", "ADEP3", "PPOS", "Typ4", "EPAX", "APAX", "T", "PK"])

    out = pd.DataFrame(index=df_api_raw.index)
    out["BIBT"] = _coalesce_values(
        df_api_raw,
        [
            "expectedArrivalTime",
            "plannedArrivalTime",
            "estimatedTime.local",
            "estimatedTime",
            "scheduledTime.local",
            "scheduledTime",
            "times.estimated",
            "times.scheduled",
            "estimated",
            "scheduled",
            "scheduledArrivalTime",
            "actualArrivalTime",
            "BIBT",
        ],
    )
    out["BIBT"] = _parse_api_datetime_series(out["BIBT"])

    out["FLN"] = _coalesce_columns(
        df_api_raw,
        ["flightnumber", "flightNumber", "flight.number", "identifier", "iataNumber", "number", "FLN"],
    ).astype("string").str.strip()

    out["ADEP3"] = _coalesce_columns(
        df_api_raw,
        [
            "departure.airport.iata",
            "departure.airport.code",
            "departure.airportIata",
            "originAirport3LCode",
            "origin",
            "origin.iata",
            "ADEP3",
        ],
    ).astype("string").str.strip()

    out["Typ4"] = _coalesce_columns(
        df_api_raw,
        [
            "aircraft.model",
            "aircraft.type",
            "aircraft.iataType",
            "aircraft.aircraftType",
            "aircraftType",
            "Typ4",
        ],
        default="Acft",
    ).astype("string").str.strip()
    out.loc[out["Typ4"].isin(["", "<NA>"]), "Typ4"] = "Acft"

    out["EPAX"] = _coalesce_numeric_columns(
        df_api_raw,
        [
            "passengers.expected",
            "expectedPassengers",
            "expectedPassengerCount",
            "pax.expected",
            "load.expected",
            "capacity",
            "seatCapacity",
            "EPAX",
        ],
    )
    out["APAX"] = _coalesce_numeric_columns(
        df_api_raw,
        [
            "passengers.actual",
            "actualPassengers",
            "actualPassengerCount",
            "pax.actual",
            "load.actual",
            "APAX",
        ],
    )

    terminal_series = _coalesce_columns(
        df_api_raw,
        ["arrivalTerminal", "terminal", "airportResources.terminal", "resources.terminal", "arrival.terminal", "T"],
    )
    out["T"] = _normalize_terminal_number(terminal_series)
    out["PPOS"] = _ppos_from_terminal_series(terminal_series)

    ias_series = _coalesce_columns(df_api_raw, ["iasKennung", "IASKennung", "ias_kennung"])
    out["PK"] = (
        ias_series.astype("string")
        .str.strip()
        .str.upper()
        .eq("A")
        .map({True: "JA", False: "NEIN"})
    )

    out = out[out["BIBT"].notna()].copy()
    out = out[out["FLN"].notna() & (out["FLN"] != "")].copy()

    return out.reset_index(drop=True)


def prepare_flights_for_simulation(df_raw: pd.DataFrame, source: str) -> pd.DataFrame:
    """
    Bereitet Quelldaten aus Datei oder API einheitlich für die Simulation auf.
    """
    if source == "api":
        return parse_flights_csv_fixed(normalize_api_flights_for_simulation(df_raw))
    return parse_flights_csv_fixed(df_raw)

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
    invalid_bibt = int(out["BIBT"].isna().sum())
    if invalid_bibt:
        raise ValueError(
            f"{invalid_bibt} Zeile(n) enthalten keine gültige BIBT im Format TT.MM.JJJJ HH:MM."
        )
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

    # SPAX berechnen: Priorität APAX > EPAX > Dictionary-Fallback (vektorisiert)
    # 1. Fallback-Werte aus Typ4-Mapping erstellen
    default_pax = out["Typ4"].map(DEFAULT_EPAX_BY_TYP4).fillna(100)

    # 2. SPAX mit Prioritätenkette füllen: APAX -> EPAX -> default_pax
    if "APAX" in out.columns:
        # Fülle Lücken in APAX mit Werten aus EPAX, dann mit den Default-Werten
        out["SPAX"] = out["APAX"].fillna(out["EPAX"]).fillna(default_pax)
    else:
        # Fülle Lücken in EPAX mit den Default-Werten
        out["SPAX"] = out["EPAX"].fillna(default_pax)

    # 3. Finalen Fallback (falls alle Stricke reißen) und Typkonvertierung sicherstellen
    out["SPAX"] = out["SPAX"].fillna(100).astype(int)
    
    return out.sort_values("BIBT")


def assign_gks(df: pd.DataFrame) -> pd.DataFrame:
    """
    Weist jedem Flug ein Terminal (T1/T2) zu.

    Die Zuweisung erfolgt primär basierend auf der Parkposition (PPOS) gemäß
    der Konfiguration in `flight_allocation.py`. Flüge ohne feste PPOS-Zuweisung
    werden standardmäßig T2 zugewiesen.
    """
    def get_terminal(row: pd.Series):
        ppos_val = str(row.get("PPOS", ""))
        terminal_val = row.get("T")

        if ppos_val in set(API_TERMINAL_PPOS.values()) and pd.notna(terminal_val):
            try:
                terminal_num = int(terminal_val)
            except (TypeError, ValueError):
                terminal_num = None
            else:
                if terminal_num == 1:
                    return "T1"
                if terminal_num == 2:
                    return "T2"

        if ppos_val in FLIGHT_ALLOCATION["T1"]["ppos"]:
            return "T1"
        # T2 ist der Standard für alles andere, einschließlich unbekannter PPOS
        return "T2"

    df['GKS'] = df.apply(get_terminal, axis=1)
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

    # Ermitteln, wie viele Zeilen den Fallback-Wert für die Pax-Zahl verwenden
    if "APAX" in df2.columns:
        fallback_mask = df2["APAX"].isna() & df2["EPAX"].isna()
    else:
        fallback_mask = df2["EPAX"].isna()
    fallback_count = int(fallback_mask.sum())

    # DataFrame für die Konvertierung vorbereiten, anstatt zu iterieren
    df_sim = df2.reset_index().copy()  # reset_index() gibt uns eine 'index' Spalte für den flight_key

    df_sim["flight_key"] = (
        df_sim["BIBT"].dt.strftime('%Y%m%d-%H%M') + "_" +
        df_sim["PPOS"].astype(str) + "_" +
        df_sim["FLN"].astype(str) + "_" +
        df_sim["index"].astype(str)
    )
    df_sim = df_sim.rename(columns={
        "FLN": "fln",
        "PPOS": "ppos",
        "Typ4": "acft",
        "SPAX": "spax",
        "GKS": "terminal"
    })

    # Benötigte Spalten auswählen und in eine Liste von Dictionaries konvertieren
    sim_cols = ["flight_key", "fln", "ppos", "spax", "acft", "t_arr_min", "terminal"]
    # Sicherstellen, dass spax ein int und t_arr_min ein float ist, wie es die Engine erwartet
    df_sim['spax'] = df_sim['spax'].astype(int)
    df_sim['t_arr_min'] = df_sim['t_arr_min'].astype(float)
    flights = cast(List[Dict[str, Any]], df_sim[sim_cols].to_dict('records'))
    
    return flights, t0, df2, fallback_count


# =========================================================
# App-Layout und UI-Logik
# =========================================================
st.set_page_config(page_title="SIM EES", layout="wide", initial_sidebar_state="expanded")
st.title("Simulation des EES-Prozesses am Flughafen")

# Custom CSS für gleichhohe KPI-Kacheln
st.markdown(
    """
    <style>
    [data-testid="stMetric"] {
        min-height: 140px;
        border-radius: 10px;
        }

    /* Vergrößert die Radio-Buttons für die Terminal-Auswahl */
    div[data-testid="stRadio"] > div[role="radiogroup"] > label {
        font-size: 1.1rem;
        padding: 0.5rem 1rem;
        border: 1px solid #e0e0e0;
        border-radius: 7px;
        margin: 0 0.25rem;
        transition: all 0.2s;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label:hover {
        background-color: #f0f2f6;
    }
   
    </style>
    """,

    unsafe_allow_html=True,
)

# Initialisiere Defaults (wichtig, falls User Settings noch nicht besucht hat)
init_session_state()
# Render settings in the sidebar (migrated from pages/2_Einstellungen.py)
from settings_sidebar import render_settings_sidebar
render_settings_sidebar(show_sim_button=True)


def get_schedule_breaches(df_res, t0, service_level_min, groups: list[str], value_col: str, window_min=15):
    """Analysiert Wartezeiten einer Passagiergruppe und identifiziert Service-Level-Verletzungen.

    Args:
        df_res: DataFrame mit den Ergebnissen eines Simulationslaufs.
        t0: Startzeitpunkt der Simulation.
        service_level_min: Die maximale erlaubte mittlere Wartezeit in Minuten.
        groups: Liste der Passagiergruppen, die analysiert werden sollen (z.B. ["TCN_V", "TCN_AT"]).
        value_col: Die Spalte mit der zu prüfenden Wartezeit (z.B. "wait_tcn").
        window_min: Die Fenstergröße für den gleitenden Mittelwert.

    Returns:
        Eine Liste von 15-Minuten-Intervallen (als Strings), in denen der Service Level verletzt wurde.
    """
    if df_res.empty:
        return []

    # Berechne die rollierende mittlere Wartezeit für die angegebene Passagiergruppe.
    ts_wait_group = build_wait_time_timeseries_by_group_rolling(df_res, t0, groups, value_col, window_min=window_min, step_min=5)

    # Finde alle Zeitpunkte, an denen die mittlere Wartezeit den Schwellenwert überschreitet
    breached_times = ts_wait_group[ts_wait_group["mean_wait"] > service_level_min]

    if breached_times.empty:
        return []

    # Konvertiere die relativen Minuten in absolute Zeitstempel
    breached_timestamps = t0 + pd.to_timedelta(breached_times["t_min"], unit="m")

    # Finde die einzigartigen 15-Minuten-Intervalle, die betroffen sind
    breached_intervals = set()
    for ts in breached_timestamps:
        start_of_interval = ts.floor('15min')
        end_of_interval = start_of_interval + pd.Timedelta(minutes=15)
        end_str = "00:00" if end_of_interval.time() == pd.Timestamp('00:00').time() and end_of_interval.date() > start_of_interval.date() else end_of_interval.strftime('%H:%M')
        interval_key = f"{start_of_interval.strftime('%H:%M')}-{end_str}"
        breached_intervals.add(interval_key)
    return list(breached_intervals)

def render_terminal_details(
    terminal_id: str,
    df_res: pd.DataFrame,
    t0: pd.Timestamp,
    cfg: Any,
    df_ts: pd.DataFrame | None = None,
):
    """Rendert den Detailbereich für ein einzelnes Terminal."""
    df_res_term = df_res[df_res["terminal"] == terminal_id]
    if df_res_term.empty:
        st.info(f"Keine Daten für Terminal {terminal_id}.")
        return

    ts_w_tcn = build_wait_time_timeseries_by_group_rolling(
        df_res_term, t0, ["TCN_V", "TCN_AT"], "wait_tcn", window_min=15, step_min=1
    )
    ts_w_eu = build_wait_time_timeseries_by_group_rolling(
        df_res_term, t0, ["EU_MANUAL"], "wait_eu", window_min=15, step_min=1
    )
    ts_w_ep = build_wait_time_timeseries_by_group_rolling(
        df_res_term, t0, ["EASYPASS"], "wait_easypass", window_min=15, step_min=1
    )
    all_waits = pd.concat([ts_w_tcn, ts_w_eu, ts_w_ep])
    max_w = all_waits["mean_wait"].max() if not all_waits.empty else 0

    with st.container(border=True):
        st.markdown(f"##### {terminal_id} - Ø Wartezeit (rollierend 15 min)")
        tab1, tab2 = st.tabs(["TCN-Gruppen", "EU/Easypass-Gruppen"])

        with tab1:
            plot_mean_wait_over_time_rolling(
                [(ts_w_tcn, "TCN")],
                t0,
                window_min=15,
                y_max=max_w,
                cfg=cfg,
                secondary_axis_type="TCN",
            )

        with tab2:
            plot_mean_wait_over_time_rolling(
                [(ts_w_eu, "EU"), (ts_w_ep, "Easypass")],
                t0,
                window_min=15,
                y_max=max_w,
                cfg=cfg,
                secondary_axis_type="EU",
            )

    if df_ts is not None and not df_ts.empty:
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.markdown(f"##### {terminal_id} - P95 Wartezeit/h")
                plot_terminal_overview_combined(df_res, t0, terminal=terminal_id, cfg=cfg, bin_minutes_heatmap=60)
        with col2:
            with st.container(border=True):
                st.markdown(f"##### {terminal_id} - Anzahl Personen in Wartschlange/h")
                plot_queue_heatmap(df_ts, t0, terminal=terminal_id, cfg=cfg, bin_minutes=60)
    else:
        with st.container(border=True):
            st.markdown(f"##### {terminal_id} - P95 Wartezeit/h")
            plot_terminal_overview_combined(df_res, t0, terminal=terminal_id, cfg=cfg, bin_minutes_heatmap=60)
        st.info(
            f"Für Terminal {terminal_id} sind keine gespeicherten Warteschlangen-Zeitreihen vorhanden. "
            "Die Queue-Heatmap kann deshalb nicht angezeigt werden."
        )


def _build_capacity_dataframe(cfg: Any) -> pd.DataFrame | None:
    """Erzeugt die Kapazitätstabelle aus einer Konfiguration."""
    if cfg is None:
        return None
    tcn_schedule = getattr(cfg, "cap_tcn_schedule", None)
    eu_schedule = getattr(cfg, "cap_eu_schedule", None)
    if not tcn_schedule or not eu_schedule:
        return None
    sorted_intervals = sorted(tcn_schedule.keys())
    return pd.DataFrame(
        {
            "Intervall": sorted_intervals,
            "TCN Kapazität": [tcn_schedule.get(k) for k in sorted_intervals],
            "EU Kapazität": [eu_schedule.get(k) for k in sorted_intervals],
        }
    )


def render_results_dashboard(
    df_res: pd.DataFrame,
    t0: pd.Timestamp,
    cfg_t1: Any,
    cfg_t2: Any,
    *,
    df_ts_t1: pd.DataFrame | None = None,
    df_ts_t2: pd.DataFrame | None = None,
    run_seed: int | None = None,
    show_tables: bool = True,
    allow_save: bool = False,
    terminal_radio_key: str = "selected_terminal_tab",
):
    """Rendert die Ergebnisansicht für Live- und gespeicherte Runs."""
    if df_res.empty:
        st.warning("Keine Passagiere simuliert.")
        return

    df_res = df_res.copy()
    if "BIBT" in df_res.columns:
        df_res["BIBT"] = pd.to_datetime(df_res["BIBT"], errors="coerce")
    if "wait_total" not in df_res.columns:
        df_res["wait_total"] = df_res["wait_sss"] + df_res["wait_easypass"] + df_res["wait_eu"] + df_res["wait_tcn"]

    df_res_t1_filtered = df_res[df_res["terminal"] == "T1"]
    df_res_t2_filtered = df_res[df_res["terminal"] == "T2"]
    pax_t1 = len(df_res_t1_filtered)
    pax_t2 = len(df_res_t2_filtered)

    df_hourly_pax = df_res.copy()
    if "BIBT" in df_hourly_pax.columns and not df_hourly_pax["BIBT"].isna().all():
        df_hourly_pax["hour_of_day"] = df_hourly_pax["BIBT"].dt.hour
    else:
        df_hourly_pax["hour_of_day"] = (t0 + pd.to_timedelta(df_hourly_pax["arrival_min"], unit="m")).dt.hour
    if not df_hourly_pax.empty:
        df_hourly_pax = df_hourly_pax.groupby(["hour_of_day", "terminal"]).size().unstack(fill_value=0)
        min_hour, max_hour = df_hourly_pax.index.min(), df_hourly_pax.index.max()
        if min_hour == max_hour:
            max_hour += 1
        df_hourly_pax = df_hourly_pax.reindex(range(min_hour, max_hour + 1), fill_value=0)
    else:
        df_hourly_pax = pd.DataFrame(columns=["T1", "T2"]).reindex(range(6, 24), fill_value=0)
    for term in ["T1", "T2"]:
        if term not in df_hourly_pax.columns:
            df_hourly_pax[term] = 0
    df_hourly_pax = df_hourly_pax.fillna(0).astype(int)

    df_hourly_p95_wait_eu = df_res[df_res["group"] == "EU_MANUAL"].copy()
    if not df_hourly_p95_wait_eu.empty:
        if "BIBT" in df_hourly_p95_wait_eu.columns and not df_hourly_p95_wait_eu["BIBT"].isna().all():
            df_hourly_p95_wait_eu["hour_of_day"] = df_hourly_p95_wait_eu["BIBT"].dt.hour
        else:
            df_hourly_p95_wait_eu["hour_of_day"] = (t0 + pd.to_timedelta(df_hourly_p95_wait_eu["arrival_min"], unit="m")).dt.hour
        df_hourly_p95_wait_eu = (
            df_hourly_p95_wait_eu.groupby(["hour_of_day", "terminal"])["wait_eu"].quantile(0.95).unstack(fill_value=0)
        )
        min_hour, max_hour = df_hourly_p95_wait_eu.index.min(), df_hourly_p95_wait_eu.index.max()
        if min_hour == max_hour:
            max_hour += 1
        df_hourly_p95_wait_eu = df_hourly_p95_wait_eu.reindex(range(min_hour, max_hour + 1), fill_value=0.0)
    else:
        df_hourly_p95_wait_eu = pd.DataFrame(columns=["T1", "T2"]).reindex(range(6, 24), fill_value=0.0)
    for term in ["T1", "T2"]:
        if term not in df_hourly_p95_wait_eu.columns:
            df_hourly_p95_wait_eu[term] = 0.0
    df_hourly_p95_wait_eu = df_hourly_p95_wait_eu.fillna(0).astype(float).round(1)

    df_hourly_p95_wait_tcn = df_res[df_res["group"].isin(["TCN_V", "TCN_AT"])].copy()
    if not df_hourly_p95_wait_tcn.empty:
        if "BIBT" in df_hourly_p95_wait_tcn.columns and not df_hourly_p95_wait_tcn["BIBT"].isna().all():
            df_hourly_p95_wait_tcn["hour_of_day"] = df_hourly_p95_wait_tcn["BIBT"].dt.hour
        else:
            df_hourly_p95_wait_tcn["hour_of_day"] = (t0 + pd.to_timedelta(df_hourly_p95_wait_tcn["arrival_min"], unit="m")).dt.hour
        df_hourly_p95_wait_tcn = (
            df_hourly_p95_wait_tcn.groupby(["hour_of_day", "terminal"])["wait_tcn"].quantile(0.95).unstack(fill_value=0)
        )
        min_hour, max_hour = df_hourly_p95_wait_tcn.index.min(), df_hourly_p95_wait_tcn.index.max()
        if min_hour == max_hour:
            max_hour += 1
        df_hourly_p95_wait_tcn = df_hourly_p95_wait_tcn.reindex(range(min_hour, max_hour + 1), fill_value=0.0)
    else:
        df_hourly_p95_wait_tcn = pd.DataFrame(columns=["T1", "T2"]).reindex(range(6, 24), fill_value=0.0)
    for term in ["T1", "T2"]:
        if term not in df_hourly_p95_wait_tcn.columns:
            df_hourly_p95_wait_tcn[term] = 0.0
    df_hourly_p95_wait_tcn = df_hourly_p95_wait_tcn.fillna(0).astype(float).round(1)

    p95_wait_eu_t1 = df_hourly_p95_wait_eu["T1"].max() if "T1" in df_hourly_p95_wait_eu.columns else 0
    p95_wait_eu_t2 = df_hourly_p95_wait_eu["T2"].max() if "T2" in df_hourly_p95_wait_eu.columns else 0
    p95_wait_tcn_t1 = df_hourly_p95_wait_tcn["T1"].max() if "T1" in df_hourly_p95_wait_tcn.columns else 0
    p95_wait_tcn_t2 = df_hourly_p95_wait_tcn["T2"].max() if "T2" in df_hourly_p95_wait_tcn.columns else 0

    selected_terminal_tab = st.radio(
        "Terminal auswählen",
        ["Terminal 1", "Terminal 2"],
        horizontal=True,
        key=terminal_radio_key,
    )

    if selected_terminal_tab == "Terminal 1":
        render_terminal_details("T1", df_res, t0, cfg_t1, df_ts_t1)
        c1, c2, c3 = st.columns(3)
        c1.metric("**T1** EU-manual - P95 Wartezeit (Max/h)", f"{p95_wait_eu_t1:.1f} min", chart_data=df_hourly_p95_wait_eu["T1"], chart_type="area", border=True)
        c2.metric("**T1** TCN - P95 Wartezeit (Max/h)", f"{p95_wait_tcn_t1:.1f} min", chart_data=df_hourly_p95_wait_tcn["T1"], chart_type="area", border=True)
        c3.metric("**T1** - Anzahl Passagiere", f"{pax_t1:,}".replace(",", "."), chart_data=df_hourly_pax["T1"], chart_type="area", border=True)

    if selected_terminal_tab == "Terminal 2":
        render_terminal_details("T2", df_res, t0, cfg_t2, df_ts_t2)
        cp1, cp2, cp3 = st.columns(3)
        cp1.metric("**T2** EU-manual - P95 Wartezeit (Max/h)", f"{p95_wait_eu_t2:.1f} min", chart_data=df_hourly_p95_wait_eu["T2"], chart_type="area", border=True)
        cp2.metric("**T2** TCN - P95 Wartezeit (Max/h)", f"{p95_wait_tcn_t2:.1f} min", chart_data=df_hourly_p95_wait_tcn["T2"], chart_type="area", border=True)
        cp3.metric("**T2** - Anzahl Passagiere", f"{pax_t2:,}".replace(",", "."), chart_data=df_hourly_pax["T2"], chart_type="area", border=True)

    if not show_tables:
        return

    st.subheader("Bus-Ankünfte (Bulks)")
    if "Bus" in df_res["transport_mode"].unique():
        df_bus = df_res[df_res["transport_mode"] == "Bus"].copy()
        bus_bulks = df_bus.groupby("arrival_min").agg(
            pax_count=("pax_id", "count"),
            fln=("fln", "first"),
            ppos=("ppos", "first"),
            terminal=("terminal", "first"),
        ).reset_index()
        bus_travel_time = getattr(cfg_t1, "bus_travel_time_min", st.session_state.get("bus_travel_time_min", 2.5))
        bus_bulks["departure_min"] = bus_bulks["arrival_min"] - bus_travel_time
        bus_bulks["arrival_time"] = t0 + pd.to_timedelta(bus_bulks["arrival_min"], unit="m")
        bus_bulks["departure_time"] = t0 + pd.to_timedelta(bus_bulks["departure_min"], unit="m")
        display_df = bus_bulks[["fln", "pax_count", "ppos", "departure_time", "arrival_time", "terminal"]].rename(
            columns={
                "terminal": "Terminal",
                "fln": "Flugnummer",
                "ppos": "PPOS",
                "pax_count": "Passagiere",
                "departure_time": "Bus Abfahrt",
                "arrival_time": "Bus Ankunft",
            }
        ).sort_values(["Terminal", "Bus Ankunft"])
        st.dataframe(display_df.style.format({"Bus Abfahrt": "{:%H:%M:%S}", "Bus Ankunft": "{:%H:%M:%S}"}), width="stretch")
    else:
        st.info("Keine Flüge mit Bustransfer in dieser Simulation.")

    df_cap_t1 = _build_capacity_dataframe(cfg_t1)
    df_cap_t2 = _build_capacity_dataframe(cfg_t2)
    if df_cap_t1 is not None and df_cap_t2 is not None:
        st.subheader("Ermittelte Kapazitäten")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("###### Terminal 1")
            st.dataframe(df_cap_t1, hide_index=True, width="stretch")
        with col2:
            st.markdown("###### Terminal 2")
            st.dataframe(df_cap_t2, hide_index=True, width="stretch")

    total = int(len(df_res))
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

    st.subheader("Gruppenübersicht")
    df_gsum = (
        df_res.groupby("group", as_index=False)
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

    st.subheader("Detaildaten (Passagiere)")
    st.dataframe(df_res, width="stretch")

    save_col, download_col = st.columns(2)
    if allow_save:
        with save_col:
            if st.button("Simulationsrun speichern", width="stretch"):
                try:
                    saved_path = persist_run_results(
                        df_res=df_res,
                        df_fsum=df_fsum,
                        df_gsum=df_gsum,
                        df_cap_t1=df_cap_t1,
                        df_cap_t2=df_cap_t2,
                        df_ts_t1=df_ts_t1,
                        df_ts_t2=df_ts_t2,
                        run_seed=run_seed,
                    )
                    st.session_state["last_saved_run_path"] = saved_path
                except Exception as exc:
                    st.error(f"Simulationsrun konnte nicht gespeichert werden: {exc}")
        saved_path = st.session_state.get("last_saved_run_path")
        if saved_path:
            st.success(f"Simulationsrun gespeichert. Dateibasis: {saved_path}")

    csv_bytes = df_res.to_csv(index=False).encode("utf-8")
    with download_col:
        st.download_button(
            "Passenger-Details als CSV herunterladen",
            data=csv_bytes,
            file_name="passenger_results.csv",
            mime="text/csv",
            width="stretch",
        )
    
# Ensure Einstellungen page reloads saved settings when arriving from Home
st.session_state["_settings_loaded"] = False


def clear_results():
    """Löscht zwischengespeicherte Simulationsergebnisse aus dem Session State."""
    keys = [
        "last_df_res_t1",
        "last_df_res_t2",
        "last_t0",
        "last_df_selected",
        "last_cfg_t1",
        "last_cfg_t2",
        "last_run_seed",
        "last_saved_run_path",
        "edited_df",
    ]
    for k in keys:
        st.session_state.pop(k, None)

# Visual frame for upload section using expander (always expanded)
with st.expander("📋 Flugplan importieren", expanded=True):
    import_mode = st.radio(
        "Importquelle",
        options=["Datei-Import", "API-Import", "Gespeicherter Run"],
        horizontal=True,
        key="import_mode",
    )

    if import_mode == "Datei-Import":
        uploaded = st.file_uploader(
            "Flugplan hochladen (CSV oder XLSX, Pflichtspalten: BIBT, FLN, ADEP3, PPOS, Typ4, EPAX, APAX, T, PK )",
            type=["csv", "xlsx"],
            key="flight_plan_uploader",
        )
    elif import_mode == "API-Import":
        uploaded = None
        st.caption(f"Verwendete API: `{API_ARRIVALS_URL}`")
        selected_api_date = st.date_input(
            "Datum",
            key="api_selected_date",
            value=date.today(),
            format="DD.MM.YYYY",
            help="Es werden nur Flüge des gewählten Kalendertags angezeigt.",
        )
        if st.button("API-Daten laden", type="primary", width="stretch"):
            try:
                df_api_raw = filter_api_flights_by_date(load_api_data(), selected_api_date)
                st.session_state["api_df_raw"] = df_api_raw
                st.session_state["api_df_display"] = normalize_api_flights(df_api_raw)
                st.session_state["current_df"] = prepare_flights_for_simulation(df_api_raw, source="api")
                st.session_state["current_df_source"] = "api"
                st.session_state["api_loaded_date"] = selected_api_date
                st.session_state.pop("saved_run_payload", None)
                clear_results()
            except Exception as e:
                st.error(f"API-Daten konnten nicht geladen werden: {e}")
    else:
        uploaded = None
        saved_runs = list_saved_runs()
        if not saved_runs:
            st.info("Im Ordner `runs` wurden keine gespeicherten Simulationsruns gefunden.")
        else:
            available_dates = [flight_date for flight_date in dict.fromkeys(run["flight_date"] for run in saved_runs if run["flight_date"] is not None)]
            if not available_dates:
                st.warning("Die gespeicherten Runs enthalten kein auswertbares Flugdatum (`BIBT`).")
            else:
                selected_saved_date = st.selectbox(
                    "Flugplan-Tag",
                    options=available_dates,
                    format_func=lambda value: value.strftime("%d.%m.%Y"),
                    key="saved_run_flight_date",
                )
                runs_for_date = [run for run in saved_runs if run["flight_date"] == selected_saved_date]
                run_labels = {run["base_path"]: run["label"] for run in runs_for_date}
                selected_run_base = st.selectbox(
                    "Gespeicherter Durchlauf",
                    options=[run["base_path"] for run in runs_for_date],
                    format_func=lambda value: run_labels[value],
                    key="saved_run_base_path",
                )
                if st.button("Run laden", type="primary", width="stretch"):
                    try:
                        st.session_state["saved_run_payload"] = load_saved_run(selected_run_base)
                        st.session_state["saved_run_meta"] = next(run for run in runs_for_date if run["base_path"] == selected_run_base)
                        clear_results()
                    except Exception as exc:
                        st.error(f"Gespeicherter Run konnte nicht geladen werden: {exc}")


if import_mode == "API-Import":
    df_api_display = st.session_state.get("api_df_display")
    if df_api_display is None:
        st.info("Bitte API-Daten laden.")
        st.stop()

    df_api_sim = st.session_state.get("current_df")
    if df_api_sim is None or st.session_state.get("current_df_source") != "api":
        st.info("Bitte API-Daten erneut laden.")
        st.stop()

    loaded_date = st.session_state.get("api_loaded_date")
    if loaded_date is not None:
        st.caption(f"{len(df_api_display)} Datensätze für den {loaded_date.strftime('%d.%m.%Y')} aus der API geladen.")
    else:
        st.caption(f"{len(df_api_display)} Datensätze aus der API geladen.")
    st.dataframe(df_api_display, width="stretch", hide_index=True)

if uploaded is not None:
    # Prüfen, ob sich die Datei geändert hat (anhand Name/Größe)
    # Bevor wir teures Parsing machen.
    file_id = f"{uploaded.name}_{uploaded.size}"
    if st.session_state.get("last_file_id") != file_id:
        try:
            df_new = prepare_flights_for_simulation(read_csv_auto(uploaded), source="file")
            st.session_state["last_file_id"] = file_id
            st.session_state["current_df"] = df_new
            st.session_state["current_df_source"] = "file"
            st.session_state.pop("saved_run_payload", None)
            clear_results()
        except Exception as e:
            st.error(f"Datei konnte nicht verarbeitet werden: {e}")
            st.stop()

if import_mode != "Gespeicherter Run":
    if "current_df" in st.session_state:
        df_all = st.session_state["current_df"]
        current_source = st.session_state.get("current_df_source")
        if import_mode == "Datei-Import":
            if uploaded is None and current_source == "file":
                st.info(f"Verwende geladene Dateidaten ({len(df_all)} Flüge). Ziehen Sie eine neue Datei hierher, um zu aktualisieren.")
            elif current_source != "file":
                st.info("Bitte Datei (CSV oder XLSX) hochladen.")
                st.stop()
        else:
            if current_source == "api":
                st.info(f"Verwende geladene API-Daten ({len(df_all)} Flüge) für die Simulation.")
            else:
                st.info("Bitte API-Daten laden.")
                st.stop()
    else:
        if import_mode == "Datei-Import":
            st.info("Bitte Datei (CSV oder XLSX) hochladen.")
        else:
            st.info("Bitte API-Daten laden.")
        st.stop()

    df_all = assign_gks(df_all)
    desired_cols = ["BIBT", "FLN", "ADEP3", "Typ4", "EPAX", "APAX", "SPAX", "PPOS", "GKS", "T", "PK"]
    new_order = [c for c in desired_cols if c in df_all.columns] + [c for c in df_all.columns if c not in desired_cols]
    df_all = df_all[new_order]

    fln_all = sorted(df_all["FLN"].unique().tolist())
    if not fln_all:
        st.warning("Keine Flüge nach PK-Filter vorhanden.")
        st.stop()

    with st.expander("✈️ Flüge für Simulation auswählen", expanded=True):
        if "APAX" in df_all.columns:
            fallback_mask_all = df_all["APAX"].isna() & df_all["EPAX"].isna()
        else:
            fallback_mask_all = df_all["EPAX"].isna()
        fallback_count_all = int(fallback_mask_all.sum())

        if fallback_count_all > 0:
            st.warning(f"{fallback_count_all} Flüge ohne APAX/EPAX — Standardwert für Passagierzahl wird verwendet.")

        if "edited_df" not in st.session_state:
            df_editable = df_all.copy()
            df_editable.insert(0, "Aktiv", True)
            st.session_state["edited_df"] = df_editable

        df_before_edit = st.session_state["edited_df"]
        disabled_cols = [c for c in df_all.columns if c != "GKS"]

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

        locked_ppos = set(FLIGHT_ALLOCATION["T1"]["ppos"]) | set(FLIGHT_ALLOCATION["T2"]["ppos"])
        reverted_flights = []
        gks_changed_mask = (df_before_edit["GKS"] != edited_df["GKS"])

        if gks_changed_mask.any():
            changed_indices = edited_df[gks_changed_mask].index
            for idx in changed_indices:
                ppos = edited_df.loc[idx, "PPOS"]
                if str(ppos) in locked_ppos:
                    original_gks = df_before_edit.loc[idx, "GKS"]
                    edited_df.loc[idx, "GKS"] = original_gks
                    reverted_flights.append(edited_df.loc[idx, "FLN"])

        if reverted_flights:
            st.warning(f"Die GKS-Zuweisung für Flüge mit fester PPOS-Zuweisung ({', '.join(sorted(list(set(reverted_flights))))}) kann nicht geändert werden und wurde zurückgesetzt.")

        st.session_state["edited_df"] = edited_df
        df_selected_from_editor = edited_df[edited_df["Aktiv"]]
        flights, t0, df_selected, fallback_count = flights_to_sim_input(df_selected_from_editor)
        st.caption(f"{len(df_selected)} von {len(df_all)} Flügen für die Simulation ausgewählt.")

    run_btn = st.session_state.get("_run_simulation", False)

    if not flights:
        st.warning("Keine Flüge nach FLN-Auswahl.")
        st.stop()

    if run_btn:
    # Reset the flag so it doesn't persist across reruns
        st.session_state["_run_simulation"] = False

        process_time_scale = st.session_state["process_time_scale_pct"] / 100.0
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
            mu_easypass_s=st.session_state["mu_easypass_s"],
            sigma_easypass_s=st.session_state["sigma_easypass_s"],
            max_easypass_s=st.session_state["max_easypass_s"] * process_time_scale,
            mu_eu_s=st.session_state["mu_eu_s"],
            sigma_eu_s=st.session_state["sigma_eu_s"],
            max_eu_s=st.session_state["max_eu_s"] * process_time_scale,
            mean_sss_s=st.session_state["mean_sss_s"] * process_time_scale,
            sd_sss_s=st.session_state["sd_sss_s"] * process_time_scale,
            mu_tcn_v_s=st.session_state["mu_tcn_v_s"],
            sigma_tcn_v_s=st.session_state["sigma_tcn_v_s"],
            max_tcn_v_s=st.session_state["max_tcn_v_s"] * process_time_scale,
        )

        flights_t1 = [f for f in flights if f["terminal"] == "T1"]
        flights_t2 = [f for f in flights if f["terminal"] == "T2"]
        run_seed = int(st.session_state["seed"])

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

                cfg_t1 = SimConfig(
                    service_level_min=service_level_min,
                    cap_tcn_schedule=cap_tcn_schedule_t1,
                    cap_eu_schedule=cap_eu_schedule_t1,
                    cap_sss=(st.session_state["cap_sss_t1"] if st.session_state["sss_enabled_t1"] else 0),
                    cap_easypass=st.session_state["cap_easypass_t1"],
                    sss_enabled=st.session_state["sss_enabled_t1"],
                    **sim_params
                )
                cfg_t2 = SimConfig(
                    service_level_min=service_level_min,
                    cap_tcn_schedule=cap_tcn_schedule_t2,
                    cap_eu_schedule=cap_eu_schedule_t2,
                    cap_sss=(st.session_state["cap_sss"] if st.session_state["sss_enabled_t2"] else 0),
                    cap_easypass=st.session_state["cap_easypass"],
                    sss_enabled=st.session_state["sss_enabled_t2"],
                    **sim_params
                )

                m1 = run_simulation(flights_t1, cfg_t1, t0, seed=run_seed)
                df_res_t1 = pd.DataFrame([asdict(r) for r in m1.results])
                if not df_res_t1.empty:
                    df_res_t1["wait_total"] = df_res_t1["wait_sss"] + df_res_t1["wait_easypass"] + df_res_t1["wait_eu"] + df_res_t1["wait_tcn"]
                ts_t1 = m1.queue_ts

                m2 = run_simulation(flights_t2, cfg_t2, t0, seed=run_seed)
                df_res_t2 = pd.DataFrame([asdict(r) for r in m2.results])
                if not df_res_t2.empty:
                    df_res_t2["wait_total"] = df_res_t2["wait_sss"] + df_res_t2["wait_easypass"] + df_res_t2["wait_eu"] + df_res_t2["wait_tcn"]
                ts_t2 = m2.queue_ts

                breaches_tcn_t1 = get_schedule_breaches(df_res_t1, t0, service_level_min, groups=["TCN_V", "TCN_AT"], value_col="wait_tcn")
                breaches_eu_t1 = get_schedule_breaches(df_res_t1, t0, service_level_min, groups=["EU_MANUAL"], value_col="wait_eu")
                breaches_tcn_t2 = get_schedule_breaches(df_res_t2, t0, service_level_min, groups=["TCN_V", "TCN_AT"], value_col="wait_tcn")
                breaches_eu_t2 = get_schedule_breaches(df_res_t2, t0, service_level_min, groups=["EU_MANUAL"], value_col="wait_eu")

                scenarios = [
                    (breaches_tcn_t1, cap_tcn_schedule_t1, max_cap_tcn_t1),
                    (breaches_eu_t1, cap_eu_schedule_t1, max_cap_eu),
                    (breaches_tcn_t2, cap_tcn_schedule_t2, max_cap_tcn_t2),
                    (breaches_eu_t2, cap_eu_schedule_t2, max_cap_eu),
                ]

                capacity_changed = False
                for breaches, schedule, max_cap in scenarios:
                    for interval in breaches:
                        if interval in schedule and schedule[interval] < max_cap:
                            schedule[interval] += 1
                            capacity_changed = True

                if not (breaches_tcn_t1 or breaches_eu_t1 or breaches_tcn_t2 or breaches_eu_t2):
                    st.success(f"✅ Service Level in Iteration {i} erreicht!")
                    status.update(label=f"Service Level in Iteration {i} erreicht!", state="complete")
                    break
                if not capacity_changed:
                    st.warning("⚠️ Service Level nicht erreicht. Die Kapazität konnte nicht weiter erhöht werden, da für alle verbleibenden Verletzungen bereits die Maximalkapazität erreicht ist.")
                    status.update(label=f"Maximale Kapazität für kritische Intervalle in Iteration {i} erreicht.", state="error")
                    break
                if i == max_iterations:
                    st.error(f"🛑 Simulation nach {max_iterations} Iterationen gestoppt. Service Level wurde nicht erreicht.")
                    status.update(label="Maximale Iterationen erreicht.", state="error")

        st.session_state["last_df_res_t1"] = df_res_t1
        st.session_state["last_df_ts_t1"] = pd.DataFrame(ts_t1)
        st.session_state["last_df_res_t2"] = df_res_t2
        st.session_state["last_df_ts_t2"] = pd.DataFrame(ts_t2)
        st.session_state["last_cfg_t1"] = cfg_t1
        st.session_state["last_cfg_t2"] = cfg_t2
        st.session_state["last_t0"] = t0
        st.session_state["last_df_selected"] = df_selected
        st.session_state["last_run_seed"] = run_seed
        st.session_state.pop("last_saved_run_path", None)

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
    df_ts_t1 = st.session_state.get("last_df_ts_t1")
    df_ts_t2 = st.session_state.get("last_df_ts_t2")
    t0 = st.session_state.get("last_t0", 0)
    df_selected = st.session_state.get("last_df_selected")
    run_seed = st.session_state.get("last_run_seed")

    df_res = build_results_export_dataframe(df_res_t1, df_res_t2, df_selected)
    if df_selected is not None:
        df_selected_with_key = df_selected.reset_index().copy()
        df_selected_with_key["flight_key"] = (
            df_selected_with_key["BIBT"].dt.strftime("%Y%m%d-%H%M") + "_"
            + df_selected_with_key["PPOS"].astype(str) + "_"
            + df_selected_with_key["FLN"].astype(str) + "_"
            + df_selected_with_key["index"].astype(str)
        )
        df_res = pd.merge(df_res, df_selected_with_key[["flight_key", "BIBT"]], on="flight_key", how="left")

    render_results_dashboard(
        df_res=df_res,
        t0=t0,
        cfg_t1=cfg_t1,
        cfg_t2=cfg_t2,
        df_ts_t1=df_ts_t1,
        df_ts_t2=df_ts_t2,
        run_seed=run_seed,
        show_tables=True,
        allow_save=True,
        terminal_radio_key="selected_terminal_tab_live",
    )

if import_mode == "Gespeicherter Run":
    saved_run_payload = st.session_state.get("saved_run_payload")
    saved_run_meta = st.session_state.get("saved_run_meta")
    if saved_run_payload is not None:
        st.markdown("---")
        st.header("Gespeicherter Simulationsrun")
        if saved_run_meta is not None and saved_run_meta.get("flight_date") is not None:
            st.caption(
                f"Flugplan-Tag: {saved_run_meta['flight_date'].strftime('%d.%m.%Y')} | "
                f"{saved_run_meta['label']}"
            )
        render_results_dashboard(
            df_res=saved_run_payload["df_res"],
            t0=saved_run_payload["t0"],
            cfg_t1=saved_run_payload["cfg_t1"],
            cfg_t2=saved_run_payload["cfg_t2"],
            df_ts_t1=saved_run_payload["df_ts_t1"],
            df_ts_t2=saved_run_payload["df_ts_t2"],
            show_tables=False,
            allow_save=False,
            terminal_radio_key="selected_terminal_tab_saved",
        )
