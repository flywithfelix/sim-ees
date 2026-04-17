# SIM EES - Simulation des EES-Prozesses am Flughafen

Eine Streamlit-basierte, diskrete Ereignissimulation zur Analyse und Visualisierung von Passagierströmen an der Grenzkontrolle unter Berücksichtigung des Entry/Exit Systems (EES).

## Features

*   **Flugplan-basiert**: Simuliert Passagierankünfte auf Basis importierter Flugplandaten (`.csv` oder `.xlsx`).
*   **API-Import für Flugdaten**: Lädt Ankunftsdaten über die Hamburg-Airport-API und bereitet sie direkt für die Simulation auf.
*   **Gespeicherte Runs wieder öffnen**: Bereits gespeicherte Ergebnisse aus dem Ordner `runs` können später zur Ansicht erneut geladen werden.
*   **Detaillierte Passagiermodellierung**: Unterscheidet zwischen verschiedenen Passagiergruppen (`Easypass`, `EU_MANUAL`, `TCN_AT`, `TCN_V`) mit jeweils eigenen Prozesspfaden.
*   **Fachlich fokussierte Konfiguration**: Zentrale Stellgrößen wie Service Level, Passbox-Kapazitäten, SSS-Nutzung und globale Prozesszeit-Skalierung sind über die UI steuerbar.
*   **Iterative Kapazitätsanpassung**: Ein "Passbox"-Modus ermittelt iterativ die benötigten Schalterkapazitäten, um ein definiertes Service-Level zu erreichen.
*   **Umfassende Visualisierung**: Interaktive Diagramme und Tabellen zur Analyse von Wartezeiten, Auslastung, Kapazitäten und Passagieraufkommen.

## Installation & Start

### Voraussetzungen

*   Python 3.9+

### Setup

1.  **Repository klonen**:
    ```bash
    git clone <repository-url>
    cd <repository-ordner>
    ```

2.  **Virtuelle Umgebung erstellen**:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Windows: .venv\Scripts\activate
    ```

3.  **Abhängigkeiten installieren**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Umgebungsvariablen konfigurieren**:
    Für den API-Import wird ein Subscription Key benötigt. Legen Sie eine `.env` im Projektverzeichnis an, z.B. auf Basis von `.env.example`.

    ```env
    HAMBURG_AIRPORT_SUBSCRIPTION_KEY=<ihr-subscription-key>
    ```

### Anwendung starten

```bash
streamlit run Simulation.py
```

## Benutzung

1.  **Importquelle wählen**: Im Importbereich kann zwischen `Datei-Import`, `API-Import` und `Gespeicherter Run` gewechselt werden. Standardmäßig ist `API-Import` vorausgewählt.
2.  **Datei-Import**: Flugplan-Datei (CSV oder XLSX) hochladen. Das Format wird automatisch erkannt.
3.  **API-Import**: Kalendertag wählen und Daten über den fest hinterlegten Hamburg-Airport-Endpunkt laden. Die Flüge werden danach direkt in das interne Format überführt.
4.  **Flüge auswählen**: Nach Datei- oder API-Import werden alle gültigen Flüge in einer Tabelle angezeigt und können über `Aktiv` ein- oder ausgeschlossen werden. Für nicht fest zugeordnete Flüge kann `GKS` angepasst werden.
5.  **Einstellungen anpassen**: Die wichtigsten Simulationsparameter werden in der linken Seitenleiste gesetzt.
6.  **Simulation starten**: Über `▶️ Simulation starten` in der Seitenleiste.
7.  **Ergebnisse analysieren**: Nach Abschluss der Simulation werden KPIs, Diagramme und Tabellen im Hauptbereich angezeigt.
8.  **Run speichern**: Ein abgeschlossener Lauf kann im Ordner `runs` gespeichert und später erneut geöffnet werden.

## API-Import

Der API-Import verwendet fest den Endpunkt `https://rest.api.hamburg-airport.de/v2/flights/arrivals`.

Verhalten:

*   Vor dem Laden wird ein Kalendertag gewählt.
*   Die API-Antwort wird anschließend auf diesen Tag gefiltert.
*   Die geladenen Flüge werden in das interne Simulationsformat überführt.
*   Eine Simulation ist direkt auf Basis der API-Daten möglich.

## Gespeicherte Runs

Gespeicherte Runs werden im Ordner `runs` abgelegt.

Gespeichert werden je nach Lauf u. a.:

*   Passenger-Details
*   Flugübersicht
*   Gruppenübersicht
*   Kapazitätstabellen für T1 und T2
*   bei neueren Läufen zusätzlich Queue-Zeitreihen

Über den Importmodus `Gespeicherter Run` kann ein gespeicherter Lauf später wieder geöffnet werden.

Wichtig:

*   Gespeicherte Runs werden nur angezeigt.
*   Es findet keine neue Simulation aus den gespeicherten Ergebnisdateien statt.
*   Ältere Runs enthalten unter Umständen noch keine Queue-Zeitreihen und können deshalb nicht jede Visualisierung vollständig darstellen.

## Ergebnisse

Die Anwendung zeigt nach einem Lauf unter anderem:

*   Wartezeit-Diagramme für TCN sowie EU/Easypass
*   Heatmaps für P95-Wartezeiten
*   KPIs je Terminal
*   Bus-Ankünfte
*   ermittelte Kapazitäten je Intervall
*   Flugübersicht
*   Gruppenübersicht
*   Detaildaten auf Passagierebene

## Für Entwickler

### Projektstruktur

*   `Simulation.py`: Haupteinstiegspunkt der Streamlit-Anwendung.
*   `engine.py`: Kern der Simulation mit `simpy`-basierten Prozessen.
*   `settings_sidebar.py`: UI-Logik der Einstellungs-Seitenleiste.
*   `plotting.py`: Erstellung der Diagramme.
*   `parameter.py`: Zentrale Standardkonfigurationen.
*   `typ4_defaults.py`: Mapping-Daten für Flugzeugtypen und Default-Pax.
*   `pages/1_Hilfe.py`: Hilfeseite für Anwender.
*   `runs/`: Ablage gespeicherter Simulationsläufe.
*   `.env`: Lokale Umgebungsvariablen wie der API-Subscription-Key.
*   `.env.example`: Vorlage für die benötigten Umgebungsvariablen.

### Wichtige Abhängigkeiten

*   **Streamlit**: Web-Framework und UI.
*   **SimPy**: Diskrete Ereignissimulation.
*   **Pandas**: Datenverarbeitung.
*   **Plotly**: Interaktive Diagramme.
*   **python-dotenv**: Laden lokaler Umgebungsvariablen aus `.env`.

### Konfiguration

Die meisten Standardwerte sind in `parameter.py` zentralisiert. Dazu gehören unter anderem:

*   Standardwerte für Prozesszeiten
*   Service-Level-Vorgaben
*   minimale und maximale Kapazitäten
*   Session-State-Defaults wie die vorausgewählte Importquelle

Für den API-Import wird zusätzlich die Umgebungsvariable `HAMBURG_AIRPORT_SUBSCRIPTION_KEY` aus der `.env` gelesen.

## Eingabedaten: Flugplan

Die Simulationslogik ist auf ein bestimmtes Format der Flugplandatei angewiesen.

### Pflichtspalten

| Spalte | Beschreibung | Beispiel |
| :-- | :-- | :-- |
| `BIBT` | Block-In-Zeit des Fluges. Format: `TT.MM.JJJJ HH:MM` | `01.01.2024 06:30` |
| `FLN` | Flugnummer | `LH2024` |
| `PPOS` | Parkposition | `01A` |
| `PK` | Kennzeichen, ob der Flug Passagiere für die Grenzkontrolle hat | `JA` |
| `EPAX` | Erwartete Passagieranzahl | `150` |
| `Typ4` | ICAO-Code des Flugzeugtyps | `A320` |
| `T` | Terminal-Information aus der Quelldatei | `1` |

### Optionale Spalten

| Spalte | Beschreibung | Beispiel |
| :-- | :-- | :-- |
| `APAX` | Tatsächliche Passagieranzahl | `145` |
| `ADEP3` | Herkunftsflughafen (ICAO-Code) | `EDDF` |

### Logik zur Passagierzahl (`SPAX`)

Die finale Passagierzahl für die Simulation (`SPAX`) wird nach folgender Priorität ermittelt:

1.  Wert aus `APAX`
2.  Wert aus `EPAX`
3.  Fallback auf einen Standardwert basierend auf `Typ4`
4.  Generischer Standardwert `100`

Wenn also keine belastbare Passagierzahl in der Quelle vorhanden ist, verwendet die Anwendung einen typbezogenen Ersatzwert.

---

Bei Fragen oder Problemen können Sie ein Issue im Repository erstellen. Pull Requests zur Verbesserung der Anwendung sind willkommen.

