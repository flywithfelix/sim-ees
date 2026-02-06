"""
Standard-Passagierzahlen (EPAX) pro Flugzeugtyp (Typ4).

Dieses Modul enthält ein Dictionary, das als Fallback dient, um die
erwartete Passagieranzahl für einen Flug zu bestimmen, wenn keine
expliziten APAX- oder EPAX-Werte im Flugplan vorhanden sind.
"""

DEFAULT_EPAX_BY_TYP4 = {
    # Allgemein
    "Acft": 100,

    # Flugzeugtypen (aus typ4_seats.CSV)
    "A20N": 179,
    "A21N": 221,
    "A318": 126,
    "A319": 144,
    "A320": 174,
    "A321": 203,
    "A332": 275,
    "A333": 291,
    "A359": 300,
    "AT43": 46,
    "AT45": 48,
    "AT75": 67,
    "AT76": 72,
    "B38M": 188,
    "B39M": 170,
    "B733": 149,
    "B734": 169,
    "B737": 137,
    "B738": 185,
    "B739": 183,
    "B748": 364,
    "B752": 183,
    "B753": 272,
    "B77L": 302,
    "B77W": 366,
    "B788": 254,
    "B789": 337,
    "BCS1": 115,
    "BCS3": 140,
    "CRJ9": 87,
    "CRJX": 96,
    "DH8D": 76,
    "E145": 60,
    "E170": 74,
    "E190": 101,
    "E195": 114,
    "E290": 106,
    "E295": 131,
    "E75L": 88,
    "E75S": 80,
    "SB20": 58,
}
