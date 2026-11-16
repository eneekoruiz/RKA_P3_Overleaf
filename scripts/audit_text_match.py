import pypdf

reader = pypdf.PdfReader('overleaf_downloaded.pdf')
full_pdf_text = "\n".join([p.extract_text() for p in reader.pages])

checks = [
    "Praktika honen helburua Rosmaster robota Gazeboko",
    "LiDAR sentsorea robotaren aurrealdearekiko",
    "Azaldu nola kalkulatzen duzun robota eta paretaren arteko angelua",
    "self.get_clock()",
    "Kp-ren zein balio tartean da portaera egokia",
    "Zein da Kp handitzeak/txikitzeak duen eragina",
    "Jaso robotaren posizioa denboran zehar eta irudikatu",
    "Aurreko ataletik datorren Kp-ren abiapuntu on bat hartuta",
    "Zein da Ki handitzeak/txikitzeak duen eragina",
    "Zein da Kd handitzeak/txikitzeak duen eragina",
    "Enuntziatuko hasierako adibideak",
    "Probatutako konfigurazioen artean, P kontrolagailuak Kp = 1,5",
    "0,307"
]

print("--- TEXT RECONCILIATION AUDIT ---")
for c in checks:
    found = c.lower() in full_pdf_text.lower()
    print(f"[{'PASS' if found else 'FAIL'}] {c[:60]}")
