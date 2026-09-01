# Portfolio Command Center — FINAL

A phone-friendly personal portfolio dashboard for 14 holdings.

## What is included
- Your verified quantities:
  MON100 2509; ADANIPORTS 72; ADANIGREEN 90; LAURUSLABS 46;
  MODIS 225; ETERNAL 254; GOLDCASE 3388; 360ONE 68;
  TRITURBINE 130; POWERINDIA 2; POLYCAB 7; GVT&D 13;
  METROPOLIS 91; WABAG 24.
- Back-calculated average costs from the latest holdings screenshots.
- ADD / HOLD / TRIM rules.
- Position-size protection.
- GOLDCASE fallback handling.
- Daily price history.
- Mobile-friendly Streamlit layout.

## One-time online setup — no CMD after this
The easiest route is Streamlit Community Cloud.

1. Create a GitHub repository named `portfolio-command-center`.
2. Upload `streamlit_app.py`, `requirements.txt`, `.streamlit/config.toml`, and `.gitignore`.
3. In Streamlit Community Cloud, create an app from that repository and choose `streamlit_app.py`.
4. In the app's Secrets settings, add:

BHARATSTOCK_API_KEY = "YOUR_KEY"

5. Deploy.

After deployment, open the app on Android in Chrome → menu → **Add to Home screen**.
From then on, use it like an app. You do NOT need to run Python or CMD.

## Important
The app is decision-support only and never places trades.
GOLDCASE is intentionally left as GOLDCASE and has its dedicated fallback.
The SQLite history is suitable for local use; cloud deployments may reset local files when the app is rebuilt. For permanent cloud history, add a hosted database later.
