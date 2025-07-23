import os
import re
import uuid
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from yt_dlp import YoutubeDL
import time
import unicodedata # สำหรับจัดการอักขระ Unicode และ Emoji ในชื่อไฟล์

# สร้างแอป Flask
app = Flask(__name__)
# เปิดใช้งาน CORS เพื่อให้ frontend เรียกใช้งานได้
CORS(app)

# โฟลเดอร์สำหรับเก็บไฟล์ดาวน์โหลด (สามารถกำหนดผ่าน Environment Variable บน Render ได้)
DOWNLOAD_FOLDER = os.getenv('DOWNLOAD_FOLDER', 'downloads')
# สร้างโฟลเดอร์ดาวน์โหลดหากยังไม่มี
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# กำหนดชื่อไฟล์คุกกี้ที่จะใช้ภายใน Docker Container ของ Render
COOKIE_FILE_NAME = 'runtime_cookies.txt'
# ตั้งค่า COOKIE_FILE_PATH ให้อยู่ใน DOWNLOAD_FOLDER
COOKIE_FILE_PATH = os.path.join(DOWNLOAD_FOLDER, COOKIE_FILE_NAME)

# ฟังก์ชันสำหรับเขียนคุกกี้จาก Environment Variable ลงไฟล์
def setup_cookies():
    # ดึงค่าคุกกี้รวมจาก Environment Variable ที่คุณจะตั้งชื่อบน Render (เช่น 'ALL_COOKIES')
    combined_cookies_content = os.getenv('ALL_COOKIES', '')

    if combined_cookies_content:
        try:
            # เปิดไฟล์เพื่อเขียนเนื้อหาคุกกี้ลงไป (encoding='utf-8' เพื่อรองรับตัวอักษรพิเศษ)
            with open(COOKIE_FILE_PATH, 'w', encoding='utf-8') as f:
                f.write(combined_cookies_content)
            print(f"Cookies successfully written to {COOKIE_FILE_PATH}")
        except Exception as e:
            print(f"Error writing cookies to {COOKIE_FILE_PATH}: {e}")
    else:
        print("No cookies found in ALL_COOKIES environment variable. Skipping cookie setup.")

# เรียกใช้ setup_cookies ทันทีเมื่อแอปพลิเคชันเริ่มต้น
setup_cookies()

# ฟังก์ชันตรวจสอบ URL เบื้องต้น (รองรับแพลตฟอร์มที่หลากหลาย)
def is_valid_url(url):
    # Regex นี้ครอบคลุมแพลตฟอร์มวิดีโอยอดนิยมหลายรายการ
    # รวมถึงรูปแบบลิงก์ของ TikTok ที่หลากหลาย (tiktok.com, vm.tiktok.com, vt.tiktok.com)
    pattern = re.compile(r'^(https?://)?(www\.)?('
                         r'youtube\.com|youtu\.be|facebook\.com|web\.facebook\.com|fb\.watch|instagram\.com|tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com|'
                         r'dailymotion\.com|vimeo\.com|twitch\.tv|twitter\.com|soundcloud\.com|bilibili\.com|nicovideo\.jp'
                         r')/.*', re.IGNORECASE)
    return bool(pattern.match(url))

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

    # สร้าง UUID ชั่วคราวสำหรับชื่อไฟล์ชั่วคราว (รับประกันความไม่ซ้ำและไม่มีอักขระพิเศษ)
    temp_uuid = str(uuid.uuid4())
    # yt-dlp จะบันทึกไฟล์ลงในชื่อชั่วคราวนี้
    temp_output_template = os.path.join(DOWNLOAD_FOLDER, f'{temp_uuid}.%(ext)s')

    ydl_opts = {
        'format': get_format_string(quality),
        'merge_output_format': 'mp4', # ตรวจสอบให้แน่ใจว่าผลลัพธ์สุดท้ายเป็น MP4
        'outtmpl': temp_output_template, # ใช้ชื่อไฟล์ชั่วคราว
        'noplaylist': True, # ไม่ดาวน์โหลดเพลย์ลิสต์
        'cookiefile': COOKIE_FILE_PATH, # ใช้ไฟล์คุกกี้สำหรับการยืนยันตัวตน
        'progress_hooks': [progress_hook], # แนบ progress hook
        'retries': 7, # เพิ่มจำนวน retry หากมีปัญหาการเชื่อมต่อชั่วคราว
        'quiet': True, # ปิดการแสดงผลของ yt-dlp ใน console (ยกเว้น Error)
        'no_warnings': True, # ปิดการแสดงคำเตือนของ yt-dlp
        # 'verbose': True, # เปิดใช้งานสำหรับ Debugging เพื่อดู Log ละเอียดของ yt-dlp ใน Render Logs
    }

    final_filename = None # ตัวแปรสำหรับเก็บชื่อไฟล์สุดท้ายที่เป็นมิตรกับผู้ใช้

    try:
        print(f"Starting download for URL: {url} with quality: {quality}")
        with YoutubeDL(ydl_opts) as ydl:
            # ดึงข้อมูลและดาวน์โหลดวิดีโอ
            info_dict = ydl.extract_info(url, download=True)

            # --- ค้นหาไฟล์ที่ดาวน์โหลดจริงและเปลี่ยนชื่อ ---
            # yt-dlp อาจบันทึกไฟล์ด้วยนามสกุลที่แตกต่างกันเล็กน้อย หรือมีไฟล์ชั่วคราว
            # ค้นหาไฟล์ที่ดาวน์โหลดจริงโดยใช้ UUID ที่เรากำหนดเป็น prefix
            downloaded_files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(temp_uuid)]
            
            if not downloaded_files:
                raise Exception(f"No file found in {DOWNLOAD_FOLDER} starting with UUID {temp_uuid} after download attempt. yt-dlp might have failed silently.")
            
            # สมมติว่ามีเพียงไฟล์เดียวที่ตรงกับ UUID prefix
            actual_downloaded_temp_filename = downloaded_files[0]
            actual_downloaded_temp_filepath = os.path.join(DOWNLOAD_FOLDER, actual_downloaded_temp_filename)

            # ตรวจสอบว่าไฟล์ชั่วคราวมีอยู่จริงหรือไม่
            if not os.path.exists(actual_downloaded_temp_filepath):
                raise Exception(f"Downloaded temporary file '{actual_downloaded_temp_filename}' not found on disk at '{actual_downloaded_temp_filepath}'.")

            # ดึงชื่อวิดีโอและทำความสะอาดสำหรับชื่อไฟล์สุดท้าย
            title = info_dict.get('title', 'unknown_title')
            
            # การ Sanitize ชื่อไฟล์อย่างเข้มงวด:
            # 1. แปลง Unicode (รวมถึง Emoji) เป็น ASCII และละทิ้งอักขระที่ไม่สามารถแปลงได้
            title = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode('utf-8')
            # 2. ลบอักขระที่ไม่ใช่ตัวอักษร, ตัวเลข, ช่องว่าง, ขีดกลาง, จุด
            title = re.sub(r'[^\w\s\-\.]', '', title)
            # 3. แทนที่ช่องว่างหลายช่องด้วยช่องว่างเดียวและลบช่องว่างที่หัวท้าย
            title = re.sub(r'\s+', ' ', title).strip()
            # 4. เปลี่ยนช่องว่างเป็น underscore เพื่อความเข้ากันได้กับชื่อไฟล์
            title = title.replace(' ', '_')

            # ดึง ID วิดีโอ (สำคัญสำหรับชื่อไฟล์ที่ไม่ซ้ำกัน)
            video_id = info_dict.get('id', str(uuid.uuid4())) # ใช้ UUID หากไม่พบ ID

            # กำหนดนามสกุลไฟล์ที่ถูกต้องจากไฟล์ที่ดาวน์โหลดจริง
            final_ext = os.path.splitext(actual_downloaded_temp_filename)[1]
            if not final_ext: # หากไม่พบนามสกุลไฟล์ ให้ใช้ .mp4 เป็นค่าเริ่มต้น
                final_ext = '.mp4'

            # สร้างชื่อไฟล์สุดท้ายที่ต้องการ
            final_filename = f"{title}-{video_id}{final_ext}"

            # เปลี่ยนชื่อไฟล์ชั่วคราวให้เป็นชื่อไฟล์สุดท้ายที่ต้องการ
            final_filepath = os.path.join(DOWNLOAD_FOLDER, final_filename)
            os.rename(actual_downloaded_temp_filepath, final_filepath)
            print(f"Renamed '{actual_downloaded_temp_filename}' to '{final_filename}'")
            # --------------------------------------------------------------------

            return jsonify({
                'success': True,
                'message': 'Download successful!',
                'filename': final_filename,
                'download_url': f'/download-file/{final_filename}' # ส่ง URL สำหรับดาวน์โหลดไฟล์กลับไป
            })

    except Exception as e:
        print(f"Error downloading video from {url}: {e}")
        # ส่งข้อความ Error ที่เป็นมิตรกับผู้ใช้มากขึ้น
        return jsonify({'success': False, 'message': f'An error occurred during download: {str(e)}'}), 500

# Endpoint สำหรับส่งไฟล์ที่ดาวน์โหลดเสร็จแล้วกลับไปยังผู้ใช้
@app.route('/download-file/<filename>', methods=['GET'])
def download_file(filename):
    if not filename:
        return 'Invalid filename', 400

    # ตรวจสอบความปลอดภัย: ป้องกัน Path Traversal
    # ตรวจสอบให้แน่ใจว่า path ของไฟล์ที่ร้องขออยู่ภายใต้ DOWNLOAD_FOLDER จริงๆ
    file_path = os.path.join(DOWNLOAD_FOLDER, filename)
    safe_download_folder_abs = os.path.abspath(DOWNLOAD_FOLDER)
    safe_file_path_abs = os.path.abspath(file_path)

    # ตรวจสอบว่า absolute path ของไฟล์ที่ร้องขอเริ่มต้นด้วย absolute path ของโฟลเดอร์ดาวน์โหลดหรือไม่
    if not safe_file_path_abs.startswith(safe_download_folder_abs):
        return 'File access forbidden', 403 # Forbidden

    if not os.path.exists(file_path):
        print(f"File not found at path: {file_path}")
        return 'File not found', 404

    # ส่งไฟล์เป็น attachment
    response = send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)

    # (Optional) ลบไฟล์หลังส่งเสร็จ (ระมัดระวังหากต้องการให้ดาวน์โหลดซ้ำได้)
    # @response.call_on_close
    # def remove_file_after_download():
    #     try:
    #         if os.path.exists(file_path):
    #             os.remove(file_path)
    #             print(f"Cleaned up file: {file_path}")
    #     except Exception as e:
    #         print(f"Error cleaning up file {file_path}: {e}")
    # return response
    return response

# ฟังก์ชันล้างไฟล์เก่าทิ้ง (ควรตั้ง cron job หรือเรียกเองเป็นระยะ)
def cleanup_old_files(max_age_hours=6):
    now = time.time()
    for f in os.listdir(DOWNLOAD_FOLDER):
        fp = os.path.join(DOWNLOAD_FOLDER, f)
        if os.path.isfile(fp):
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
    # สำหรับการรันในเครื่องของคุณ ให้รัน cleanup_old_files ด้วย
    cleanup_old_files() # รัน cleanup เมื่อแอปเริ่มทำงาน
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)