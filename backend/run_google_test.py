# backend/run_google_test.py
import json, traceback, sys, os

# Try to load .env if python-dotenv is available (so your existing .env is used)
try:
    from dotenv import load_dotenv
    load_dotenv()  # looks for .env in cwd
    print("Loaded .env (if present).")
except Exception:
    print("python-dotenv not installed or failed to load .env (optional).")

# Show which env values are visible to this process
print("GOOGLE_API_KEY set?", bool(os.getenv("GOOGLE_API_KEY")))
print("GOOGLE_CX/CSE set?", os.getenv("GOOGLE_CSE_ID") or os.getenv("GOOGLE_CX"))

# Now import your app module and call the functions
try:
    # Make sure you run this from the 'backend' folder so 'app' package is importable
    from app.services.google_search import run_google_dork, google_search_raw
except Exception as e:
    print("IMPORT ERROR: could not import app.services.google_search")
    traceback.print_exc()
    sys.exit(1)

q = "+603 6204 7788"   # change this to test another number or IC (e.g., "000807-10-0695")
print("\nCalling run_google_dork for:", q)
try:
    res = run_google_dork(q, num_results=5)
    print("run_google_dork returned:")
    print(json.dumps(res, indent=2, ensure_ascii=False))
except Exception:
    print("run_google_dork raised an exception:")
    traceback.print_exc()

print("\nCalling google_search_raw to inspect raw Google items (if any):")
try:
    items = google_search_raw(f'"{q}"', num=5)
    print("google_search_raw returned", len(items), "items")
    for i, it in enumerate(items[:5]):
        print("---- item", i, "----")
        print("title:", it.get("title"))
        print("link:", it.get("link"))
        print("snippet:", it.get("snippet"))
except Exception:
    print("google_search_raw raised an exception:")
    traceback.print_exc()
