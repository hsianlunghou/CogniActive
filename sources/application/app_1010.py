import cv2
import mediapipe as mp
import numpy as np
import json
import csv
import os
import threading
import queue
import time
import base64
import pyrebase

from flask import Flask, render_template, Response, jsonify, request, jsonify
from datetime import datetime
from io import BytesIO
from PIL import Image

config = {
    
};
firebase = pyrebase.initialize_app(config)

db = firebase.database()

# web application initialization
app = Flask(__name__)

frame_queue = queue.Queue(maxsize = 3)
latest_result = None
lock = threading.Lock()

# MediaPipe Initialization
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# Global Variable
TARGET_LANDMARKS = [11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]

LANDMARK_NAMES = {
    11: 'LEFT_SHOULDER',
    12: 'RIGHT_SHOULDER',
    13: 'LEFT_ELBOW',
    14: 'RIGHT_ELBOW',
    15: 'LEFT_WRIST',
    16: 'RIGHT_WRIST',
    17: 'LEFT_PINKY',
    18: 'RIGHT_PINKY',
    19: 'LEFT_INDEX',
    20: 'RIGHT_INDEX',
    21: 'LEFT_THUMB',
    22: 'RIGHT_THUMB'
}

pose = None
is_recording = False
recorded_data = []
start_time = None
latest_landmarks = None

# model initialization
def init_pose():
    return mp_pose.Pose(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        model_complexity=1,
        static_image_mode=False
    )

# initailize pose model
pose = init_pose()


'''
改成非同步串流
1. 使用 threading + Streaming Queue
2. 讓攝像機在另一條 thread 裡運行
3. 避免 Out of Memory
'''
def process_frame(image_data):
    # process the frame and return processed image and pose data
    global latest_landmarks, is_recording, recorded_data, start_time
    
    try:
        # decode base64 image
        image_bytes = base64.b64decode(image_data.split(',')[1])
        image = Image.open(BytesIO(image_bytes))
        frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # convert color space
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image_rgb.flags.writeable = False
        
        # pose estimation
        results = pose.process(image_rgb)
        
        image_rgb.flags.writeable = True
        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        
        landmarks_data = None
        
        if results.pose_landmarks:
            latest_landmarks = results.pose_landmarks
            
            # pose connections
            mp_drawing.draw_landmarks(
                image_bgr,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style()
            )
            
            # target landmarks
            h, w, c = image_bgr.shape
            for idx in TARGET_LANDMARKS:
                landmark = results.pose_landmarks.landmark[idx]
                cx, cy = int(landmark.x * w), int(landmark.y * h)
                cv2.circle(image_bgr, (cx, cy), 8, (0, 0, 255), -1)
                cv2.putText(image_bgr, str(idx), (cx + 10, cy - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            
            # call back landmarks data
            landmarks_data = []
            for landmark in results.pose_landmarks.landmark:
                landmarks_data.append({
                    'x': float(landmark.x),
                    'y': float(landmark.y),
                    'z': float(landmark.z),
                    'visibility': float(landmark.visibility)
                })
            
            # record data
            if is_recording and start_time:
                elapsed_time = (datetime.now() - start_time).total_seconds()
                record = {
                    'timestamp': elapsed_time,
                    'landmarks': landmarks_data
                }
                recorded_data.append(record)
        
        # image encoding is base64
        _, buffer = cv2.imencode('.jpg', image_bgr)
        processed_image = base64.b64encode(buffer).decode('utf-8')
        
        return {
            'status': 'success',
            'image': f'data:image/jpeg;base64,{processed_image}',
            'landmarks': landmarks_data
        }
        
    except Exception as e:
        print(f"[Error] Processing frame: {e}")
        return {'status': 'error', 'message': str(e)}

@app.route('/')
def index():
    return render_template('index.html')

# while no get favicon.ico, response to web (avoid 502 status)
@app.route('/favicon.ico')
def favicon():
    return Response(status=204)

@app.route('/process_frame', methods=['POST'])
def process_frame_route():
    # receive frame from frontend data and process
    try:
        data = request.get_json()
        image_data = data.get('image')
        
        if not image_data:
            return jsonify({'status': 'error', 'message': '沒有收到圖片資訊'})
        
        result = process_frame(image_data)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/pose_data')
def pose_data():
    # GET current pose landmarks data in real-time
    global latest_landmarks
    
    if latest_landmarks is None:
        return jsonify({'status': 'no_data', 'message': '無法獲取資料'})
    
    try:
        landmarks = []
        for landmark in latest_landmarks.landmark:
            landmarks.append({
                'x': float(landmark.x),
                'y': float(landmark.y),
                'z': float(landmark.z),
                'visibility': float(landmark.visibility)
            })
        return jsonify({'status': 'success', 'data': landmarks})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/start_recording', methods=['POST'])
def start_recording():
    global is_recording, recorded_data, start_time
    
    try:
        is_recording = True
        recorded_data = []
        start_time = datetime.now()
        
        return jsonify({'status': 'success', 'message': '開始記錄'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/stop_recording', methods=['POST'])
def stop_recording():
    global is_recording, recorded_data, start_time
    
    try:
        if not is_recording:
            return jsonify({'status': 'error', 'message': '不在記錄狀態'})
        
        is_recording = False
        
        # if not os.path.exists('recordings'):
        #     os.makedirs('recordings')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # csv_filename = f'recordings/pose_data_{timestamp}.csv'      
        # json_filename = f'recordings/pose_data_{timestamp}.json'
        
        # save to CSV
        '''with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            if recorded_data:
                fieldnames = ['timestamp']
                for i in range(33):
                    fieldnames.extend([f'landmark_{i}_x', f'landmark_{i}_y', 
                                     f'landmark_{i}_z', f'landmark_{i}_visibility'])
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for record in recorded_data:
                    row = {'timestamp': round(record['timestamp'], 3)}
                    for i, landmark in enumerate(record['landmarks']):
                        row[f'landmark_{i}_x'] = round(landmark['x'], 6)
                        row[f'landmark_{i}_y'] = round(landmark['y'], 6)
                        row[f'landmark_{i}_z'] = round(landmark['z'], 6)
                        row[f'landmark_{i}_visibility'] = round(landmark['visibility'], 6)
                    writer.writerow(row)'''
        # save to JSON
        json_data = {
            'recording_info': {
                'timestamp': timestamp,
                'total_frames': len(recorded_data),
                'start_time': start_time.isoformat() if start_time else None
            },
            'frames': []
        }
        
        for record in recorded_data:
            frame_data = {
                'timestamp': round(record['timestamp'], 3),
                'landmarks': []
            }
            for i, landmark in enumerate(record['landmarks']):
                frame_data['landmarks'].append({
                    'id': i,
                    'name': LANDMARK_NAMES.get(i, f'LANDMARK_{i}'),
                    'x': round(landmark['x'], 6),
                    'y': round(landmark['y'], 6),
                    'z': round(landmark['z'], 6),
                    'visibility': round(landmark['visibility'], 6)
                })
            json_data['frames'].append(frame_data)
        
        db.child("pose_json").push(json_data)

        # with open(json_filename, 'w', encoding='utf-8') as jsonfile:
        #     json.dump(json_data, jsonfile, indent=2, ensure_ascii=False)
        
        data_count = len(recorded_data)
        recorded_data = []
        start_time = None
        
        return jsonify({
            'status': 'success',
            'message': '記錄已經保存',
            # 'csv_filename': csv_filename,
            # 'json_filename': json_filename,
            'records': data_count
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/recording_status')
def recording_status():
    global is_recording, start_time, recorded_data
    
    status = {
        'is_recording': is_recording,
        'records_count': len(recorded_data)
    }
    
    if is_recording and start_time:
        elapsed = (datetime.now() - start_time).total_seconds()
        status['elapsed_time'] = round(elapsed, 1)
    
    return jsonify(status)

if __name__ == '__main__':
    app.run(debug=True, threaded=True, host='0.0.0.0', port=5000)