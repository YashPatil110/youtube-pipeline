import os
import json
import asyncio
import sys
from dotenv import load_dotenv
from google import genai
from telegram_approver import request_approval
from youtube_uploader import upload_short
from free_clipper import download_and_clip
from trend_hunter import get_daily_viral_shorts_plan, extract_viral_hooks_from_video


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

async def run_pipeline(source_url: str = None, start_sec: int = None, duration_sec: int = 40, show_query: str = None):
    print("=" * 60)
    print("🎬 YOUTUBE SHORTS VIRAL HOOK & AUTOMATION PIPELINE")
    print("=" * 60)

    # 1. Determine clip target using Trend Hunter if URL or timestamp is not explicitly provided
    if not source_url or start_sec is None:
        target_query = show_query or source_url
        if target_query:
            print(f"🔎 Scanning viral hooks for show/podcast: '{target_query}'...")
        else:
            print("🤖 No input provided -> Activating 24/7 Autopilot Trend Hunter!")

        plan = get_daily_viral_shorts_plan(query=target_query, num_shorts=1, target_duration=duration_sec)
        if not plan:
            print("⚠️ Could not locate a viral candidate. Please check connection.")
            return

        chosen = plan[0]
        source_url = chosen["video_url"]
        start_sec = chosen["start_sec"]
        duration_sec = chosen["duration_sec"]
        print(f"🎯 Selected Hook: {chosen['video_title']}")
        print(f"   Vibe: [{chosen['vibe'].upper()}] | Time: {start_sec}s - {chosen['end_sec']}s ({duration_sec}s)")
        print(f"   Reason: {chosen['hook_reason']}")

    # 2. Download, Center-Crop (9:16), and Extract locally (100% Free)
    print(f"\n1. Processing clip from: {source_url} (Start: {start_sec}s, Duration: {duration_sec}s)")
    clip_result = download_and_clip(
        youtube_url=source_url, 
        start_sec=start_sec, 
        duration_sec=duration_sec
    )
    
    local_clip_path = clip_result["local_video_path"]
    
    # 3. Generate Metadata & Transcript via Gemini AI
    metadata = generate_shorts_metadata(local_clip_path)
    transcript = metadata.get("transcript", "")
    print(f"   Extracted Transcript: {transcript[:120]}...")
    print(f"   Generated Title: {metadata['title']}")

    # 4. Send Preview to Telegram with Inline Approval Buttons
    decision = await request_approval(local_clip_path, metadata)

    # 5. Upload to YouTube Shorts if approved
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
    import argparse
    parser = argparse.ArgumentParser(description="YouTube Shorts Automation Pipeline with Trend Hunter")
    parser.add_argument("--url", type=str, default=None, help="Direct YouTube or podcast link")
    parser.add_argument("--show", type=str, default=None, help="Show name (e.g. 'Friends', 'The Office', 'Kapil Sharma Show')")
    parser.add_argument("--start", type=int, default=None, help="Start time in seconds (optional, auto-detected if omitted)")
    parser.add_argument("--duration", type=int, default=40, help="Clip duration in seconds (30-60s)")
    args = parser.parse_args()

    asyncio.run(run_pipeline(
        source_url=args.url,
        start_sec=args.start,
        duration_sec=args.duration,
        show_query=args.show
    ))