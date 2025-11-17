from flask import Flask, render_template, Response, jsonify, request
import cv2
import mediapipe as mp
import numpy as np
import json
from datetime import datetime
import csv
import os
import threading
import time

# web application initialization
app = Flask(__name__)

# MediaPipe Initialization
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# Global Variable
'''
    Part of Function
    - target landmarks
    - camera control
    - pose model
    - recording pannel
'''
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

camera = None
camera_lock = threading.Lock()

pose = None

is_recording = False
recorded_data = []
start_time = None
latest_landmarks = None

# model initialization
def init_pose():
    '''
        min_detection_confidence: initial detection confidence
        min_tracking_confidence: tracking confidence
        model_complexity: tracking confidence
        static_image_mode (input mode):
            False is video stream
            True is image format
    '''
    return mp_pose.Pose(
        min_detection_confidence = 0.5,
        min_tracking_confidence = 0.5,
        model_complexity = 1,
        static_image_mode = False
    )

def generate_frames():
    # video frame
    global camera, is_recording, recorded_data, start_time, latest_landmarks, pose
    
    # create parallel threading: processing of pose instance
    local_pose = init_pose()
    
    while True:
        with camera_lock:
            if camera is None or not camera.isOpened():
                break
            
            success, frame = camera.read()
        
        if not success or frame is None:
            time.sleep(0.01)
            continue
        
        try:
            # check empty frame or not
            if frame.size == 0:
                continue
            
            # convert color space
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image.flags.writeable = False
            
            # pose detection
            results = local_pose.process(image)
            
            # 3D human pose
            image.flags.writeable = True
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            
            if results.pose_landmarks:
                # record newest landmarks
                latest_landmarks = results.pose_landmarks
                
                # compose 3D pose
                mp_drawing.draw_landmarks(
                    image,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style()
                )
                
                # show target landmarks
                for idx in TARGET_LANDMARKS:
                    landmark = results.pose_landmarks.landmark[idx]

                    h, w, c = image.shape

                    cx, cy = int(landmark.x * w), int(landmark.y * h)
                    
                    # highlight target landmarks
                    cv2.circle(image, (cx, cy), 8, (0, 0, 255), -1)
                    cv2.putText(image, str(idx), (cx + 10, cy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

                # while recording, need to save data 
                if is_recording and start_time:
                    elapsed_time = (datetime.now() - start_time).total_seconds()
                    
                    landmarks_list = []

                    for landmark in results.pose_landmarks.landmark:
                        landmarks_list.append({
                            'x': landmark.x,
                            'y': landmark.y,
                            'z': landmark.z,
                            'visibility': landmark.visibility
                        })
                    
                    record = {
                        'timestamp': elapsed_time,
                        'landmarks': landmarks_list
                    }
                    recorded_data.append(record)
            
            # encode format is JPEG
            ret, buffer = cv2.imencode('.jpg', image)

            if not ret:
                continue
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                   
        except Exception as e:
            print(f"[Error] In video frame: {e}")
            time.sleep(0.01)
            continue
    
    # clear memory
    local_pose.close()

def get_pose_data():
    # get pose data for 3D visualization and chart
    global latest_landmarks
    
    if latest_landmarks is None:
        return None
    
    try:
        landmarks = []
        for landmark in latest_landmarks.landmark:
            landmarks.append({
                'x': float(landmark.x),
                'y': float(landmark.y),
                'z': float(landmark.z),
                'visibility': float(landmark.visibility)
            })
        return landmarks
    except Exception as e:
        print(f"[Error] Getting pose data: {e}")
        return None

@app.route('/')
def index():
    # main page
    return render_template('index.html')

@app.route('/start_camera', methods=['POST'])
def start_camera():
    # start camera
    global camera, pose
    
    with camera_lock:
        try:
            if camera is not None:
                return jsonify({'status': 'error', 'message': 'Camera 已在運作中­'})
            
            # try to open the access to camera
            camera = cv2.VideoCapture(0)
            
            # camera settings
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            camera.set(cv2.CAP_PROP_FPS, 30)
            
            # waiting initialization
            time.sleep(1)
            
            # check if camera opened successfully
            if not camera.isOpened():
                camera = None
                return jsonify({'status': 'error', 'message': 'Camera 無法開啟'})
            
            # try to read the frame data to test system operation
            ret, test_frame = camera.read()
            if not ret or test_frame is None:
                camera.release()
                camera = None
                return jsonify({'status': 'error', 'message': 'Camera 無法讀取影像'})
            
            return jsonify({'status': 'success', 'message': 'Camera 已經啟動'})
            
        except Exception as e:
            if camera is not None:
                camera.release()
                camera = None
            return jsonify({'status': 'error', 'message': f'Camera 啟動失敗: {str(e)}'})

@app.route('/stop_camera', methods=['POST'])
def stop_camera():
    # Stop Camera 
    global camera, pose, latest_landmarks
    
    with camera_lock:
        try:
            if camera is not None:
                camera.release()
                camera = None
            
            latest_landmarks = None
            
            return jsonify({'status': 'success', 'message': 'Camera 已經停止'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Camera 無法停止運作: {str(e)}'})

@app.route('/video_feed')
def video_feed():
    # video streaming route
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/pose_data')
def pose_data():
    # get pose data
    try:
        data = get_pose_data()
        if data:
            return jsonify({'status': 'success', 'data': data})
        return jsonify({'status': 'no_data', 'message': '無法獲取資料'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/start_recording', methods=['POST'])
def start_recording():
    # Start recording
    global is_recording, recorded_data, start_time
    
    try:
        if camera is None:
            return jsonify({'status': 'error', 'message': '請先開啟 Camera'})
        
        is_recording = True
        recorded_data = []
        start_time = datetime.now()
        
        return jsonify({'status': 'success', 'message': '開始記錄'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/stop_recording', methods=['POST'])
def stop_recording():
    # Stop recording and save the csv file and json file
    global is_recording, recorded_data, start_time
    
    try:
        if not is_recording:
            return jsonify({'status': 'error', 'message': '不在記錄狀態'})
        
        is_recording = False
        
        # create recordings directory
        if not os.path.exists('recordings'):
            os.makedirs('recordings')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f'recordings/pose_data_{timestamp}.csv'
        json_filename = f'recordings/pose_data_{timestamp}.json'
        
        # save CSV file
        with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            if recorded_data:
                # add column 
                fieldnames = ['timestamp']

                # MediaPipe have 33 landmarks
                for i in range(33):  
                    fieldnames.extend([f'landmark_{i}_x', f'landmark_{i}_y', 
                                     f'landmark_{i}_z', f'landmark_{i}_visibility'])
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                # write the data
                for record in recorded_data:
                    row = {'timestamp': round(record['timestamp'], 3)}
                    for i, landmark in enumerate(record['landmarks']):
                        row[f'landmark_{i}_x'] = round(landmark['x'], 6)
                        row[f'landmark_{i}_y'] = round(landmark['y'], 6)
                        row[f'landmark_{i}_z'] = round(landmark['z'], 6)
                        row[f'landmark_{i}_visibility'] = round(landmark['visibility'], 6)
                    writer.writerow(row)
        
        # save JSON file
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
        
        with open(json_filename, 'w', encoding='utf-8') as jsonfile:
            json.dump(json_data, jsonfile, indent=2, ensure_ascii=False)
        
        data_count = len(recorded_data)
        recorded_data = []
        start_time = None
        
        return jsonify({
            'status': 'success', 
            'message': f'記錄已經保存',
            'csv_filename': csv_filename,
            'json_filename': json_filename,
            'records': data_count
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/recording_status')
def recording_status():
    # get recording status
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
    app.run(debug=True, threaded=True, host='127.0.0.1', port=5000)