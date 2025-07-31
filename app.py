# app.py
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import os

app = Flask(__name__)

# Set your Gemini API key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-2.5-pro')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    prompt = data.get("prompt", "")
    mode = data.get("mode", "custom")

    formatted_prompt = get_prompt_template(mode, prompt)
    try:
        response = model.generate_content(formatted_prompt)
        return jsonify({"response": response.text})
    except Exception as e:
        return jsonify({"response": f"Error: {str(e)}"})

def get_prompt_template(mode, user_input):
    templates = {
        "email": f"Write a formal and concise job application email. Include only the subject line and email body. The email should be tailored to the specified role, use professional language, and exclude unnecessary symbols or filler content: {user_input}",
        "blog": f"Write a blog post on: {user_input}",
        "code": f"Generate only the code for the following task: {user_input}.Omit all explanations and comments.Include a clear heading and the code block only.",
        "summary": f"Summarize the following text: {user_input}",
        "custom": user_input
    }
    return templates.get(mode, user_input)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render will override with correct port
    app.run(host="0.0.0.0", port=port)