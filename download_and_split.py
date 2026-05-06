import os
import sys
import subprocess
import requests
import shutil
import time
import json
from pathlib import Path
from datetime import datetime

def download_with_tikwm_pagination(keyword, max_count):
    """دانلود ویدیوهای تیک‌تاک با پشتیبانی کامل از pagination"""
    videos_dir = Path("videos")
    videos_dir.mkdir(exist_ok=True)
    
    api_url = "https://tikwm.com/api/feed/search"
    downloaded_files = []
    all_video_ids = set()
    cursor = "0"
    page = 1
    
    print(f"🌐 Searching for '{keyword}' (Target: {max_count} videos)")
    
    while len(downloaded_files) < max_count:
        params = {
            "keywords": keyword,
            "count": min(20, max_count - len(downloaded_files)),
            "cursor": cursor
        }
        
        print(f"\n📄 Fetching page {page} (cursor={cursor})...")
        
        try:
            response = requests.get(api_url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("code") == 0:
                    videos_data = data.get("data", {})
                    videos_list = videos_data.get("videos", [])
                    has_more = videos_data.get("hasMore", False)
                    next_cursor = videos_data.get("cursor", cursor)
                    
                    print(f"  Found {len(videos_list)} videos in this page")
                    print(f"  hasMore: {has_more}, next_cursor: {next_cursor}")
                    
                    if not videos_list:
                        print("  No videos found, stopping...")
                        break
                    
                    new_downloads = 0
                    for video_info in videos_list:
                        if len(downloaded_files) >= max_count:
                            break
                        
                        video_url = video_info.get("play")
                        if not video_url:
                            video_url = video_info.get("video_url", "")
                        
                        video_id = str(video_info.get("video_id", video_info.get("id", "")))
                        
                        if video_id in all_video_ids:
                            continue
                        
                        if video_url:
                            print(f"    ⬇️ Downloading video {len(downloaded_files) + 1}/{max_count}")
                            
                            author = video_info.get("author", {}).get("unique_id", "unknown")
                            output_path = videos_dir / f"{keyword}_{len(downloaded_files) + 1}_{video_id}.mp4"
                            
                            try:
                                video_response = requests.get(video_url, timeout=60, stream=True)
                                if video_response.status_code == 200:
                                    with open(output_path, 'wb') as f:
                                        for chunk in video_response.iter_content(chunk_size=8192):
                                            f.write(chunk)
                                    downloaded_files.append(output_path)
                                    all_video_ids.add(video_id)
                                    new_downloads += 1
                                    size_mb = output_path.stat().st_size / (1024 * 1024)
                                    print(f"      ✅ Downloaded: {size_mb:.2f} MB - @{author}")
                                    
                                    # ذخیره متادیتا
                                    info_path = videos_dir / f"{keyword}_{len(downloaded_files)}_{video_id}_info.json"
                                    with open(info_path, 'w', encoding='utf-8') as f:
                                        json.dump({
                                            'id': video_id,
                                            'author': author,
                                            'title': video_info.get('title', ''),
                                            'duration': video_info.get('duration', 0),
                                            'views': video_info.get('play_count', 0),
                                            'likes': video_info.get('digg_count', 0),
                                            'comments': video_info.get('comment_count', 0),
                                            'download_time': datetime.now().isoformat()
                                        }, f, ensure_ascii=False, indent=2)
                                else:
                                    print(f"      ❌ Failed: HTTP {video_response.status_code}")
                            except Exception as e:
                                print(f"      ❌ Error: {e}")
                        else:
                            print(f"    ⚠️ No URL for video {video_id}")
                    
                    if new_downloads == 0:
                        print("  No new videos downloaded, stopping pagination")
                        break
                    
                    if has_more and next_cursor and len(downloaded_files) < max_count:
                        cursor = str(next_cursor)
                        page += 1
                        time.sleep(1)
                    else:
                        print(f"\n  No more pages available (hasMore={has_more})")
                        break
                        
                else:
                    print(f"  API returned error code {data.get('code')}: {data.get('msg')}")
                    break
            else:
                print(f"  HTTP Error: {response.status_code}")
                break
                
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Network error: {e}")
            break
        except Exception as e:
            print(f"⚠️ Unexpected error: {e}")
            break
    
    print(f"\n✅ Total downloaded: {len(downloaded_files)} videos")
    return downloaded_files

def create_rar_archive(files, keyword):
    """ساخت آرشیو RAR در پوشه downloads"""
    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)
    
    if not files:
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"tiktok_{keyword}_{timestamp}"
    
    print(f"\n📦 Creating RAR archive in downloads/ folder...")
    print(f"   Archive name: {archive_name}")
    
    temp_archive_dir = Path("temp_archive")
    temp_archive_dir.mkdir(exist_ok=True)
    
    for file in files:
        dest = temp_archive_dir / file.name
        shutil.copy2(file, dest)
    
    original_dir = os.getcwd()
    os.chdir(temp_archive_dir)
    
    output_path = original_dir / downloads_dir / archive_name
    cmd = f'rar a -v95m -m5 -ep1 "{output_path}.rar" *.mp4'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    os.chdir(original_dir)
    
    if result.returncode != 0:
        print(f"❌ RAR Error: {result.stderr}")
        return None
    
    rar_files = list(downloads_dir.glob(f"{archive_name}.part*.rar")) + \
                list(downloads_dir.glob(f"{archive_name}.rar"))
    
    if rar_files:
        total_size = sum(f.stat().st_size for f in rar_files) / (1024 * 1024)
        print(f"\n✅ RAR archive created successfully!")
        print(f"   📁 {len(rar_files)} part(s)")
        print(f"   💾 Total size: {total_size:.2f} MB")
        
        info_file = downloads_dir / f"{archive_name}_info.txt"
        with open(info_file, 'w', encoding='utf-8') as f:
            f.write(f"TikTok Download Information\n")
            f.write(f"=" * 40 + "\n")
            f.write(f"Keyword: {keyword}\n")
            f.write(f"Date: {timestamp}\n")
            f.write(f"Total Videos: {len(files)}\n")
            f.write(f"Archive: {archive_name}.rar\n")
            f.write(f"Parts: {len(rar_files)}\n")
            f.write(f"Total Size: {total_size:.2f} MB\n")
            f.write(f"\nRepository URL: https://github.com/{os.environ.get('GITHUB_REPOSITORY', '')}/tree/main/downloads\n")
        
        return archive_name
    
    return None

def main():
    keyword = os.environ.get("KEYWORD", "").strip()
    count = int(os.environ.get("COUNT", 5))
    
    if not keyword:
        print("❌ Error: KEYWORD environment variable is required")
        sys.exit(1)
    
    print("=" * 70)
    print(f"🎵 TikTok Video Downloader (Full Pagination Support)")
    print(f"🔍 Keyword: {keyword}")
    print(f"📊 Count: {count} videos")
    print("=" * 70)
    
    # نصب پیش‌نیازها
    print("\n📦 Checking prerequisites...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "requests"], capture_output=True)
    
    # چک کردن وجود rar
    rar_check = subprocess.run(["which", "rar"], capture_output=True)
    if rar_check.returncode != 0:
        print("   Installing RAR...")
        subprocess.run(["sudo", "apt-get", "update", "-qq"], capture_output=True)
        subprocess.run(["sudo", "apt-get", "install", "-y", "rar"], capture_output=True)
    
    # دانلود ویدیوها
    print("\n📡 Downloading videos from TikTok API...")
    videos = download_with_tikwm_pagination(keyword, count)
    
    if not videos:
        print("\n❌ No videos downloaded!")
        print("\n💡 Suggestions:")
        print("   - Try a different keyword")
        print("   - Check if API is accessible")
        sys.exit(1)
    
    print(f"\n✅ Downloaded {len(videos)} videos to videos/ folder")
    
    # نمایش حجم و اطلاعات
    print("\n📹 Downloaded videos:")
    total_size = 0
    for video in videos:
        size_mb = video.stat().st_size / (1024 * 1024)
        total_size += size_mb
        print(f"   - {video.name}: {size_mb:.2f} MB")
    print(f"\n📊 Total videos size: {total_size:.2f} MB")
    
    # ساخت آرشیو RAR
    archive_name = create_rar_archive(videos, keyword)
    
    if not archive_name:
        print("❌ Failed to create RAR archive")
        sys.exit(1)
    
    # پاکسازی فایل‌های موقت
    print("\n🧹 Cleaning up temporary files...")
    shutil.rmtree("temp_archive", ignore_errors=True)
    
    print("\n" + "=" * 70)
    print(f"✅ SUCCESS!")
    print(f"\n📁 Files saved in repository:")
    print(f"   📂 downloads/ - RAR archive files")
    print(f"   📂 videos/ - Original video files")
    print(f"\n📦 Archive location:")
    print(f"   https://github.com/{os.environ.get('GITHUB_REPOSITORY', '')}/tree/main/downloads")
    print("=" * 70)
    
    # نمایش فایل‌های موجود
    print("\n📂 Files in downloads folder:")
    for file in Path("downloads").iterdir():
        if file.is_file():
            size_mb = file.stat().st_size / (1024 * 1024)
            print(f"   - {file.name} ({size_mb:.2f} MB)")

if __name__ == "__main__":
    main()
