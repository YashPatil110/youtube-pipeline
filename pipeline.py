import os
import json
import asyncio
import sys
from dotenv import load_dotenv
from google import genai
from telegram_approver import request_approval
from youtube_uploader import upload_short
from free_clipper import download_and_clip

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv(override=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

def generate_shorts_metadata(video_path: str) -> dict:
    print("2. Generating high-CTR metadata & transcription via Gemini...")
    uploaded_file = client.files.upload(file=video_path)
    prompt = """
    You are an expert YouTube Shorts optimizer.
    Analyze this video clip and its audio carefully:
    1. Transcribe the spoken audio words into text.
    2. Create a curiosity-driven, punchy title under 50 characters with 1 emoji.
    3. Create a 2-sentence hook description highlighting the drama, tension, or surprise.
    4. Provide 3-5 viral hashtags.

    Return ONLY a valid JSON object matching this schema:
    {
      "transcript": "Exact transcription of spoken audio",
      "title": "Punchy title under 50 characters with 1 emoji",
      "description": "2-sentence hook description",
      "tags": ["shorts", "entertainment", "challenge"]
    }
    """
    try:
        response = client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=[uploaded_file, prompt],
            config={'response_mime_type': 'application/json'}
        )
        return json.loads(response.text)
    finally:
        try:
            client.files.delete(name=uploaded_file.name)
        except Exception:
            pass

from datetime import datetime

def log_decision(source_url: str, metadata: dict, decision: str, youtube_url: str = None):
    log_file = "history_log.json"
    history = []
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
            
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_url": source_url,
        "title": metadata.get("title", ""),
        "decision": decision,
        "youtube_url": youtube_url
    }
    history.append(entry)
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        print(f"📝 Decision tracked in {log_file} -> Status: {decision.upper()}")
    except Exception as e:
        print(f"⚠️ Could not write to {log_file}: {e}")

async def main(source_url: str, start_sec: int = 15, duration_sec: int = 40):
    print("=" * 50)
    print("STARTING YOUTUBE SHORTS AUTOMATION PIPELINE")
    print("=" * 50)

    # 1. Download, Center-Crop (9:16), and Extract Transcript locally (100% Free)
    print(f"1. Processing clip from: {source_url}")
    clip_result = download_and_clip(
        youtube_url=source_url, 
        start_sec=start_sec, 
        duration_sec=duration_sec
    )
    
    local_clip_path = clip_result["local_video_path"]
    # 2. Generate Metadata & Transcript via Gemini AI
    metadata = generate_shorts_metadata(local_clip_path)
    transcript = metadata.get("transcript", "")
    print(f"   Extracted Transcript: {transcript[:120]}...")
    print(f"   Generated Title: {metadata['title']}")

    # 3. Send Preview to Telegram with Inline Approval Buttons
    decision = await request_approval(local_clip_path, metadata)

    # 4. Upload to YouTube Shorts if you tap "Approve"
    if decision == "approved":
        print("4. Upload approved by user. Initiating YouTube upload...")
        video_id = upload_short(
            file_path=local_clip_path,
            title=metadata["title"],
            description=metadata["description"],
            tags=metadata["tags"]
        )
        yt_url = f"https://youtube.com/shorts/{video_id}"
        print(f"🎉 Success! Watch it at: {yt_url}")
        log_decision(source_url, metadata, decision="approved", youtube_url=yt_url)
    else:
        print("🛑 Video rejected. Upload discarded.")
        log_decision(source_url, metadata, decision="discarded", youtube_url=None)
        
        # Clean up local video file automatically to save disk space
        if os.path.exists(local_clip_path):
            try:
                os.remove(local_clip_path)
                print(f"🧹 Cleaned up local video file: {local_clip_path} (Disk space saved)")
            except OSError as e:
                print(f"⚠️ Failed to remove {local_clip_path}: {e}")

if __name__ == "__main__":
    # Test with any long YouTube link (e.g., an entertainment show, podcast, or game highlight)
    # Set the starting timestamp in seconds (start_sec) where the action happens
    TEST_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Replace with your test link
    START_SECOND = 30
    CLIP_DURATION = 35

    asyncio.run(main(TEST_URL, start_sec=START_SECOND, duration_sec=CLIP_DURATION))