# app.py
from flask import Flask, render_template, request, jsonify
from collections import defaultdict
from supabase_client import supabase
import google.generativeai as genai
from datetime import datetime
from dotenv import load_dotenv
import os

app = Flask(__name__)

load_dotenv()  # loads .env file

# Set your Gemini API key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("Missing GOOGLE_API_KEY in environment variables.")
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
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    print(f"Received request from IP: {ip}")

    result = supabase.table("ip_usage").select("*").eq("ip", ip).execute()
    existing = result.data[0] if result.data else None
    now = datetime.now()

    if existing:
        last_access = datetime.fromisoformat(existing["last_access"])
        hours_since_last = (now - last_access).total_seconds() / 3600

        # Reset count if more than 24 hours passed
        if hours_since_last >= 24:
            existing["count"] = 0
            supabase.table("ip_usage").update({
                "count": 0,
                "last_access": now.isoformat()
            }).eq("ip", ip).execute()

        # Block if count still >= 3 after reset
        if existing["count"] >= 3:
            print(f"Limit exceeded for IP: {ip}")
            return jsonify({
                "response": "Limit exceeded! You can access after 24 hours",
                "limitExceeded": True,
                "remaining": 0
            })

    formatted_prompt = get_prompt_template(mode, prompt)

    try:
        response = model.generate_content(formatted_prompt)

        if existing:
            new_count = existing["count"] + 1
            supabase.table("ip_usage").update({
                "count": new_count,
                "last_access": now.isoformat()
            }).eq("ip", ip).execute()
        else:
            new_count = 1
            supabase.table("ip_usage").insert({
                "ip": ip,
                "count": new_count,
                "last_access": now.isoformat()
            }).execute()

        remaining = max(0, 3 - new_count)  # ✅ Recalculate after update

        return jsonify({
            "response": response.text,
            "limitExceeded": new_count >= 3,
            "remaining": remaining
        })
    except Exception as e:
        print("Error during generation:", str(e))
        return jsonify({"response": "Generation error. Please try again later.", "limitExceeded": False, "remaining": 0})

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
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)