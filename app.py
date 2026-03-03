import os
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

from analyzer import analyze_code

load_dotenv()

app = Flask(__name__)
CORS(app)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "Server is running!"})


@app.route("/analyze", methods=["POST"])
def analyze():
    payload = request.get_json(silent=True) or {}

    code = payload.get("code")
    language = payload.get("language", "python")

    if not isinstance(code, str) or not code.strip():
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Invalid or missing 'code' field in request body.",
                }
            ),
            400,
        )

    try:
        result = analyze_code(code=code, language=language)
        return jsonify(result), 200
    except Exception as exc:  # pragma: no cover - defensive
        app.logger.exception("Error during code analysis: %s", exc)
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Internal server error during analysis.",
                }
            ),
            500,
        )


if __name__ == "__main__":
    app.run(debug=True)

