import os
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
import pickle

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def get_youtube_service():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    return build("youtube", "v3", credentials=creds)

def upload_short(file_path: str, title: str, description: str, tags: list, progress_callback=None):
    youtube = get_youtube_service()
    
    # Ensuring #Shorts is appended so YouTube routes it to the Shorts shelf
    full_description = f"{description}\n\n#Shorts " + " ".join([f"#{t.strip('#')}" for t in tags])

    body = {
        "snippet": {
            "title": title[:100],
            "description": full_description,
            "tags": tags,
            "categoryId": "24"  # Entertainment
        },
        "status": {
            "privacyStatus": "public",  # or "unlisted" / "private"
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(file_path, mimetype="video/mp4", chunksize=1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"Uploading to YouTube: {pct}%")
            if progress_callback:
                progress_callback(pct)

    if progress_callback:
        progress_callback(100)

    print(f"✅ Upload Complete! Video ID: {response.get('id')}")
    return response.get("id")