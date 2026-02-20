# app.py
from flask import Flask, render_template, request, jsonify, redirect, session, url_for
from supabase_client import supabase
from google import genai
from dotenv import load_dotenv
import os
import jwt


load_dotenv()  # loads .env file FIRST before anything else

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-dev-secret")

# Supabase & Gemini config
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
REDIRECT_URL = os.getenv("REDIRECT_URL", "http://localhost:8002/auth/callback")

if not GOOGLE_API_KEY:
    raise ValueError("Missing GOOGLE_API_KEY in environment variables.")

# New google-genai SDK client
client = genai.Client(api_key=GOOGLE_API_KEY)
GEMINI_MODEL = "gemini-2.5-flash"


@app.route("/auth/callback")
def auth_callback():
    access_token = request.args.get("access_token")
    print("Access token received:", access_token)   
    if not access_token:
        return render_template("auth_callback.html")

    try:
        payload = jwt.decode(access_token, options={"verify_signature": False})
        email = payload.get("email")
        name = payload.get("user_metadata", {}).get("full_name", "")

        if not email:
            return jsonify({"success": False, "message": "Email not found in token"}), 401

        # Sync with custom users table
        user_resp = supabase.table("users").select("*").eq("email", email).maybe_single().execute()
        user_data = user_resp.data if user_resp else None
        if not user_data:
            supabase.table("users").insert({"email": email, "name": name, "generation_count": 0}).execute()
        else:
            supabase.table("users").update({"name": name}).eq("email", email).execute()

        # ...rest of your logic...
        session["email"] = email
        session["name"] = name
        return jsonify({"success": True})
    except Exception as e:
        print("Auth callback error:", str(e))
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/login")
def login():
    print("Redirecting to login page")
    supabase_oauth_url = f"{SUPABASE_URL}/auth/v1/authorize?provider=google&redirect_to={REDIRECT_URL}"
    return render_template("login.html", supabase_oauth_url=supabase_oauth_url)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/")
def index():
    if "email" not in session:
        return redirect("/login")
    return render_template("index.html", name=session.get("name"))

@app.route('/generate', methods=['POST'])
def generate():
    # Ensure user is logged in
    email = session.get("email")
    if not email:
        return jsonify({"response": "Not logged in", "limitExceeded": True, "remaining": 0}), 401

    # Get user record
    user_result = supabase.table("users").select("*").eq("email", email).maybe_single().execute()
    user = user_result.data if user_result else None
    if not user:
        return jsonify({"response": "User not found", "limitExceeded": True, "remaining": 0}), 404

    # Check generation limit
    generation_count = user.get("generation_count", 0)
    if generation_count >= 3:
        return jsonify({
            "response": "Generation limit reached! You can access after admin reset.",
            "limitExceeded": True,
            "remaining": 0
        })

    # Get prompt and mode from request
    data = request.get_json()
    prompt = data.get("prompt", "")
    mode = data.get("mode", "custom")
    formatted_prompt = get_prompt_template(mode, prompt)

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=formatted_prompt
        )

        # Increment generation count for user
        supabase.table("users").update({
            "generation_count": generation_count + 1
        }).eq("email", email).execute()

        remaining = max(0, 3 - (generation_count + 1))

        return jsonify({
            "response": response.text,
            "limitExceeded": (generation_count + 1) >= 3,
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
    port = int(os.environ.get("PORT", 8002))
    app.run(host='0.0.0.0', port=port)