import requests
import urllib3
import csv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ===============================================================
# 🔍 CONSULTA CENTRALIZADA BCRA
# ===============================================================
def consultar_bcra(cuit: str) -> dict:
    """
    Consulta múltiple al BCRA:
      - Cheques rechazados
      - Situación general
      - Detalle por entidad
    """
    base = "https://api.bcra.gob.ar/CentralDeDeudores/v1.0/Deudas/"
    endpoints = {
        "cheques": f"{base}ChequesRechazados/{cuit}",
        "general": f"{base}InformacionGeneral/{cuit}",
        "entidades": f"{base}Entidades/{cuit}"
    }

    resultados = {}

    for tipo, url in endpoints.items():
        try:
            r = requests.get(url, timeout=15, verify=False)
            if r.status_code == 200:
                resultados[tipo] = r.json().get("results", {})
            elif r.status_code == 404:
                resultados[tipo] = {"sin_datos": True}
            else:
                resultados[tipo] = {"error": f"HTTP {r.status_code}"}
        except Exception as e:
            resultados[tipo] = {"error": str(e)}

    return resultados


# ===============================================================
# 🧾 PROCESAMIENTO DE CHEQUES
# ===============================================================
def procesar_cheques(data: dict) -> list:
    cheques = []
    causales = data.get("causales", [])
    for c in causales:
        causa = c.get("causal")
        for e in c.get("entidades", []):
            for d in e.get("detalle", []):
                cheques.append({
                    "nroCheque": d.get("nroCheque"),
                    "fechaRechazo": d.get("fechaRechazo"),
                    "monto": d.get("monto"),
                    "causal": causa,
                    "estadoMulta": d.get("estadoMulta"),
                    "entidad": e.get("entidadNombre")
                })
    return cheques


# ===============================================================
# 💾 EXPORTACIÓN CSV
# ===============================================================
def exportar_csv(cheques, cuit):
    if not cheques:
        return
    archivo = f"cheques_rechazados_{cuit}.csv"
    with open(archivo, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cheques[0].keys())
        writer.writeheader()
        writer.writerows(cheques)
    print(f"📁 Archivo CSV generado: {archivo}")


# ===============================================================
# 🧠 MAIN
# ===============================================================
def main():
    CUIT = "30714615951"
#    CUIT = "20310868834"
    print(f"-> Consultando datos del BCRA para CUIT: {CUIT}")

    datos = consultar_bcra(CUIT)

    # --- SITUACIÓN GENERAL ---
    general = datos.get("general", {})
    if general.get("sin_datos"):
        print("\nℹ️ No existen deudas registradas en la Central de Deudores (solo cheques rechazados).")
    elif general and "error" not in general:
        print("\n📋 Situación General:")
        print(f"  - Nombre: {general.get('denominacion', 'N/A')}")
        print(f"  - Situación: {general.get('situacion', 'N/A')}")
        print(f"  - Calificación: {general.get('calificacion', 'N/A')}")
        print(f"  - Total deuda: ${general.get('totalDeuda', 0):,.2f}")
        print(f"  - Última actualización: {general.get('ultimaActualizacion', 'N/A')}")
    else:
        print("\n⚠️ No se pudo obtener información general:", general.get("error"))

    # --- ENTIDADES ---
    entidades = datos.get("entidades", [])
    if isinstance(entidades, dict) and entidades.get("sin_datos"):
        print("\nℹ️ Sin detalle de entidades financieras activas.")
    elif isinstance(entidades, list) and entidades:
        print("\n🏦 Deudas por entidad:")
        for e in entidades:
            print(f"  - {e.get('nombreEntidad')} → ${e.get('saldoTotal', 0):,.2f} ({e.get('situacion')})")
    else:
        if entidades:
            print("\n⚠️ No se pudo obtener detalle por entidad:", entidades)
        else:
            print("\nℹ️ Sin datos de entidades financieras.")

    # --- CHEQUES RECHAZADOS ---
    # --- CHEQUES RECHAZADOS ---
    cheques_data = datos.get("cheques", {})
    cheques = procesar_cheques(cheques_data)
    if cheques:
        total = sum(c.get("monto") or 0 for c in cheques)
        fechas = [c.get("fechaRechazo") for c in cheques if c.get("fechaRechazo")]
        ultima_fecha = max(fechas) if fechas else "N/A"

        print(f"\n🚨 {len(cheques)} cheques rechazados.")
        print(f"💰 Total rechazado: ${total:,.2f}")
        print(f"📅 Último cheque rechazado: {ultima_fecha}")

        causas = {}
        for c in cheques:
            causas[c["causal"]] = causas.get(c["causal"], 0) + 1
        print(f"🔎 Detalle de causas: {causas}")

        exportar_csv(cheques, CUIT)
    else:
        print("\n✅ No se encontraron cheques rechazados.")




# ===============================================================
if __name__ == "__main__":
    main()
