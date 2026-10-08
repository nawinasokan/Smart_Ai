# 🤖 Smart AI Assistant

Smart AI is an intelligent assistant web app built with **Flask**, **Supabase**, and the **Gemini API**. It gives you a sidebar workspace — Chat, Documents, Summarize, Translate, Email Draft, Blog Writer, History, and Settings — all backed by Google's Gemini model, with Google sign-in and a per-user generation limit.

---

## 🌐 Features

- 💬 **Chat** — conversational assistant with a General/Code mode toggle and the ability to attach a document (PDF/DOCX/XLSX/TXT) mid-conversation.
- 📄 **Documents** — drag-and-drop file upload with automatic text extraction, then one-click summarization.
- 📝 **Summarize** — paste any text and get a clear, concise summary.
- 🌍 **Translate** — translate text into 10+ languages while preserving tone and meaning.
- ✉️ **Email Draft** — generate a polished, professional email from a role, company, and key points.
- 📰 **Blog Writer** — turn a topic into a structured blog post with a chosen tone and length.
- 🕑 **History** — every generation is saved, filterable by type, expandable, and deletable.
- ⚙️ **Settings** — profile info, live usage stats, and account management.
- 📤 **Export** — download any result as **PDF**, **DOCX**, or **XLSX** (key points), or copy it to the clipboard.
- 🔐 **Google Sign-In** — authentication via Supabase Auth.
- 🚦 **Usage Limits** — each user gets a fixed number of generations, tracked in Supabase and reset by an admin.

---

## 🚀 Tech Stack

| Layer       | Technology                              |
|-------------|------------------------------------------|
| Backend     | Python, Flask                            |
| Auth & DB   | Supabase (Google OAuth + Postgres)       |
| AI Service  | Gemini API (Google `google-genai` SDK)   |
| Frontend    | HTML, CSS, vanilla JavaScript            |
| File parsing| pypdf, python-docx, openpyxl             |
| Export      | fpdf2, python-docx, openpyxl             |

---

## 🧭 Flow of Application

1. 🔓 **Sign in** – User authenticates with Google via Supabase.
2. 🧭 **Pick a view** – Chat, Documents, Summarize, Translate, Email Draft, or Blog Writer.
3. 🧾 **Provide input** – Type a prompt, paste text, or upload a document.
4. 🤖 **Gemini API** – Flask backend formats a prompt and sends it to Gemini.
5. ✅ **Result** – The response is shown, saved to History, and can be exported or copied.

---

## 🛠️ Setup & Local Development

### 1. Clone the repository

```bash
git clone <repository-url>
cd Smart_Ai
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up Supabase

1. Create a project at [supabase.com](https://supabase.com).
2. Enable the **Google** provider under **Authentication → Providers**, and add your app's redirect URL (see step 5) to the allowed redirect URLs.
3. Create a `users` table:

   ```sql
   create table if not exists users (
     id uuid primary key default gen_random_uuid(),
     email text unique not null,
     name text,
     generation_count integer not null default 0
   );
   ```

4. Run [`supabase_schema.sql`](supabase_schema.sql) in the Supabase SQL editor — it creates the `history` table used by the Chat/History features.
5. From **Project Settings → API**, copy the **Project URL** and the **service_role key** (needed server-side to bypass RLS).

### 5. Configure environment variables

Create a `.env` file in the project root:

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-service-role-key

# Google Gemini
GOOGLE_API_KEY=your-gemini-api-key

# Flask
FLASK_SECRET_KEY=a-long-random-secret-string

# OAuth redirect — where Supabase sends the user after Google sign-in
REDIRECT_URL=http://localhost:8002/auth/callback

# Optional — port the app runs on (defaults to 8002)
PORT=8002
```

Get a `GOOGLE_API_KEY` from [Google AI Studio](https://aistudio.google.com/apikey).

### 6. Run the app

```bash
python app.py
```

The app will be available at **http://localhost:8002**.

For a production-style run (as used by the included `Procfile`):

```bash
gunicorn app:app
```

---

## 📁 Project Structure

```
Smart_Ai/
├── app.py                  # Flask app, routes, Gemini + Supabase integration
├── supabase_client.py      # Supabase client initialization
├── supabase_schema.sql     # SQL to create the "history" table
├── requirements.txt        # Python dependencies
├── Procfile                 # gunicorn start command (for deployment)
├── vercel.json              # Vercel deployment config
└── templates/
    ├── index.html           # Main app (sidebar + all feature views)
    ├── login.html            # Google sign-in page
    └── auth_callback.html    # OAuth callback / token handoff page
```
