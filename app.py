from flask import Flask, request, jsonify
from cheques_bcra_v2 import consultar_cheques_bcra
from afip_a13 import consultar_cuit_afip   # <-- INTEGRACIÓN AFIP

app = Flask(__name__)

@app.route('/api/consulta', methods=['GET'])
def api_consulta():
    cuit = request.args.get('cuit')
    if not cuit:
        return jsonify({"error": "Falta el parámetro ?cuit="}), 400

    # --- CONSULTA CHEQUES BCRA ---
    data = consultar_cheques_bcra(cuit)
    if not data:
        return jsonify({
            "cuit": cuit,
            "mensaje": "CUIT sin cheques rechazados",
            "padron_afip": consultar_cuit_afip(cuit)  # <-- A13 igual se consulta
        })

    total = sum(ch.get('monto', 0) for ch in data)
    ultima_fecha = max(ch.get('fechaRechazo', '0000-00-00') for ch in data)
    causas = {}
    for ch in data:
        causas[ch['causal']] = causas.get(ch['causal'], 0) + 1

    # --- CONSULTA PADRÓN AFIP ---
    try:
        info_afip = consultar_cuit_afip(cuit)
    except Exception as e:
        info_afip = {"error": "Error consultando AFIP", "detalle": str(e)}

    # --- RESPUESTA JSON COMPLETA ---
    return jsonify({
        "cuit": cuit,
        "total": total,
        "cantidad": len(data),
        "ultima_fecha": ultima_fecha,
        "causas": causas,
        "padron_afip": info_afip  # <-- SE AGREGA AL JSON FINAL
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

