import os
import re
import uuid
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from yt_dlp import YoutubeDL
import time
import unicodedata

# สร้างแอป Flask
app = Flask(__name__)
# เปิดใช้งาน CORS เพื่อให้ frontend เรียกใช้งานได้
CORS(app)

# โฟลเดอร์สำหรับเก็บไฟล์ดาวน์โหลด (สามารถกำหนดผ่าน Environment Variable บน Render ได้)
DOWNLOAD_FOLDER = os.getenv('DOWNLOAD_FOLDER', 'downloads')
# สร้างโฟลเดอร์ดาวน์โหลดหากยังไม่มี
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Dictionary สำหรับแมปแพลตฟอร์มกับชื่อ Environment Variable
# เพิ่มแพลตฟอร์มอื่นๆ ที่คุณต้องการใช้คุกกี้ได้ที่นี่
COOKIE_PLATFORMS = {
    'youtube': 'YOUTUBE_COOKIES',
    'tiktok': 'TIKTOK_COOKIES',
    'facebook': 'FACEBOOK_COOKIES',
     'instagram': 'INSTAGRAM_COOKIES', # ตัวอย่าง
     'twitter': 'TWITTER_COOKIES',       # ตัวอย่าง
}

# ฟังก์ชันสำหรับเขียนคุกกี้จาก Environment Variable ลงไฟล์เฉพาะแพลตฟอร์ม
def setup_cookies():
    """
    Reads platform-specific cookies from environment variables
    and writes them to separate files in the DOWNLOAD_FOLDER.
    """
    for platform, env_var in COOKIE_PLATFORMS.items():
        cookies_content = os.getenv(env_var, '')
        if cookies_content:
            # กำหนด path ของไฟล์คุกกี้สำหรับแพลตฟอร์มนั้นๆ
            cookie_file_path = os.path.join(DOWNLOAD_FOLDER, f'{platform}_cookies.txt')
            try:
                # เปิดไฟล์เพื่อเขียนเนื้อหาคุกกี้ลงไป
                with open(cookie_file_path, 'w', encoding='utf-8') as f:
                    f.write(cookies_content)
                print(f"Cookies for {platform} successfully written to {cookie_file_path}")
            except Exception as e:
                print(f"Error writing cookies for {platform} to {cookie_file_path}: {e}")
        else:
            print(f"No cookies found in {env_var} environment variable. Skipping cookie setup for {platform}.")

# เรียกใช้ setup_cookies ทันทีเมื่อแอปพลิเคชันเริ่มต้น
setup_cookies()

# ฟังก์ชันตรวจสอบ URL เบื้องต้น (รองรับแพลตฟอร์มที่หลากหลาย)
def is_valid_url(url):
    # Regex นี้ครอบคลุมแพลตฟอร์มวิดีโอยอดนิยมหลายรายการ
    pattern = re.compile(r'^(https?://)?(www\.)?('
                         r'youtube\.com|youtu\.be|facebook\.com|web\.facebook\.com|fb\.watch|instagram\.com|tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com|'
                         r'dailymotion\.com|vimeo\.com|twitch\.tv|twitter\.com|soundcloud\.com|bilibili\.com|nicovideo\.jp'
                         r')/.*', re.IGNORECASE)
    return bool(pattern.match(url))

# ฟังก์ชันสำหรับระบุแพลตฟอร์มจาก URL
def get_platform_from_url(url):
    """Determines the platform from a given URL."""
    # ใช้ URL Pattern เพื่อระบุแพลตฟอร์ม
    if re.search(r'(youtube\.com|youtu\.be)', url, re.IGNORECASE):
        return 'youtube'
    elif re.search(r'(tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com)', url, re.IGNORECASE):
        return 'tiktok'
    elif re.search(r'(facebook\.com|fb\.watch|web\.facebook\.com)', url, re.IGNORECASE):
        return 'facebook'
    # เพิ่มแพลตฟอร์มอื่นๆ ที่มีคุกกี้ได้ที่นี่
    return None

# ฟังก์ชันแปลงค่าคุณภาพเป็น format string ของ yt-dlp
def get_format_string(quality):
    if quality == 'best':
        return 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]'
    elif quality == 'high':
        return 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    elif quality == 'medium':
        return 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    elif quality == 'low':
        return 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    elif quality == '360':
        return 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    # ค่าเริ่มต้นหากคุณภาพไม่ระบุหรือไม่รู้จัก
    return 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]'

# Hook สำหรับแสดงความคืบหน้าการดาวน์โหลด (สำหรับ Log ใน Server)
def progress_hook(d):
    if d['status'] == 'downloading':
        print(f"Downloading: {d['_percent_str']} at {d['_speed_str']} of {d['_total_bytes_str']}")
    elif d['status'] == 'finished':
        print(f"Done downloading, now post-processing... {d.get('filename', 'unknown filename')}")

# Route สำหรับหน้าหลัก (แสดงหน้า index.html)
@app.route('/')
def index():
    return render_template('index.html')

# Endpoint สำหรับดาวน์โหลดวิดีโอ
@app.route('/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url')
    quality = data.get('quality', 'best') # คุณภาพเริ่มต้นเป็น 'best'

    # ตรวจสอบว่ามี URL หรือไม่
    if not url:
        return jsonify({'success': False, 'message': 'Please provide a video URL.'}), 400

    # ตรวจสอบความถูกต้องของ URL
    if not is_valid_url(url):
        return jsonify({'success': False, 'message': 'Invalid or unsupported URL.'}), 400

    # ระบุแพลตฟอร์มและ path ของไฟล์คุกกี้ที่เกี่ยวข้อง
    platform = get_platform_from_url(url)
    cookie_file_path = None
    if platform:
        path_candidate = os.path.join(DOWNLOAD_FOLDER, f'{platform}_cookies.txt')
        if os.path.exists(path_candidate):
            cookie_file_path = path_candidate

    # สร้าง UUID ชั่วคราวสำหรับชื่อไฟล์ชั่วคราว (รับประกันความไม่ซ้ำและไม่มีอักขระพิเศษ)
    temp_uuid = str(uuid.uuid4())
    temp_output_template = os.path.join(DOWNLOAD_FOLDER, f'{temp_uuid}.%(ext)s')

    ydl_opts = {
        'format': get_format_string(quality),
        'merge_output_format': 'mp4', # ตรวจสอบให้แน่ใจว่าผลลัพธ์สุดท้ายเป็น MP4
        'outtmpl': temp_output_template, # ใช้ชื่อไฟล์ชั่วคราว
        'noplaylist': True, # ไม่ดาวน์โหลดเพลย์ลิสต์
        'progress_hooks': [progress_hook], # แนบ progress hook
        'retries': 7, # เพิ่มจำนวน retry หากมีปัญหาการเชื่อมต่อชั่วคราว
        'quiet': True, # ปิดการแสดงผลของ yt-dlp ใน console (ยกเว้น Error)
        'no_warnings': True, # ปิดการแสดงคำเตือนของ yt-dlp
        # 'verbose': True, # เปิดใช้งานสำหรับ Debugging เพื่อดู Log ละเอียดของ yt-dlp ใน Render Logs
    }
    
    # ถ้ามีไฟล์คุกกี้สำหรับแพลตฟอร์มนี้ ให้เพิ่มเข้าไปใน yt_dlp options
    if cookie_file_path:
        ydl_opts['cookiefile'] = cookie_file_path
        print(f"Using cookie file: {cookie_file_path}")
    else:
        print("No specific cookie file found for this platform. Proceeding without cookies.")

    final_filename = None # ตัวแปรสำหรับเก็บชื่อไฟล์สุดท้ายที่เป็นมิตรกับผู้ใช้

    try:
        print(f"Starting download for URL: {url} with quality: {quality}")
        with YoutubeDL(ydl_opts) as ydl:
            # ดึงข้อมูลและดาวน์โหลดวิดีโอ
            info_dict = ydl.extract_info(url, download=True)

            # --- ค้นหาไฟล์ที่ดาวน์โหลดจริงและเปลี่ยนชื่อ ---
            downloaded_files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(temp_uuid)]
            
            if not downloaded_files:
                raise Exception(f"No file found in {DOWNLOAD_FOLDER} starting with UUID {temp_uuid} after download attempt. yt-dlp might have failed silently.")
            
            actual_downloaded_temp_filename = downloaded_files[0]
            actual_downloaded_temp_filepath = os.path.join(DOWNLOAD_FOLDER, actual_downloaded_temp_filename)

            if not os.path.exists(actual_downloaded_temp_filepath):
                raise Exception(f"Downloaded temporary file '{actual_downloaded_temp_filename}' not found on disk at '{actual_downloaded_temp_filepath}'.")

            title = info_dict.get('title', 'unknown_title')
            
            # การ Sanitize ชื่อไฟล์อย่างเข้มงวด
            title = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode('utf-8')
            title = re.sub(r'[^\w\s\-\.]', '', title)
            title = re.sub(r'\s+', ' ', title).strip()
            title = title.replace(' ', '_')

            video_id = info_dict.get('id', str(uuid.uuid4()))

            final_ext = os.path.splitext(actual_downloaded_temp_filename)[1]
            if not final_ext:
                final_ext = '.mp4'

            final_filename = f"{title}-{video_id}{final_ext}"

            final_filepath = os.path.join(DOWNLOAD_FOLDER, final_filename)
            os.rename(actual_downloaded_temp_filepath, final_filepath)
            print(f"Renamed '{actual_downloaded_temp_filename}' to '{final_filename}'")
            
            return jsonify({
                'success': True,
                'message': 'Download successful!',
                'filename': final_filename,
                'download_url': f'/download-file/{final_filename}'
            })

    except Exception as e:
        print(f"Error downloading video from {url}: {e}")
        return jsonify({'success': False, 'message': f'An error occurred during download: {str(e)}'}), 500

# Endpoint สำหรับส่งไฟล์ที่ดาวน์โหลดเสร็จแล้วกลับไปยังผู้ใช้
@app.route('/download-file/<filename>', methods=['GET'])
def download_file(filename):
    if not filename:
        return 'Invalid filename', 400

    file_path = os.path.join(DOWNLOAD_FOLDER, filename)
    safe_download_folder_abs = os.path.abspath(DOWNLOAD_FOLDER)
    safe_file_path_abs = os.path.abspath(file_path)

    if not safe_file_path_abs.startswith(safe_download_folder_abs):
        return 'File access forbidden', 403

    if not os.path.exists(file_path):
        print(f"File not found at path: {file_path}")
        return 'File not found', 404

    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)

# ฟังก์ชันล้างไฟล์เก่าทิ้ง (ควรตั้ง cron job หรือเรียกเองเป็นระยะ)
def cleanup_old_files(max_age_hours=6):
    now = time.time()
    for f in os.listdir(DOWNLOAD_FOLDER):
        fp = os.path.join(DOWNLOAD_FOLDER, f)
        # ตรวจสอบว่าเป็นไฟล์และไม่ใช่มันเป็นไฟล์คุกกี้
        if os.path.isfile(fp) and not f.endswith('_cookies.txt'):
            # ลบไฟล์ที่เก่ากว่า max_age_hours
            if now - os.path.getmtime(fp) > max_age_hours * 3600:
                try:
                    os.remove(fp)
                    print(f"Cleaned up old file: {fp}")
                except Exception as e:
                    print(f"Error cleaning up old file {fp}: {e}")
            else:
                print(f"Keeping recent file: {fp}")

# ตรวจสอบว่าแอปถูกรันโดยตรงหรือโดย Gunicorn
if __name__ == '__main__':
    cleanup_old_files()
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
