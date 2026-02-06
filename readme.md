# SIM EES - Simulation des EES-Prozesses am Flughafen

Eine Streamlit-basierte, diskrete Ereignissimulation zur Analyse und Visualisierung von Passagierströmen an der Grenzkontrolle unter Berücksichtigung des Entry/Exit Systems (EES).

## 🌟 Features

*   **Flugplan-basiert**: Simuliert Passagierankünfte basierend auf einem importierbaren Flugplan (CSV/XLSX).
*   **Detaillierte Passagiermodellierung**: Unterscheidet zwischen verschiedenen Passagiergruppen (`Easypass`, `EU-manual`, `TCN-AT`, `TCN-V`) mit jeweils eigenen Prozesspfaden.
*   **Flexible Konfiguration**: Nahezu alle Simulationsparameter (Prozesszeiten, Passagiermix, Kapazitäten, Gehgeschwindigkeiten etc.) sind über die UI einstellbar.
*   **Iterative Kapazitätsanpassung**: Ein "Passbox"-Modus ermittelt iterativ die benötigten Schalterkapazitäten, um ein definiertes Service-Level (maximale Wartezeit) zu erreichen.
*   **Umfassende Visualisierung**: Interaktive Diagramme (Zeitreihen, Heatmaps) und Tabellen zur detaillierten Analyse der Ergebnisse (Wartezeiten, Warteschlangenlängen, KPIs).
*   **Speichern & Laden**: Benutzereinstellungen können gespeichert und wieder geladen werden, um die Reproduzierbarkeit zu gewährleisten.

## 🚀 Installation & Start

### Voraussetzungen
*   Python 3.9+

### Setup

1.  **Repository klonen**:
    ```bash
    git clone <repository-url>
    cd <repository-ordner>
    ```

2.  **Virtuelle Umgebung erstellen (empfohlen)**:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Auf Windows: .venv\Scripts\activate
    ```

3.  **Abhängigkeiten installieren**:
    Erstellen Sie eine `requirements.txt`-Datei mit folgendem Inhalt und installieren Sie diese.

    **requirements.txt**:
    ```
    simpy>=4.0,<5.0
    pandas>=1.5,<3.0
    streamlit>=1.25,<2.0
    plotly>=5.15,<6.0
    openpyxl>=3.1,<4.0
    ```

    ```bash
    pip install -r requirements.txt
    ```

### Anwendung starten

Führen Sie den folgenden Befehl im Hauptverzeichnis des Projekts aus:

```bash
streamlit run Simulation.py
```

Die Anwendung sollte sich nun in Ihrem Webbrowser öffnen.

## 📖 Benutzung

1.  **Flugplan hochladen**: Ziehen Sie eine Flugplan-Datei (CSV oder XLSX) in den Upload-Bereich. Das Format wird automatisch erkannt. Stellen Sie sicher, dass die Datei die benötigten Spalten enthält.
2.  **Flüge auswählen**: In der Tabelle werden alle gültigen Flüge angezeigt. Standardmäßig sind alle Flüge für die Simulation aktiviert. Sie können einzelne Flüge über die Checkbox "Aktiv" deaktivieren.
3.  **Einstellungen anpassen**: Öffnen Sie die Expander in der linken Seitenleiste, um Simulationsparameter wie den Passagiermix, Kapazitäten, Prozesszeiten und Service-Level-Ziele anzupassen.
4.  **Simulation starten**: Klicken Sie auf den Button "▶️ Simulation starten" oben in der Seitenleiste.
5.  **Ergebnisse analysieren**: Nach Abschluss der Simulation werden die Ergebnisse im Hauptbereich angezeigt, unterteilt in KPIs, Diagramme und detaillierte Tabellen.

## 👨‍💻 Für Entwickler

### Projektstruktur

Das Projekt ist modular aufgebaut, um die Wartbarkeit zu erleichtern:

*   `Simulation.py`: Der Haupteinstiegspunkt der Streamlit-Anwendung. Enthält die UI-Logik, die Orchestrierung der Simulationsläufe und die Darstellung der Ergebnisse.
*   `engine.py`: Das Herzstück der Simulation. Definiert die `simpy`-basierten Prozesse für Passagiere, die Ressourcenverwaltung und die Datenstrukturen (`SimConfig`, `PassengerResult`).
*   `settings_sidebar.py`: Rendert die komplette Einstellungs-Seitenleiste und deren Logik.
*   `plotting.py`: Enthält alle Funktionen zur Erstellung der `plotly`-Diagramme.
*   `session_state_init.py`: Verwaltet die Initialisierung, das Speichern und Laden des `st.session_state`.
*   `passenger_data.py`: Eine zentrale Konfigurationsdatei für die meisten Standard-Simulationsparameter (z.B. Prozesszeiten, Kapazitäten, Passagiermix).
*   `flight_allocation.py`, `ppos_distances.py`, `typ4_defaults.py`: Enthalten statische Mapping-Daten für die Terminalzuweisung, Gehdistanzen und Flugzeugtypen.

### Wichtige Abhängigkeiten

*   **Streamlit**: Für das Web-Framework und die UI-Komponenten.
*   **SimPy**: Für die diskrete Ereignissimulation.
*   **Pandas**: Für die Datenmanipulation, insbesondere des Flugplans und der Ergebnis-DataFrames.
*   **Plotly**: Für die Erstellung der interaktiven Diagramme.

### Konfiguration

Die meisten "magischen Zahlen" und Standardwerte sind in `passenger_data.py` zentralisiert. Wenn Sie grundlegende Annahmen der Simulation (z.B. die durchschnittliche Prozesszeit am EU-Schalter) ändern möchten, ist dies der richtige Ort.

## 📋 Eingabedaten: Flugplan

Die Simulationslogik ist auf ein bestimmtes Format der Flugplandatei angewiesen.

**Pflichtspalten**:

| Spalte | Beschreibung                                                                                              | Beispiel      |
| :------- | :-------------------------------------------------------------------------------------------------------- | :------------ |
| `BIBT`   | Block-In-Zeit (Ankunftszeit des Fluges). Format: `TT.MM.JJJJ HH:MM`                                        | `01.01.2024 06:30` |
| `FLN`    | Flugnummer.                                                                                               | `LH2024`      |
| `PPOS`   | Parkposition. Wird für die Terminalzuweisung und Gehdistanz verwendet.                                    | `01A`         |
| `PK`     | Kennzeichen, ob der Flug Passagiere für die Grenzkontrolle hat. Muss "JA" (oder Äquivalent) sein.         | `JA`          |
| `EPAX`   | Erwartete Passagieranzahl. Wird verwendet, wenn `APAX` nicht verfügbar ist.                               | `150`         |
| `Typ4`   | ICAO-Code des Flugzeugtyps. Dient als Fallback zur Bestimmung der Passagierzahl.                          | `A320`        |
| `T`      | Terminal-Information aus der Quelldatei (wird aktuell nicht primär genutzt, aber erwartet).               | `1`           |

**Optionale Spalten**:

| Spalte  | Beschreibung                                                                                              | Beispiel |
| :------ | :-------------------------------------------------------------------------------------------------------- | :------- |
| `APAX`  | Tatsächliche Passagieranzahl. Hat Priorität vor `EPAX` und dem Fallback über `Typ4`.                        | `145`    |
| `ADEP3` | Herkunftsflughafen (ICAO-Code).                                                                             | `EDDF`   |

**Logik zur Passagierzahl (`SPAX`)**:

Die finale Passagierzahl für die Simulation (`SPAX`) wird nach folgender Priorität ermittelt:
1.  Wert aus `APAX` (falls vorhanden und gültig).
2.  Wert aus `EPAX` (falls vorhanden und gültig).
3.  Fallback auf einen Standardwert basierend auf dem `Typ4` aus `typ4_defaults.py`.
4.  Wenn alles fehlschlägt, wird ein generischer Standardwert von 100 verwendet.

---

Bei Fragen oder Problemen können Sie ein Issue im Repository erstellen. Pull Requests zur Verbesserung der Anwendung sind willkommen!