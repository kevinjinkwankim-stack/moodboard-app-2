from flask import Flask, request, jsonify, send_file, render_template
import os
import uuid
import subprocess
import shutil
import cv2
import zipfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 512  # 512MB upload limit

UPLOAD_FOLDER = 'uploads'
FRAME_FOLDER = 'static/frames'
ZIP_FOLDER = 'zips'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(FRAME_FOLDER, exist_ok=True)
os.makedirs(ZIP_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    project_name = request.form.get('name')
    url = request.form.get('url')
    video_file = request.files.get('video')

    project_folder = os.path.join(FRAME_FOLDER, project_name)
    os.makedirs(project_folder, exist_ok=True)

    download_path = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()))
    os.makedirs(download_path, exist_ok=True)

    video_path = os.path.join(download_path, "video.mp4")

    try:
        if video_file:
            video_file.save(video_path)
        elif url:
            output_template = os.path.join(download_path, "video.%(ext)s")
            yt_dlp_command = ["yt-dlp", url, "-o", output_template]
            result = subprocess.run(yt_dlp_command, capture_output=True, text=True)
            if result.returncode != 0:
                return jsonify({"error": "Failed to download URL", "details": result.stderr})
            for file in os.listdir(download_path):
                if file.startswith("video."):
                    original_file = os.path.join(download_path, file)
                    os.rename(original_file, video_path)
                    break
            else:
                return jsonify({"error": "Download failed: No compatible video file found."})
        else:
            return jsonify({"error": "No video or URL provided"})

        print(">>> Starting frame extraction")
        frames = extract_frames(video_path, project_folder, project_name)
        return jsonify({
            "frames": [os.path.join('frames', project_name, f).replace('\\', '/') for f in frames],
            "project": project_name
        })

    except Exception as e:
        print("Exception occurred:", str(e))
        return jsonify({"error": str(e)})

@app.route('/download_zip/<project_name>')
def download_zip(project_name):
    folder_path = os.path.join(FRAME_FOLDER, project_name)
    zip_path = os.path.join(ZIP_FOLDER, f"{project_name}.zip")

    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                zipf.write(os.path.join(root, file), arcname=file)

    return send_file(zip_path, as_attachment=True)

@app.route('/download_selected', methods=['POST'])
def download_selected():
    data = request.get_json()
    selected_files = data.get('files', [])
    zip_name = data.get('zip_name', 'selected')
    zip_path = os.path.join(ZIP_FOLDER, f"{zip_name}.zip")

    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file_path in selected_files:
            full_path = os.path.join('static', file_path.replace('frames/', 'frames/'))
            if os.path.exists(full_path):
                zipf.write(full_path, arcname=os.path.basename(full_path))

    return send_file(zip_path, as_attachment=True)

def extract_frames(video_path, output_dir, base_name):
    print(">>> Running extract_frames")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise Exception("Failed to open video file")

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    interval = int(cap.get(cv2.CAP_PROP_FPS)) * 5  # one frame every 5 seconds

    frames = []
    current_frame = 0
    idx = 0

    while current_frame < frame_count:
        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
        ret, frame = cap.read()
        if not ret:
            break
        frame_name = f"{base_name}_{idx + 1}.jpg"
        frame_path = os.path.join(output_dir, frame_name)
        cv2.imwrite(frame_path, frame)
        frames.append(frame_name)
        current_frame += interval
        idx += 1

    cap.release()
    print(f"Extracted {len(frames)} frames")
    return frames

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
