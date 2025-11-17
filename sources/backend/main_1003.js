let cameraActive = false;
let recording = false;
let updateInterval = null;
let chartData = {
    timestamps: [],
    leftElbow: [],
    rightElbow: [],
    leftWrist: [],
    rightWrist: [],
    startTime: null
};

const MAX_DATA_POINTS = 50;

function toggleCamera() {
    const btn = document.getElementById('btnCamera');
    
    if (!cameraActive) {
        btn.disabled = true;
        btn.innerHTML = 'Camera 啟動中­<span class="loading"></span>';
        
        fetch('/start_camera', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    cameraActive = true;
                    document.getElementById('videoFeed').src = '/video_feed';
                    document.getElementById('videoFeed').style.display = 'block';
                    document.getElementById('videoPlaceholder').style.display = 'none';
                    btn.innerHTML = '關閉鏡頭';
                    btn.disabled = false;
                    document.getElementById('btnRecord').disabled = false;
                    showStatus('鏡頭已經啟動', 'active');
                    
                    // update 3D visualization and chart
                    startUpdating();
                }
            })
            .catch(error => {
                console.error('Error:', error);
                btn.innerHTML = '開啟鏡頭';
                btn.disabled = false;
                showStatus('無法啟動鏡頭', 'error');
            });
    } else {
        fetch('/stop_camera', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                cameraActive = false;
                document.getElementById('videoFeed').style.display = 'none';
                document.getElementById('videoPlaceholder').style.display = 'block';
                btn.innerHTML = '開啟鏡頭';
                document.getElementById('btnRecord').disabled = true;
                document.getElementById('btnStop').disabled = true;
                showStatus('鏡頭已經關閉', '');
                stopUpdating();
                recording = false;
            });
    }
}

function startRecording() {
    fetch('/start_recording', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                recording = true;
                document.getElementById('btnRecord').disabled = true;
                document.getElementById('btnStop').disabled = false;
                showStatus('開始記錄資料­', 'recording');
                
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
    updateInterval = setInterval(updateVisualizations, 100);
}

function stopUpdating() {
    if (updateInterval) {
        clearInterval(updateInterval);
        updateInterval = null;
    }
}

function updateVisualizations() {
    fetch('/pose_data')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success' && data.data) {
                update3DPlots(data.data);
                updateLineChart(data.data);
            }
        })
        .catch(error => console.error('Error fetching pose data:', error));
}

function update3DPlots(landmarks) {
    // prepare 3D pose data: invert y axis for correct orientation
    const x = landmarks.map(l => l.x);
    const y = landmarks.map(l => 1 - l.y);  // invert y-axis
    const z = landmarks.map(l => -l.z);     // invert z-axis

    // MediaPipe human pose connections
    const connections = [
        [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
        [11, 23], [12, 24], [23, 24], [23, 25], [24, 26],
        [25, 27], [26, 28], [27, 29], [28, 30], [29, 31], [30, 32]
    ];

    // create lines for connections
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

    // View 1: Front view (looking at XY plane)
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

    // View 2: Side view (looking at ZY plane from right side)
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

    // Use Plotly.react with config to disable interactions
    const config = {
        staticPlot: false,
        displayModeBar: false,
        responsive: true
    };

    Plotly.react('plot3d_view1', [trace_lines, trace_points], layout1, config);
    Plotly.react('plot3d_view2', [trace_lines, trace_points], layout2, config);
}

function updateLineChart(landmarks) {
    // ensure required landmarks to get
    if (!landmarks || !landmarks[13] || !landmarks[14] || !landmarks[15] || !landmarks[16]) {
        return; 
    }

    const currentTime = Date.now() / 1000;
    if (!chartData.startTime) {
        chartData.startTime = currentTime;
    }
    const elapsedTime = currentTime - chartData.startTime;

    // hand keypoints tracking: y-coordinate inverted for correct display
    const leftElbow_y  = (1 - landmarks[13].y) * 100;
    const rightElbow_y = (1 - landmarks[14].y) * 100;
    const leftWrist_y  = (1 - landmarks[15].y) * 100;
    const rightWrist_y = (1 - landmarks[16].y) * 100;

    // add new data points (restrict to MAX_DATA_POINTS)
    /*
    Plotly.extendTraces('lineChart', {
        x: [[elapsedTime], [elapsedTime], [elapsedTime], [elapsedTime]],
        y: [[leftElbow_y], [rightElbow_y], [leftWrist_y], [rightWrist_y]]
    }, [0, 1, 2, 3], MAX_DATA_POINTS);
    */
   Plotly.extendTraces('lineChart', {
        x: [[elapsedTime], [elapsedTime], [elapsedTime], [elapsedTime]],
        y: [[leftElbow_y], [rightElbow_y], [leftWrist_y], [rightWrist_y]]
    }, [0, 1, 2, 3]);

    // keep X axis to show final 10 seconds
    Plotly.relayout('lineChart', {
        // 'xaxis.range': [Math.max(0, elapsedTime - 10), elapsedTime + 0.5]
        'xaxis.range': [Math.max(0, elapsedTime - 10), elapsedTime]
    });
}

// initailize empty plots
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
    
    // Front view initialization
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
    
    // Side view initialization
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