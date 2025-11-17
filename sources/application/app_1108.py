import cv2
import mediapipe as mp
import numpy as np
import threading
import queue
import time
import base64
import pyrebase

from flask import Flask, render_template, Response, jsonify, request
from datetime import datetime
from io import BytesIO
from PIL import Image
from scipy.signal import butter, lfilter, periodogram

# Firebase configuration
config = {
    # Add your Firebase config here
    
}
firebase = pyrebase.initialize_app(config)
db = firebase.database()

# Flask application initialization
app = Flask(__name__)

# Asynchronous processing queue (max 3 frames to prevent memory overflow)
'''
    - Before operating current task, no need to wait other task
    - Avoid stopping program
'''
frame_queue = queue.Queue(maxsize=3)
result_queue = queue.Queue(maxsize=3)
processing_active = False
processing_thread = None

# MediaPipe initialization
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles
mp_face = mp.solutions.face_detection.FaceDetection(
    model_selection=0, 
    min_detection_confidence=0.6
)

# Global variables
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

# control pannel
'''
    Divide three parts 
    1. continous data
    - is_recording: record status
    - recorded_data: temporary storage
    - start_time: initial time

    2. pose data
    - latest_landmarks: current data

    3. heart rate
    - latest_result: current data
    - latest_bpm: current bpm value
    - lock: thread status
'''
is_recording = False
recorded_data = []
start_time = None

latest_landmarks = None

latest_result = None
latest_bpm = None
lock = threading.Lock()

# Heart rate detection variables
'''
    - fps: Assumed frame rate
    - g_values: Collect green channel values from face ROI
    - Store BPM history for smoothing data
'''
fps = 30  
g_values = []  
bpm_history = []  

def init_pose():
    # Initialize MediaPipe Pose model
    return mp_pose.Pose(
        min_detection_confidence = 0.8,
        min_tracking_confidence = 0.8,
        model_complexity = 1,
        static_image_mode = False
    )

def bandpass_filter(signal, low = 0.8, high = 3.0, fs = 30, order = 5):
    # Bandpass filter for heart rate signal processing
    """
    Args:
        signal: Input signal (green channel values)
        low: Low cutoff frequency (Hz) - 0.8 Hz = 48 BPM
        high: High cutoff frequency (Hz) - 3.0 Hz = 180 BPM
        fs: Sampling frequency (Hz)
        order: Filter order
    Returns:
        Filtered signal
    """

    # keep certained range and remove noise
    nyquist = 0.5 * fs

    # In order to remove respiratory, light variation
    low_normalized = low / nyquist

    # In order to remove dynamic movement
    high_normalized = high / nyquist

    b, a = butter(order, [low_normalized, high_normalized], btype = 'band')
    return lfilter(b, a, signal)

def calculate_heart_rate(g_values_window, fps):
    # Calculate heart rate from green channel values using rPPG
    """
    Args:
        g_values_window: Window of green channel values
        fps: Frame Rate
    Returns:
        Heart rate in BPM or None if invalid
    """
    try:
        # Apply bandpass filter
        filtered_signal = bandpass_filter(np.array(g_values_window), fs = fps)
        
        # Calculate power spectral density using periodogram
        frequencies, power = periodogram(filtered_signal, fs = fps)
        
        # Find dominant frequency in valid heart rate range (0.8-3.0 Hz = 48-180 BPM)
        valid_indices = np.where((frequencies >= 0.8) and (frequencies <= 3.0))
        if len(valid_indices[0]) == 0:
            return None
        
        valid_frequencies = frequencies[valid_indices]
        valid_power = power[valid_indices]
        
        # Get frequency with maximum power
        dominant_frequency = valid_frequencies[np.argmax(valid_power)]

        # Convert Hz to BPM
        heart_rate = dominant_frequency * 60  
        
        # Validate heart rate is in reasonable range
        if heart_rate > 40 and heart_rate < 180:
            return heart_rate
        return None
        
    except Exception as e:
        print(f"[ERROR] Heart rate calculation error: {e}")
        return None

def smooth_bpm(new_bpm, history, max_history=5):
    # Smooth BPM using moving average
    """
    Args:
        new_bpm: New BPM value
        history: List of previous BPM values
        max_history: Maximum history length
    Returns:
        Smoothed BPM value
    """
    history.append(new_bpm)
    if len(history) > max_history:
        history.pop(0)
    return np.mean(history)

def process_frame_worker():
    # Background thread worker for processing frames asynchronously
    global latest_result, latest_landmarks, is_recording, recorded_data, start_time
    global processing_active, latest_bpm, g_values, bpm_history
    
    # Initialize pose model in worker thread
    local_pose = init_pose()
    
    print("[INFO] Frame processing thread started")
    
    while processing_active:
        try:
            # Get frame from queue with timeout to avoid blocking
            if not frame_queue.empty():
                image_data = frame_queue.get(timeout = 0.1)
                
                # Decode base64 image
                image_bytes = base64.b64decode(image_data.split(',')[1])
                image = Image.open(BytesIO(image_bytes))
                frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                
                # Convert color space for MediaPipe
                image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image_rgb.flags.writeable = False
                
                # Pose estimation
                results = local_pose.process(image_rgb)
                
                # Draw pose landmarks
                image_rgb.flags.writeable = True
                image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
                
                landmarks_data = None
                
                if results.pose_landmarks:
                    with lock:
                        latest_landmarks = results.pose_landmarks
                    
                    # Draw pose connections
                    mp_drawing.draw_landmarks(
                        image_bgr,
                        results.pose_landmarks,
                        mp_pose.POSE_CONNECTIONS,
                        landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style()
                    )
                    
                    # Highlight target landmarks
                    h, w, c = image_bgr.shape
                    for idx in TARGET_LANDMARKS:
                        landmark = results.pose_landmarks.landmark[idx]
                        cx, cy = int(landmark.x * w), int(landmark.y * h)
                        cv2.circle(image_bgr, (cx, cy), 8, (0, 0, 255), -1)
                        cv2.putText(image_bgr, str(idx), (cx + 10, cy - 10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                    
                    # Prepare landmarks data
                    landmarks_data = []
                    for landmark in results.pose_landmarks.landmark:
                        landmarks_data.append({
                            'x': float(landmark.x),
                            'y': float(landmark.y),
                            'z': float(landmark.z),
                            'visibility': float(landmark.visibility)
                        })
                    
                    # Record data if recording is active
                    if is_recording and start_time:
                        elapsed_time = (datetime.now() - start_time).total_seconds()
                        record = {
                            'timestamp': elapsed_time,
                            'landmarks': landmarks_data
                        }
                        with lock:
                            recorded_data.append(record)
                
                # Face detection: rPPG heart rate estimation
                face_result = mp_face.process(image_rgb)
                current_bpm = None
                
                if face_result.detections:
                    # Get first detected face bounding box
                    detection = face_result.detections[0]
                    bbox = detection.location_data.relative_bounding_box
                    
                    h, w, _ = frame.shape
                    x = int(bbox.xmin * w)
                    y = int(bbox.ymin * h)
                    box_w = int(bbox.width * w)
                    box_h = int(bbox.height * h)
                    
                    # Extract forehead region (upper 1/3 of face)
                    forehead_height = int(box_h / 3)
                    roi = frame[y:y+forehead_height, x:x+box_w]
                    
                    if roi.size > 0:
                        # Calculate mean green channel value (most sensitive to blood volume changes)
                        g_mean = np.mean(roi[:, :, 1])
                        g_values.append(g_mean)
                        
                        # Draw face bounding box
                        cv2.rectangle(image_bgr, (x, y), (x+box_w, y+box_h), (0, 255, 0), 2)
                        cv2.rectangle(image_bgr, (x, y), (x+box_w, y+forehead_height), (255, 0, 0), 2)
                        cv2.putText(image_bgr, "ROI", (x, y-10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                        
                        # Calculate heart rate every 8 seconds (240 frames at 30 fps)
                        window_size = fps * 8
                        if len(g_values) >= window_size:
                            heart_rate = calculate_heart_rate(g_values[-window_size:], fps)
                            
                            if heart_rate is not None:
                                # Smooth BPM using moving average
                                smoothed_bpm = smooth_bpm(heart_rate, bpm_history)
                                with lock:
                                    latest_bpm = round(smoothed_bpm, 1)
                                current_bpm = latest_bpm
                            
                            # Keep only last 10 seconds of data to prevent memory buildup
                            if len(g_values) > fps * 10:
                                g_values = g_values[-(fps * 10):]
                
                # Display heart rate on frame
                with lock:
                    if latest_bpm is not None:
                        cv2.putText(image_bgr, f"Heart Rate: {latest_bpm} BPM", 
                                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                    else:
                        cv2.putText(image_bgr, "Heart Rate: Detecting...", 
                                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
                
                # Encode processed image to base64
                _, buffer = cv2.imencode('.jpg', image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
                processed_image = base64.b64encode(buffer).decode('utf-8')
                
                result = {
                    'status': 'success',
                    'image': f'data:image/jpeg;base64,{processed_image}',
                    'landmarks': landmarks_data,
                    'bpm': latest_bpm if latest_bpm is not None else 0
                }
                
                # Update latest result
                with lock:
                    latest_result = result
                
                # Put result in queue (non-blocking)
                if not result_queue.full():
                    result_queue.put(result)
                
                # Clear frame queue marker
                frame_queue.task_done()
                
            else:
                # No frames to process, sleep briefly
                time.sleep(0.01)
                
        except queue.Empty:
            continue
        except Exception as e:
            print(f"[ERROR] Frame processing error: {e}")
            continue
    
    # Cleanup
    local_pose.close()
    mp_face.close()
    print("[INFO] Frame processing thread stopped")

def start_processing_thread():
    # Start background processing thread
    global processing_active, processing_thread
    
    if processing_thread is None or not processing_thread.is_alive():
        processing_active = True
        processing_thread = threading.Thread(target=process_frame_worker, daemon=True)
        processing_thread.start()
        print("[INFO] Processing thread started")

def stop_processing_thread():
    # Stop background processing thread
    global processing_active, processing_thread
    
    processing_active = False
    if processing_thread is not None:
        processing_thread.join(timeout=2)
        print("[INFO] Processing thread stopped")

@app.route('/')
def index():
    # Render main page
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    # Handle favicon requests to avoid 404 errors
    return Response(status=204)

@app.route('/start_processing', methods=['POST'])
def start_processing():
    # Start the async processing thread
    try:
        start_processing_thread()
        return jsonify({'status': 'success', 'message': '執行緒已啟動'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/process_frame', methods=['POST'])
def process_frame_route():
    # Receive frame from frontend and queue for async processing
    global latest_result
    
    try:
        data = request.get_json()
        image_data = data.get('image')
        
        if not image_data:
            return jsonify({'status': 'error', 'message': '沒有收到圖片資訊'})
        
        # Add frame to queue (non-blocking)
        if not frame_queue.full():
            frame_queue.put(image_data)
        else:
            # Queue is full, skip this frame to prevent memory buildup
            print("[WARNING] Frame queue full, skipping frame")
        
        # Return latest processed result immediately
        with lock:
            if latest_result is not None:
                return jsonify(latest_result)
            else:
                return jsonify({'status': 'processing', 'message': '處理中', 'bpm': 0})
        
    except Exception as e:
        print(f"[ERROR] process_frame_route: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/pose_data')
def pose_data():
    # Get current pose landmarks data
    global latest_landmarks
    
    with lock:
        if latest_landmarks is None:
            return jsonify({'status': 'no_data', 'message': '無法獲取資料'})
    
    try:
        landmarks = []
        with lock:
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

@app.route('/get_heart_rate')
def get_heart_rate():
    # Get current heart rate
    with lock:
        return jsonify({
            'status': 'success',
            'bpm': latest_bpm if latest_bpm is not None else 0,
            'detecting': latest_bpm is None
        })

@app.route('/start_recording', methods=['POST'])
def start_recording():
    # Start recording pose data
    global is_recording, recorded_data, start_time
    
    try:
        with lock:
            is_recording = True
            recorded_data = []
            start_time = datetime.now()
        
        return jsonify({'status': 'success', 'message': '開始記錄'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/stop_recording', methods=['POST'])
def stop_recording():
    # Stop recording and save data to Firebase
    global is_recording, recorded_data, start_time, latest_bpm
    
    try:
        with lock:
            if not is_recording:
                return jsonify({'status': 'error', 'message': '不在記錄狀態'})
            
            is_recording = False
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Prepare JSON data with heart rate
            json_data = {
                'recording_info': {
                    'timestamp': timestamp,
                    'total_frames': len(recorded_data),
                    'start_time': start_time.isoformat() if start_time else None,
                    'heart_rate_bpm': latest_bpm if latest_bpm is not None else 0
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
            
            # Save to Firebase
            db.child("pose_json").push(json_data)
            
            data_count = len(recorded_data)
            recorded_data = []
            start_time = None
        
        return jsonify({
            'status': 'success',
            'message': '記錄已經保存',
            'records': data_count,
            'heart_rate': latest_bpm if latest_bpm is not None else 0
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/recording_status')
def recording_status():
    # Get current recording status
    global is_recording, start_time, recorded_data
    
    with lock:
        status = {
            'is_recording': is_recording,
            'records_count': len(recorded_data)
        }
        
        if is_recording and start_time:
            elapsed = (datetime.now() - start_time).total_seconds()
            status['elapsed_time'] = round(elapsed, 1)
    
    return jsonify(status)

@app.route('/queue_status')
def queue_status():
    # Get queue status for monitoring
    return jsonify({
        'frame_queue_size': frame_queue.qsize(),
        'result_queue_size': result_queue.qsize(),
        'processing_active': processing_active,
        'heart_rate_samples': len(g_values)
    })

# Start processing thread when app starts
start_processing_thread()

if __name__ == '__main__':
    try:
        app.run(debug=False, threaded=True, host='0.0.0.0', port=5000)
    finally:
        # Cleanup on shutdown
        stop_processing_thread()