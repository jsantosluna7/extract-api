from flask import Flask, request, jsonify
import pdfplumber
import requests
import json

app = Flask(__name__)

API_KEY = "AIzaSyCbcjSLhGVB1UmF4uqpbwlCwyghUHfGyXk"
MODEL = "gemini-2.5-flash" 

@app.post("/extract-requisition")
def extract_requisition():

    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No se envió archivo PDF"}), 400

    # Extraer texto
    texto = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            texto += (page.extract_text() or "") + "\n"

    # Cargar tu schema completo
    with open("schema.json", "r", encoding="utf-8") as f:
        SCHEMA = f.read()

    # Construir el prompt especialmente para evaluar el PDF contra el schema
    prompt_text = f"""
Extrae los campos del siguiente PDF y genera JSON válido conforme a este schema:

{SCHEMA}

Texto extraído:
{texto}
"""

    # Construir la petición REST correctamente según docs de Generative Language
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_text}
                ]
            }
        ]
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"
    headers = {"Content-Type": "application/json"}

    response = requests.post(url, headers=headers, json=body)

    if response.status_code != 200:
        return jsonify({
            "error": "Gemini API error",
            "detalle": response.text
        }), response.status_code

    # Obtener texto de respuesta
    try:
        out = response.json()
        # Extraer texto principal de la respuesta
        candidato = out.get("candidates", [])[0]
        texto_salida = candidato.get("content", {}).get("parts", [{}])[0].get("text", "")
        data = json.loads(texto_salida)
    except Exception as e:
        return jsonify({
            "error": "No se pudo parsear JSON de Gemini",
            "raw": response.text
        }), 500

    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True)
