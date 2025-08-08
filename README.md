
Jigyasa V2 - Google Sheets backend (Staging)

Files:
- Home.py : Streamlit app (entry)
- requirements.txt : dependencies for Streamlit Cloud
- README.md : this file

Setup:
1. Add your Google service-account JSON to Streamlit Secrets under key: gcp_service_account
2. Ensure the Google Sheet (shared earlier) is shared with the service account email as Editor.
3. Deploy this app to Streamlit Cloud and set main file path to Home.py
