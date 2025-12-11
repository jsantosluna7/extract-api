from flask import Flask, request, jsonify
import pdfplumber
import google.generativeai as genai
import json

print("Inicializando servidor...")

# Configura tu API key
genai.configure(api_key="AIzaSyCbcjSLhGVB1UmF4uqpbwlCwyghUHfGyXk")
print("Gemini configurado.")

app = Flask(__name__)
print("Flask inicializado.")

# Cargar schema desde archivo
with open("schema.json", "r", encoding="utf-8") as f:
    SCHEMA = f.read()

print("Schema cargado.")


@app.post("/extract-requisition")
def extract_requisition():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No se envió archivo PDF"}), 400

    # Extrae texto del PDF
    texto = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            texto += (page.extract_text() or "") + "\n"

    # Prompt para Gemini
    system_prompt = f"""
Eres un extractor experto de datos. Recibirás texto extraído de un PDF de requisición 
y debes convertirlo EXACTAMENTE al siguiente JSON Schema.

Debes devolver SOLO JSON válido, sin explicaciones y sin texto adicional.

Si algún dato no aparece en el PDF:
- Strings: ""
- Números: 0
- Arrays: []
- Nullables: null

El resultado DEBE cumplir estrictamente el siguiente schema:

{SCHEMA}
"""

    model = genai.GenerativeModel("gemini-1.5-pro")

    # Llamada a Gemini
    response = model.generate_content(
        system_prompt + "\n\n" + texto,
        generation_config={
            "response_mime_type": "application/json"   # ← fuerza JSON
        }
    )

    # Intentar parsear como JSON
    try:
        data = json.loads(response.text)
    except Exception as e:
        return jsonify({"error": "Gemini devolvió JSON inválido", "raw": response.text}), 500

    return jsonify(data)


# ------------ **AQUÍ ESTABA EL PROBLEMA** ------------
if __name__ == "__main__":
    print("Servidor ejecutándose en http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
