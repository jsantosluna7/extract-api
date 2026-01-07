from dotenv import load_dotenv
import os
from flask import Flask, request, jsonify
import pdfplumber
import requests
import json
from jsonschema import validate, ValidationError
from openai import OpenAI

app = Flask(__name__)
load_dotenv()

# --- KEYS ---
API_KEY_GOOGLE = os.getenv("API_KEY_GOOGLE")
MODEL_GOOGLE = os.getenv("MODEL_GOOGLE")

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def call_gemini(prompt_text):
    body = {
        "contents": [
            {"parts": [{"text": prompt_text}]}
        ]
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_GOOGLE}:generateContent?key={API_KEY_GOOGLE}"
    response = requests.post(url, json=body, timeout=60)
    if response.status_code == 200:
        return response.json()
    else:
        raise RuntimeError(f"Gemini error: {response.status_code} {response.text}")

def call_chatgpt(prompt_text):
    # usa responses.create con gpt-5.2
    resp = openai_client.responses.create(
        model="gpt-5.2",
        input=prompt_text
    )
    return resp

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

    raw_text = None

    # --- 1) Intentar con Google Gemini ---
    try:
        out = call_gemini(prompt_text)
        raw_text = out["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e_gemini:
        # --- Fallback a ChatGPT si falla Gemini ---
        try:
            chat_resp = call_chatgpt(prompt_text)
            raw_text = chat_resp.output_text  # texto de gpt-5.2
        except Exception as e_openai:
            return jsonify({
                "error": "Fallo tanto Gemini como ChatGPT",
                "gemini_error": str(e_gemini),
                "openai_error": str(e_openai)
            }), 500

    import re
    cleaned = re.sub(r"```(?:json)?\s*({.*?})\s*```", r"\1", raw_text, flags=re.DOTALL)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return jsonify({
            "error": "No se pudo parsear JSON generado",
            "raw_output": raw_text,
            "exception": str(e)
        }), 500

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
    
    # Agregar campo items_count
    lines = data.get("lines", [])
    try:
        items_count = len(lines)
    except Exception:
        items_count = 0
    
    # Devolver con items_count = 0
    result = {
        **data,
        "items_count": items_count
    }

    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
