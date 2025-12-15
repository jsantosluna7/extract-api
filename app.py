from dotenv import load_dotenv
import os
from flask import Flask, request, jsonify
import pdfplumber
import requests
import json
from jsonschema import validate, ValidationError

app = Flask(__name__)

load_dotenv()

API_KEY = os.getenv("API_KEY")
MODEL = os.getenv("MODEL")

@app.post("/extract-requisition")
def extract_requisition():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No se envió archivo PDF"}), 400

    texto = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            texto += (page.extract_text() or "") + "\n"

    with open("schema.json", "r", encoding="utf-8") as f:
        SCHEMA = json.load(f)

    prompt_text = f"""
Extrae los datos del PDF a JSON conforme al siguiente schema:

{json.dumps(SCHEMA, indent=2)}

Texto:
{texto}
"""

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
    response = requests.post(url, json=body)

    if response.status_code != 200:
        return jsonify({
            "error": "Gemini API error",
            "detalle": response.text
        }), response.status_code

    # Extraer texto de respuesta
    out = response.json()
    raw_text = out["candidates"][0]["content"]["parts"][0]["text"]

    # Limpiar marcadores de código si hay
    import re
    cleaned = re.sub(r"```(?:json)?\s*({.*?})\s*```", r"\1", raw_text, flags=re.DOTALL)

    # Intentar parsear a JSON
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return jsonify({
            "error": "No se pudo parsear JSON de Gemini",
            "raw_output": raw_text,
            "exception": str(e)
        }), 500

    # �️ VALIDAR contra tu schema
    try:
        validate(instance=data, schema=SCHEMA)
    except ValidationError as err:
        return jsonify({
            "error": "El JSON no cumple con el schema",
            "validation_error": err.message,
            "path": list(err.path),
            "schema_path": list(err.schema_path),
            "data": data
        }), 400

    # Si pasa validación, devolver resultado
    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True)
