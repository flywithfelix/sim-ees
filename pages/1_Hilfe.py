import streamlit as st

st.set_page_config(page_title="Hilfe - SIM EES", layout="wide")

st.title("Hilfe & Anleitung")

st.markdown(
    """
Diese Seite erklärt die Anwendung aus Sicht des Betriebs:
Welche Flüge werden betrachtet, wie werden sie einem Terminal zugeordnet,
welche Kapazitäten werden angesetzt und wie sind die Ergebnisse zu lesen.
Vorkenntnisse in Simulation sind dafür nicht erforderlich.
"""
)

st.header("Ablauf")

with st.expander("1. Importquelle wählen", expanded=True):
    st.markdown(
        """
Auf der Startseite stehen im Bereich **"Flugplan importieren"** drei Quellen zur Verfügung:

1. **Datei-Import**
   Sie laden einen eigenen Flugplan aus einer `.csv`- oder `.xlsx`-Datei.
2. **API-Import**
   Sie laden Ankünfte vom Hamburg-Airport-Endpunkt für einen gewählten Kalendertag.
3. **Gespeicherter Run**
   Sie öffnen einen früher gespeicherten Durchlauf nur zur Ansicht.

Für neue Berechnungen verwenden Sie Datei-Import oder API-Import.
Für den späteren Vergleich bereits gerechneter Tage verwenden Sie Gespeicherter Run.
"""
    )

with st.expander("2. Datei-Import"):
    st.markdown(
        """
Beim **Datei-Import** können `.csv`- und `.xlsx`-Dateien hochgeladen werden.
CSV-Trennzeichen werden automatisch erkannt.

Pflichtspalten:
- `BIBT`: Ankunftszeit, z. B. `01.01.2026 06:30`
- `FLN`: Flugnummer
- `PPOS`: Parkposition
- `PK`: Kennzeichen für grenzkontrollpflichtige Passagiere, z. B. `JA`
- `EPAX`: erwartete Passagierzahl
- `Typ4`: Flugzeugtyp
- `T`: Terminalinformation aus der Quelle

Optionale Spalten:
- `APAX`: tatsächliche Passagierzahl, hat Vorrang vor `EPAX`
- `ADEP3`: Herkunftsflughafen

Wichtig für die fachliche Einordnung:
- Es werden nur Flüge weiterverarbeitet, bei denen `PK` auf einen grenzkontrollpflichtigen Flug hinweist
- `APAX` wird verwendet, wenn vorhanden
- falls `APAX` fehlt, wird `EPAX` verwendet
- wenn beides fehlt, nutzt die App einen Standardwert passend zum Flugzeugtyp
"""
    )

with st.expander("3. API-Import"):
    st.markdown(
        """
Beim **API-Import** wird der Endpunkt
`https://rest.api.hamburg-airport.de/v2/flights/arrivals`
verwendet.

Ablauf:
1. Datum auswählen
2. **"API-Daten laden"** klicken
3. Geladene Flüge prüfen
4. Flüge wie beim Datei-Import für die Simulation auswählen

Wichtig:
- Die geladenen Flüge werden direkt für die weitere Bearbeitung vorbereitet
- Sie können die Flüge danach wie bei einem Datei-Import auswählen oder ausschließen
- Gefiltert wird auf den gewählten Kalendertag

Damit eignet sich der API-Import vor allem für einen schnellen Blick auf einen konkreten Betriebstag,
ohne vorher selbst eine Datei aufzubereiten.
"""
    )

with st.expander("4. Gespeicherte Runs anzeigen"):
    st.markdown(
        """
Mit **"Gespeicherter Run"** können bereits abgelegte Ergebnisse aus dem Ordner `runs` geladen werden.

Ablauf:
1. Flugplan-Tag auswählen
2. Einen konkreten Durchlauf für diesen Tag auswählen
3. **"Run laden"** klicken

Die Auswahl ist zweistufig, damit für einen Flugtag mehrere gespeicherte Durchläufe unterschieden werden können.

Wichtig:
- Gespeicherte Runs werden **nur angezeigt**
- Es findet **keine neue Berechnung** aus diesen gespeicherten Ergebnissen statt
- Angezeigt wird der damalige Ergebnisstand des gewählten Laufs
- Ältere Runs können teilweise ohne Warteschlangen-Heatmap geladen werden, wenn damals noch keine Queue-Zeitreihen mitgespeichert wurden

Das ist hilfreich, wenn Sie z. B. mehrere Varianten für denselben Flugtag gespeichert haben
und diese später miteinander vergleichen möchten.
"""
    )

with st.expander("5. Flüge für die Simulation auswählen"):
    st.markdown(
        """
Nach Datei- oder API-Import erscheint der Bereich **"Flüge für Simulation auswählen"**.

Dort können Sie:
- einzelne Flüge über die Spalte **`Aktiv`** ein- oder ausschließen
- die Spalte **`GKS`** für nicht fest zugewiesene Flüge auf `T1` oder `T2` setzen

Regeln zur GKS-Zuweisung:
- Flüge mit fester Parkpositions-Zuordnung werden automatisch einem Terminal zugewiesen
- diese feste Zuordnung kann nicht überschrieben werden
- nur Flüge ohne feste Zuordnung sind im `GKS`-Dropdown manuell änderbar

Praktisch bedeutet das:
- Sie entscheiden hier, welche Ankünfte in die Betrachtung eingehen
- und bei nicht eindeutig zugeordneten Flügen, an welchem Terminal deren Grenzkontrollprozess angenommen wird
"""
    )

with st.expander("6. Einstellungen in der Seitenleiste"):
    st.markdown(
        """
Die wichtigsten Steuerungen befinden sich in der linken Seitenleiste:

- **Service Level**
  Zielwert für die noch akzeptable durchschnittliche Wartezeit von TCN- und EU-Passagieren je 15-Minuten-Intervall
- **Passbox**
  Obergrenzen für automatisch geöffnete TCN- und EU-Schalter
- **SSS (Kiosk)**
  Aktivierung der SSS-Kioske getrennt für T1 und T2
- **Skalierung & Sonstiges**
  Globale Prozesszeit-Skalierung, TCN-AT-Ziel und maximale Anzahl an Simulationsiterationen

Über **"Alle Einstellungen zurücksetzen"** werden die Session-Werte auf Standard zurückgesetzt.

Wenn Sie mit dem Tool neu arbeiten, genügen meist diese Entscheidungen:
- Soll SSS im jeweiligen Terminal berücksichtigt werden?
- Wie hoch dürfen TCN- und EU-Kapazitäten maximal steigen?
- Welche Wartezeit soll als Zielgröße gelten?
"""
    )

with st.expander("7. Simulation starten und Ergebnisse lesen"):
    st.markdown(
        """
Die Simulation wird über den Button **"Simulation starten"** oben in der Seitenleiste ausgelöst.

Während des Laufs:
- prüft die Anwendung wiederholt, ob die angesetzten Kapazitäten ausreichen
- werden TCN- und EU-Kapazitäten schrittweise erhöht, wenn die gewählte Ziel-Wartezeit nicht eingehalten wird

Nach Abschluss werden u. a. angezeigt:
- Wartezeit-Diagramme für TCN sowie EU/Easypass
- Heatmaps für P95-Wartezeiten
- KPIs je Terminal
- Bus-Ankünfte
- ermittelte Kapazitäten je Intervall
- Flugübersicht
- Gruppenübersicht
- Detaildaten auf Passagierebene

Die Ergebnisse beantworten vor allem diese Fragen:
- Zu welchen Zeiten wird es kritisch?
- In welchem Terminal entsteht die Belastung?
- Welche Kapazitäten wären nötig, um das gewählte Ziel einzuhalten?
"""
    )

with st.expander("8. Ergebnisse speichern und wieder öffnen"):
    st.markdown(
        """
Ein abgeschlossener Live-Run kann über **"Simulationsrun speichern"** im Ordner `runs` abgelegt werden.

Gespeichert werden dabei:
- Passenger-Details
- Flugübersicht
- Gruppenübersicht
- Kapazitätstabellen für T1 und T2
- bei neueren Runs zusätzlich Queue-Zeitreihen für eine vollständigere spätere Anzeige

Über den Importmodus **"Gespeicherter Run"** können diese Ergebnisse später wieder geöffnet werden.

So lassen sich Ergebnisse z. B. vor und nach einer geänderten GKS-Zuordnung
oder mit und ohne SSS sauber nebeneinander betrachten.
"""
    )

st.header("Fachliche Logik")

with st.expander("Wie wird SPAX bestimmt?", expanded=True):
    st.markdown(
        """
`SPAX` ist die Passagierzahl, mit der der Flug in die Berechnung eingeht.
Sie wird pro Flug in dieser Reihenfolge bestimmt:

1. `APAX`, falls vorhanden und gültig
2. `EPAX`, falls vorhanden und gültig
3. Standardwert aus `typ4_defaults.py` passend zu `Typ4`
4. generischer Fallback-Wert `100`

Wenn also keine belastbare Passagierzahl in der Quelle enthalten ist,
arbeitet die App mit einem typbezogenen Ersatzwert.
"""
    )

with st.expander("Was macht die iterative Kapazitätsanpassung?"):
    st.markdown(
        """
Die App beginnt mit einer geringen Ausgangskapazität und prüft danach,
ob die angesetzten TCN- und EU-Schalter ausreichen.

Falls nicht:
- werden die Zeitabschnitte mit zu hoher Wartezeit erkannt
- die passenden TCN- oder EU-Kapazitäten in diesen Abschnitten erhöht
- die Berechnung erneut durchgeführt

Dieser Prozess endet, wenn:
- das Service-Level eingehalten wird oder
- die maximal erlaubten Kapazitäten bzw. Iterationen erreicht sind

Vereinfacht gesagt sucht die Anwendung also einen realistischen Schalterplan,
mit dem die gewählte Wartezeit möglichst eingehalten wird.
"""
    )

with st.expander("Wichtige Begriffe"):
    st.markdown(
        """
- **EES**: Entry/Exit System
- **TCN**: Third-Country National
- **TCN-V**: TCN-Passagiere, die im Modell dem Visum-/Visa-Prozesspfad zugeordnet werden
- **TCN-AT**: TCN-Passagiere, die im Modell dem gewählten Annex-III-Zielpfad folgen
- **SSS**: Self-Service System bzw. Kiosk vor der eigentlichen Kontrolle
- **Easypass / E-Gate**: automatisierte Grenzkontrolle
- **P95**: Wert, unter dem 95 % aller beobachteten Wartezeiten liegen
- **PPOS**: Parkposition des Flugzeugs
- **GKS**: Grenzkontrollstelle, in der App als Terminalzuordnung T1/T2 verwendet
- **BIBT**: Zeitpunkt, zu dem das Flugzeug an der Parkposition steht
"""
    )
