# app.py
from flask import Flask, render_template, request, jsonify, redirect, session, url_for, send_file
from supabase_client import supabase
from google import genai
from dotenv import load_dotenv
from pypdf import PdfReader
from docx import Document
from openpyxl import Workbook, load_workbook
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import os
import io
import jwt


load_dotenv()  # loads .env file FIRST before anything else

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-dev-secret")
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB upload cap

# Supabase & Gemini config
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
REDIRECT_URL = os.getenv("REDIRECT_URL")

if not GOOGLE_API_KEY:
    raise ValueError("Missing GOOGLE_API_KEY in environment variables.")

# New google-genai SDK client
client = genai.Client(api_key=GOOGLE_API_KEY)
GEMINI_MODEL = "gemini-3.7-flash"

GENERATION_LIMIT = 3
MAX_PROMPT_CHARS = 18000
ALLOWED_DOC_EXTENSIONS = {"pdf", "docx", "xlsx", "txt"}


# ─── Auth ────────────────────────────────────────────────────────────────────
@app.route("/auth/callback")
def auth_callback():
    access_token = request.args.get("access_token")
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

        session["email"] = email
        session["name"] = name
        return jsonify({"success": True})
    except Exception as e:
        print("Auth callback error:", str(e))
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/login")
def login():
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


# ─── Account / usage info ───────────────────────────────────────────────────
@app.route("/api/me")
def api_me():
    email = session.get("email")
    if not email:
        return jsonify({"authenticated": False}), 401

    user_result = supabase.table("users").select("*").eq("email", email).maybe_single().execute()
    user = user_result.data if user_result and user_result.data else {}
    generation_count = user.get("generation_count", 0)

    return jsonify({
        "authenticated": True,
        "email": email,
        "name": session.get("name") or user.get("name") or "",
        "generationCount": generation_count,
        "limit": GENERATION_LIMIT,
        "remaining": max(0, GENERATION_LIMIT - generation_count),
        "model": GEMINI_MODEL,
    })


# ─── Generation ──────────────────────────────────────────────────────────────
@app.route('/generate', methods=['POST'])
def generate():
    email = session.get("email")
    if not email:
        return jsonify({"response": "Not logged in", "limitExceeded": True, "remaining": 0}), 401

    user_result = supabase.table("users").select("*").eq("email", email).maybe_single().execute()
    user = user_result.data if user_result else None
    if not user:
        return jsonify({"response": "User not found", "limitExceeded": True, "remaining": 0}), 404

    generation_count = user.get("generation_count", 0)
    if generation_count >= GENERATION_LIMIT:
        return jsonify({
            "response": "Generation limit reached! You can access after admin reset.",
            "limitExceeded": True,
            "remaining": 0
        })

    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    mode = data.get("mode") or "custom"
    target_lang = (data.get("targetLang") or "English").strip()

    if not prompt:
        return jsonify({
            "response": "Prompt is empty.",
            "limitExceeded": False,
            "remaining": max(0, GENERATION_LIMIT - generation_count)
        }), 400

    prompt = prompt[:MAX_PROMPT_CHARS]
    formatted_prompt = get_prompt_template(mode, prompt, target_lang)

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=formatted_prompt
        )
        result_text = response.text or ""

        new_count = generation_count + 1
        supabase.table("users").update({
            "generation_count": new_count
        }).eq("email", email).execute()

        save_history(email, mode, prompt, result_text)

        remaining = max(0, GENERATION_LIMIT - new_count)

        return jsonify({
            "response": result_text,
            "limitExceeded": new_count >= GENERATION_LIMIT,
            "remaining": remaining
        })
    except Exception as e:
        print("Error during generation:", str(e))
        return jsonify({
            "response": "Generation error. Please try again later.",
            "limitExceeded": False,
            "remaining": max(0, GENERATION_LIMIT - generation_count)
        })


def get_prompt_template(mode, user_input, target_lang="English"):
    templates = {
        "email": f"Write a formal and concise job application email. Include only the subject line and email body. The email should be tailored to the specified role, use professional language, and exclude unnecessary symbols or filler content: {user_input}",
        "blog": f"Write a well-structured, engaging blog post with a clear title and section headings on: {user_input}",
        "code": f"Generate only the code for the following task: {user_input}. Omit all explanations and comments. Include a clear heading and the code block only.",
        "summary": f"Summarize the following text clearly and concisely. Lead with a one-sentence overview, then list the key points as short bullet lines:\n\n{user_input}",
        "translate": f"Translate the following text into {target_lang}. Preserve the original tone and meaning. Output only the translated text, with no notes or explanations:\n\n{user_input}",
        "custom": user_input
    }
    return templates.get(mode, user_input)


# ─── History ─────────────────────────────────────────────────────────────────
def save_history(email, mode, prompt, response_text):
    try:
        supabase.table("history").insert({
            "email": email,
            "mode": mode,
            "prompt": prompt[:2000],
            "response": response_text[:20000],
        }).execute()
    except Exception as e:
        print("History save skipped:", str(e))


@app.route("/api/history")
def api_history_list():
    email = session.get("email")
    if not email:
        return jsonify({"items": []}), 401

    try:
        res = supabase.table("history").select("*").eq("email", email).order("created_at", desc=True).limit(100).execute()
        items = res.data or []
    except Exception as e:
        print("History fetch failed:", str(e))
        items = []

    return jsonify({"items": items})


@app.route("/api/history/<item_id>", methods=["DELETE"])
def api_history_delete(item_id):
    email = session.get("email")
    if not email:
        return jsonify({"success": False}), 401

    try:
        supabase.table("history").delete().eq("id", item_id).eq("email", email).execute()
        return jsonify({"success": True})
    except Exception as e:
        print("History delete failed:", str(e))
        return jsonify({"success": False, "message": str(e)}), 500


# ─── Document text extraction ─────────────────────────────────────────────────
def extract_text_from_pdf(file_stream):
    reader = PdfReader(file_stream)
    parts = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def extract_text_from_docx(file_stream):
    doc = Document(file_stream)
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def extract_text_from_xlsx(file_stream):
    wb = load_workbook(file_stream, data_only=True, read_only=True)
    parts = []
    for sheet in wb.worksheets:
        parts.append(f"# Sheet: {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


@app.route("/api/documents/extract", methods=["POST"])
def api_documents_extract():
    email = session.get("email")
    if not email:
        return jsonify({"success": False, "message": "Not logged in"}), 401

    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify({"success": False, "message": "No file uploaded"}), 400

    ext = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
    if ext not in ALLOWED_DOC_EXTENSIONS:
        return jsonify({"success": False, "message": "Unsupported file type. Use PDF, DOCX, XLSX or TXT."}), 400

    try:
        stream = io.BytesIO(upload.read())
        if ext == "pdf":
            text = extract_text_from_pdf(stream)
        elif ext == "docx":
            text = extract_text_from_docx(stream)
        elif ext == "xlsx":
            text = extract_text_from_xlsx(stream)
        else:
            text = stream.read().decode("utf-8", errors="ignore")

        text = text.strip()
        if not text:
            return jsonify({"success": False, "message": "No readable text found in that file."}), 422

        truncated = len(text) > MAX_PROMPT_CHARS
        return jsonify({
            "success": True,
            "filename": upload.filename,
            "text": text[:MAX_PROMPT_CHARS],
            "truncated": truncated
        })
    except Exception as e:
        print("Document extraction failed:", str(e))
        return jsonify({"success": False, "message": "Could not read this file."}), 500


# ─── Export ──────────────────────────────────────────────────────────────────
def build_pdf_bytes(content, title):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    pdf.set_font("Helvetica", size=11)
    for line in content.split("\n"):
        safe_line = line.encode("latin-1", "replace").decode("latin-1")
        pdf.multi_cell(0, 7, safe_line if safe_line else " ", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(pdf.output())


def build_docx_bytes(content, title):
    doc = Document()
    doc.add_heading(title, level=1)
    for para in content.split("\n"):
        doc.add_paragraph(para)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_xlsx_bytes(content, title):
    wb = Workbook()
    ws = wb.active
    ws.title = "Key Points"
    ws.append([title])
    ws.append([])
    ws.append(["#", "Point"])
    lines = [l.strip(" -•\t") for l in content.split("\n") if l.strip()]
    for i, line in enumerate(lines, start=1):
        ws.append([i, line])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@app.route("/api/export", methods=["POST"])
def api_export():
    email = session.get("email")
    if not email:
        return jsonify({"success": False, "message": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    fmt = (data.get("format") or "txt").lower()
    title = (data.get("title") or "Smart AI Output")[:120]
    base_name = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_") or "smart-ai-output"

    if not content:
        return jsonify({"success": False, "message": "Nothing to export."}), 400

    try:
        if fmt == "pdf":
            file_bytes = build_pdf_bytes(content, title)
            mimetype = "application/pdf"
            filename = f"{base_name}.pdf"
        elif fmt == "docx":
            file_bytes = build_docx_bytes(content, title)
            mimetype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            filename = f"{base_name}.docx"
        elif fmt == "xlsx":
            file_bytes = build_xlsx_bytes(content, title)
            mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = f"{base_name}.xlsx"
        else:
            file_bytes = content.encode("utf-8")
            mimetype = "text/plain"
            filename = f"{base_name}.txt"

        return send_file(
            io.BytesIO(file_bytes),
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        print("Export failed:", str(e))
        return jsonify({"success": False, "message": "Export failed."}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8002))
    app.run(host='0.0.0.0', port=port)
