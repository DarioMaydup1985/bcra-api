import base64
import os
import datetime
import requests
import xml.etree.ElementTree as ET
import html

CRT_FILE = "certificado.crt"
KEY_FILE = "clave.key"

CUIT_EMISOR = "20310868834"
WS = "ws_sr_padron_a13"

URL_LOGIN = "https://wsaa.afip.gob.ar/ws/services/LoginCms"
URL_PADRON = "https://aws.afip.gob.ar/sr-padron/webservices/personaServiceA13"


# -----------------------------------------------------
# 1) Generar TRA
# -----------------------------------------------------
def crear_tra():
    ahora = datetime.datetime.now()
    hasta = ahora + datetime.timedelta(hours=12)

    tra = f"""
    <loginTicketRequest version="1.0">
        <header>
            <uniqueId>{int(ahora.timestamp())}</uniqueId>
            <generationTime>{(ahora - datetime.timedelta(minutes=5)).isoformat()}</generationTime>
            <expirationTime>{hasta.isoformat()}</expirationTime>
        </header>
        <service>{WS}</service>
    </loginTicketRequest>
    """

    return tra.strip().encode("utf-8")


# -----------------------------------------------------
# 2) Firmar CMS con OpenSSL del servidor
# -----------------------------------------------------
def generar_cms(tra_xml):
    with open("TRA.xml", "w", encoding="utf-8") as f:
        f.write(tra_xml)

    cmd = (
        f'openssl smime -sign -in TRA.xml '
        f'-signer {CRT_FILE} '
        f'-inkey {KEY_FILE} '
        f'-out cms.der -outform DER -nodetach'
    )

    os.system(cmd)

    with open("cms.der", "rb") as f:
        cms_b64 = base64.b64encode(f.read()).decode("utf-8")

    return cms_b64


# -----------------------------------------------------
# 3) Obtener Token y Sign de WSAA
# -----------------------------------------------------
def solicitar_token_sign(cms):
    soap_env = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:wsaa="http://wsaa.view.sua.dvadac.dvadca.afip.gov.ar/">
   <soapenv:Header/>
   <soapenv:Body>
      <wsaa:loginCms>
         <wsaa:in0>{cms}</wsaa:in0>
      </wsaa:loginCms>
   </soapenv:Body>
</soapenv:Envelope>"""

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": ""
    }

    resp = requests.post(URL_LOGIN, data=soap_env.encode(), headers=headers, verify=True)

    try:
        login_cms_return = resp.text.split("<loginCmsReturn>")[1].split("</loginCmsReturn>")[0]
    except:
        raise Exception("Error: AFIP no devolvió loginCmsReturn")

    inner = html.unescape(login_cms_return)

    try:
        token = inner.split("<token>")[1].split("</token>")[0]
        sign  = inner.split("<sign>")[1].split("</sign>")[0]
    except:
        raise Exception("Error extrayendo token/sign")

    return token, sign


# -----------------------------------------------------
# 4) Llamar al Padrón A13 con CUIT
# -----------------------------------------------------
def consultar_padron(token, sign, cuit):
    soap = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope 
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:a13="http://a13.soap.ws.server.puc.sr/">
    <soapenv:Header/>
    <soapenv:Body>
        <a13:getPersona>
            <token>{token}</token>
            <sign>{sign}</sign>
            <cuitRepresentada>{CUIT_EMISOR}</cuitRepresentada>
            <idPersona>{cuit}</idPersona>
        </a13:getPersona>
    </soapenv:Body>
</soapenv:Envelope>"""

    headers = {"Content-Type": "text/xml; charset=utf-8"}
    resp = requests.post(URL_PADRON, data=soap.encode(), headers=headers)

    return resp.text


# -----------------------------------------------------
# 5) Parsear XML A13 → JSON
# -----------------------------------------------------
def parsear_a13(xml):
    xml = xml.replace('<?xml version="1.0" encoding="utf-8"?>', "")
    root = ET.fromstring(xml)

    ns = {
        "soap": "http://schemas.xmlsoap.org/soap/envelope/",
        "a13": "http://a13.soap.ws.server.puc.sr/"
    }

    persona = root.find(".//persona", ns)
    if persona is None:
        return {"error": "Sin datos AFIP"}

    result = {
        "cuit": persona.findtext("idPersona"),
        "nombre": persona.findtext("nombre"),
        "apellido": persona.findtext("apellido"),
        "estadoClave": persona.findtext("estadoClave"),
        "actividadPrincipal": persona.findtext("descripcionActividadPrincipal"),
        "numeroDocumento": persona.findtext("numeroDocumento"),
    }

    dom = persona.find("domicilio")
    if dom is not None:
        result["domicilioFiscal"] = dom.findtext("direccion")

    return result


# -----------------------------------------------------
# 6) FUNCIÓN QUE USA TODO EL FLUJO (IMPORTANTE)
# -----------------------------------------------------
def consultar_cuit_afip(cuit):
    tra = crear_tra()
    cms = generar_cms(tra.decode("utf-8"))
    token, sign = solicitar_token_sign(cms)
    xml = consultar_padron(token, sign, cuit)
    return parsear_a13(xml)
