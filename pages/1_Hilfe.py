import streamlit as st

st.set_page_config(page_title="Hilfe", layout="wide")
st.title("Hilfe & Dokumentation")

st.markdown("""
### Anleitung zur Simulation

1. **Startseite (Home):** Laden Sie hier Ihren Flugplan (CSV/XLSX) hoch.
2. **Einstellungen:** Passen Sie Kapazitäten, Prozesszeiten und den Passagiermix in der Sidebar an.
3. **Start:** Klicken Sie auf "▶️ Simulation starten" in der Sidebar um die Simulation auszuführen.

Weitere Informationen folgen in Kürze.
""")

st.markdown("---")
if st.button("⬅️ Zurück zur Startseite", use_container_width=True):
    st.switch_page("Startseite.py")
