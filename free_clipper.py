import os
import time
import subprocess
import yt_dlp

def download_and_clip(youtube_url: str, start_sec: int, duration_sec: int = 40):
    raw_video = "downloaded_raw.mkv"
    output_short = "output_short.mp4"
    
    # 1. Clean up old artifacts
    for f in [raw_video, output_short, "temp_raw_video.mp4", "temp_raw.mp4"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass

    # 2. Try fast direct stream cropping (avoids downloading huge 500MB-1GB files)
    stream_success = False
    try:
        print(f"Extracting stream URLs for fast clipping: {youtube_url}")
        ydl_opts = {
            'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
            'quiet': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            formats = info.get('requested_formats') or [info]
            v_url = formats[0]['url']
            a_url = formats[1]['url'] if len(formats) > 1 else v_url

        print(f"Fast-cropping 9:16 vertical clip from second {start_sec} for {duration_sec}s...")
        crop_cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_sec), "-i", v_url,
            "-ss", str(start_sec), "-i", a_url,
            "-t", str(duration_sec),
            "-vf", "crop=ih*(9/16):ih,scale=1080:1920",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
            "-c:a", "aac",
            output_short
        ]
        subprocess.run(crop_cmd, check=True)
        if os.path.exists(output_short) and os.path.getsize(output_short) > 10000:
            stream_success = True
            print("⚡ Fast stream crop completed in seconds!")
    except Exception as e:
        print(f"Stream-seeking unavailable ({e}). Falling back to full download.")

    # 3. Fallback if streaming extraction failed
    if not stream_success:
        ydl_opts = {
            'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
            'merge_output_format': 'mkv',
            'outtmpl': 'downloaded_raw.%(ext)s',
            'overwrites': True,
            'quiet': False
        }

        print(f"Downloading stream from YouTube: {youtube_url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])

        time.sleep(1)
        if not os.path.exists(raw_video) and os.path.exists("downloaded_raw.mp4"):
            raw_video = "downloaded_raw.mp4"

        print(f"Cropping 9:16 vertical clip from second {start_sec} for {duration_sec}s...")
        crop_cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_sec),
            "-t", str(duration_sec),
            "-i", raw_video,
            "-vf", "crop=ih*(9/16):ih,scale=1080:1920",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
            "-c:a", "aac",
            output_short
        ]
        subprocess.run(crop_cmd, check=True)

    # Clean up large raw download if any to save disk space
    if os.path.exists(raw_video):
        try:
            os.remove(raw_video)
        except OSError:
            pass

    return {
        "local_video_path": output_short
    }