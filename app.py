
from flask import Flask, request, jsonify, send_file, render_template
import os
import uuid
import subprocess
import shutil
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector
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
            print("Received file:", video_file.filename)
            print("Saving to:", video_path)
            video_file.save(video_path)
            print("Video uploaded locally:", video_path)

        elif url:
            output_template = os.path.join(download_path, "video.%(ext)s")
            yt_dlp_command = ["python3", "-m", "yt_dlp", url, "-o", output_template]

            print("Running yt-dlp command:", " ".join(yt_dlp_command))
            result = subprocess.run(yt_dlp_command, capture_output=True, text=True)
            print("yt-dlp stdout:", result.stdout)
            print("yt-dlp stderr:", result.stderr)

            if result.returncode != 0:
                return jsonify({"error": "Failed to download URL", "details": result.stderr})

            downloaded_files = os.listdir(download_path)
            print("Downloaded files:", downloaded_files)

            for file in downloaded_files:
                if file.startswith("video."):
                    original_file = os.path.join(download_path, file)
                    os.rename(original_file, video_path)
                    break
            else:
                return jsonify({"error": "Download failed: No compatible video file found.", "files": downloaded_files})

        else:
            return jsonify({"error": "No video or URL provided"})

        print("Extracting frames from:", video_path)
        frames = extract_frames(video_path, project_folder, project_name)
        print("Frames extracted:", frames)
        return jsonify({"frames": [os.path.join('frames', project_name, f).replace('\\', '/') for f in frames], "project": project_name})

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
    print("Initializing scene detection")
    video_manager = VideoManager([video_path])
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=30.0))

    video_manager.set_downscale_factor()
    video_manager.start()

    scene_manager.detect_scenes(frame_source=video_manager)
    scene_list = scene_manager.get_scene_list()
    print(f"Detected {len(scene_list)} scenes.")

    frames = []
    cap = cv2.VideoCapture(video_path)
    
    for idx, (start_timecode, _) in enumerate(scene_list):
        start_frame = start_timecode.get_frames()
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        ret, frame = cap.read()
        if ret:
            frame_name = f"{base_name}_{idx + 1}.jpg"
            frame_path = os.path.join(output_dir, frame_name)
            cv2.imwrite(frame_path, frame)
            frames.append(frame_name)

    cap.release()
    return frames
    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
