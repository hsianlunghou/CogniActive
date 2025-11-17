let cameraActive = false;
let recording = false;
let updateInterval = null;
let videoStream = null;
let videoElement = null;
let canvasElement = null;
let processingFrame = false;
let chartData = {
    timestamps: [],
    leftElbow: [],
    rightElbow: [],
    leftWrist: [],
    rightWrist: [],
    startTime: null
};

// Movement tracking
let motionTracker = {
    history: [],            // Save history data
    maxHistory: 100,        // keep 100 datapoints recently
    metrics: {
        leftElbowAngle: null,
        rightElbowAngle: null,
        speed: null,
        acceleration: null
    },
    baseline: null,          // standard behavior
    lastUpdate: null
};

const MAX_DATA_POINTS = 50;

// Frame interval: 100 ms to reduce server load (10 FPS)
const FRAME_INTERVAL = 100;

// Maximum attempts for processing
const MAX_RETRY_ATTEMPTS = 3;

function toggleCamera() {
    const btn = document.getElementById('btnCamera');
    
    if (!cameraActive) {
        btn.disabled = true;
        btn.innerHTML = 'Camera 啟動中<span class="loading"></span>';
        
        // Request user camera permission
        navigator.mediaDevices.getUserMedia({ 
            video: { 
                width: 640, 
                height: 480,
                facingMode: 'user'
            } 
        })
        .then(stream => {
            videoStream = stream;
            cameraActive = true;
            
            // Create video element to display camera stream
            videoElement = document.createElement('video');
            videoElement.srcObject = stream;
            videoElement.autoplay = true;
            videoElement.style.display = 'none';
            document.body.appendChild(videoElement);
            
            // Create canvas for video stream (reduced resolution to save bandwidth)
            canvasElement = document.createElement('canvas');
            canvasElement.width = 320;  // Reduced from 640
            canvasElement.height = 240; // Reduced from 480
            
            // Display processed video
            const videoFeed = document.getElementById('videoFeed');
            videoFeed.style.display = 'block';
            document.getElementById('videoPlaceholder').style.display = 'none';
            
            btn.innerHTML = '關閉鏡頭';
            btn.disabled = false;
            document.getElementById('btnRecord').disabled = false;
            showStatus('鏡頭已經啟動', 'active');
            
            // Initialize processing thread on backend
            initProcessingThread();
            
            // Start processing frames
            startProcessingFrames();
            startUpdating();
        })
        .catch(error => {
            console.error('Error accessing camera:', error);
            btn.innerHTML = '開啟鏡頭';
            btn.disabled = false;
            showStatus('無法啟動鏡頭,請確認權限設定', 'error');
        });
    } else {
        stopCamera();
        btn.innerHTML = '開啟鏡頭';
        showStatus('鏡頭已經關閉', '');
    }
}

function stopCamera() {
    cameraActive = false;
    processingFrame = false;
    
    if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop());
        videoStream = null;
    }
    
    if (videoElement) {
        videoElement.remove();
        videoElement = null;
    }
    
    document.getElementById('videoFeed').style.display = 'none';
    document.getElementById('videoPlaceholder').style.display = 'block';
    document.getElementById('btnRecord').disabled = true;
    document.getElementById('btnStop').disabled = true;
    
    stopUpdating();
    recording = false;
}

function initProcessingThread() {
    // Initialize backend processing thread
    fetch('/start_processing', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            console.log('[INFO] Processing thread initialized:', data.message);
        })
        .catch(error => {
            console.error('[ERROR] Failed to initialize processing thread:', error);
        });
}

function goBack() {
    // Check the current status
    if (cameraActive || recording) {
        if (!confirm('正在進行訓練，確定要返回首頁嗎？')) {
            return;
        }
        // Stop camera and recording
        stopCamera();
    }
    
    // return to main page
    window.location.href = "/";
}

function startProcessingFrames() {
    if (!cameraActive) return;
    
    const ctx = canvasElement.getContext('2d');
    const videoFeed = document.getElementById('videoFeed');
    
    function processFrame() {
        if (!cameraActive || !videoElement) return;
        
        // Skip if already processing a frame (prevent queue buildup)
        if (processingFrame) {
            setTimeout(processFrame, FRAME_INTERVAL);
            return;
        }
        
        processingFrame = true;
        
        // Draw video frame to canvas
        ctx.drawImage(videoElement, 0, 0, canvasElement.width, canvasElement.height);
        
        // Convert to base64 with compression
        const imageData = canvasElement.toDataURL('image/jpeg', 0.6); // Reduced quality to 0.6
        
        // Send to backend for processing
        sendFrameWithRetry(imageData, 0)
            .then(data => {
                if (data.status === 'success' && data.image) {
                    // Display processed image
                    videoFeed.src = data.image;
                    
                    // Update visualizations with pose data
                    if (data.landmarks) {
                        updateLineChart(data.landmarks);
                        update3DPlots(data.landmarks);
                    }
                }
            })
            .catch(error => {
                console.error('[ERROR] Frame processing failed:', error);
            })
            .finally(() => {
                processingFrame = false;
                // Schedule next frame
                setTimeout(processFrame, FRAME_INTERVAL);
            });
    }
    
    // Start frame processing loop
    processFrame();
}

function sendFrameWithRetry(imageData, attemptCount) {
    // Retry mechanism to handle temporary network issues
    return fetch('/process_frame', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ image: imageData })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .catch(error => {
        if (attemptCount < MAX_RETRY_ATTEMPTS) {
            console.warn(`[WARN] Retry attempt ${attemptCount + 1}/${MAX_RETRY_ATTEMPTS}`);
            // Wait briefly before retry
            return new Promise(resolve => setTimeout(resolve, 100))
                .then(() => sendFrameWithRetry(imageData, attemptCount + 1));
        } else {
            throw error;
        }
    });
}

function startRecording() {
    fetch('/start_recording', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                recording = true;
                document.getElementById('btnRecord').disabled = true;
                document.getElementById('btnStop').disabled = false;
                showStatus('開始記錄資料', 'recording');
                
                // Reset chart data
                chartData = {
                    timestamps: [],
                    leftElbow: [],
                    rightElbow: [],
                    leftWrist: [],
                    rightWrist: [],
                    startTime: null
                };

                motionTracker = {
                    history: [],
                    maxHistory: 100,
                    metrics: {
                        reactionTime: null,
                        coordination: null,
                        speed: null,
                        acceleration: null,
                        accuracy: null
                    },
                    baseline: null,
                    lastUpdate: null
                };
            }
        })
        .catch(error => {
            console.error('[ERROR] Start recording failed:', error);
            showStatus('記錄啟動失敗', 'error');
        });
}

function stopRecording() {
    fetch('/stop_recording', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                recording = false;
                document.getElementById('btnRecord').disabled = false;
                document.getElementById('btnStop').disabled = true;
                showStatus(`停止記錄資料 (共 ${data.records} 筆)`, 'active');
            }
        })
        .catch(error => {
            console.error('[ERROR] Stop recording failed:', error);
            showStatus('記錄停止失敗', 'error');
        });
}

function showStatus(message, type) {
    const status = document.getElementById('status');
    status.textContent = message;
    status.className = 'status ' + type;
    status.style.display = 'block';
    
    if (type !== 'recording') {
        setTimeout(() => {
            status.style.display = 'none';
        }, 3000);
    }
}

function startUpdating() {
    // Monitor queue status periodically
    updateInterval = setInterval(checkQueueStatus, 5000); // Every 5 seconds
}

function stopUpdating() {
    if (updateInterval) {
        clearInterval(updateInterval);
        updateInterval = null;
    }
}

function checkQueueStatus() {
    // Monitor backend queue status for debugging
    fetch('/queue_status')
        .then(response => response.json())
        .then(data => {
            console.log('[INFO] Queue status:', data);
            // Alert if queue is building up
            if (data.frame_queue_size > 2) {
                console.warn('[WARN] Frame queue building up:', data.frame_queue_size);
            }
        })
        .catch(error => {
            console.error('[ERROR] Failed to check queue status:', error);
        });
}

function update3DPlots(landmarks) {
    const x = landmarks.map(l => l.x);
    const y = landmarks.map(l => 1 - l.y);
    const z = landmarks.map(l => -l.z);

    const connections = [
        [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
        [11, 23], [12, 24], [23, 24], [23, 25], [24, 26],
        [25, 27], [26, 28], [27, 29], [28, 30], [29, 31], [30, 32]
    ];

    const lines_x = [], lines_y = [], lines_z = [];
    connections.forEach(conn => {
        lines_x.push(x[conn[0]], x[conn[1]], null);
        lines_y.push(y[conn[0]], y[conn[1]], null);
        lines_z.push(z[conn[0]], z[conn[1]], null);
    });

    const trace_points = {
        x: x, y: y, z: z,
        mode: 'markers',
        type: 'scatter3d',
        marker: { size: 5, color: 'rgb(0, 200, 100)' },
        showlegend: false
    };

    const trace_lines = {
        x: lines_x, y: lines_y, z: lines_z,
        mode: 'lines',
        type: 'scatter3d',
        line: { color: 'rgb(100, 150, 250)', width: 3 },
        showlegend: false
    };

    const layout1 = {
        scene: {
            camera: {
                eye: { x: 0, y: 0, z: 1.5 },
                up: { x: 0, y: 1, z: 0 },
                center: { x: 0, y: 0, z: 0 }
            },
            xaxis: { 
                range: [0, 1],
                title: '',
                showticklabels: false,
                showgrid: true
            },
            yaxis: { 
                range: [0, 1],
                title: '',
                showticklabels: false,
                showgrid: true
            },
            zaxis: { 
                range: [-0.5, 0.5],
                title: '',
                showticklabels: false,
                showgrid: true
            },
            aspectmode: 'manual',
            aspectratio: { x: 1, y: 1, z: 0.5 }
        },
        margin: { l: 0, r: 0, t: 30, b: 0 },
        showlegend: false,
        height: 280,
        title: {
            text: '正面',
            font: { size: 12 }
        }
    };

    const layout2 = {
        scene: {
            camera: {
                eye: { x: 1.5, y: 0, z: 0 },
                up: { x: 0, y: 1, z: 0 },
                center: { x: 0, y: 0, z: 0 }
            },
            xaxis: { 
                range: [0, 1],
                title: '',
                showticklabels: false,
                showgrid: true
            },
            yaxis: { 
                range: [0, 1],
                title: '',
                showticklabels: false,
                showgrid: true
            },
            zaxis: { 
                range: [-0.5, 0.5],
                title: '',
                showticklabels: false,
                showgrid: true
            },
            aspectmode: 'manual',
            aspectratio: { x: 1, y: 1, z: 0.5 }
        },
        margin: { l: 0, r: 0, t: 30, b: 0 },
        showlegend: false,
        height: 280,
        title: {
            text: '側面',
            font: { size: 12 }
        }
    };

    const config = {
        staticPlot: false,
        displayModeBar: false,
        responsive: true
    };

    Plotly.react('plot3d_view1', [trace_lines, trace_points], layout1, config);
    Plotly.react('plot3d_view2', [trace_lines, trace_points], layout2, config);
}

/* Behaviorial analysis */

// Movement distance
function calculateDistance(current, previous) {
    const dx = current.leftWrist.x - previous.leftWrist.x;
    const dy = current.leftWrist.y - previous.leftWrist.y;
    return Math.sqrt(dx * dx + dy * dy);
}

// Movement speed (seconds)
function calculateSpeed(current, previous, deltaT) {
    if (deltaT === 0) return 0;
    const distance = calculateDistance(current, previous);
    return distance / deltaT;
}

// Acceleration
function calculateAcceleration(currentSpeed, previousSpeed, deltaT) {
    if (deltaT === 0) return 0;
    return (currentSpeed - previousSpeed) / deltaT;
}

// Joint angle calculation 

function calculateAngle(shoulder, elbow, wrist) {
    // calculate vector
    const vector1 = {
        x: shoulder.x - elbow.x,
        y: shoulder.y - elbow.y
    };
    
    const vector2 = {
        x: wrist.x - elbow.x,
        y: wrist.y - elbow.y
    };
    
    // count radian
    const dotProduct = vector1.x * vector2.x + vector1.y * vector2.y;
    const magnitude1 = Math.sqrt(vector1.x * vector1.x + vector1.y * vector1.y);
    const magnitude2 = Math.sqrt(vector2.x * vector2.x + vector2.y * vector2.y);
    
    const cosAngle = dotProduct / (magnitude1 * magnitude2);
    const angleRad = Math.acos(Math.max(-1, Math.min(1, cosAngle)));
    
    // convert to angle
    return (angleRad * 180 / Math.PI).toFixed(1);
}

// Update metrics
function updateMotionMetrics(landmarks) {
    const currentTime = Date.now() / 1000;
    
    if (!chartData.startTime) {
        chartData.startTime = currentTime;
    }
    const elapsedTime = currentTime - chartData.startTime;
    
    // Create current datapoints
    const current = {
        timestamp: currentTime,
        elapsed: elapsedTime,
        landmarks: {
            leftShoulder: { 
                x: landmarks[11].x * 100, 
                y: (1 - landmarks[11].y) * 100 
            },
            rightShoulder: { 
                x: landmarks[12].x * 100, 
                y: (1 - landmarks[12].y) * 100 
            },
            leftElbow: { 
                x: landmarks[13].x * 100, 
                y: (1 - landmarks[13].y) * 100 
            },
            rightElbow: { 
                x: landmarks[14].x * 100, 
                y: (1 - landmarks[14].y) * 100 
            },
            leftWrist: { 
                x: landmarks[15].x * 100, 
                y: (1 - landmarks[15].y) * 100 
            },
            rightWrist: { 
                x: landmarks[16].x * 100, 
                y: (1 - landmarks[16].y) * 100 
            }
        },
        derivatives: {
            distance: 0,
            speed: 0,
            acceleration: 0
        },
        angles: {
            leftElbow: 0,
            rightElbow: 0
        }
    };
    
    // Calculate joint angle
    current.angles.leftElbow = calculateAngle(
        current.landmarks.leftShoulder,
        current.landmarks.leftElbow,
        current.landmarks.leftWrist
    );
    
    current.angles.rightElbow = calculateAngle(
        current.landmarks.rightShoulder,
        current.landmarks.rightElbow,
        current.landmarks.rightWrist
    );

    // Set standard behavior
    if (!motionTracker.baseline && motionTracker.history.length === 5) {
        motionTracker.baseline = current.landmarks;
    }
    
    // Use history data to calculate
    if (motionTracker.history.length > 0) {
        const previous = motionTracker.history[motionTracker.history.length - 1];
        const deltaT = currentTime - previous.timestamp;
        
        if (deltaT > 0) {
            current.derivatives.distance = calculateDistance(current.landmarks, previous.landmarks);
            current.derivatives.speed = calculateSpeed(current.landmarks, previous.landmarks, deltaT);
            
            if (previous.derivatives && previous.derivatives.speed !== null) {
                current.derivatives.acceleration = calculateAcceleration(
                    current.derivatives.speed,
                    previous.derivatives.speed,
                    deltaT
                );
            }
        }
    }
    
    // Add history records
    motionTracker.history.push(current);
    if (motionTracker.history.length > motionTracker.maxHistory) {
        motionTracker.history.shift();
    }
    
    // Update metrics
    motionTracker.metrics = {
        leftElbowAngle: current.angles.leftElbow,
        rightElbowAngle: current.angles.rightElbow,
        speed: current.derivatives.speed.toFixed(2),
        acceleration: current.derivatives.acceleration.toFixed(2),
    };
    
    // Update to show
    updateMetricsDisplay();
}

function updateMetricsDisplay() {
    const metrics = motionTracker.metrics;
    
    // Update left elbow
    const leftAngleEl = document.getElementById('metricLeftAngle');
    if (leftAngleEl) {
        leftAngleEl.textContent = metrics.leftElbowAngle;
    }
    
    // Update right elbow
    const rightAngleEl = document.getElementById('metricRightAngle');
    if (rightAngleEl) {
        rightAngleEl.textContent = metrics.rightElbowAngle;
    }
    
    // Update speed
    const speedEl = document.getElementById('metricSpeed');
    if (speedEl) {
        speedEl.textContent = `${metrics.speed}`;
    }
    
    // Update acceleration
    const accelEl = document.getElementById('metricAcceleration');
    if (accelEl) {
        accelEl.textContent = `${metrics.acceleration}`;
    }
    
}

function updateLineChart(landmarks) {
    if (!landmarks || !landmarks[13] || !landmarks[14] || !landmarks[15] || !landmarks[16]) {
        return;
    }

    const currentTime = Date.now() / 1000;
    if (!chartData.startTime) {
        chartData.startTime = currentTime;
    }
    const elapsedTime = currentTime - chartData.startTime;

    // Convert to the coordinate location (observe vertical movement)
    const leftElbow_y  = (1 - landmarks[13].y) * 100;
    const rightElbow_y = (1 - landmarks[14].y) * 100;
    const leftWrist_y  = (1 - landmarks[15].y) * 100;
    const rightWrist_y = (1 - landmarks[16].y) * 100;

    Plotly.extendTraces('lineChart', {
        x: [[elapsedTime], [elapsedTime], [elapsedTime], [elapsedTime]],
        y: [[leftElbow_y], [rightElbow_y], [leftWrist_y], [rightWrist_y]]
    }, [0, 1, 2, 3]);

    Plotly.relayout('lineChart', {
        'xaxis.range': [Math.max(0, elapsedTime - 10), elapsedTime]
    });

    updateMotionMetrics(landmarks);
}

// Initialize empty plots on page load
window.onload = function() {
    const emptyLayout = {
        xaxis: { 
            title: '時間戳記',
            range: [0, 10],
            showgrid: false
        },
        yaxis: { 
            title: '肘腕垂直移動變化',
            range: [0, 100],
            showgrid: false
        },
        margin: { l: 50, r: 30, t: 30, b: 50 },
        height: 300
    };
    Plotly.newPlot(
        'lineChart', [
            { x: [], y: [], mode: 'lines', name: '左手肘' },
            { x: [], y: [], mode: 'lines', name: '右手肘' },
            { x: [], y: [], mode: 'lines', name: '左手腕' },
            { x: [], y: [], mode: 'lines', name: '右手腕' }
        ], emptyLayout);
    
    const emptyTrace = {
        type: 'scatter3d',
        mode: 'markers',
        x: [0],
        y: [0],
        z: [0],
        marker: {
            size: 0.1,
            color: 'rgba(0,0,0,0)'
        }
    };

    const empty3DLayout1 = {
        scene: {
            camera: {
                eye: { x: 0, y: 0, z: 1.5 },
                up: { x: 0, y: 1, z: 0 }
            },
            xaxis: { range: [0, 1], showticklabels: false, title: '' },
            yaxis: { range: [0, 1], showticklabels: false, title: '' },
            zaxis: { range: [-0.5, 0.5], showticklabels: false, title: '' },
            aspectmode: 'manual',
            aspectratio: { x: 1, y: 1, z: 0.5 }
        },
        margin: { l: 0, r: 0, t: 30, b: 0 },
        height: 280,
        title: { text: '正面', font: { size: 12 } }
    };
    
    const empty3DLayout2 = {
        scene: {
            camera: {
                eye: { x: 1.5, y: 0, z: 0 },
                up: { x: 0, y: 1, z: 0 }
            },
            xaxis: { range: [0, 1], showticklabels: false, title: '' },
            yaxis: { range: [0, 1], showticklabels: false, title: '' },
            zaxis: { range: [-0.5, 0.5], showticklabels: false, title: '' },
            aspectmode: 'manual',
            aspectratio: { x: 1, y: 1, z: 0.5 }
        },
        margin: { l: 0, r: 0, t: 30, b: 0 },
        height: 280,
        title: { text: '側面', font: { size: 12 } }
    };
    
    const config = { displayModeBar: false };
    Plotly.newPlot('plot3d_view1', [emptyTrace], empty3DLayout1, config);
    Plotly.newPlot('plot3d_view2', [emptyTrace], empty3DLayout2, config);
};
