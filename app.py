import os
import traceback

from dotenv import load_dotenv
from flask import Flask, request, jsonify
from main import main

app = Flask(__name__)
load_dotenv()
@app.route('/start', methods=['POST'])
def start():
    try:
        data = request.get_json()
        user_id = data.get("email")
        user_pw = data.get("password")
        code = data.get("code")
        language = data.get("language")
        problem = data.get("problemNum")
        capsolver_key = os.getenv("capsolver_key")
        print(capsolver_key)

        result, correct = main(user_id, user_pw, code, language, problem, capsolver_key)

        return jsonify({
            "message": result,
            "correct": correct
        }), 200

    except Exception as e:
        print("Exception occurred:", e)
        traceback.print_exc()
        return jsonify({"message": str(e) or "Unknown error", "correct": False}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

