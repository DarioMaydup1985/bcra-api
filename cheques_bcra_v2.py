import requests
import urllib3
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def consultar_cheques_bcra(cuit: str):
    """
    Consulta el BCRA (Central de Deudores) para obtener los cheques rechazados.
    Muestra total, causa principal y fecha del último cheque.
    """
    url = f"https://api.bcra.gob.ar/CentralDeDeudores/v1.0/Deudas/ChequesRechazados/{cuit}"
    print(f"-> Consultando API BCRA Cheques Rechazados para CUIT: {cuit}")

    try:
        r = requests.get(url, timeout=15, verify=False)
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return None

    if r.status_code != 200:
        print(f"❌ Error HTTP {r.status_code}")
        return None

    data = r.json()
    causales = data.get("results", {}).get("causales", [])
    cheques = []

    for c in causales:
        causa = c.get("causal")
        for e in c.get("entidades", []):
            for d in e.get("detalle", []):
                cheques.append({
                    "nroCheque": d.get("nroCheque"),
                    "fechaRechazo": d.get("fechaRechazo"),
                    "monto": d.get("monto"),
                    "causal": causa,
                    "estadoMulta": d.get("estadoMulta")
                })

    if cheques:
        total = sum(ch.get('monto') or 0 for ch in cheques)
        fechas = [ch.get("fechaRechazo") for ch in cheques if ch.get("fechaRechazo")]
        ultima_fecha = max(fechas) if fechas else "N/A"

        causa_principal = causales[0]["causal"] if causales else "Desconocida"

        print(f"🚨 {len(cheques)} cheques rechazados.")
        print(f"💰 Total: ${total:,.2f}")
        print(f"📅 Último cheque rechazado: {ultima_fecha}")
        print(f"🔎 Causa principal: {causa_principal}")

        return cheques

    else:
        print("✅ El CUIT no registra cheques rechazados.")
        return []


# --- PRUEBA ---
if __name__ == "__main__":
    CUIT = "30714615951"
    cheques = consultar_cheques_bcra(CUIT)
