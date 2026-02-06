import streamlit as st

st.set_page_config(page_title="Hilfe - SIM EES", layout="wide")

st.title("Hilfe & Anleitung")

st.markdown("""
Willkommen zur Hilfe-Seite der EES-Simulation! Dieses Werkzeug wurde entwickelt, um die Auswirkungen des Entry/Exit Systems (EES) auf die Passagierprozesse an der Grenzkontrolle zu analysieren. Hier finden Sie eine Anleitung zur Benutzung der Anwendung und Erklärungen zu den wichtigsten Konzepten.
""")

st.header("Schritt-für-Schritt-Anleitung")

with st.expander("Schritt 1: Flugplan hochladen", expanded=True):
    st.markdown("""
    Der erste Schritt ist immer das Hochladen eines Flugplans.
    
    1.  **Datei auswählen**: Klicken Sie auf "Browse files" im Upload-Bereich auf der Startseite oder ziehen Sie Ihre Datei per Drag & Drop hinein.
    2.  **Unterstützte Formate**: Die Anwendung akzeptiert `.csv`- und `.xlsx`-Dateien. Das Trennzeichen für CSV-Dateien (Komma oder Semikolon) wird automatisch erkannt.
    3.  **Benötigte Spalten**: Damit der Flugplan korrekt verarbeitet werden kann, müssen mindestens die folgenden Spalten vorhanden sein:
        *   `BIBT`: Ankunftszeit des Fluges (z.B. `01.01.2024 06:30`)
        *   `FLN`: Flugnummer
        *   `PPOS`: Parkposition
        *   `PK`: Kennzeichen, ob der Flug grenzkontrollpflichtige Passagiere hat (muss "JA" oder ein Äquivalent sein)
        *   `EPAX`: Erwartete Passagieranzahl
        *   `Typ4`: Flugzeugtyp (ICAO-Code)
        *   `T`: Terminal-Information aus der Quelldatei
    
    Nach dem Upload wird die Datei automatisch eingelesen und die gültigen Flüge werden in der Tabelle angezeigt.
    """)

with st.expander("Schritt 2: Flüge für die Simulation auswählen"):
    st.markdown("""
    Nach dem Upload sehen Sie eine Tabelle mit allen Flügen, die für die Simulation in Frage kommen.
    
    *   **Flüge aktivieren/deaktivieren**: Standardmäßig sind alle Flüge für die Simulation ausgewählt. Sie können einzelne Flüge ausschließen, indem Sie das Häkchen in der Spalte **"Aktiv"** entfernen.
    *   **Terminalzuweisung (GKS)**: Die Spalte **"GKS"** (Grenzkontrollstelle) zeigt an, welchem Terminal (T1/T2) ein Flug zugewiesen ist.
        *   Für Flüge mit einer festen Parkposition (z.B. "01A", "05B") ist diese Zuweisung **gesperrt**.
        *   Für Flüge ohne feste Zuweisung (PPOS "unbekannt") können Sie das Terminal manuell über das Dropdown-Menü in der Tabelle ändern.
    """)

with st.expander("Schritt 3: Einstellungen in der Seitenleiste anpassen"):
    st.markdown("""
    Die linke Seitenleiste enthält alle Parameter, um die Simulation an Ihre Bedürfnisse anzupassen. Die wichtigsten Einstellungen sind:
    
    *   **Passagiermix**: Legen Sie die prozentuale Verteilung der Passagiere auf die Gruppen `Easypass`, `EU-manual`, `TCN-AT` und `TCN-V` fest. **Die Summe muss immer 100% ergeben!**
    *   **SSS (Kiosk) & Easypass**: Aktivieren/deaktivieren Sie die SSS-Kioske pro Terminal und legen Sie die Anzahl der Kioske bzw. E-Gates fest.
    *   **Service Level**: Wählen Sie das Ziel für die maximale durchschnittliche Wartezeit (z.B. `<20 min`). Dieses Ziel wird von der iterativen Kapazitätsanpassung ("Passbox") verwendet.
    *   **Passbox**: Hier stellen Sie die **maximalen** Schalterkapazitäten für die automatische Anpassung ein. Die Simulation wird nie mehr Schalter öffnen als hier angegeben.
    *   **Prozesszeiten**: Passen Sie die Parameter für die Verteilungen der Prozesszeiten an den einzelnen Stationen an (z.B. Mittelwert, Standardabweichung).
    *   **Skalierung & Sonstiges**: Hier finden Sie globale Einstellungen wie einen Skalierungsfaktor für alle Prozesszeiten oder den "Random Seed" für die Reproduzierbarkeit der Ergebnisse.
    """)

with st.expander("Schritt 4: Simulation starten und Ergebnisse analysieren"):
    st.markdown("""
    1.  **Starten**: Klicken Sie auf den großen Button **"▶️ Simulation starten"** oben in der Seitenleiste.
    2.  **Status**: Während die Simulation läuft, zeigt eine Statusbox den Fortschritt der iterativen Kapazitätsanpassung an.
    3.  **Ergebnisse**: Nach Abschluss werden die Ergebnisse im Hauptbereich der Seite angezeigt.
        *   **KPIs**: Die wichtigsten Kennzahlen wie die P95-Wartezeit (95% aller Passagiere warten kürzer als dieser Wert) und die maximale Warteschlange auf einen Blick.
        *   **Diagramme**: Interaktive Grafiken zeigen den zeitlichen Verlauf von Wartezeiten und Warteschlangenlängen, die stündliche Auslastung als Heatmap und das Passagieraufkommen.
        *   **Tabellen**: Detaillierte Tabellen listen die ermittelten Schalterkapazitäten pro Zeitintervall, eine Zusammenfassung pro Flug und pro Passagiergruppe sowie die Rohdaten jedes einzelnen simulierten Passagiers auf.
    """)

st.header("Glossar & wichtige Konzepte")

with st.expander("Was bedeuten die Abkürzungen?"):
    st.markdown("""
    *   **EES**: Entry/Exit System. Das neue europäische System zur Erfassung von Drittstaatsangehörigen.
    *   **TCN**: Third-Country National (Drittstaatsangehöriger).
        *   **TCN-V**: Visumsbefreite und -pflichtige TCNs.
        *   **TCN-AT**: TCNs gemäß Anhang III (Annex III), die visumsfrei einreisen dürfen.
    *   **SSS**: Self-Service System (Kiosk), an dem TCNs ihre Daten vor der eigentlichen Grenzkontrolle selbst erfassen können.
    *   **Easypass / E-Gate**: Automatisierte Grenzkontrollschleusen.
    *   **P95**: 95%-Perzentil. Ein statistischer Wert, der angibt, dass 95% der beobachteten Werte unterhalb dieser Schwelle liegen. (z.B. "P95 Wartezeit von 25 Minuten" bedeutet, 95% der Passagiere warteten 25 Minuten oder weniger).
    *   **PPOS**: Planned Parking Position.
    *   **GKS**: Grenzkontrollstelle (hier synonym mit Terminal 1 oder 2).
    *   **BIBT**: Best Block-In Time. Der Zeitpunkt, an dem das Flugzeug an seiner Parkposition zum Stehen kommt.
    """)

with st.expander("Was ist die iterative Kapazitätsanpassung (Passbox)?"):
    st.markdown("""
    Dies ist ein Kernfeature der Simulation. Anstatt feste Schalterzahlen vorzugeben, können Sie ein **Service-Level-Ziel** (z.B. "maximale durchschnittliche Wartezeit von 20 Minuten") definieren.
    
    Die Simulation läuft dann in mehreren Schleifen (Iterationen):
    1.  Sie startet mit einer minimalen Anzahl an Schaltern.
    2.  Nach jedem Durchlauf prüft sie, in welchen 15-Minuten-Intervallen das Service-Level-Ziel für die TCN- oder EU-Passagiergruppen verletzt wurde.
    3.  Für jedes verletzte Intervall erhöht sie die Anzahl der entsprechenden Schalter um eins (bis zum von Ihnen definierten Maximum im "Passbox"-Menü).
    4.  Sie startet die Simulation mit den neuen Kapazitäten erneut.
    
    Dieser Prozess wird wiederholt, bis entweder das Service-Level in allen Intervallen erreicht ist oder die maximale Anzahl an Iterationen bzw. die maximalen Schalterkapazitäten erreicht sind. Das Ergebnis ist ein dynamischer Schalteröffnungsplan, der auf den tatsächlichen Bedarf reagiert.
    """)

with st.expander("Wie wird die Passagieranzahl (SPAX) bestimmt?"):
    st.markdown("""
    Die finale Passagieranzahl für die Simulation (`SPAX`) wird pro Flug nach folgender Priorität ermittelt:
    1.  Wert aus der Spalte `APAX` (falls vorhanden und gültig).
    2.  Wert aus der Spalte `EPAX` (falls vorhanden und gültig).
    3.  Ein Standardwert basierend auf dem Flugzeugtyp (`Typ4`), der in der Datei `typ4_defaults.py` hinterlegt ist.
    4.  Wenn alles fehlschlägt, wird ein generischer Standardwert von 100 verwendet.
    """)