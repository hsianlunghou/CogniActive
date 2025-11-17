let cameraActive = false;
let recording = false;
let updateInterval = null;
let videoStream = null;
let videoElement = null;
let canvasElement = null;
let chartData = {
    timestamps: [],
    leftElbow: [],
    rightElbow: [],
    leftWrist: [],
    rightWrist: [],
    startTime: null
};

const MAX_DATA_POINTS = 50;

// per 100 ms send one frame (value set 100), but system configuration need to 1 second (value set 1000)
const FRAME_INTERVAL = 100; 

function toggleCamera() {
    const btn = document.getElementById('btnCamera');
    
    if (!cameraActive) {
        btn.disabled = true;
        btn.innerHTML = 'Camera 啟動中<span class="loading"></span>';
        
        // ask the user to permission of camera
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
            
            // create video element to show camera stream
            videoElement = document.createElement('video');
            videoElement.srcObject = stream;
            videoElement.autoplay = true;
            videoElement.style.display = 'none';
            document.body.appendChild(videoElement);
            
            // create canvas (640 * 480, 320 * 240)
            canvasElement = document.createElement('canvas');
            canvasElement.width = 320;
            canvasElement.height = 240;
            
            // show processing video
            const videoFeed = document.getElementById('videoFeed');
            videoFeed.style.display = 'block';
            document.getElementById('videoPlaceholder').style.display = 'none';
            
            btn.innerHTML = '關閉鏡頭';
            btn.disabled = false;
            document.getElementById('btnRecord').disabled = false;
            showStatus('鏡頭已經啟動', 'active');
            
            // start processing frames
            startProcessingFrames();
            startUpdating();
        })
        .catch(error => {
            console.error('Error accessing camera:', error);
            btn.innerHTML = '開啟鏡頭';
            btn.disabled = false;
            showStatus('無法啟動鏡頭，請確認權限設定', 'error');
        });
    } else {
        stopCamera();
        btn.innerHTML = '開啟鏡頭';
        showStatus('鏡頭已經關閉', '');
    }
}

function stopCamera() {
    cameraActive = false;
    
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

function startProcessingFrames() {
    if (!cameraActive) return;
    
    const ctx = canvasElement.getContext('2d');
    const videoFeed = document.getElementById('videoFeed');
    
    function processFrame() {
        if (!cameraActive || !videoElement) return;
        
        // video to canvas
        ctx.drawImage(videoElement, 0, 0, canvasElement.width, canvasElement.height);
        
        // convert to base64
        const imageData = canvasElement.toDataURL('image/jpeg', 0.8);
        
        // return backend
        fetch('/process_frame', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ image: imageData })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success' && data.image) {
                // show processed image
                videoFeed.src = data.image;
                
                // update charts
                if (data.landmarks) {
                    updateLineChart(data.landmarks);
                    update3DPlots(data.landmarks);
                }
            }
        })
        .catch(error => console.error('Error processing frame:', error));
        
        // process next frame
        setTimeout(processFrame, FRAME_INTERVAL);
    }
    
    processFrame();
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
                
                // reset chart data
                chartData = {
                    timestamps: [],
                    leftElbow: [],
                    rightElbow: [],
                    leftWrist: [],
                    rightWrist: [],
                    startTime: null
                };
            }
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
                showStatus('停止記錄資料', 'active');
            }
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
    // no need for extra update interval as we update during frame processing
}

function stopUpdating() {
    if (updateInterval) {
        clearInterval(updateInterval);
        updateInterval = null;
    }
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
            text: 'Front View',
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
            text: 'Side View',
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

function updateLineChart(landmarks) {
    if (!landmarks || !landmarks[13] || !landmarks[14] || !landmarks[15] || !landmarks[16]) {
        return;
    }

    const currentTime = Date.now() / 1000;
    if (!chartData.startTime) {
        chartData.startTime = currentTime;
    }
    const elapsedTime = currentTime - chartData.startTime;

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
}

// Initialize Empty Plots
window.onload = function() {
    const emptyLayout = {
        xaxis: { 
            title: 'Time (seconds)',
            range: [0, 10],
            showgrid: false
        },
        yaxis: { 
            title: 'Angle Position',
            range: [0, 100],
            showgrid: false
        },
        margin: { l: 50, r: 30, t: 30, b: 50 },
        height: 300
    };
    Plotly.newPlot(
        'lineChart', [
            { x: [], y: [], mode: 'lines', name: 'Left Elbow' },
            { x: [], y: [], mode: 'lines', name: 'Right Elbow' },
            { x: [], y: [], mode: 'lines', name: 'Left Wrist' },
            { x: [], y: [], mode: 'lines', name: 'Right Wrist' }
        ], emptyLayout);
    
    const empty3DLayout1 = {
        scene: {
            camera: {
                eye: { x: 0, y: 0, z: 1.5 },
                up: { x: 0, y: 1, z: 0 }
            },
            xaxis: { range: [0, 1], showticklabels: false },
            yaxis: { range: [0, 1], showticklabels: false },
            zaxis: { range: [-0.5, 0.5], showticklabels: false },
            aspectmode: 'manual',
            aspectratio: { x: 1, y: 1, z: 0.5 }
        },
        margin: { l: 0, r: 0, t: 30, b: 0 },
        height: 280,
        title: { text: 'Front View', font: { size: 12 } }
    };
    
    const empty3DLayout2 = {
        scene: {
            camera: {
                eye: { x: 1.5, y: 0, z: 0 },
                up: { x: 0, y: 1, z: 0 }
            },
            xaxis: { range: [0, 1], showticklabels: false },
            yaxis: { range: [0, 1], showticklabels: false },
            zaxis: { range: [-0.5, 0.5], showticklabels: false },
            aspectmode: 'manual',
            aspectratio: { x: 1, y: 1, z: 0.5 }
        },
        margin: { l: 0, r: 0, t: 30, b: 0 },
        height: 280,
        title: { text: 'Side View', font: { size: 12 } }
    };
    
    const config = { displayModeBar: false };
    Plotly.newPlot('plot3d_view1', [], empty3DLayout1, config);
    Plotly.newPlot('plot3d_view2', [], empty3DLayout2, config);
};