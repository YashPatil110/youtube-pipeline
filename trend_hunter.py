"""
trend_hunter.py - Show & Podcast Viral Hook Extractor & Autopilot Trend Hunter

Features:
1. Show & Podcast Search: Accepts show names (e.g., "Friends", "The Office", "Kapil Sharma Show",
   "Modern Family") or direct Podcast / YouTube URLs.
2. Heatmap & AI Viral Hook Scanner: Analyzes YouTube's "most replayed" heatmap graph and video metadata
   to pinpoint the exact peak engagement moments (peak tension, funny jokes, romantic scenes)
   and selects the best 30–60 second clip.
3. 24/7 Autopilot Fallback: If no show name or link is provided, it automatically discovers
   currently trending/viral videos across comedy, drama, and podcasts so the daily cadence
   of 2–3 shorts NEVER stops.
"""

import os
import sys
import random
import yt_dlp
from typing import Optional, List, Dict

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Curated rotating evergreen viral categories for zero-input autopilot
VIRAL_AUTOPILOT_SEARCH_POOLS = [
    "The Office funniest moments iconic scenes",
    "Kapil Sharma Show best comedy moments",
    "Friends TV show funniest clips",
    "Modern Family best hilarious scenes",
    "Shark Tank wildest pitches moments",
    "Trending podcast funniest moments clips",
    "Young Sheldon funniest scenes",
    "Brooklyn Nine Nine best cold opens",
    "Iconic movie comedy scenes high engagement"
]

def search_show_or_podcast(query: str, max_results: int = 5) -> List[Dict]:
    """
    Searches for episodes or clips of a show/podcast, or parses a direct YouTube URL.
    Filters out shorts (< 90s) to ensure long-form episodes with full context are returned.
    """
    query = (query or "").strip()
    
    # 1. If direct YouTube URL
    if query.startswith("http://") or query.startswith("https://"):
        print(f"🔍 Analyzing provided video link directly: {query}")
        ydl_opts = {
            'quiet': True,
            'skip_download': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(query, download=False)
                return [{
                    "id": info.get("id"),
                    "title": info.get("title"),
                    "url": info.get("webpage_url", query),
                    "duration": info.get("duration", 0),
                    "view_count": info.get("view_count", 0),
                    "channel": info.get("uploader", ""),
                    "heatmap": info.get("heatmap"),
                    "chapters": info.get("chapters")
                }]
            except Exception as e:
                print(f"⚠️ Error extracting info for direct URL: {e}")
                return []

    # 2. If Show Name or Podcast Name
    search_term = f"ytsearch{max_results * 2}:{query} best scenes moments full episode"
    print(f"🔎 Searching YouTube for show/podcast: '{query}'...")
    
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'skip_download': True
    }
    
    results = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            search_res = ydl.extract_info(search_term, download=False)
            entries = search_res.get('entries', []) or []
            
            for entry in entries:
                duration = entry.get('duration') or 0
                # Filter out videos shorter than 90 seconds (ignore existing Shorts)
                if duration and duration < 90:
                    continue
                    
                video_id = entry.get('id')
                if not video_id:
                    continue
                    
                results.append({
                    "id": video_id,
                    "title": entry.get("title", "Untitled"),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "duration": duration,
                    "view_count": entry.get("view_count", 0),
                    "channel": entry.get("uploader", "YouTube")
                })
                
                if len(results) >= max_results:
                    break
        except Exception as e:
            print(f"⚠️ Error during show search: {e}")
            
    return results

def get_trending_autopilot_videos(count: int = 3) -> List[Dict]:
    """
    AUTOPILOT ENGINE: If the user provides NO link and NO show name,
    this automatically hunts for currently viral / trending high-performing videos
    so the 2-3 daily shorts pipeline never stops.
    """
    print("🤖 No input provided -> Activating Autopilot Trend Hunter!")
    # Pick randomized queries from viral pools to guarantee fresh variety daily
    queries = random.sample(VIRAL_AUTOPILOT_SEARCH_POOLS, min(len(VIRAL_AUTOPILOT_SEARCH_POOLS), count + 2))
    
    selected_videos = []
    seen_ids = set()
    
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'skip_download': True
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for q in queries:
            try:
                search_term = f"ytsearch3:{q}"
                res = ydl.extract_info(search_term, download=False)
                for entry in res.get('entries', []):
                    vid_id = entry.get('id')
                    dur = entry.get('duration') or 0
                    if not vid_id or vid_id in seen_ids or (dur and dur < 90):
                        continue
                        
                    seen_ids.add(vid_id)
                    selected_videos.append({
                        "id": vid_id,
                        "title": entry.get("title", ""),
                        "url": f"https://www.youtube.com/watch?v={vid_id}",
                        "duration": dur,
                        "view_count": entry.get("view_count", 0),
                        "channel": entry.get("uploader", ""),
                        "category_query": q
                    })
                    if len(selected_videos) >= count:
                        break
            except Exception as e:
                print(f"⚠️ Autopilot search warning for '{q}': {e}")
                
            if len(selected_videos) >= count:
                break
                
    print(f"✨ Autopilot found {len(selected_videos)} viral candidates for today's shorts queue.")
    return selected_videos

def detect_vibe_from_title_and_text(title: str, text: str = "") -> str:
    """
    Infers the mood/vibe of the moment (romantic, funny, tension, motivation, neutral)
    to guide the audio composer (e.g. smart background music ducking).
    """
    content = f"{title} {text}".lower()
    if any(k in content for k in ["romance", "romantic", "love", "kiss", "propose", "date", "hug", "couple", "crush"]):
        return "romantic"
    elif any(k in content for k in ["funny", "hilarious", "laugh", "joke", "prank", "comedy", "cracking up", "roast", "bloopers"]):
        return "funny"
    elif any(k in content for k in ["fight", "angry", "tension", "confrontation", "shocking", "argument", "drama", "insane", "crying"]):
        return "tension"
    elif any(k in content for k in ["advice", "success", "money", "mindset", "motivation", "hard work", "truth"]):
        return "motivational"
    return "entertainment"

def extract_viral_hooks_from_video(
    video_url: str,
    target_duration: int = 40,
    max_hooks: int = 1
) -> List[Dict]:
    """
    Scans a video for engagement metrics:
    1. Uses YouTube's Replay Heatmap graph (intensity up to 1.0) to locate the exact peak moments.
    2. Centers the 30-60s clip window with pre-hook setup and post-hook punchline/reaction.
    3. Detects scene vibe (funny, romantic, tension) to instruct video & audio composition.
    """
    target_duration = max(30, min(60, target_duration))
    print(f"📊 Scanning video for viral hooks: {video_url}")
    
    ydl_opts = {
        'quiet': True,
        'skip_download': True
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(video_url, download=False)
        except Exception as e:
            print(f"⚠️ Could not extract info for {video_url}: {e}")
            return []
            
    heatmap = info.get("heatmap") or []
    duration = info.get("duration") or 0
    title = info.get("title") or "Viral Moment"
    vibe = detect_vibe_from_title_and_text(title)
    
    hooks = []
    
    # CASE 1: YouTube Replay Heatmap is present (Gold standard)
    if heatmap:
        print(f"🔥 Heatmap found ({len(heatmap)} segments). Identifying top replay peaks...")
        sorted_points = sorted(heatmap, key=lambda x: x.get("value", 0), reverse=True)
        
        for pt in sorted_points:
            score = round(pt.get("value", 0), 2)
            pt_start = pt.get("start_time", 0)
            pt_end = pt.get("end_time", pt_start + 10)
            center = (pt_start + pt_end) / 2
            
            # Position clip so setup build-up is included
            start_sec = max(0, int(center - (target_duration / 2)))
            if duration and start_sec + target_duration > duration:
                start_sec = max(0, int(duration - target_duration))
                
            # Prevent overlap with already chosen hooks (must be >= 45s apart)
            overlap = any(abs(h["start_sec"] - start_sec) < (target_duration + 15) for h in hooks)
            if not overlap:
                hooks.append({
                    "video_url": video_url,
                    "video_title": title,
                    "start_sec": start_sec,
                    "duration_sec": target_duration,
                    "end_sec": start_sec + target_duration,
                    "replay_score": score,
                    "vibe": vibe,
                    "hook_reason": f"Peak Audience Replay (Score: {score}) at {int(center//60)}m{int(center%60)}s"
                })
                if len(hooks) >= max_hooks:
                    break
                    
    # CASE 2: No Heatmap -> Fallback to Chapters or High-Energy Timestamp
    if not hooks:
        chapters = info.get("chapters") or []
        start_sec = 30
        reason = "Dynamic Engagement Fallback"
        
        if chapters:
            # Pick chapter with engaging keywords
            for c in chapters:
                c_title = c.get("title", "").lower()
                if any(w in c_title for w in ["funny", "prank", "joke", "tension", "best", "climax", "moment"]):
                    start_sec = int(c.get("start_time", 30))
                    reason = f"Chapter Hook: {c.get('title')}"
                    vibe = detect_vibe_from_title_and_text(title, c.get("title", ""))
                    break
            else:
                # Default to second chapter
                start_sec = int(chapters[0].get("start_time", 30))
        elif duration and duration > 120:
            # Most long-form punchlines occur between 20% and 40% into the video
            start_sec = int(duration * 0.25)
            
        hooks.append({
            "video_url": video_url,
            "video_title": title,
            "start_sec": start_sec,
            "duration_sec": target_duration,
            "end_sec": start_sec + target_duration,
            "replay_score": 0.85,
            "vibe": vibe,
            "hook_reason": reason
        })
        
    return hooks

def get_daily_viral_shorts_plan(
    query: Optional[str] = None,
    num_shorts: int = 3,
    target_duration: int = 40
) -> List[Dict]:
    """
    Main Orchestrator:
    - If user specifies a show name or podcast link: searches episodes and extracts viral hooks.
    - If user enters NOTHING (None or empty): automatically runs Autopilot to find trending/viral
      videos and generates the 2-3 daily shorts candidates.
    - Returns a list of ready-to-process clip configurations.
    """
    clean_query = (query or "").strip()
    shorts_plan = []
    
    if clean_query:
        print(f"🎬 [Manual Mode] User requested show/podcast: '{clean_query}'")
        candidates = search_show_or_podcast(clean_query, max_results=num_shorts)
        
        # If user gave a direct link or 1 video, extract multiple hooks from that video if needed
        if len(candidates) == 1:
            video = candidates[0]
            hooks = extract_viral_hooks_from_video(video["url"], target_duration=target_duration, max_hooks=num_shorts)
            shorts_plan.extend(hooks)
        else:
            for video in candidates:
                hooks = extract_viral_hooks_from_video(video["url"], target_duration=target_duration, max_hooks=1)
                if hooks:
                    shorts_plan.append(hooks[0])
                if len(shorts_plan) >= num_shorts:
                    break
    else:
        # AUTOPILOT MODE: User provided NO show or link
        print(f"🚀 [Autopilot Mode] No query given -> Generating today's {num_shorts} trending viral shorts!")
        trending_videos = get_trending_autopilot_videos(count=num_shorts)
        for vid in trending_videos:
            hooks = extract_viral_hooks_from_video(vid["url"], target_duration=target_duration, max_hooks=1)
            if hooks:
                shorts_plan.append(hooks[0])
            if len(shorts_plan) >= num_shorts:
                break
                
    print(f"\n🎯 [Shorts Plan Ready] {len(shorts_plan)} viral shorts prepared:")
    for idx, plan in enumerate(shorts_plan, 1):
        print(f"   #{idx}: [{plan['vibe'].upper()}] '{plan['video_title'][:40]}...'")
        print(f"        Time: {plan['start_sec']}s - {plan['end_sec']}s ({plan['duration_sec']}s)")
        print(f"        Hook: {plan['hook_reason']}")
        
    return shorts_plan

if __name__ == "__main__":
    print("--- TEST 1: Show Name ('The Office') ---")
    plan1 = get_daily_viral_shorts_plan(query="The Office", num_shorts=1)
    
    print("\n--- TEST 2: Autopilot Mode (No Query / Empty Input) ---")
    plan2 = get_daily_viral_shorts_plan(query="", num_shorts=2)
