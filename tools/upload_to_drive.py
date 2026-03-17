"""
upload_to_drive.py
Uploads the assembled newsletter HTML to a Google Drive folder using OAuth.

Requires:
    GOOGLE_CLIENT_ID      — OAuth client ID
    GOOGLE_CLIENT_SECRET  — OAuth client secret
    GOOGLE_REFRESH_TOKEN  — OAuth refresh token (run tools/auth_google.py once to get this)
    GOOGLE_DRIVE_FOLDER_ID — ID of the target Drive folder

Usage:
    python tools/upload_to_drive.py
    python tools/upload_to_drive.py --html .tmp/newsletter_2026-03-17.html
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


def get_service():
    client_id     = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN", "").strip()

    for name, val in [("GOOGLE_CLIENT_ID", client_id),
                      ("GOOGLE_CLIENT_SECRET", client_secret),
                      ("GOOGLE_REFRESH_TOKEN", refresh_token)]:
        if not val:
            print(f"ERROR: {name} not set.", file=sys.stderr)
            sys.exit(1)

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("drive", "v3", credentials=creds)


def find_latest_html() -> Path | None:
    candidates = sorted(Path(".tmp").glob("newsletter_*.html"), reverse=True)
    return candidates[0] if candidates else None


def upload_file(service, file_path: Path, folder_id: str) -> str:
    """Upload file to Drive folder, overwriting if same name exists. Returns file URL."""
    file_name = file_path.name

    query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    existing = results.get("files", [])

    media = MediaFileUpload(str(file_path), mimetype="text/html", resumable=False)

    if existing:
        file_id = existing[0]["id"]
        service.files().update(fileId=file_id, media_body=media).execute()
        print(f"  Updated existing file: {file_name}")
    else:
        metadata = {"name": file_name, "parents": [folder_id]}
        result = service.files().create(
            body=metadata, media_body=media, fields="id"
        ).execute()
        file_id = result["id"]
        print(f"  Uploaded new file: {file_name}")

    return f"https://drive.google.com/file/d/{file_id}/view"


def main():
    parser = argparse.ArgumentParser(description="Upload newsletter HTML to Google Drive.")
    parser.add_argument("--html", default=None, help="Path to HTML file (default: latest in .tmp/)")
    args = parser.parse_args()

    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    if not folder_id:
        print("ERROR: GOOGLE_DRIVE_FOLDER_ID not set.", file=sys.stderr)
        sys.exit(1)

    html_path = Path(args.html) if args.html else find_latest_html()
    if not html_path or not html_path.exists():
        print("ERROR: No newsletter HTML found. Run assemble_html.py first.", file=sys.stderr)
        sys.exit(1)

    print(f"Uploading {html_path.name} to Google Drive...")
    service = get_service()
    url = upload_file(service, html_path, folder_id)
    print(f"  Done: {url}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
