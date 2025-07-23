import os
import re
import uuid
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from yt_dlp import YoutubeDL
import time
import unicodedata # ສຳລັບຈັດການໂຕອັກສອນ Unicode ແລະ Emoji ໃນຊື່ໄຟລ໌

# ສ້າງແອັບ Flask ຂຶ້ນມາ
app = Flask(__name__)
# ເປີດໃຊ້ CORS ເພື່ອໃຫ້ໜ້າເວັບ (frontend) ເອີ້ນໃຊ້ງານໄດ້
CORS(app)

# ໂຟນເດີສຳລັບເກັບໄຟລ໌ທີ່ດາວໂຫລດ (ສາມາດຕັ້ງຄ່າຜ່ານ Environment Variable ເທິງ Render ໄດ້)
DOWNLOAD_FOLDER = os.getenv('DOWNLOAD_FOLDER', 'downloads')
# ສ້າງໂຟນເດີດາວໂຫລດຂຶ້ນມາ ຖ້າຍັງບໍ່ມີ
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ຕັ້ງຊື່ໄຟລ໌ຄຸກກີ້ທີ່ຈະໃຊ້ພາຍໃນ Docker Container ຂອງ Render
COOKIE_FILE_NAME = 'runtime_cookies.txt'
# ກຳນົດເສັ້ນທາງເຕັມຂອງໄຟລ໌ຄຸກກີ້ ໃຫ້ຢູ່ໃນໂຟນເດີດາວໂຫລດ
COOKIE_FILE_PATH = os.path.join(DOWNLOAD_FOLDER, COOKIE_FILE_NAME)

# ຟັງຊັນສຳລັບຂຽນຄຸກກີ້ຈາກ Environment Variable ລົງໄຟລ໌
def setup_cookies():
    # ດຶງຄ່າຄຸກກີ້ທັງໝົດຈາກ Environment Variable ທີ່ຕັ້ງຊື່ໄວ້ເທິງ Render (ເຊັ່ນ: 'ALL_COOKIES')
    combined_cookies_content = os.getenv('ALL_COOKIES', '')

    if combined_cookies_content:
        try:
            # ເປີດໄຟລ໌ເພື່ອຂຽນເນື້ອຫາຄຸກກີ້ລົງໄປ (encoding='utf-8' ເພື່ອຮອງຮັບໂຕອັກສອນພິເສດ)
            with open(COOKIE_FILE_PATH, 'w', encoding='utf-8') as f:
                f.write(combined_cookies_content)
            print(f"Cookies successfully written to {COOKIE_FILE_PATH}")
        except Exception as e:
            print(f"Error writing cookies to {COOKIE_FILE_PATH}: {e}")
    else:
        print("No cookies found in ALL_COOKIES environment variable. Skipping cookie setup.")

# ເອີ້ນໃຊ້ setup_cookies ທັນທີເມື່ອແອັບພລິເຄຊັນເລີ່ມຕົ້ນ
setup_cookies()

# ຟັງຊັນກວດສອບ URL ເບື້ອງຕົ້ນ (ຮອງຮັບຫຼາຍແພລັດຟອມ)
def is_valid_url(url):
    # Regex ນີ້ຄອບຄຸມແພລັດຟອມວິດີໂອຍອດນິຍົມຫຼາຍລາຍການ
    # ລວມທັງຮູບແບບລິ້ງຂອງ TikTok ທີ່ຫຼາກຫຼາຍ (tiktok.com, vm.tiktok.com, vt.tiktok.com)
    pattern = re.compile(r'^(https?://)?(www\.)?('
                         r'youtube\.com|youtu\.be|facebook\.com|web\.facebook\.com|fb\.watch|instagram\.com|tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com|'
                         r'dailymotion\.com|vimeo\.com|twitch\.tv|twitter\.com|soundcloud\.com|bilibili\.com|nicovideo\.jp'
                         r')/.*', re.IGNORECASE)
    return bool(pattern.match(url))

# ຟັງຊັນປ່ຽນຄ່າຄຸນນະພາບເປັນ format string ຂອງ yt-dlp
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
    # ຄ່າເລີ່ມຕົ້ນຖ້າຄຸນນະພາບບໍ່ໄດ້ລະບຸ ຫຼື ບໍ່ຮູ້ຈັກ
    return 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]'

# Hook ສຳລັບສະແດງຄວາມຄືບໜ້າການດາວໂຫລດ (ສຳລັບ Log ໃນ Server)
def progress_hook(d):
    if d['status'] == 'downloading':
        print(f"Downloading: {d['_percent_str']} at {d['_speed_str']} of {d['_total_bytes_str']}")
    elif d['status'] == 'finished':
        print(f"Done downloading, now post-processing... {d.get('filename', 'unknown filename')}")

# Route ສຳລັບໜ້າຫຼັກ (ສະແດງໜ້າ index.html)
@app.route('/')
def index():
    return render_template('index.html')

# Endpoint ສຳລັບດາວໂຫລດວິດີໂອ (ເມື່ອ Frontend ສົ່ງຄຳຮ້ອງຂໍ POST ມາ)
@app.route('/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url')
    quality = data.get('quality', 'best') # ຄຸນນະພາບເລີ່ມຕົ້ນແມ່ນ 'best'

    # ກວດສອບວ່າມີ URL ບໍ່
    if not url:
        return jsonify({'success': False, 'message': 'Please provide a video URL.'}), 400

    # ກວດສອບຄວາມຖືກຕ້ອງຂອງ URL
    if not is_valid_url(url):
        return jsonify({'success': False, 'message': 'Invalid or unsupported URL.'}), 400

    # ສ້າງ UUID ຊົ່ວຄາວສຳລັບຊື່ໄຟລ໌ຊົ່ວຄາວ (ຮັບປະກັນຄວາມບໍ່ຊໍ້າກັນ ແລະ ບໍ່ມີໂຕອັກສອນພິເສດ)
    temp_uuid = str(uuid.uuid4())
    # yt-dlp ຈະບັນທຶກໄຟລ໌ລົງໃນຊື່ຊົ່ວຄາວນີ້
    temp_output_template = os.path.join(DOWNLOAD_FOLDER, f'{temp_uuid}.%(ext)s')

    # ຕັ້ງຄ່າຕົວເລືອກຕ່າງໆ ສຳລັບ yt-dlp
    ydl_opts = {
        'format': get_format_string(quality), # ຮູບແບບຄຸນນະພາບທີ່ຕ້ອງການ
        'merge_output_format': 'mp4', # ໃຫ້ແນ່ໃຈວ່າຜົນລັບສຸດທ້າຍເປັນ MP4
        'outtmpl': temp_output_template, # ໃຊ້ຊື່ໄຟລ໌ຊົ່ວຄາວ
        'noplaylist': True, # ບໍ່ດາວໂຫລດເພລລິດ
        'cookiefile': COOKIE_FILE_PATH, # ໃຊ້ໄຟລ໌ຄຸກກີ້ສຳລັບການຢືນຢັນຕົວຕົນ
        'progress_hooks': [progress_hook], # ເພີ່ມ progress hook ເພື່ອສະແດງຄວາມຄືບໜ້າ
        'retries': 7, # ເພີ່ມຈຳນວນຄັ້ງທີ່ຈະລອງໃໝ່ ຖ້າມີບັນຫາການເຊື່ອມຕໍ່ຊົ່ວຄາວ
        'quiet': True, # ປິດການສະແດງຜົນຂອງ yt-dlp ໃນ console (ຍົກເວັ້ນ Error)
        'no_warnings': True, # ປິດການສະແດງຄຳເຕືອນຂອງ yt-dlp
        # 'verbose': True, # ເປີດໃຊ້ງານສຳລັບ Debugging ເພື່ອເບິ່ງ Log ລະອຽດຂອງ yt-dlp ໃນ Render Logs
    }

    final_filename = None # ຕົວປ່ຽນສຳລັບເກັບຊື່ໄຟລ໌ສຸດທ້າຍທີ່ຜູ້ໃຊ້ສາມາດອ່ານໄດ້

    try:
        print(f"Starting download for URL: {url} with quality: {quality}")
        with YoutubeDL(ydl_opts) as ydl:
            # ດຶງຂໍ້ມູນ ແລະ ດາວໂຫລດວິດີໂອ
            info_dict = ydl.extract_info(url, download=True)

            # --- ຄົ້ນຫາໄຟລ໌ທີ່ດາວໂຫລດແທ້ຈິງ ແລະ ປ່ຽນຊື່ ---
            # yt-dlp ອາດຈະບັນທຶກໄຟລ໌ດ້ວຍນາມສະກຸນທີ່ແຕກຕ່າງກັນເລັກນ້ອຍ ຫຼື ມີໄຟລ໌ຊົ່ວຄາວ
            # ຄົ້ນຫາໄຟລ໌ທີ່ດາວໂຫລດແທ້ຈິງໂດຍໃຊ້ UUID ທີ່ເຮົາກຳນົດເປັນ prefix
            downloaded_files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(temp_uuid)]
            
            if not downloaded_files:
                raise Exception(f"No file found in {DOWNLOAD_FOLDER} starting with UUID {temp_uuid} after download attempt. yt-dlp might have failed silently.")
            
            # ສົມມຸດວ່າມີພຽງໄຟລ໌ດຽວທີ່ກົງກັບ UUID prefix
            actual_downloaded_temp_filename = downloaded_files[0]
            actual_downloaded_temp_filepath = os.path.join(DOWNLOAD_FOLDER, actual_downloaded_temp_filename)

            # ກວດສອບວ່າໄຟລ໌ຊົ່ວຄາວມີຢູ່ແທ້ບໍ່
            if not os.path.exists(actual_downloaded_temp_filepath):
                raise Exception(f"Downloaded temporary file '{actual_downloaded_temp_filename}' not found on disk at '{actual_downloaded_temp_filepath}'.")

            # ດຶງຊື່ວິດີໂອ ແລະ ທຳຄວາມສະອາດສຳລັບຊື່ໄຟລ໌ສຸດທ້າຍ
            title = info_dict.get('title', 'unknown_title')
            
            # ການ Sanitize ຊື່ໄຟລ໌ຢ່າງເຂັ້ມງວດ:
            # 1. ປ່ຽນ Unicode (ລວມທັງ Emoji) ເປັນ ASCII ແລະ ບໍ່ສົນໃຈໂຕອັກສອນທີ່ບໍ່ສາມາດປ່ຽນໄດ້
            title = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode('utf-8')
            # 2. ລົບໂຕອັກສອນທີ່ບໍ່ແມ່ນໂຕອັກສອນ, ຕົວເລກ, ຊ່ອງຫວ່າງ, ຂີດກາງ, ຈຸດ
            title = re.sub(r'[^\w\s\-\.]', '', title)
            # 3. ແທນທີ່ຊ່ອງຫວ່າງຫຼາຍຊ່ອງດ້ວຍຊ່ອງຫວ່າງດຽວ ແລະ ລົບຊ່ອງຫວ່າງທີ່ຫົວທ້າຍ
            title = re.sub(r'\s+', ' ', title).strip()
            # 4. ປ່ຽນຊ່ອງຫວ່າງເປັນ underscore ເພື່ອໃຫ້ໃຊ້ງານໄດ້ກັບຊື່ໄຟລ໌
            title = title.replace(' ', '_')

            # ດຶງ ID ວິດີໂອ (ສຳຄັນສຳລັບຊື່ໄຟລ໌ທີ່ບໍ່ຊໍ້າກັນ)
            video_id = info_dict.get('id', str(uuid.uuid4())) # ໃຊ້ UUID ຖ້າບໍ່ພົບ ID

            # ກຳນົດນາມສະກຸນໄຟລ໌ທີ່ຖືກຕ້ອງຈາກໄຟລ໌ທີ່ດາວໂຫລດແທ້ຈິງ
            final_ext = os.path.splitext(actual_downloaded_temp_filename)[1]
            if not final_ext: # ຖ້າບໍ່ພົບນາມສະກຸນໄຟລ໌ ໃຫ້ໃຊ້ .mp4 ເປັນຄ່າເລີ່ມຕົ້ນ
                final_ext = '.mp4'

            # ສ້າງຊື່ໄຟລ໌ສຸດທ້າຍທີ່ຕ້ອງການ
            final_filename = f"{title}-{video_id}{final_ext}"

            # ປ່ຽນຊື່ໄຟລ໌ຊົ່ວຄາວໃຫ້ເປັນຊື່ໄຟລ໌ສຸດທ້າຍທີ່ຕ້ອງການ
            final_filepath = os.path.join(DOWNLOAD_FOLDER, final_filename)
            os.rename(actual_downloaded_temp_filepath, final_filepath)
            print(f"Renamed '{actual_downloaded_temp_filename}' to '{final_filename}'")
            # --------------------------------------------------------------------

            return jsonify({
                'success': True,
                'message': 'Download successful!',
                'filename': final_filename,
                'download_url': f'/download-file/{final_filename}' # ສົ່ງ URL ສຳລັບດາວໂຫລດໄຟລ໌ກັບຄືນໄປ
            })

    except Exception as e:
        print(f"Error downloading video from {url}: {e}")
        # ສົ່ງຂໍ້ຄວາມ Error ທີ່ຜູ້ໃຊ້ສາມາດເຂົ້າໃຈໄດ້ງ່າຍຂຶ້ນ
        return jsonify({'success': False, 'message': f'An error occurred during download: {str(e)}'}), 500

# Endpoint ສຳລັບສົ່ງໄຟລ໌ທີ່ດາວໂຫລດສຳເລັດແລ້ວກັບຄືນໄປຫາຜູ້ໃຊ້
@app.route('/download-file/<filename>', methods=['GET'])
def download_file(filename):
    if not filename:
        return 'Invalid filename', 400

    # ກວດສອບຄວາມປອດໄພ: ປ້ອງກັນ Path Traversal (ບໍ່ໃຫ້ຜູ້ໃຊ້ເຂົ້າເຖິງໄຟລ໌ນອກໂຟນເດີທີ່ກຳນົດ)
    # ໃຫ້ແນ່ໃຈວ່າ path ຂອງໄຟລ໌ທີ່ຮ້ອງຂໍຢູ່ພາຍໃຕ້ DOWNLOAD_FOLDER ແທ້ໆ
    file_path = os.path.join(DOWNLOAD_FOLDER, filename)
    safe_download_folder_abs = os.path.abspath(DOWNLOAD_FOLDER)
    safe_file_path_abs = os.path.abspath(file_path)

    # ກວດສອບວ່າ absolute path ຂອງໄຟລ໌ທີ່ຮ້ອງຂໍເລີ່ມຕົ້ນດ້ວຍ absolute path ຂອງໂຟນເດີດາວໂຫລດບໍ່
    if not safe_file_path_abs.startswith(safe_download_folder_abs):
        return 'File access forbidden', 403 # ຫ້າມເຂົ້າເຖິງ

    if not os.path.exists(file_path):
        print(f"File not found at path: {file_path}")
        return 'File not found', 404

    # ສົ່ງໄຟລ໌ເປັນ attachment (ໝາຍເຖິງໃຫ້ Browser ດາວໂຫລດໄຟລ໌)
    response = send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)

    # (ທາງເລືອກ) ລຶບໄຟລ໌ຫຼັງຈາກສົ່ງສຳເລັດ (ຕ້ອງລະມັດລະວັງ ຖ້າຕ້ອງການໃຫ້ດາວໂຫລດຊໍ້າໄດ້)
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

# ຟັງຊັນລ້າງໄຟລ໌ເກົ່າຖິ້ມ (ຄວນຕັ້ງ cron job ຫຼື ເອີ້ນເອງເປັນໄລຍະ)
def cleanup_old_files(max_age_hours=6):
    now = time.time()
    for f in os.listdir(DOWNLOAD_FOLDER):
        fp = os.path.join(DOWNLOAD_FOLDER, f)
        if os.path.isfile(fp):
            # ລຶບໄຟລ໌ທີ່ເກົ່າກວ່າ max_age_hours (6 ຊົ່ວໂມງ)
            if now - os.path.getmtime(fp) > max_age_hours * 3600:
                try:
                    os.remove(fp)
                    print(f"Cleaned up old file: {fp}")
                except Exception as e:
                    print(f"Error cleaning up old file {fp}: {e}")
            else:
                print(f"Keeping recent file: {fp}")

# ກວດສອບວ່າແອັບຖືກຣັນໂດຍກົງ ຫຼື ໂດຍ Gunicorn (ສຳລັບ Server)
if __name__ == '__main__':
    # ສຳລັບການຣັນໃນເຄື່ອງຂອງທ່ານ ໃຫ້ຣັນ cleanup_old_files ດ້ວຍ
    cleanup_old_files() # ຣັນ cleanup ເມື່ອແອັບເລີ່ມເຮັດວຽກ
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
