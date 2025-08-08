from flask import Flask, render_template, request, jsonify, send_file
import os
import shutil
import uuid
import zipfile
import cv2
from scenedetect import detect, ContentDetector
from scenedetect.frame_timecode import FrameTimecode
from scenedetect.video_manager import VideoManager
from scenedetect.scene_manager import SceneManager
from scenedetect.stats_manager import StatsManager

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
STATIC_FOLDER = 'static'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400

    video = request.files['video']
    name = request.form.get('name') or uuid.uuid4().hex

    temp_id = str(uuid.uuid4())
    project_path = os.path.join(UPLOAD_FOLDER, temp_id)
    frame_output_dir = os.path.join(STATIC_FOLDER, temp_id)
    os.makedirs(project_path, exist_ok=True)
    os.makedirs(frame_output_dir, exist_ok=True)

    video_path = os.path.join(project_path, 'video.mp4')
    video.save(video_path)

    # Detect scenes and extract one frame per scene
    try:
        video_manager = VideoManager([video_path])
        stats_manager = StatsManager()
        scene_manager = SceneManager(stats_manager)
        scene_manager.add_detector(ContentDetector())
        video_manager.set_downscale_factor()
        video_manager.start()
        scene_manager.detect_scenes(frame_source=video_manager)
        scene_list = scene_manager.get_scene_list()

        # Extract one frame per scene
        frame_paths = []
        cap = cv2.VideoCapture(video_path)
        for i, (start_time, _) in enumerate(scene_list):
            frame_num = start_time.get_frames()
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            success, frame = cap.read()
            if success:
                frame_filename = f'{temp_id}/frame_{i+1}.jpg'
                frame_path = os.path.join(STATIC_FOLDER, frame_filename)
                cv2.imwrite(frame_path, frame)
                frame_paths.append(frame_filename)
        cap.release()

        return jsonify({"project": temp_id, "frames": frame_paths})

    except Exception as e:
        print("Exception occurred:", e)
        return jsonify({"error": str(e)}), 500

@app.route('/download_zip/<project_id>')
def download_zip(project_id):
    zip_filename = f"{project_id}.zip"
    zip_path = os.path.join(UPLOAD_FOLDER, zip_filename)
    with zipfile.ZipFile(zip_path, 'w') as zf:
        folder_path = os.path.join(STATIC_FOLDER, project_id)
        for filename in os.listdir(folder_path):
            frame_path = os.path.join(folder_path, filename)
            zf.write(frame_path, arcname=filename)
    return send_file(zip_path, as_attachment=True)

@app.route('/download_selected', methods=['POST'])
def download_selected():
    data = request.json
    files = data.get('files', [])
    zip_name = data.get('zip_name', 'selected_frames') + '.zip'
    zip_path = os.path.join(UPLOAD_FOLDER, zip_name)
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for f in files:
            path = os.path.join(STATIC_FOLDER, f)
            if os.path.exists(path):
                zf.write(path, arcname=os.path.basename(f))
    return send_file(zip_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
