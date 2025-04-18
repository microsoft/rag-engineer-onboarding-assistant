# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from flask import Flask, request, jsonify
from flask_cors import CORS
from RAG_Chatbot.chat import send_chat

app = Flask(__name__)
CORS(app)

@app.route('/', methods=['GET'])
def root():
    return "Hello, World!"

@app.route('/chat', methods=['POST'])
def chat():
    messages = request.json.get('messages', [])
    response = send_chat(messages)
    structured_response = {
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response['message']['content']
                }
            }
        ]
    }
    return jsonify(structured_response)

if __name__ == '__main__':
    app.run(host='localhost')
