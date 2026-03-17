"""
upload_to_drive.py
Uploads the assembled newsletter HTML to a Google Drive folder using a service account.

Requires:
    GOOGLE_SERVICE_ACCOUNT_JSON  — contents of the service account key JSON
    GOOGLE_DRIVE_FOLDER_ID       — ID of the target Drive folder

Usage:
    python tools/upload_to_drive.py
    python tools/upload_to_drive.py --html .tmp/newsletter_2026-03-17.html
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_service():
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not sa_json:
        print("ERROR: GOOGLE_SERVICE_ACCOUNT_JSON not set.", file=sys.stderr)
        sys.exit(1)

    sa_info = json.loads(sa_json)
    creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def find_latest_html() -> Path | None:
    candidates = sorted(Path(".tmp").glob("newsletter_*.html"), reverse=True)
    return candidates[0] if candidates else None


def upload_file(service, file_path: Path, folder_id: str) -> str:
    """Upload file to a Shared Drive folder, overwriting if same name exists. Returns file URL."""
    file_name = file_path.name

    # Check if a file with this name already exists in the folder (Shared Drive)
    query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
    results = service.files().list(
        q=query,
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    existing = results.get("files", [])

    media = MediaFileUpload(str(file_path), mimetype="text/html", resumable=False)

    if existing:
        file_id = existing[0]["id"]
        service.files().update(
            fileId=file_id,
            media_body=media,
            supportsAllDrives=True,
        ).execute()
        print(f"  Updated existing file: {file_name}")
    else:
        metadata = {"name": file_name, "parents": [folder_id]}
        result = service.files().create(
            body=metadata,
            media_body=media,
            fields="id",
            supportsAllDrives=True,
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
