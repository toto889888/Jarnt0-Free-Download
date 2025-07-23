import os # ໂມດູນນີ້ຊ່ວຍຈັດການກັບລະບົບໄຟລ໌ (ເຊັ່ນ: ສ້າງໂຟນເດີ, ກວດສອບໄຟລ໌)
import re # ໂມດູນນີ້ຊ່ວຍຊອກຫາຮູບແບບຂອງຂໍ້ຄວາມ (Regex)
import uuid # ໂມດູນນີ້ຊ່ວຍສ້າງ ID ທີ່ບໍ່ຊໍ້າກັນ (Unique ID)
from flask import Flask, request, jsonify, send_from_directory, render_template # ນຳເຂົ້າສິ່ງທີ່ຈຳເປັນຈາກ Flask
from flask_cors import CORS # ນຳເຂົ້າ CORS ເພື່ອໃຫ້ໜ້າເວັບ (Frontend) ເອີ້ນໃຊ້ Backend ໄດ້
from yt_dlp import YoutubeDL # ນຳເຂົ້າ YoutubeDL, ເຄື່ອງມືຫຼັກສຳລັບດາວໂຫລດວິດີໂອ
import time # ໂມດູນນີ້ຊ່ວຍຈັດການກັບເວລາ (ເຊັ່ນ: ກວດສອບເວລາສ້າງໄຟລ໌)
import unicodedata # ໂມດູນນີ້ຊ່ວຍຈັດການກັບໂຕອັກສອນ Unicode (ເຊັ່ນ: Emoji ໃນຊື່ໄຟລ໌)

# ສ້າງແອັບ Flask ຂຶ້ນມາ (ຄືກັບການສ້າງໂປຣແກຣມ Web Server)
app = Flask(__name__)
# ເປີດໃຊ້ CORS ເພື່ອໃຫ້ Frontend ທີ່ມາຈາກໂດເມນອື່ນສາມາດຕິດຕໍ່ກັບ Backend ນີ້ໄດ້
CORS(app)

# ກຳນົດໂຟນເດີສຳລັບເກັບໄຟລ໌ທີ່ດາວໂຫລດ (ຖ້າບໍ່ມີການຕັ້ງຄ່າ Environment Variable, ມັນຈະໃຊ້ຊື່ 'downloads')
DOWNLOAD_FOLDER = os.getenv('DOWNLOAD_FOLDER', 'downloads')
# ສ້າງໂຟນເດີດາວໂຫລດຂຶ້ນມາ ຖ້າຍັງບໍ່ມີ (ok_exist=True ໝາຍເຖິງບໍ່ໃຫ້ Error ຖ້າມີຢູ່ແລ້ວ)
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Dictionary (ຄືກັບລາຍການ) ນີ້ສຳລັບບອກວ່າແພລັດຟອມໃດຄວນໃຊ້ Cookie ຈາກ Environment Variable ໂຕໃດ
# ເຮົາສາມາດເພີ່ມແພລັດຟອມອື່ນໆ ທີ່ຕ້ອງການ Cookie ໄດ້ທີ່ນີ້
COOKIE_PLATFORMS = {
    'youtube': 'YOUTUBE_COOKIES',
    'tiktok': 'TIKTOK_COOKIES',
    'facebook': 'FACEBOOK_COOKIES',
     'instagram': 'INSTAGRAM_COOKIES', # ຕົວຢ່າງ
     'twitter': 'TWITTER_COOKIES',       # ຕົວຢ່າງ
}

# ຟັງຊັນສຳລັບຂຽນ Cookie ຈາກ Environment Variable ລົງໄຟລ໌ສະເພາະແຕ່ລະແພລັດຟອມ
def setup_cookies():
    """
    ອ່ານ Cookie ສະເພາະແພລັດຟອມຈາກ Environment Variables
    ແລະຂຽນລົງໄຟລ໌ແຍກກັນໃນ DOWNLOAD_FOLDER.
    """
    for platform, env_var in COOKIE_PLATFORMS.items(): # ວົນລູບຜ່ານແຕ່ລະແພລັດຟອມທີ່ກຳນົດໄວ້
        cookies_content = os.getenv(env_var, '') # ດຶງຄ່າ Cookie ຈາກ Environment Variable
        if cookies_content: # ຖ້າມີ Cookie
            # ກຳນົດເສັ້ນທາງຂອງໄຟລ໌ Cookie ສຳລັບແພລັດຟອມນັ້ນໆ (ເຊັ່ນ: downloads/youtube_cookies.txt)
            cookie_file_path = os.path.join(DOWNLOAD_FOLDER, f'{platform}_cookies.txt')
            try:
                # ເປີດໄຟລ໌ເພື່ອຂຽນເນື້ອຫາ Cookie ລົງໄປ (encoding='utf-8' ເພື່ອຮອງຮັບໂຕອັກສອນພິເສດ)
                with open(cookie_file_path, 'w', encoding='utf-8') as f:
                    f.write(cookies_content)
                print(f"Cookies for {platform} successfully written to {cookie_file_path}") # ສະແດງຂໍ້ຄວາມໃນ Log
            except Exception as e:
                print(f"Error writing cookies for {platform} to {cookie_file_path}: {e}") # ສະແດງຂໍ້ຜິດພາດໃນ Log
        else:
            print(f"No cookies found in {env_var} environment variable. Skipping cookie setup for {platform}.") # ສະແດງຂໍ້ຄວາມຖ້າບໍ່ມີ Cookie

# ເອີ້ນໃຊ້ setup_cookies ທັນທີເມື່ອແອັບພລິເຄຊັນເລີ່ມຕົ້ນ (ເພື່ອໃຫ້ມີ Cookie ພ້ອມໃຊ້)
setup_cookies()

# ຟັງຊັນກວດສອບ URL ເບື້ອງຕົ້ນ (ຮອງຮັບຫຼາຍແພລັດຟອມ)
def is_valid_url(url):
    # Regex (ຮູບແບບການຊອກຫາຂໍ້ຄວາມ) ນີ້ຄອບຄຸມແພລັດຟອມວິດີໂອຍອດນິຍົມຫຼາຍລາຍການ
    pattern = re.compile(r'^(https?://)?(www\.)?('
                         r'youtube\.com|youtu\.be|facebook\.com|web\.facebook\.com|fb\.watch|instagram\.com|tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com|'
                         r'dailymotion\.com|vimeo\.com|twitch\.tv|twitter\.com|soundcloud\.com|bilibili\.com|nicovideo\.jp'
                         r')/.*', re.IGNORECASE) # re.IGNORECASE ໝາຍເຖິງບໍ່ສົນໃຈໂຕນ້ອຍໂຕໃຫຍ່
    return bool(pattern.match(url)) # ຖ້າກົງກັບຮູບແບບໃດໜຶ່ງ ຈະສົ່ງຄ່າ True, ຖ້າບໍ່ແມ່ນສົ່ງ False

# ຟັງຊັນສຳລັບລະບຸແພລັດຟອມຈາກ URL
def get_platform_from_url(url):
    """ລະບຸແພລັດຟອມຈາກ URL ທີ່ໃຫ້ມາ."""
    # ໃຊ້ URL Pattern ເພື່ອລະບຸແພລັດຟອມ
    if re.search(r'(youtube\.com|youtu\.be)', url, re.IGNORECASE):
        return 'youtube'
    elif re.search(r'(tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com)', url, re.IGNORECASE):
        return 'tiktok'
    elif re.search(r'(facebook\.com|fb\.watch|web\.facebook\.com)', url, re.IGNORECASE):
        return 'facebook'
    # ເພີ່ມແພລັດຟອມອື່ນໆ ທີ່ມີ Cookie ໄດ້ທີ່ນີ້
    return None # ຖ້າບໍ່ພົບແພລັດຟອມທີ່ກຳນົດ

# ຟັງຊັນປ່ຽນຄ່າຄຸນນະພາບເປັນ format string ຂອງ yt-dlp
def get_format_string(quality):
    if quality == 'best': # ຄຸນນະພາບດີທີ່ສຸດ
        return 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]' # ເລືອກວິດີໂອແລະສຽງທີ່ດີທີ່ສຸດແລ້ວລວມກັນເປັນ mp4
    elif quality == 'high': # 1080p
        return 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    elif quality == 'medium': # 720p
        return 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    elif quality == 'low': # 480p
        return 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    elif quality == '360': # 360p
        return 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    # ຄ່າເລີ່ມຕົ້ນຖ້າຄຸນນະພາບບໍ່ໄດ້ລະບຸ ຫຼື ບໍ່ຮູ້ຈັກ
    return 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]'

# Hook ສຳລັບສະແດງຄວາມຄືບໜ້າການດາວໂຫລດ (ສຳລັບ Log ໃນ Server)
def progress_hook(d):
    if d['status'] == 'downloading': # ຖ້າກຳລັງດາວໂຫລດ
        print(f"Downloading: {d['_percent_str']} at {d['_speed_str']} of {d['_total_bytes_str']}") # ສະແດງເປີເຊັນ, ຄວາມໄວ, ຂະໜາດທັງໝົດ
    elif d['status'] == 'finished': # ຖ້າດາວໂຫລດສຳເລັດ
        print(f"Done downloading, now post-processing... {d.get('filename', 'unknown filename')}") # ສະແດງວ່າສຳເລັດແລ້ວ ແລະ ກຳລັງປະມວນຜົນ

# Route ສຳລັບໜ້າຫຼັກ (ເມື່ອເຂົ້າໄປທີ່ URL ຂອງ Server)
@app.route('/')
def index():
    return render_template('index.html') # ສົ່ງໄຟລ໌ index.html ກັບຄືນໄປໃຫ້ Browser ສະແດງ

# Endpoint ສຳລັບດາວໂຫລດວິດີໂອ (ເມື່ອ Frontend ສົ່ງຄຳຮ້ອງຂໍ POST ມາທີ່ /download)
@app.route('/download', methods=['POST'])
def download_video():
    data = request.json # ຮັບຂໍ້ມູນທີ່ສົ່ງມາຈາກ Frontend (ເຊັ່ນ: URL, quality)
    url = data.get('url') # ດຶງຄ່າ URL
    quality = data.get('quality', 'best') # ດຶງຄ່າຄຸນນະພາບ (ຄ່າເລີ່ມຕົ້ນແມ່ນ 'best')

    # ຕວດສອບວ່າບໍ່ມີ URL ບໍ່
    if not url:
        return jsonify({'success': False, 'message': 'Please provide a video URL.'}), 400 # ສົ່ງຂໍ້ຄວາມຜິດພາດກັບຄືນໄປ

    # ຕວດສອບຄວາມຖືກຕ້ອງຂອງ URL
    if not is_valid_url(url):
        return jsonify({'success': False, 'message': 'Invalid or unsupported URL.'}), 400 # ສົ່ງຂໍ້ຄວາມຜິດພາດກັບຄືນໄປ

    # ລະບຸແພລັດຟອມແລະ path ຂອງໄຟລ໌ Cookie ທີ່ກ່ຽວຂ້ອງ
    platform = get_platform_from_url(url) # ດຶງຊື່ແພລັດຟອມຈາກ URL
    cookie_file_path = None
    if platform: # ຖ້າພົບແພລັດຟອມ
        path_candidate = os.path.join(DOWNLOAD_FOLDER, f'{platform}_cookies.txt') # ສ້າງເສັ້ນທາງໄຟລ໌ Cookie
        if os.path.exists(path_candidate): # ຖ້າໄຟລ໌ Cookie ນັ້ນມີຢູ່
            cookie_file_path = path_candidate # ກຳນົດໃຫ້ໃຊ້ໄຟລ໌ Cookie ນັ້ນ

    # ສ້າງ UUID (ID ທີ່ບໍ່ຊໍ້າກັນ) ຊົ່ວຄາວສຳລັບຊື່ໄຟລ໌ຊົ່ວຄາວ
    temp_uuid = str(uuid.uuid4())
    # ກຳນົດຮູບແບບຊື່ໄຟລ໌ຊົ່ວຄາວທີ່ຈະບັນທຶກໂດຍ yt-dlp
    temp_output_template = os.path.join(DOWNLOAD_FOLDER, f'{temp_uuid}.%(ext)s')

    # ຕັ້ງຄ່າຕົວເລືອກຕ່າງໆ ສຳລັບ yt-dlp (ເຄື່ອງມືດາວໂຫລດ)
    ydl_opts = {
        'format': get_format_string(quality), # ຮູບແບບຄຸນນະພາບທີ່ຕ້ອງການ
        'merge_output_format': 'mp4', # ໃຫ້ແນ່ໃຈວ່າຜົນລັບສຸດທ້າຍເປັນ MP4
        'outtmpl': temp_output_template, # ໃຊ້ຊື່ໄຟລ໌ຊົ່ວຄາວ
        'noplaylist': True, # ບໍ່ດາວໂຫລດເພລລິດ (ຖ້າລິ້ງເປັນເພລລິດ)
        'progress_hooks': [progress_hook], # ແນບ progress hook ເພື່ອສະແດງຄວາມຄືບໜ້າ
        'retries': 7, # ເພີ່ມຈຳນວນຄັ້ງທີ່ຈະລອງໃໝ່ ຖ້າມີບັນຫາການເຊື່ອມຕໍ່ຊົ່ວຄາວ
        'quiet': True, # ປິດການສະແດງຜົນຂອງ yt-dlp ໃນ console (ຍົກເວັ້ນ Error)
        'no_warnings': True, # ປິດການສະແດງຄຳເຕືອນຂອງ yt-dlp
        # 'verbose': True, # ເປີດໃຊ້ງານສຳລັບ Debugging ເພື່ອເບິ່ງ Log ລະອຽດຂອງ yt-dlp ໃນ Render Logs
    }
    
    # ຖ້າມີໄຟລ໌ Cookie ສຳລັບແພລັດຟອມນີ້, ໃຫ້ເພີ່ມເຂົ້າໄປໃນ yt_dlp options
    if cookie_file_path:
        ydl_opts['cookiefile'] = cookie_file_path
        print(f"Using cookie file: {cookie_file_path}")
    else:
        print("No specific cookie file found for this platform. Proceeding without cookies.")

    final_filename = None # ຕົວປ່ຽນສຳລັບເກັບຊື່ໄຟລ໌ສຸດທ້າຍທີ່ຜູ້ໃຊ້ສາມາດອ່ານໄດ້

    try:
        print(f"Starting download for URL: {url} with quality: {quality}")
        with YoutubeDL(ydl_opts) as ydl: # ສ້າງ Object ຂອງ YoutubeDL ດ້ວຍຕົວເລືອກທີ່ກຳນົດ
            # ດຶງຂໍ້ມູນ ແລະ ດາວໂຫລດວິດີໂອ
            info_dict = ydl.extract_info(url, download=True) # download=True ໝາຍເຖິງໃຫ້ດາວໂຫລດເລີຍ

            # --- ຄົ້ນຫາໄຟລ໌ທີ່ດາວໂຫລດແທ້ຈິງ ແລະ ປ່ຽນຊື່ ---
            # yt-dlp ອາດຈະບັນທຶກໄຟລ໌ດ້ວຍນາມສະກຸນທີ່ແຕກຕ່າງກັນເລັກນ້ອຍ ຫຼື ມີໄຟລ໌ຊົ່ວຄາວ
            # ຄົ້ນຫາໄຟລ໌ທີ່ດາວໂຫລດແທ້ຈິງໂດຍໃຊ້ UUID ທີ່ເຮົາກຳນົດເປັນ prefix
            downloaded_files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(temp_uuid)]
            
            if not downloaded_files: # ຖ້າບໍ່ພົບໄຟລ໌ທີ່ດາວໂຫລດ
                raise Exception(f"No file found in {DOWNLOAD_FOLDER} starting with UUID {temp_uuid} after download attempt. yt-dlp might have failed silently.")
            
            # ສົມມຸດວ່າມີພຽງໄຟລ໌ດຽວທີ່ກົງກັບ UUID prefix
            actual_downloaded_temp_filename = downloaded_files[0]
            actual_downloaded_temp_filepath = os.path.join(DOWNLOAD_FOLDER, actual_downloaded_temp_filename)

            # ກວດສອບວ່າໄຟລ໌ຊົ່ວຄາວມີຢູ່ແທ້ບໍ່
            if not os.path.exists(actual_downloaded_temp_filepath):
                raise Exception(f"Downloaded temporary file '{actual_downloaded_temp_filename}' not found on disk at '{actual_downloaded_temp_filepath}'.")

            # ດຶງຊື່ວິດີໂອ ແລະ ທຳຄວາມສະອາດສຳລັບຊື່ໄຟລ໌ສຸດທ້າຍ
            title = info_dict.get('title', 'unknown_title') # ດຶງຊື່ວິດີໂອ, ຖ້າບໍ່ພົບໃຫ້ໃຊ້ 'unknown_title'
            
            # ການ Sanitize ຊື່ໄຟລ໌ຢ່າງເຂັ້ມງວດ: ເພື່ອໃຫ້ຊື່ໄຟລ໌ໃຊ້ງານໄດ້ດີໃນທຸກລະບົບ
            # 1. ປ່ຽນ Unicode (ລວມທັງ Emoji) ເປັນ ASCII ແລະ ບໍ່ສົນໃຈໂຕອັກສອນທີ່ບໍ່ສາມາດປ່ຽນໄດ້
            title = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode('utf-8')
            # 2. ລົບໂຕອັກສອນທີ່ບໍ່ແມ່ນໂຕອັກສອນ, ຕົວເລກ, ຊ່ອງຫວ່າງ, ຂີດກາງ, ຈຸດ
            title = re.sub(r'[^\w\s\-\.]', '', title)
            # 3. ແທນທີ່ຊ່ອງຫວ່າງຫຼາຍຊ່ອງດ້ວຍຊ່ອງຫວ່າງດຽວ ແລະ ລົບຊ່ອງຫວ່າງທີ່ຫົວທ້າຍ
            title = re.sub(r'\s+', ' ', title).strip()
            # 4. ປ່ຽນຊ່ອງຫວ່າງເປັນ underscore ເພື່ອໃຫ້ໃຊ້ງານໄດ້ກັບຊື່ໄຟລ໌
            title = title.replace(' ', '_')

            # ດຶງ ID ວິດີໂອ (ສຳຄັນສຳລັບຊື່ໄຟລ໌ທີ່ບໍ່ຊໍ້າກັນ)
            video_id = info_dict.get('id', str(uuid.uuid4())) # ໃຊ້ UUID ຖ້າບໍ່ພົບ ID ວິດີໂອ

            # ກຳນົດນາມສະກຸນໄຟລ໌ທີ່ຖືກຕ້ອງຈາກໄຟລ໌ທີ່ດາວໂຫລດແທ້ຈິງ
            final_ext = os.path.splitext(actual_downloaded_temp_filename)[1] # ດຶງນາມສະກຸນ (ເຊັ່ນ: .mp4)
            if not final_ext: # ຖ້າບໍ່ພົບນາມສະກຸນໄຟລ໌ ໃຫ້ໃຊ້ .mp4 ເປັນຄ່າເລີ່ມຕົ້ນ
                final_ext = '.mp4'

            # ສ້າງຊື່ໄຟລ໌ສຸດທ້າຍທີ່ຕ້ອງການ (ເຊັ່ນ: ຊື່ວິດີໂອ-ID_ວິດີໂອ.mp4)
            final_filename = f"{title}-{video_id}{final_ext}"

            # ປ່ຽນຊື່ໄຟລ໌ຊົ່ວຄາວໃຫ້ເປັນຊື່ໄຟລ໌ສຸດທ້າຍທີ່ຕ້ອງການ
            final_filepath = os.path.join(DOWNLOAD_FOLDER, final_filename)
            os.rename(actual_downloaded_temp_filepath, final_filepath) # ປ່ຽນຊື່ໄຟລ໌
            print(f"Renamed '{actual_downloaded_temp_filename}' to '{final_filename}'") # ສະແດງຂໍ້ຄວາມໃນ Log
            
            # ສົ່ງຂໍ້ມູນກັບຄືນໄປ Frontend ວ່າສຳເລັດແລ້ວ ແລະ ບອກຊື່ໄຟລ໌ທີ່ດາວໂຫລດໄດ້
            return jsonify({
                'success': True,
                'message': 'Download successful!',
                'filename': final_filename,
                'download_url': f'/download-file/{final_filename}' # ສົ່ງ URL ສຳລັບດາວໂຫລດໄຟລ໌ກັບຄືນໄປ
            })

    except Exception as e: # ຖ້າເກີດຂໍ້ຜິດພາດໃດໆ ໃນຂະນະດາວໂຫລດ
        print(f"Error downloading video from {url}: {e}") # ສະແດງຂໍ້ຜິດພາດໃນ Log
        # ສົ່ງຂໍ້ຄວາມ Error ທີ່ຜູ້ໃຊ້ສາມາດເຂົ້າໃຈໄດ້ງ່າຍຂຶ້ນ
        return jsonify({'success': False, 'message': f'An error occurred during download: {str(e)}'}), 500 # ສົ່ງຂໍ້ຄວາມຜິດພາດກັບຄືນໄປ

# Endpoint ສຳລັບສົ່ງໄຟລ໌ທີ່ດາວໂຫລດສຳເລັດແລ້ວກັບຄືນໄປຫາຜູ້ໃຊ້ (ເມື່ອ Browser ຮ້ອງຂໍໄຟລ໌)
@app.route('/download-file/<filename>', methods=['GET'])
def download_file(filename):
    if not filename: # ຖ້າບໍ່ມີຊື່ໄຟລ໌
        return 'Invalid filename', 400 # ສົ່ງຂໍ້ຄວາມຜິດພາດ

    file_path = os.path.join(DOWNLOAD_FOLDER, filename) # ສ້າງເສັ້ນທາງເຕັມຂອງໄຟລ໌
    safe_download_folder_abs = os.path.abspath(DOWNLOAD_FOLDER) # ເສັ້ນທາງເຕັມຂອງໂຟນເດີດາວໂຫລດ
    safe_file_path_abs = os.path.abspath(file_path) # ເສັ້ນທາງເຕັມຂອງໄຟລ໌ທີ່ຮ້ອງຂໍ

    # ກວດສອບຄວາມປອດໄພ: ປ້ອງກັນ Path Traversal (ບໍ່ໃຫ້ຜູ້ໃຊ້ເຂົ້າເຖິງໄຟລ໌ນອກໂຟນເດີທີ່ກຳນົດ)
    # ໃຫ້ແນ່ໃຈວ່າ path ຂອງໄຟລ໌ທີ່ຮ້ອງຂໍຢູ່ພາຍໃຕ້ DOWNLOAD_FOLDER ແທ້ໆ
    if not safe_file_path_abs.startswith(safe_download_folder_abs):
        return 'File access forbidden', 403 # ຫ້າມເຂົ້າເຖິງ

    if not os.path.exists(file_path): # ຖ້າໄຟລ໌ບໍ່ມີຢູ່
        print(f"File not found at path: {file_path}") # ສະແດງຂໍ້ຄວາມໃນ Log
        return 'File not found', 404 # ສົ່ງຂໍ້ຄວາມຜິດພາດ

    # ສົ່ງໄຟລ໌ເປັນ attachment (ໝາຍເຖິງໃຫ້ Browser ດາວໂຫລດໄຟລ໌, ບໍ່ແມ່ນເປີດເບິ່ງ)
    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)

# ຟັງຊັນລ້າງໄຟລ໌ເກົ່າຖິ້ມ (ຄວນຕັ້ງ cron job ຫຼື ເອີ້ນເອງເປັນໄລຍະ)
def cleanup_old_files(max_age_hours=6): # ກຳນົດວ່າໄຟລ໌ທີ່ເກົ່າກວ່າ 6 ຊົ່ວໂມງຈະຖືກລຶບ
    now = time.time() # ເວລາປັດຈຸບັນ
    for f in os.listdir(DOWNLOAD_FOLDER): # ວົນລູບຜ່ານທຸກໄຟລ໌ໃນໂຟນເດີດາວໂຫລດ
        fp = os.path.join(DOWNLOAD_FOLDER, f) # ເສັ້ນທາງເຕັມຂອງໄຟລ໌
        # ຕວດສອບວ່າເປັນໄຟລ໌ ແລະ ບໍ່ແມ່ນໄຟລ໌ Cookie (ເພື່ອບໍ່ໃຫ້ລຶບ Cookie ຖິ້ມ)
        if os.path.isfile(fp) and not f.endswith('_cookies.txt'):
            # ລຶບໄຟລ໌ທີ່ເກົ່າກວ່າ max_age_hours
            if now - os.path.getmtime(fp) > max_age_hours * 3600: # 3600 ວິນາທີ = 1 ຊົ່ວໂມງ
                try:
                    os.remove(fp) # ລຶບໄຟລ໌
                    print(f"Cleaned up old file: {fp}") # ສະແດງຂໍ້ຄວາມໃນ Log
                except Exception as e:
                    print(f"Error cleaning up old file {fp}: {e}") # ສະແດງຂໍ້ຜິດພາດໃນ Log
            else:
                print(f"Keeping recent file: {fp}") # ຖ້າໄຟລ໌ຍັງໃໝ່ຢູ່ ໃຫ້ເກັບໄວ້

# ຕວດສອບວ່າແອັບຖືກຣັນໂດຍກົງ ຫຼື ໂດຍ Gunicorn (ສຳລັບ Server)
if __name__ == '__main__': # ຖ້າໄຟລ໌ນີ້ຖືກຣັນໂດຍກົງ (ບໍ່ແມ່ນຖືກ import ໄປໃຊ້)
    cleanup_old_files() # ຣັນຟັງຊັນລ້າງໄຟລ໌ເກົ່າເມື່ອແອັບເລີ່ມເຮັດວຽກ
    port = int(os.environ.get('PORT', 5000)) # ດຶງ Port ຈາກ Environment Variable ຫຼື ໃຊ້ 5000 ເປັນຄ່າເລີ່ມຕົ້ນ
    app.run(debug=True, host='0.0.0.0', port=port) # ຣັນແອັບ Flask (debug=True ສຳລັບການພັດທະນາ)
