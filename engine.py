from __future__ import annotations
from collections import Counter, defaultdict

import random
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

import simpy

from passenger_data import (
    MEAN_SSS_VH_REG_S, SD_SSS_VH_REG_S, MEAN_SSS_VH_UNREG_S, SD_SSS_VH_UNREG_S,
    MEAN_SSS_VE_REG_S, SD_SSS_VE_REG_S, MEAN_SSS_VE_UNREG_S, SD_SSS_VE_UNREG_S,
    MEAN_TCN_VH_REG_S_SSS_ENABLED, SD_TCN_VH_REG_S_SSS_ENABLED, MEAN_TCN_VH_UNREG_S_SSS_ENABLED, SD_TCN_VH_UNREG_S_SSS_ENABLED,
    MEAN_TCN_VH_REG_S_SSS_DISABLED, SD_TCN_VH_REG_S_SSS_DISABLED, MEAN_TCN_VH_UNREG_S_SSS_DISABLED, SD_TCN_VH_UNREG_S_SSS_DISABLED,
    MEAN_TCN_VE_REG_S_SSS_ENABLED, SD_TCN_VE_REG_S_SSS_ENABLED, MEAN_TCN_VE_UNREG_S_SSS_ENABLED, SD_TCN_VE_UNREG_S_SSS_ENABLED,
    MEAN_TCN_VE_REG_S_SSS_DISABLED, SD_TCN_VE_REG_S_SSS_DISABLED, MEAN_TCN_VE_UNREG_S_SSS_DISABLED, SD_TCN_VE_UNREG_S_SSS_DISABLED,
    MEAN_EASYPASS_S, SD_EASYPASS_S, MEAN_EU_S, SD_EU_S,
)
from ppos_distances import PPOS_DISTANCE_M


# Interne Gruppen
GROUPS = ["EASYPASS", "EU_MANUAL", "TCN_AT", "TCN_VH", "TCN_VE"]


# =========================
# Konfiguration
# =========================
@dataclass
class SimConfig:
    # Kapazitäten
    cap_sss: int = 6
    cap_easypass: int = 8
    cap_eu: int = 6
    cap_tcn: int = 6

    # EES-Verteilung (nur für TCN_VH / TCN_VE)
    ees_registered_share: float = 0.75
    # SSS aktiviert/deaktiviert
    sss_enabled: bool = True

    # SSS Servicezeiten nach (VH/VE) x (reg/unreg) [Sekunden]
    mean_sss_vh_reg_s: float = MEAN_SSS_VH_REG_S
    sd_sss_vh_reg_s: float = SD_SSS_VH_REG_S
    mean_sss_vh_unreg_s: float = MEAN_SSS_VH_UNREG_S
    sd_sss_vh_unreg_s: float = SD_SSS_VH_UNREG_S

    mean_sss_ve_reg_s: float = MEAN_SSS_VE_REG_S
    sd_sss_ve_reg_s: float = SD_SSS_VE_REG_S
    mean_sss_ve_unreg_s: float = MEAN_SSS_VE_UNREG_S
    sd_sss_ve_unreg_s: float = SD_SSS_VE_UNREG_S

    # TCN Servicezeiten nach (VH/VE) x (reg/unreg) x (SSS enabled/disabled) [Sekunden]
    mean_tcn_vh_reg_s: float = MEAN_TCN_VH_REG_S_SSS_ENABLED
    sd_tcn_vh_reg_s: float = SD_TCN_VH_REG_S_SSS_ENABLED
    mean_tcn_vh_unreg_s: float = MEAN_TCN_VH_UNREG_S_SSS_ENABLED
    sd_tcn_vh_unreg_s: float = SD_TCN_VH_UNREG_S_SSS_ENABLED

    mean_tcn_ve_reg_s: float = MEAN_TCN_VE_REG_S_SSS_ENABLED
    sd_tcn_ve_reg_s: float = SD_TCN_VE_REG_S_SSS_ENABLED
    mean_tcn_ve_unreg_s: float = MEAN_TCN_VE_UNREG_S_SSS_ENABLED
    sd_tcn_ve_unreg_s: float = SD_TCN_VE_UNREG_S_SSS_ENABLED

    # EASYPASS / EU
    mean_easypass_s: float = MEAN_EASYPASS_S
    sd_easypass_s: float = SD_EASYPASS_S
    mean_eu_s: float = MEAN_EU_S
    sd_eu_s: float = SD_EU_S
   
    # Deboarding
    deboard_offset_min: float = 5.0
    deboard_window_min: float = 20.0

    # Gehgeschwindigkeit (m/s) – Variation pro Passagier
    walk_speed_mean_mps: float = 1.25   # ca. 4.5 km/h
    walk_speed_sd_mps: float = 0.25
    walk_speed_floor_mps: float = 0.5   # nie langsamer als das

    # Passagiermix (muss in Summe 1.0 ergeben!)
    share_easypass: float = 0.35
    share_eu_manual: float = 0.35
    share_tcn_at: float = 0.10
    share_tcn_vh: float = 0.10
    share_tcn_ve: float = 0.10

    # Routing-Heuristik für TCN-AT
    tcn_at_policy: str = "load"  # "load" oder "queue"


# =========================
# Ergebnisstruktur
# =========================
@dataclass
class PassengerResult:
    flight_key: str
    fln: str
    pax_id: int
    group: str

    arrival_min: float
    exit_min: float
    system_min: float

    wait_sss: float = 0.0
    serv_sss: float = 0.0
    wait_easypass: float = 0.0
    serv_easypass: float = 0.0
    wait_eu: float = 0.0
    serv_eu: float = 0.0
    wait_tcn: float = 0.0
    serv_tcn: float = 0.0

    used_sss: bool = False
    used_easypass: bool = False
    used_eu: bool = False
    used_tcn: bool = False
    ees_status: str | None = None  # "EES_registered" | "EES_unregistered" | None


# =========================
# Hilfsfunktionen
# =========================
def _pos_normal(rng: random.Random, mean: float, sd: float, floor: float = 0.05) -> float:
    return max(floor, rng.normalvariate(mean, sd))


def _service_time_min(
    cfg: SimConfig,
    rng: random.Random,
    station: str,
    group: str | None = None,
    ees_status: str | None = None,
) -> float:
    """Servicezeit in Minuten (Input in Sekunden)."""

    # ---- SSS: nur relevant für VH/VE ----
    if station == "SSS":
        if group in ("TCN_VH", "TCN_VE") and ees_status in ("EES_registered", "EES_unregistered"):
            if group == "TCN_VH" and ees_status == "EES_registered":
                return _pos_normal(rng, cfg.mean_sss_vh_reg_s, cfg.sd_sss_vh_reg_s) / 60.0
            if group == "TCN_VH" and ees_status == "EES_unregistered":
                return _pos_normal(rng, cfg.mean_sss_vh_unreg_s, cfg.sd_sss_vh_unreg_s) / 60.0
            if group == "TCN_VE" and ees_status == "EES_registered":
                return _pos_normal(rng, cfg.mean_sss_ve_reg_s, cfg.sd_sss_ve_reg_s) / 60.0
            if group == "TCN_VE" and ees_status == "EES_unregistered":
                return _pos_normal(rng, cfg.mean_sss_ve_unreg_s, cfg.sd_sss_ve_unreg_s) / 60.0

        # Fallback (sollte eigentlich nicht passieren)
        #return _pos_normal(rng, cfg.mean_sss_s, cfg.sd_sss_s) / 60.0

    # ---- Easypass / EU unverändert ----
    if station == "EASYPASS":
        return _pos_normal(rng, cfg.mean_easypass_s, cfg.sd_easypass_s) / 60.0

    if station == "EU":
        return _pos_normal(rng, cfg.mean_eu_s, cfg.sd_eu_s) / 60.0

    # ---- TCN: VH/VE x reg/unreg ----
    if station == "TCN":
        if group in ("TCN_VH", "TCN_VE") and ees_status in ("EES_registered", "EES_unregistered"):
            if group == "TCN_VH" and ees_status == "EES_registered":
                return _pos_normal(rng, cfg.mean_tcn_vh_reg_s, cfg.sd_tcn_vh_reg_s) / 60.0
            if group == "TCN_VH" and ees_status == "EES_unregistered":
                return _pos_normal(rng, cfg.mean_tcn_vh_unreg_s, cfg.sd_tcn_vh_unreg_s) / 60.0
            if group == "TCN_VE" and ees_status == "EES_registered":
                return _pos_normal(rng, cfg.mean_tcn_ve_reg_s, cfg.sd_tcn_ve_reg_s) / 60.0
            if group == "TCN_VE" and ees_status == "EES_unregistered":
                return _pos_normal(rng, cfg.mean_tcn_ve_unreg_s, cfg.sd_tcn_ve_unreg_s) / 60.0

        # Fallback
        #return _pos_normal(rng, cfg.mean_tcn_s, cfg.sd_tcn_s) / 60.0

    raise ValueError(station)


def _walk_time_min(cfg: SimConfig, rng: random.Random, distance_m: float) -> float:
    speed = max(cfg.walk_speed_floor_mps, rng.normalvariate(cfg.walk_speed_mean_mps, cfg.walk_speed_sd_mps))
    seconds = distance_m / speed
    return seconds / 60.0


# =========================
# Modell
# =========================
class _DisabledResource:
    """Lightweight shim that mimics parts of simpy.Resource for a disabled station.

    - `queue`, `count`, `capacity` attributes are present for snapshot inspection.
    - `request()` returns a context manager whose __enter__ returns an immediately triggered
      env.timeout(0) event so `with res.request() as req: yield req` still works if ever used.
    """
    def __init__(self, env: simpy.Environment):
        self.queue: list = []
        self.count: int = 0
        self.capacity: int = 0
        self._env = env

    class _ReqCtx:
        def __init__(self, env: simpy.Environment):
            self._event = env.timeout(0)

        def __enter__(self):
            return self._event

        def __exit__(self, exc_type, exc, tb):
            return False

        def __await__(self):
            return self._event.__await__()

    def request(self):
        return _DisabledResource._ReqCtx(self._env)

class BorderControlModel:
    def __init__(self, env: simpy.Environment, cfg: SimConfig, rng: random.Random):
        self.env = env
        self.cfg = cfg
        self.rng = rng

        # Create real simpy resources only when enabled and capacity > 0.
        if getattr(cfg, "sss_enabled", True) and cfg.cap_sss and cfg.cap_sss > 0:
            self.sss = simpy.Resource(env, capacity=cfg.cap_sss)
        else:
            self.sss = _DisabledResource(env)
        self.easypass = simpy.Resource(env, capacity=cfg.cap_easypass)
        self.eu = simpy.PriorityResource(env, capacity=cfg.cap_eu)
        self.tcn = simpy.Resource(env, capacity=cfg.cap_tcn)

        self.results: List[PassengerResult] = []
        self.queue_ts: List[Dict[str, Any]] = []

    def snapshot(self):
        self.queue_ts.append({
            "t_min": float(self.env.now),
            "q_sss": len(self.sss.queue), "in_sss": self.sss.count,
            "q_easypass": len(self.easypass.queue), "in_easypass": self.easypass.count,
            "q_eu": len(self.eu.queue), "in_eu": self.eu.count,
            "q_tcn": len(self.tcn.queue), "in_tcn": self.tcn.count,
        })

    def eu_manual_waiting(self) -> bool:
        return any(getattr(req, "priority", 99) == 0 for req in self.eu.queue)

    def _load(self, res: simpy.Resource) -> float:
        return (len(res.queue) + res.count) / max(1, res.capacity)

    def choose_for_tcn_at(self) -> str:
        if self.cfg.tcn_at_policy == "queue":
            return "EASYPASS" if len(self.easypass.queue) <= len(self.eu.queue) else "EU"
        return "EASYPASS" if self._load(self.easypass) <= self._load(self.eu) else "EU"

    def do_station(self, station: str, pr: PassengerResult, eu_priority: int = 0):
        self.snapshot()
        t_arr = float(self.env.now)

        if station == "SSS":
            with self.sss.request() as req:
                yield req
                t_start = float(self.env.now)
                serv = _service_time_min(self.cfg, self.rng, "SSS", pr.group, pr.ees_status)
                yield self.env.timeout(serv)
            pr.used_sss = True
            pr.wait_sss += t_start - t_arr
            pr.serv_sss += serv

        elif station == "EASYPASS":
            with self.easypass.request() as req:
                yield req
                t_start = float(self.env.now)
                serv = _service_time_min(self.cfg, self.rng, "EASYPASS")
                yield self.env.timeout(serv)
            pr.used_easypass = True
            pr.wait_easypass += t_start - t_arr
            pr.serv_easypass += serv

        elif station == "EU":
            with self.eu.request(priority=eu_priority) as req:
                yield req
                t_start = float(self.env.now)
                serv = _service_time_min(self.cfg, self.rng, "EU")
                yield self.env.timeout(serv)
            pr.used_eu = True
            pr.wait_eu += t_start - t_arr
            pr.serv_eu += serv

        elif station == "TCN":
            with self.tcn.request() as req:
                yield req
                t_start = float(self.env.now)
                serv = _service_time_min(self.cfg, self.rng, "TCN", pr.group, pr.ees_status)
                yield self.env.timeout(serv)
            pr.used_tcn = True
            pr.wait_tcn += t_start - t_arr
            pr.serv_tcn += serv

        self.snapshot()

    def passenger_process(self, flight_key: str, fln: str, pax_id: int, group: str, ees_status: str | None = None):
        arrival = float(self.env.now)
        pr = PassengerResult(
            flight_key=flight_key,
            fln=fln,
            pax_id=pax_id,
            group=group,
            ees_status=ees_status,
            arrival_min=arrival,
            exit_min=arrival,
            system_min=0.0,
        )

        if group == "EASYPASS":
            yield from self.do_station("EASYPASS", pr)

        elif group == "EU_MANUAL":
            yield from self.do_station("EU", pr, eu_priority=0)

        elif group == "TCN_AT":
            station = self.choose_for_tcn_at()
            yield from self.do_station(station, pr, eu_priority=0 if station == "EU" else 0)

        elif group in ("TCN_VH", "TCN_VE"):
            # SSS nur wenn enabled
            if self.cfg.sss_enabled:
                yield from self.do_station("SSS", pr)
            if not self.eu_manual_waiting():
                yield from self.do_station("EU", pr, eu_priority=1)
            else:
                yield from self.do_station("TCN", pr)

        pr.exit_min = float(self.env.now)
        pr.system_min = pr.exit_min - pr.arrival_min
        self.results.append(pr)

    def control_summary(self) -> dict:
        """
        Kontrollwerte am Ende der Simulation:
        - Anzahl & Anteil je Gruppe
        - optional: Aufsplittung für TCN_VH/TCN_VE nach EES_registered/unregistered
        - optional: Anzahl je Flug (flight_key)
        """
        total = len(self.results)

        # 1) counts je Gruppe
        c_group = Counter(r.group for r in self.results)

        # 2) counts je (Gruppe, EES-Status) für VH/VE
        c_group_ees = Counter(
            (r.group, r.ees_status)
            for r in self.results
            if r.group in ("TCN_VH", "TCN_VE")
        )

        # 3) counts je Flug
        c_flight = Counter(r.flight_key for r in self.results)

        def pct(n: int) -> float:
            return (100.0 * n / total) if total else 0.0

        # Tabellarisch (als List[dict]) – super für Streamlit/Plotly/CSV
        table_by_group = []
        for g, n in sorted(c_group.items(), key=lambda x: (-x[1], x[0])):
            table_by_group.append({
                "group": g,
                "count": n,
                "share_pct": round(pct(n), 1),
            })

        # EES-Split (nur VH/VE)
        table_by_group_ees = []
        for (g, ees), n in sorted(c_group_ees.items(), key=lambda x: (-x[1], x[0][0], str(x[0][1]))):
            table_by_group_ees.append({
                "group": g,
                "ees_status": ees,
                "count": n,
                "share_pct": round(pct(n), 1),
            })

        # Optional: Soll/Ist Vergleich gegen cfg-Mix (nur Gruppen, nicht EES)
        target = {
            "EASYPASS": self.cfg.share_easypass,
            "EU_MANUAL": self.cfg.share_eu_manual,
            "TCN_AT": self.cfg.share_tcn_at,
            "TCN_VH": self.cfg.share_tcn_vh,
            "TCN_VE": self.cfg.share_tcn_ve,
        }
        table_mix_check = []
        for g in ["EASYPASS", "EU_MANUAL", "TCN_AT", "TCN_VH", "TCN_VE"]:
            n = c_group.get(g, 0)
            ist = (n / total) if total else 0.0
            soll = target.get(g, 0.0)
            table_mix_check.append({
                "group": g,
                "count": n,
                "ist_pct": round(100.0 * ist, 1),
                "soll_pct": round(100.0 * soll, 1),
                "diff_pct_points": round(100.0 * (ist - soll), 1),
            })

        return {
            "total": total,
            "by_group": table_by_group,
            "by_group_ees": table_by_group_ees,
            "by_flight": [{"flight_key": k, "count": v} for k, v in sorted(c_flight.items())],
            "mix_check": table_mix_check,
        }



# =========================
# Flug- & Passagiererzeugung
# =========================
def assign_groups(cfg: SimConfig, rng: random.Random, n: int) -> List[str]:
    weights = [
        cfg.share_easypass,
        cfg.share_eu_manual,
        cfg.share_tcn_at,
        cfg.share_tcn_vh,
        cfg.share_tcn_ve,
    ]
    return rng.choices(GROUPS, weights=weights, k=n)


def schedule_flights(env: simpy.Environment, model: BorderControlModel, flights: List[Dict[str, Any]]):
    def flight_proc(f: Dict[str, Any]):
        # Warten bis SIBT (relativ)
        yield env.timeout(max(0.0, f["t_arr_min"] - env.now))

        pax = int(f["spax"])
        groups = assign_groups(model.cfg, model.rng, pax)

        # Distanz einmal pro Flug bestimmen (PPOS -> Border)
        distance_m = float(PPOS_DISTANCE_M.get(str(f["ppos"]), 0.0))

        for i, g in enumerate(groups, start=1):
            # 5 Min Türen öffnen (= deboard_offset_min) + Deboarding-Verteilung im Fenster
            deboard_delay = (
                model.cfg.deboard_offset_min
                + model.rng.random() * model.cfg.deboard_window_min
            )

            # Fußweg zur Grenzkontrolle (abhängig von PPOS und individueller Gehgeschwindigkeit)
            walk_delay = _walk_time_min(model.cfg, model.rng, distance_m)

            # EES-Status nur für TCN_VH / TCN_VE
            ees_status = None
            if g in ("TCN_VH", "TCN_VE"):
                if model.rng.random() < model.cfg.ees_registered_share:
                    ees_status = "EES_registered"
                else:
                    ees_status = "EES_unregistered"

            total_delay = deboard_delay + walk_delay
            env.process(spawn_after(total_delay, f["flight_key"], f["fln"], i, g, ees_status))

    def spawn_after(delay: float, flight_key: str, fln: str, pax_id: int, group: str, ees_status: str | None):
        yield env.timeout(delay)
        env.process(model.passenger_process(flight_key, fln, pax_id, group, ees_status))

    for f in flights:
        env.process(flight_proc(f))




# =========================
# Runner
# =========================
def run_simulation(
    flights: List[Dict[str, Any]],
    cfg: SimConfig,
    seed: int = 42,
    until_min: Optional[float] = None,
) -> BorderControlModel:
    rng = random.Random(seed)
    env = simpy.Environment()
    model = BorderControlModel(env, cfg, rng)
    schedule_flights(env, model, flights)

    if until_min is None:
        max_arr = max((f["t_arr_min"] for f in flights), default=0.0)
        until_min = (
            max_arr
            + cfg.deboard_offset_min
            + cfg.deboard_window_min
            + 240.0
        )

    env.run(until=until_min)
    return model