import base64
import os
import datetime
import requests
from OpenSSL import crypto
import xml.etree.ElementTree as ET


# ARCHIVOS DEL CERTIFICADO
CRT_FILE = "certificado.crt"
KEY_FILE = "clave.key"

# TU CUIT (el que está habilitado)
CUIT_EMISOR = "20310868834"

# CUIT QUE VAS A CONSULTAR (podés cambiarlo)
CUIT_CONSULTA = "27333276807"

# WebService
WS = "ws_sr_padron_a13"

# URLs de AFIP
URL_LOGIN = "https://wsaa.afip.gob.ar/ws/services/LoginCms"
URL_PADRON = "https://aws.afip.gob.ar/sr-padron/webservices/personaServiceA13"

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


def generar_cms(tra_xml):
    # Guardar el TRA como archivo temporal
    with open("TRA.xml", "w", encoding="utf-8") as f:
        f.write(tra_xml)

    # Generar CMS DER con OpenSSL (requerido por AFIP)
    cmd = (
        f'openssl smime -sign -in TRA.xml '
        f'-signer {CRT_FILE} '
        f'-inkey {KEY_FILE} '
        f'-out cms.der -outform DER -nodetach'
    )

    os.system(cmd)

    # Leer CMS DER y convertir a Base64
    with open("cms.der", "rb") as f:
        cms_b64 = base64.b64encode(f.read()).decode("utf-8")

    return cms_b64



import html  # arriba, junto con los otros imports

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

    resp = requests.post(
        URL_LOGIN,
        data=soap_env.encode("utf-8"),
        headers=headers,
        verify=True
    )

    print("\nRESPUESTA COMPLETA DE LOGIN CMS:\n")
    print(resp.text)
    print("\n-------------------------------\n")

    # 1) Extraer el bloque <loginCmsReturn>...</loginCmsReturn>
    try:
        login_cms_return = resp.text.split("<loginCmsReturn>")[1].split("</loginCmsReturn>")[0]
    except IndexError:
        raise Exception("No se encontró <loginCmsReturn> en la respuesta de WSAA.")

    # 2) Des-escapar el XML interno (convierte &lt;token&gt; en <token>)
    inner_xml = html.unescape(login_cms_return)

    # 3) Extraer token y sign del XML interno
    try:
        token = inner_xml.split("<token>")[1].split("</token>")[0]
        sign  = inner_xml.split("<sign>")[1].split("</sign>")[0]
    except IndexError:
        print("\nXML interno de loginTicketResponse:\n")
        print(inner_xml)
        raise Exception("No se pudo extraer <token> o <sign> del loginTicketResponse.")

    return token, sign


def consultar_padron(token, sign):
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
            <idPersona>{CUIT_CONSULTA}</idPersona>
        </a13:getPersona>
    </soapenv:Body>
</soapenv:Envelope>"""

    headers = {"Content-Type": "text/xml; charset=utf-8"}
    resp = requests.post(URL_PADRON, data=soap.encode(), headers=headers)
    return resp.text


if __name__ == "__main__":
    print("Generando TRA...")
    tra = crear_tra()

    print("Firmando TRA (CMS DER)...")
    cms = generar_cms(tra.decode("utf-8"))

    print("Solicitando Token & Sign a AFIP...")
    token, sign = solicitar_token_sign(cms)

    print("\nConsultando Padrón A13...")
    respuesta = consultar_padron(token, sign)

    print("\n--- RESPUESTA A13 ---")
    print(respuesta)
    print("\n--- RESPUESTA A13 PARSEADA ---")

    # Limpieza del XML
    xml_clean = respuesta.replace('<?xml version="1.0" encoding="utf-8"?>', "")
    root = ET.fromstring(xml_clean)

    ns = {
        "soap": "http://schemas.xmlsoap.org/soap/envelope/",
        "a13": "http://a13.soap.ws.server.puc.sr/"
    }

    # Buscar nodo <persona>
    persona = root.find(".//persona", ns)

    if persona is None:
        print("⚠ No se encontró nodo <persona> en la respuesta A13")
    else:
        resultado = {
            "cuit": persona.findtext("idPersona"),
            "tipoPersona": persona.findtext("tipoPersona"),
            "nombre": persona.findtext("nombre"),
            "apellido": persona.findtext("apellido"),
            "numeroDocumento": persona.findtext("numeroDocumento"),
            "tipoDocumento": persona.findtext("tipoDocumento"),
            "estadoClave": persona.findtext("estadoClave"),
            "actividadPrincipal": persona.findtext("descripcionActividadPrincipal"),
            "codigoActividad": persona.findtext("idActividadPrincipal"),
            "mesCierre": persona.findtext("mesCierre"),
            "fechaNacimiento": persona.findtext("fechaNacimiento"),
        }

        # Domicilios
        domicilios = []
        for dom in persona.findall("domicilio"):
            domicilios.append({
                "direccion": dom.findtext("direccion"),
                "calle": dom.findtext("calle"),
                "numero": dom.findtext("numero"),
                "localidad": dom.findtext("localidad"),
                "codigoPostal": dom.findtext("codigoPostal"),
                "provincia": dom.findtext("descripcionProvincia"),
                "tipoDomicilio": dom.findtext("tipoDomicilio")
            })

        resultado["domicilios"] = domicilios

        import json
        print(json.dumps(resultado, indent=4, ensure_ascii=False))
