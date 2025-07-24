# ใช้ Python official image เป็น base image (ควรใช้เวอร์ชันที่ใกล้เคียงกับที่คุณใช้บนเครื่อง)
FROM python:3.10-slim-bullseye

# ติดตั้ง ffmpeg
RUN apt-get update -y && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# ตั้งค่า Working Directory
WORKDIR /app

# คัดลอก requirements.txt และติดตั้ง Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# คัดลอกไฟล์โปรเจกต์ที่เหลือทั้งหมด
COPY . .

# expose port ที่แอป Flask ของคุณจะรัน
EXPOSE 5000

# กำหนดคำสั่งเริ่มต้นเมื่อ Container รัน (จาก Procfile)
CMD ["gunicorn", "app:app", "--log-file", "-", "--timeout", "300"]
