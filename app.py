from flask import Flask, request, jsonify
from cheques_bcra_v2 import consultar_cheques_bcra

app = Flask(__name__)

@app.route('/api/consulta', methods=['GET'])
def api_consulta():
    cuit = request.args.get('cuit')
    if not cuit:
        return jsonify({"error": "Falta el parámetro ?cuit="}), 400

    data = consultar_cheques_bcra(cuit)
    if not data:
        return jsonify({"mensaje": "CUIT sin cheques rechazados"})
    
    total = sum(ch.get('monto', 0) for ch in data)
    ultima_fecha = max(ch.get('fechaRechazo', '0000-00-00') for ch in data)
    causas = {}
    for ch in data:
        causas[ch['causal']] = causas.get(ch['causal'], 0) + 1

    return jsonify({
        "cuit": cuit,
        "total": total,
        "cantidad": len(data),
        "ultima_fecha": ultima_fecha,
        "causas": causas
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
