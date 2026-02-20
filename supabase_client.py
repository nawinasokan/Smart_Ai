import os
from dotenv import load_dotenv
from supabase import create_client
load_dotenv()  
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
print(f"SUPABASE_URL: {SUPABASE_URL}")
print(f"SUPABASE_KEY: {SUPABASE_KEY}")
if SUPABASE_URL is None or SUPABASE_KEY is None:
    raise ValueError("SUPABASE_URL or SUPABASE_KEY is not set")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
 