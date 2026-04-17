from __future__ import annotations
"""
Kernmodul der Simulations-Engine.

Dieses Modul enthält die zentrale Logik für die diskrete Ereignissimulation
des Grenzkontrollprozesses mittels `simpy`. Es definiert die Datenstrukturen
für die Konfiguration und die Ergebnisse, die Simulationsprozesse für Passagiere
und die dynamische Ressourcenverwaltung.
"""
from collections import Counter, defaultdict
import math

import pandas as pd
import random
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

import simpy

from parameter import (
    MEAN_SSS_S, SD_SSS_S,
    MU_TCN_V_S_SSS_ENABLED, SIGMA_TCN_V_S_SSS_ENABLED, MU_TCN_V_S_SSS_DISABLED, SIGMA_TCN_V_S_SSS_DISABLED,
    MAX_TCN_V_S,
    MU_EASYPASS_S, SIGMA_EASYPASS_S, MAX_EASYPASS_S,
    MU_EU_S, SIGMA_EU_S, MAX_EU_S, DEBOARD_DELAY_MIN_S, DEBOARD_DELAY_MAX_S,
    BUS_CAPACITY, BUS_FILL_TIME_MIN, BUS_TRAVEL_TIME_MIN,
    PPOS_DISTANCE_M,
)


# Interne Gruppen
GROUPS = ["EASYPASS", "EU_MANUAL", "TCN_AT", "TCN_V"]


# =========================================================
# Datenstrukturen: Konfiguration und Ergebnisse
# =========================================================
@dataclass
class SimConfig:
    """Datenklasse zur Speicherung aller Konfigurationsparameter für einen Simulationslauf."""
    
    # Zeitabhängige Kapazitätspläne
    cap_tcn_schedule: dict[str, int] # Zeitplan für TCN-Schalter
    cap_eu_schedule: dict[str, int]
    mu_tcn_v_s: float
    sigma_tcn_v_s: float
    max_tcn_v_s: float

    # EASYPASS
    mu_easypass_s: float
    sigma_easypass_s: float
    max_easypass_s: float

    # EU
    mu_eu_s: float
    sigma_eu_s: float
    max_eu_s: float

    # Service Level Ziel in Minuten
    service_level_min: float

    # Kapazitäten
    cap_sss: int = 6
    cap_easypass: int = 8

    # SSS aktiviert/deaktiviert
    sss_enabled: bool = True

    # SSS Servicezeiten [Sekunden]
    mean_sss_s: float = MEAN_SSS_S
    sd_sss_s: float = SD_SSS_S

    # Deboarding
    deboard_offset_min: float = 5.0
    deboard_delay_min_s: int = DEBOARD_DELAY_MIN_S
    deboard_delay_max_s: int = DEBOARD_DELAY_MAX_S
    # Zeit für das Verlassen und Betreten des Schalters (in Sekunden)
    changeover_s: float = 0.0

    # Gehgeschwindigkeit (m/s) – Variation pro Passagier
    walk_speed_mean_mps: float = 1.25   # ca. 4.5 km/h
    walk_speed_sd_mps: float = 0.25
    walk_speed_floor_mps: float = 0.5   # nie langsamer als das

    # Bus-Transport
    bus_capacity: int = BUS_CAPACITY
    bus_fill_time_min: float = BUS_FILL_TIME_MIN
    bus_travel_time_min: float = BUS_TRAVEL_TIME_MIN

    # Passagiermix (muss in Summe 1.0 ergeben!)
    share_easypass: float = 0.35
    share_eu_manual: float = 0.35
    share_tcn_at: float = 0.10
    share_tcn_v: float = 0.20

    # Routing-Heuristik für TCN-AT
    tcn_at_target: str = "EASYPASS"  # "EASYPASS", "EU", oder "TCN"

# =========================
# Ergebnisstruktur
# =========================
@dataclass
class PassengerResult:
    """Datenklasse zur Speicherung der detaillierten Ergebnisse für einen einzelnen Passagier."""
    
    flight_key: str
    fln: str
    ppos: str
    pax_id: int
    group: str
    transport_mode: str

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


# =========================================================
# Statistische Hilfsfunktionen
# =========================================================
def _pos_normal(rng: random.Random, mean: float, sd: float, floor: float = 0.05) -> float:
    """Generiert eine normalverteilte Zufallszahl, die nicht unter `floor` fällt."""
    return max(floor, rng.normalvariate(mean, sd))


def _lognorm(rng: random.Random, mu: float, sigma: float, cap: float, floor: float = 0.05) -> float:
    """Generiert eine lognormal-verteilte Zufallszahl mit einem Minimum (floor) und Maximum (cap)."""
    if sigma <= 0:
        # Wenn sigma 0 ist, ist die Verteilung eine einzelne Spitze bei exp(mu).
        # Wir geben diesen Wert zurück, aber beachten floor und cap.
        return min(cap, max(floor, math.exp(mu)))

    val = rng.lognormvariate(mu, sigma)
    return min(cap, max(floor, val))


def _service_time_min(
    cfg: SimConfig,
    rng: random.Random,
    station: str,
    group: str | None = None,
) -> float:
    """
    Berechnet die Servicezeit für eine gegebene Station in Minuten.

    Args:
        cfg: Die Simulationskonfiguration.
        rng: Der Zufallszahlengenerator.
        station: Der Name der Station (z.B. "SSS", "TCN").
        group: Die Passagiergruppe (relevant für TCN).

    Returns:
        Die Servicezeit in Minuten.
    """

    # ---- SSS ----
    if station == "SSS":
        return _pos_normal(rng, cfg.mean_sss_s, cfg.sd_sss_s) / 60.0

    # ---- Easypass / EU unverändert ----
    if station == "EASYPASS":
        return _lognorm(rng, cfg.mu_easypass_s, cfg.sigma_easypass_s, cfg.max_easypass_s) / 60.0

    if station == "EU":
        return _lognorm(rng, cfg.mu_eu_s, cfg.sigma_eu_s, cfg.max_eu_s) / 60.0

    # ---- TCN: V x reg/unreg ----
    if station == "TCN":
        if group in ("TCN_V", "TCN_AT"):
            return _lognorm(rng, cfg.mu_tcn_v_s, cfg.sigma_tcn_v_s, cfg.max_tcn_v_s) / 60.0

    raise ValueError(station)


def _walk_time_min(cfg: SimConfig, rng: random.Random, distance_m: float) -> float:
    """Berechnet die Gehzeit eines Passagiers für eine gegebene Distanz in Minuten."""
    speed = max(cfg.walk_speed_floor_mps, rng.normalvariate(cfg.walk_speed_mean_mps, cfg.walk_speed_sd_mps))
    seconds = distance_m / speed
    return seconds / 60.0


# =========================================================
# Simulationsmodell
# =========================================================
class _DisabledResource:
    """
    Ein Platzhalter für eine deaktivierte `simpy.Resource`.

    Diese Klasse imitiert die grundlegende API einer `simpy.Resource`, um zu
    verhindern, dass der Code für die Anforderung von Ressourcen geändert werden
    muss, wenn eine Station deaktiviert ist. Anfragen werden sofort mit einer
    Verzögerung von 0 erfüllt.

    Attributes:
        queue (list): Immer eine leere Liste.
        count (int): Immer 0.
        capacity (int): Immer 0.

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

    def request(self):
        return _DisabledResource._ReqCtx(self._env)

class BorderControlModel:
    """
    Das Kernmodell der Grenzkontrollsimulation.

    Diese Klasse initialisiert und verwaltet alle `simpy`-Ressourcen (Schalter),
    enthält die Logik für die Passagierprozesse und sammelt die Ergebnisse.
    """
    
    def __init__(self, env: simpy.Environment, cfg: SimConfig, rng: random.Random, t0: pd.Timestamp, expected_passengers: int = 0):
        self.env = env
        self.cfg = cfg
        self.rng = rng
        self.t0 = t0
        self.expected_passengers = expected_passengers
        self.all_passengers_done = env.event()
        if self.expected_passengers == 0:
            self.all_passengers_done.succeed()

        # Create real simpy resources only when enabled and capacity > 0.
        if getattr(cfg, "sss_enabled", True) and cfg.cap_sss and cfg.cap_sss > 0:
            self.sss = simpy.Resource(env, capacity=cfg.cap_sss)
        else:
            self.sss = _DisabledResource(env)
        self.easypass = simpy.Resource(env, capacity=cfg.cap_easypass)
        
        # TCN wird als Server-Store mit zeitlich variabler Kapazität modelliert.
        self.tcn = simpy.Store(env)
        self.tcn_in_use = 0
        self.current_tcn_capacity = 0
        self.tcn_pending_removals = 0
        self.tcn_server_seq = 0
        self.env.process(self.tcn_capacity_manager())

        # EU wird als Prioritätswarteschlange plus Server-Store modelliert,
        # damit Prioritäten global über alle EU-Server greifen.
        self.eu_servers = simpy.Store(env)
        self.eu_waiters = simpy.PriorityStore(env)
        self.eu_in_use = 0
        self.current_eu_capacity = 0
        self.eu_manual_wait_count = 0
        self.eu_pending_removals = 0
        self.eu_server_seq = 0
        self.eu_request_seq = 0
        self.eu_dispatch_signal = env.event()
        self.env.process(self.eu_dispatcher())
        self.env.process(self.eu_capacity_manager())

        self.results: List[PassengerResult] = []
        self.queue_ts: List[Dict[str, Any]] = []

    def snapshot(self):
        """Erstellt einen Schnappschuss der aktuellen Warteschlangenlängen und Ressourcennutzung."""
        self.queue_ts.append({
            "t_min": float(self.env.now),
            "q_sss": len(self.sss.queue), "in_sss": self.sss.count,
            "q_easypass": len(self.easypass.queue), "in_easypass": self.easypass.count,
            "q_eu": len(self.eu_waiters.items), "in_eu": self.eu_in_use,
            "q_tcn": len(self.tcn.get_queue), "in_tcn": self.tcn_in_use,
        })

    def eu_manual_waiting(self) -> bool:
        """Prüft, ob aktuell Passagiere der Gruppe EU_MANUAL auf einen Schalter warten."""
        return self.eu_manual_wait_count > 0

    def _notify_eu_dispatcher(self):
        """Weckt den EU-Dispatcher auf, wenn neue Server oder Wartende vorliegen."""
        if not self.eu_dispatch_signal.triggered:
            self.eu_dispatch_signal.succeed()
        self.eu_dispatch_signal = self.env.event()

    def _remove_idle_servers(self, store: simpy.Store, count: int) -> int:
        """Entfernt bis zu `count` freie Server direkt aus einem Store."""
        removed = min(count, len(store.items))
        for _ in range(removed):
            store.items.pop()
        return removed

    def _release_tcn_server(self, server: Any):
        """Gibt einen TCN-Server frei oder entfernt ihn bei geplanter Kapazitätsreduktion."""
        if self.tcn_pending_removals > 0:
            self.tcn_pending_removals -= 1
            return
        yield self.tcn.put(server)

    def _release_eu_server(self, server: Any):
        """Gibt einen EU-Server frei oder entfernt ihn bei geplanter Kapazitätsreduktion."""
        if self.eu_pending_removals > 0:
            self.eu_pending_removals -= 1
            return
        yield self.eu_servers.put(server)
        self._notify_eu_dispatcher()

    def eu_dispatcher(self):
        """
        Verteilt freie EU-Server an wartende Passagiere nach globaler Priorität.
        """
        while True:
            while self.eu_servers.items and self.eu_waiters.items:
                server = yield self.eu_servers.get()
                _, _, assigned_event = yield self.eu_waiters.get()
                self.eu_in_use += 1
                self.snapshot()
                assigned_event.succeed(server)
            yield self.eu_dispatch_signal

    def do_station(self, station: str, pr: PassengerResult, eu_priority: int = 0):
        """
        Simuliert den Prozess des Anforderns und Nutzens einer Servicestation.

        Dieser Generator-Prozess kümmert sich um das Anstellen, Warten,
        die Service-Abwicklung und das Sammeln der entsprechenden Zeitstempel.

        Args:
            station: Die zu nutzende Station (z.B. "SSS", "EU").
            pr: Das Ergebnisobjekt des Passagiers, in das die Zeiten geschrieben werden.
            eu_priority: Die Priorität für den EU-Schalter (0 für EU_MANUAL, 1 für TCN_V).
        """
        self.snapshot()
        t_arr = float(self.env.now)
        changeover_min = self.cfg.changeover_s / 60.0

        if station == "SSS":
            with self.sss.request() as req:
                yield req
                t_start = float(self.env.now)
                serv = _service_time_min(self.cfg, self.rng, "SSS", pr.group)
                yield self.env.timeout(serv)
                if changeover_min > 0:
                    yield self.env.timeout(changeover_min)
            pr.used_sss = True
            pr.wait_sss += t_start - t_arr
            pr.serv_sss += serv

        elif station == "EASYPASS":
            with self.easypass.request() as req:
                yield req
                t_start = float(self.env.now)
                serv = _service_time_min(self.cfg, self.rng, "EASYPASS")
                yield self.env.timeout(serv)
                if changeover_min > 0:
                    yield self.env.timeout(changeover_min)
            pr.used_easypass = True
            pr.wait_easypass += t_start - t_arr
            pr.serv_easypass += serv

        elif station == "EU":
            if eu_priority == 0:
                self.eu_manual_wait_count += 1

            assigned_event = self.env.event()
            self.eu_request_seq += 1
            yield self.eu_waiters.put((eu_priority, self.eu_request_seq, assigned_event))
            self._notify_eu_dispatcher()

            server_resource = yield assigned_event
            if eu_priority == 0:
                self.eu_manual_wait_count -= 1
            t_start = float(self.env.now)
            serv = _service_time_min(self.cfg, self.rng, "EU")
            yield self.env.timeout(serv)
            if changeover_min > 0:
                yield self.env.timeout(changeover_min)

            yield from self._release_eu_server(server_resource)
            self.eu_in_use -= 1
            pr.used_eu = True
            pr.wait_eu += t_start - t_arr
            pr.serv_eu += serv

        elif station == "TCN":
            server = yield self.tcn.get()
            self.tcn_in_use += 1
            self.snapshot() # Snapshot after getting server to correctly show queue and usage
            
            t_start = float(self.env.now)
            serv = _service_time_min(self.cfg, self.rng, "TCN", pr.group)
            yield self.env.timeout(serv)
            if changeover_min > 0:
                yield self.env.timeout(changeover_min)
            
            yield from self._release_tcn_server(server)
            self.tcn_in_use -= 1
            pr.used_tcn = True
            pr.wait_tcn += t_start - t_arr
            pr.serv_tcn += serv

        self.snapshot()

    def tcn_capacity_manager(self):
        """
        Ein `simpy`-Prozess, der die Kapazität der TCN-Station dynamisch anpasst.

        Dieser Prozess liest den Kapazitätsplan aus der Konfiguration und fügt
        zum richtigen Zeitpunkt Server-Ressourcen zum `simpy.Store` hinzu oder entfernt sie.
        """
        
        # 1. Parse schedule from config
        schedule_parsed = []
        for key, cap in self.cfg.cap_tcn_schedule.items():
            start_str, _ = key.split('-') # Wir brauchen nur die Startzeit, z.B. "06:15"
            if ':' in start_str:
                start_h, start_m = map(int, start_str.split(':'))
            else:
                start_h = int(start_str)
                start_m = 0
            start_min_of_day = start_h * 60 + start_m
            schedule_parsed.append((start_min_of_day, cap))
        schedule_parsed.sort()

        # 2. Determine initial capacity at simulation start (t=0)
        sim_start_time_of_day_min = self.t0.hour * 60 + self.t0.minute
        initial_cap = schedule_parsed[-1][1] if schedule_parsed else 0 # Default to last entry if before first
        for start_min, cap in schedule_parsed:
            if sim_start_time_of_day_min >= start_min:
                initial_cap = cap
        
        self.current_tcn_capacity = initial_cap
        for _ in range(initial_cap):
            self.tcn_server_seq += 1
            yield self.tcn.put(f"TCN-Server-{self.tcn_server_seq}")

        # 3. Eine Liste aller zukünftigen Kapazitätsänderungen erstellen
        events = []
        for change_time_min, new_cap in schedule_parsed:
            # Event für den aktuellen Tag
            events.append((self.t0.normalize() + pd.Timedelta(minutes=change_time_min), new_cap))
            # Event für den nächsten Tag (falls die Simulation über Mitternacht läuft)
            events.append((self.t0.normalize() + pd.Timedelta(days=1, minutes=change_time_min), new_cap))
        
        # Events sortieren und nur die behalten, die nach dem Simulationsstart liegen
        future_events = sorted([e for e in events if e[0] > self.t0])

        # 4. Zukünftige Events sequenziell abarbeiten
        for change_datetime, new_cap in future_events:
            sim_time_for_change = (change_datetime - self.t0).total_seconds() / 60.0
            delay = sim_time_for_change - self.env.now
            if delay > 0:
                yield self.env.timeout(delay)

            diff = new_cap - self.current_tcn_capacity
            if diff > 0:
                for _ in range(diff):
                    self.tcn_server_seq += 1
                    yield self.tcn.put(f"TCN-Server-{self.tcn_server_seq}")
            elif diff < 0:
                remove_count = abs(diff)
                removed_now = self._remove_idle_servers(self.tcn, remove_count)
                self.tcn_pending_removals += remove_count - removed_now
            self.current_tcn_capacity = new_cap

    def eu_capacity_manager(self):
        """
        Ein `simpy`-Prozess, der die Kapazität der EU-Station dynamisch anpasst.

        Dieser Prozess liest den Kapazitätsplan aus der Konfiguration und fügt
        zum richtigen Zeitpunkt EU-Server zum Server-Store hinzu oder markiert
        Server für eine verzögerte Entnahme, sobald belegte Server wieder frei werden.
        """
        
        # 1. Parse schedule from config
        schedule_parsed = []
        for key, cap in self.cfg.cap_eu_schedule.items():
            start_str, _ = key.split('-')
            if ':' in start_str:
                start_h, start_m = map(int, start_str.split(':'))
            else:
                start_h = int(start_str)
                start_m = 0
            start_min_of_day = start_h * 60 + start_m
            schedule_parsed.append((start_min_of_day, cap))
        schedule_parsed.sort()

        # 2. Determine initial capacity at simulation start (t=0)
        sim_start_time_of_day_min = self.t0.hour * 60 + self.t0.minute
        initial_cap = schedule_parsed[-1][1] if schedule_parsed else 0
        for start_min, cap in schedule_parsed:
            if sim_start_time_of_day_min >= start_min:
                initial_cap = cap
        
        self.current_eu_capacity = initial_cap
        for _ in range(initial_cap):
            self.eu_server_seq += 1
            yield self.eu_servers.put(f"EU-Server-{self.eu_server_seq}")
        self._notify_eu_dispatcher()

        # 3. Eine Liste aller zukünftigen Kapazitätsänderungen erstellen
        events = []
        for change_time_min, new_cap in schedule_parsed:
            events.append((self.t0.normalize() + pd.Timedelta(minutes=change_time_min), new_cap))
            events.append((self.t0.normalize() + pd.Timedelta(days=1, minutes=change_time_min), new_cap))
        
        future_events = sorted([e for e in events if e[0] > self.t0])

        # 4. Zukünftige Events sequenziell abarbeiten
        for change_datetime, new_cap in future_events:
            sim_time_for_change = (change_datetime - self.t0).total_seconds() / 60.0
            delay = sim_time_for_change - self.env.now
            if delay > 0:
                yield self.env.timeout(delay)

            diff = new_cap - self.current_eu_capacity
            if diff > 0:
                for _ in range(diff):
                    self.eu_server_seq += 1
                    yield self.eu_servers.put(f"EU-Server-{self.eu_server_seq}")
                self._notify_eu_dispatcher()
            elif diff < 0:
                remove_count = abs(diff)
                removed_now = self._remove_idle_servers(self.eu_servers, remove_count)
                self.eu_pending_removals += remove_count - removed_now
            self.current_eu_capacity = new_cap

    def passenger_process(self, flight_key: str, fln: str, ppos: str, pax_id: int, group: str, transport_mode: str = "Walk"):
        """
        Der Hauptprozess für einen einzelnen Passagier.

        Dieser Prozess steuert den gesamten Weg eines Passagiers durch das System,
        von der Ankunft an der Grenzkontrolle bis zum Verlassen. Er entscheidet
        basierend auf der Passagiergruppe, welche Stationen in welcher Reihenfolge
        besucht werden.

        Args:
            Alle Argumente beschreiben den Passagier und seinen Ankunftskontext.
        """

        arrival = float(self.env.now)
        pr = PassengerResult(
            flight_key=flight_key,
            fln=fln,
            ppos=ppos,
            pax_id=pax_id,
            group=group,
            transport_mode=transport_mode,
            arrival_min=arrival,
            exit_min=arrival,
            system_min=0.0,
        )

        if group == "EASYPASS":
            yield from self.do_station("EASYPASS", pr)

        elif group == "EU_MANUAL":
            yield from self.do_station("EU", pr, eu_priority=0)

        elif group == "TCN_AT":
            station = self.cfg.tcn_at_target
            if station == "EASYPASS":
                yield from self.do_station("EASYPASS", pr)
            elif station == "EU":
                yield from self.do_station("EU", pr, eu_priority=0)
            elif station == "TCN":
                yield from self.do_station("TCN", pr)

        elif group == "TCN_V":
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
        if len(self.results) == self.expected_passengers and not self.all_passengers_done.triggered:
            self.all_passengers_done.succeed()

    def control_summary(self) -> dict:
        """
        Erstellt eine zusammenfassende Statistik nach Abschluss der Simulation.

        Returns:
            Ein Dictionary mit aggregierten Daten, z.B. Passagieranzahl pro Gruppe,
            pro Flug und ein Soll-Ist-Vergleich des Passagiermixes.
        """

        total = len(self.results)

        # 1) counts je Gruppe
        c_group = Counter(r.group for r in self.results)

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

        # Optional: Soll/Ist Vergleich gegen cfg-Mix (nur Gruppen, nicht EES)
        target = {
            "EASYPASS": self.cfg.share_easypass,
            "EU_MANUAL": self.cfg.share_eu_manual,
            "TCN_AT": self.cfg.share_tcn_at,
            "TCN_V": self.cfg.share_tcn_v,
        }
        table_mix_check = []
        for g in ["EASYPASS", "EU_MANUAL", "TCN_AT", "TCN_V"]:
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
            "by_flight": [{"flight_key": k, "count": v} for k, v in sorted(c_flight.items())],
            "mix_check": table_mix_check,
        }



# =========================================================
# Generatoren für Flüge und Passagiere
# =========================================================
def assign_groups(cfg: SimConfig, rng: random.Random, n: int) -> List[str]:
    """
    Weist `n` Passagieren zufällig eine Gruppe basierend auf dem konfigurierten Mix zu.
    """
    weights = [
        cfg.share_easypass,
        cfg.share_eu_manual,
        cfg.share_tcn_at,
        cfg.share_tcn_v,
    ]
    return rng.choices(GROUPS, weights=weights, k=n)


def schedule_flights(env: simpy.Environment, model: BorderControlModel, flights: List[Dict[str, Any]]):
    """
    Plant die Ankunft aller Flüge und ihrer Passagiere in der Simulation.

    Für jeden Flug wird ein eigener `simpy`-Prozess (`flight_proc`) gestartet,
    der wiederum die Ankunft der einzelnen Passagiere dieses Fluges plant.
    """
    
    def flight_proc(f: Dict[str, Any]):
        # Warten bis SIBT (relativ)
        yield env.timeout(max(0.0, f["t_arr_min"] - env.now))

        pax = int(f["spax"])
        groups = assign_groups(model.cfg, model.rng, pax)

        # Distanz einmal pro Flug bestimmen (PPOS -> Border)
        distance_m = float(PPOS_DISTANCE_M.get(str(f["ppos"]), 0.0))
        ppos = str(f["ppos"])

        if distance_m > 0:
            # Passagiere gehen zu Fuß (sequenzielles Deboarding)
            transport_mode = "Walk"
            
            # Kumulativer Deboarding-Delay, startet mit dem Offset
            cumulative_deboard_delay_min = model.cfg.deboard_offset_min
            
            for i, g in enumerate(groups, start=1):
                # Addiere die Verzögerung zwischen Passagieren (außer für den ersten)
                if i > 1:
                    inter_pax_delay_s = model.rng.randint(
                        model.cfg.deboard_delay_min_s,
                        model.cfg.deboard_delay_max_s
                    )
                    cumulative_deboard_delay_min += inter_pax_delay_s / 60.0

                walk_delay = _walk_time_min(model.cfg, model.rng, distance_m)
                
                total_delay = cumulative_deboard_delay_min + walk_delay
                env.process(spawn_after(total_delay, f["flight_key"], f["fln"], ppos, i, g, transport_mode))
        else:
            # Passagiere werden mit dem Bus gefahren
            transport_mode = "Bus"
            bus_capacity = model.cfg.bus_capacity
            bus_fill_time_max_min = model.cfg.bus_fill_time_min
            bus_travel_time = model.cfg.bus_travel_time_min

            num_buses = math.ceil(pax / bus_capacity)
            # Die Füllzeit des ersten Busses beginnt nach dem initialen Offset
            last_bus_departure_time_min = model.cfg.deboard_offset_min

            for bus_idx in range(num_buses):
                start_pax_idx = bus_idx * bus_capacity
                end_pax_idx = min((bus_idx + 1) * bus_capacity, pax)
                pax_in_this_bus = end_pax_idx - start_pax_idx

                # Füllzeit ist proportional zur Anzahl der Passagiere in diesem Bus.
                current_bus_fill_time = (pax_in_this_bus / bus_capacity) * bus_fill_time_max_min
                
                # Abfahrtszeit des Busses = Abfahrt des letzten Busses + Füllzeit des aktuellen.
                current_bus_departure_time_min = last_bus_departure_time_min + current_bus_fill_time
                
                # Ankunftszeit an der Grenzkontrolle.
                bus_arrival_at_border_min = current_bus_departure_time_min + bus_travel_time

                # Alle Passagiere dieses Busses schedulen, sie kommen als Bulk an.
                for i in range(start_pax_idx, end_pax_idx):
                    g = groups[i]
                    pax_id = i + 1
                    
                    env.process(spawn_after(bus_arrival_at_border_min, f["flight_key"], f["fln"], ppos, pax_id, g, transport_mode))

                # Abfahrtszeit für die nächste Iteration (Bus) aktualisieren.
                last_bus_departure_time_min = current_bus_departure_time_min

    def spawn_after(delay: float, flight_key: str, fln: str, ppos: str, pax_id: int, group: str, transport_mode: str):
        yield env.timeout(delay)
        env.process(model.passenger_process(flight_key, fln, ppos, pax_id, group, transport_mode))

    for f in flights:
        env.process(flight_proc(f))




# =========================================================
# Simulations-Runner
# =========================================================
def run_simulation(
    flights: List[Dict[str, Any]],
    cfg: SimConfig,
    t0: pd.Timestamp,
    seed: int = 42,
    until_min: Optional[float] = None,
) -> BorderControlModel:
    """
    Initialisiert und startet einen vollständigen Simulationslauf.

    Args:
        flights: Eine Liste von Flügen, die simuliert werden sollen.
        cfg: Die Konfiguration für diesen Simulationslauf.
        t0: Der absolute Startzeitpunkt der Simulation (t=0).
        seed: Der Seed für den Zufallszahlengenerator.
        until_min: Die maximale Simulationsdauer in Minuten.

    Returns:
        Das `BorderControlModel`-Objekt mit allen Ergebnissen.
    """
    rng = random.Random(seed)
    env = simpy.Environment()
    expected_passengers = sum(int(f["spax"]) for f in flights)
    model = BorderControlModel(env, cfg, rng, t0, expected_passengers=expected_passengers)
    schedule_flights(env, model, flights)

    if until_min is None:
        env.run(until=model.all_passengers_done)
    else:
        env.run(until=until_min)
    return model
