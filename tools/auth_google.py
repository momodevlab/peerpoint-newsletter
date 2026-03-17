"""
auth_google.py
One-time script to authorize Google Drive access and print your refresh token.
Run this locally once, then store the output values as GitHub secrets.

Usage:
    python tools/auth_google.py --credentials path/to/client_secret.json
"""

import argparse
import json

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--credentials",
        required=True,
        help="Path to your OAuth client_secret JSON file from Google Cloud Console",
    )
    args = parser.parse_args()

    flow = InstalledAppFlow.from_client_secrets_file(args.credentials, scopes=SCOPES)
    creds = flow.run_local_server(port=0)

    with open(args.credentials) as f:
        client_info = json.load(f)["installed"]

    print("\n=== Add these as GitHub Secrets ===")
    print(f"GOOGLE_CLIENT_ID:     {client_info['client_id']}")
    print(f"GOOGLE_CLIENT_SECRET: {client_info['client_secret']}")
    print(f"GOOGLE_REFRESH_TOKEN: {creds.refresh_token}")
    print("===================================\n")


if __name__ == "__main__":
    main()
