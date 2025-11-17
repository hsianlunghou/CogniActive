import tkinter as tk
import cv2
import time
import numpy as np
import threading

from tkinter import ttk
from PIL import Image, ImageTk
from collections import deque
from scipy import signal

# User Interface 
class HeartRateMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("Non-contact Heart Rate Monitor")
        self.root.geometry("1000x700")
        self.root.configure(bg='#2c3e50')
        
        # Camera and Detection 
        self.camera = None
        self.is_running = False
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        # Heart Rate Calculation
        '''
            buffered size need to add certain amount for analysis
        '''
        self.buffer_size = 300  
        self.data_buffer = deque(maxlen = self.buffer_size)

        # Sampling
        self.times = deque(maxlen = self.buffer_size)
        self.fps = 25
        
        # Store Signal Data
        self.freqs = []
        self.fft_spectrum = []

        # Store BPM Data
        self.bpm = 0
        self.bpm_history = deque(maxlen = 30)  
        self.bpm_smooth = deque(maxlen = 5)    
        
        # Signal Quality 
        self.signal_quality = 0
        self.last_valid_bpm = 0

        # Threading Operations
        self.lock = threading.Lock()

        # Per Frame for FPS
        self.last_frame_time = time.time()
        self.frame_times = deque(maxlen = 30)
        self.actual_fps = 0

        # Visualization (In 5 Seconds)
        self.spectrum_freqs = []
        self.spectrum_power = []
        self.waveform_data = deque(maxlen = 150) 
        self.waveform_times = deque(maxlen = 150)

        # Create GUI
        self.create_widgets()

    def create_widgets(self):
        # Title 
        title_frame = tk.Frame(self.root, bg = '#34495e', height=60)
        title_frame.pack(fill = tk.X, padx = 10, pady = (10, 5))
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame, 
            text = "❤️ Non Contact Heart Rate Monitor", 
            font = ('Arial', 20, 'bold'),
            bg = '#34495e',
            fg = '#ecf0f1'
        )
        title_label.pack(expand = True)
        
        # Main 
        content_frame = tk.Frame(self.root, bg = '#2c3e50')
        content_frame.pack(fill = tk.BOTH, expand = True, padx = 10, pady = 5)
        
        # Video Panel
        left_panel = tk.Frame(content_frame, bg='#34495e', width=640)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        self.video_label = tk.Label(left_panel, bg='#000000')
        self.video_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Control Panel
        right_panel_container = tk.Frame(content_frame, bg = '#34495e', width=300)
        right_panel_container.pack(side = tk.RIGHT, fill = tk.BOTH, padx = (5, 0))
        right_panel_container.pack_propagate(False)

        # Create Canvas for Scrolling
        canvas = tk.Canvas(right_panel_container, bg = '#34495e', highlightthickness = 0)
        scrollbar = tk.Scrollbar(right_panel_container, orient = "vertical", command = canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg = '#34495e')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window = scrollable_frame, anchor = "nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side = "left", fill = "both", expand = True)
        scrollbar.pack(side = "right", fill = "y")

        # Enable Scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        right_panel = scrollable_frame  
                
        # Heart Rate Display
        hr_frame = tk.Frame(right_panel, bg = '#e74c3c', height = 150)
        hr_frame.pack(fill = tk.X, padx = 10, pady = 10)
        hr_frame.pack_propagate(False)
        
        tk.Label(
            hr_frame, 
            text = "Current Heart Rate", 
            font = ('Arial', 12),
            bg = '#e74c3c',
            fg = 'white'
        ).pack(pady = (10, 0))
        
        self.bpm_label = tk.Label(
            hr_frame,
            text = "-- BPM",
            font = ('Arial', 40, 'bold'),
            bg = '#e74c3c',
            fg = 'white'
        )
        self.bpm_label.pack(pady = 10)
        
        # Status 
        status_frame = tk.Frame(right_panel, bg = '#34495e')
        status_frame.pack(fill = tk.X, padx = 10, pady = 5)
        
        tk.Label(
            status_frame,
            text = "Status:",
            font = ('Arial', 10),
            bg = '#34495e',
            fg = '#ecf0f1'
        ).pack(side = tk.LEFT)
        
        self.status_label = tk.Label(
            status_frame,
            text = "● Not Started",
            font = ('Arial', 10, 'bold'),
            bg = '#34495e',
            fg = '#95a5a6'
        )
        self.status_label.pack(side = tk.LEFT, padx = 5)
        
        # FPS Display
        fps_frame = tk.Frame(right_panel, bg = '#34495e')
        fps_frame.pack(fill = tk.X, padx = 10, pady = 5)

        tk.Label(
            fps_frame,
            text = "Camera FPS:",
            font = ('Arial', 9),
            bg = '#34495e',
            fg = '#ecf0f1'
        ).pack(side = tk.LEFT)

        self.fps_label = tk.Label(
            fps_frame,
            text = "--",
            font = ('Arial', 9, 'bold'),
            bg = '#34495e',
            fg = '#3498db'
        )
        self.fps_label.pack(side = tk.LEFT, padx = 5)

        # Frequency Spectrum Display
        spectrum_frame = tk.LabelFrame(
            right_panel,
            text = "Frequency Spectrum",
            font = ('Arial', 10, 'bold'),
            bg = '#34495e',
            fg = '#ecf0f1',
            bd = 2
        )
        spectrum_frame.pack(fill = tk.X, padx = 10, pady = 5)

        self.spectrum_canvas = tk.Canvas(
            spectrum_frame,
            width = 280,
            height = 100,
            bg = '#2c3e50',
            highlightthickness = 0
        )
        self.spectrum_canvas.pack(padx = 5, pady = 5)

        # Signal Waveform Display
        waveform_frame = tk.LabelFrame(
            right_panel,
            text = "Signal Waveform",
            font = ('Arial', 10, 'bold'),
            bg = '#34495e',
            fg = '#ecf0f1',
            bd = 2
        )
        waveform_frame.pack(fill = tk.X, padx = 10, pady = 5)

        self.waveform_canvas = tk.Canvas(
            waveform_frame,
            width = 280,
            height = 80,
            bg = '#2c3e50',
            highlightthickness = 0
        )
        self.waveform_canvas.pack(padx = 5, pady = 5)

        # Statistics Display
        stats_frame = tk.LabelFrame(
            right_panel,
            text = "Statistics",
            font = ('Arial', 11, 'bold'),
            bg = '#34495e',
            fg = '#ecf0f1',
            bd = 2
        )
        stats_frame.pack(fill = tk.X, padx = 10, pady = 10)
        
        self.avg_bpm_label = tk.Label(
            stats_frame,
            text = "Average BPM: --",
            font = ('Arial', 10),
            bg = '#34495e',
            fg = '#ecf0f1'
        )
        self.avg_bpm_label.pack(anchor = tk.W, padx = 10, pady = 5)
        
        self.min_bpm_label = tk.Label(
            stats_frame,
            text = "Min BPM: --",
            font = ('Arial', 10),
            bg = '#34495e',
            fg = '#ecf0f1'
        )
        self.min_bpm_label.pack(anchor = tk.W, padx = 10, pady = 5)
        
        self.max_bpm_label = tk.Label(
            stats_frame,
            text = "Max BPM: --",
            font = ('Arial', 10),
            bg = '#34495e',
            fg = '#ecf0f1'
        )
        self.max_bpm_label.pack(anchor = tk.W, padx = 10, pady = 5)
        
        # Signal Quality Label 
        self.quality_label = tk.Label(
            stats_frame,
            text = "Signal Quality: --",
            font = ('Arial', 10),
            bg = '#34495e',
            fg = '#ecf0f1'
        )
        self.quality_label.pack(anchor = tk.W, padx = 10, pady = 5)

        self.buffer_label = tk.Label(
            stats_frame,
            text = "Buffer: 0%",
            font = ('Arial', 10),
            bg = '#34495e',
            fg = '#ecf0f1'
        )
        self.buffer_label.pack(anchor = tk.W, padx = 10, pady = 5)
        
        # Statements
        instructions_frame = tk.LabelFrame(
            right_panel,
            text = "Statements",
            font = ('Arial', 11, 'bold'),
            bg = '#34495e',
            fg = '#ecf0f1',
            bd = 2
        )
        instructions_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        instructions_text = """
            1. Click 'Start Camera'
            2. Detect the Face 
            3. Keep still for best results
            4. Ensure the Lighting
            5. Wait for BPM Detection
        """
        
        tk.Label(
            instructions_frame,
            text = instructions_text,
            font = ('Arial', 9),
            bg = '#34495e',
            fg = '#bdc3c7',
            justify = tk.LEFT
        ).pack(padx = 10, pady = 10, anchor = tk.W)
        
        # Control Buttons 
        button_frame = tk.Frame(self.root, bg = '#2c3e50')
        button_frame.pack(fill = tk.X, padx = 10, pady = 10)
        
        self.start_button = tk.Button(
            button_frame,
            text = "Start Camera",
            command = self.toggle_camera,
            font = ('Arial', 12, 'bold'),
            bg = '#27ae60',
            fg = 'white',
            activebackground = '#229954',
            bd = 0,
            padx = 20,
            pady = 10,
            cursor = 'hand2'
        )
        self.start_button.pack(side = tk.LEFT, padx = 5)
        
        self.reset_button = tk.Button(
            button_frame,
            text = "Reset Data",
            command = self.reset_data,
            font = ('Arial', 12, 'bold'),
            bg = '#e67e22',
            fg = 'white',
            activebackground = '#d35400',
            bd = 0,
            padx = 20,
            pady = 10,
            cursor = 'hand2'
        )
        self.reset_button.pack(side = tk.LEFT, padx = 5)
        
        quit_button = tk.Button(
            button_frame,
            text = "Quit",
            command = self.quit_app,
            font = ('Arial', 12, 'bold'),
            bg = '#c0392b',
            fg = 'white',
            activebackground = '#a93226',
            bd = 0,
            padx = 20,
            pady = 10,
            cursor = 'hand2'
        )
        quit_button.pack(side = tk.RIGHT, padx = 5)
        
    def toggle_camera(self):
        if not self.is_running:
            self.start_camera()
        else:
            self.stop_camera()
            
    def start_camera(self):
        self.camera = cv2.VideoCapture(0)
        if not self.camera.isOpened():
            self.status_label.config(text = "● Camera Error", fg = '#e74c3c')
            return
        
        # Camera Setting
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.camera.set(cv2.CAP_PROP_FPS, 30)
        self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        self.camera.set(cv2.CAP_PROP_BRIGHTNESS, 20)
        self.camera.set(cv2.CAP_PROP_CONTRAST, 20)
        self.camera.set(cv2.CAP_PROP_SATURATION, 64)
        
        self.is_running = True
        self.start_button.config(text = "Stop Camera", bg = '#c0392b')
        self.status_label.config(text = "● Running", fg = '#27ae60')
        
        # Start Processing in Separate Thread (Avoid System Stopping)
        self.processing_thread = threading.Thread(target = self.update_frame, daemon = True)
        self.processing_thread.start()
        
    def stop_camera(self):
        self.is_running = False
        if self.camera:
            self.camera.release()
        self.start_button.config(text = "Start Camera", bg = '#27ae60')
        self.status_label.config(text = "● Stopped", fg = '#95a5a6')
        self.video_label.config(image = '', bg = '#000000')
        
    def update_frame(self):
        while self.is_running:
            ret, frame = self.camera.read()
            if not ret:
                self.root.after(0, self.stop_camera)
                break
            
            # Calculate FPS
            current_time = time.time()
            if self.last_frame_time:
                frame_time = current_time - self.last_frame_time
                self.frame_times.append(frame_time)
                if len(self.frame_times) > 0:
                    self.actual_fps = 1.0 / np.mean(self.frame_times)
                    self.root.after(0, lambda: self.fps_label.config(text = f"{self.actual_fps:.1f}"))
            self.last_frame_time = current_time
            
            # Processing the Frame Data
            frame_small = cv2.resize(frame, (960, 540))
            frame = cv2.flip(frame_small, 1)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect Faces (Threshold Control)
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor = 1.05,      
                minNeighbors = 8,        
                minSize = (150, 150),    
                maxSize = (600, 600),   
                flags = cv2.CASCADE_SCALE_IMAGE 
            )
            
            if len(faces) > 0:
                (x, y, w, h) = max(faces, key = lambda rect: rect[2] * rect[3])
                
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                
                # Extract Forehead Region
                forehead_y = y + int(h * 0.1)
                forehead_h = int(h * 0.25)
                forehead_x = x + int(w * 0.3)
                forehead_w = int(w * 0.4)
                
                cv2.rectangle(
                    frame, 
                    (forehead_x, forehead_y), 
                    (forehead_x + forehead_w, forehead_y + forehead_h),
                    (255, 0, 0), 
                    2
                )
                
                roi = frame[forehead_y:forehead_y+forehead_h, 
                        forehead_x:forehead_x+forehead_w]
                
                if roi.size > 0:
                    # Extract Green Channel with Gaussian 
                    roi_float = roi.astype(np.float32)
                    green_channel = roi_float[:, :, 1]
                    
                    h_roi, w_roi = green_channel.shape
                    y_center, x_center = h_roi // 2, w_roi // 2
                    
                    y_coords, x_coords = np.ogrid[:h_roi, :w_roi]
                    gaussian_weight = np.exp(-((y_coords - y_center)**2 + (x_coords - x_center)**2) / 
                                            (2 * (min(h_roi, w_roi) / 4)**2))
                    
                    green_avg = np.average(green_channel, weights = gaussian_weight)
                    
                    # use the thread
                    with self.lock:
                        self.data_buffer.append(green_avg)
                        self.times.append(current_time)
                        self.waveform_data.append(green_avg)
                        self.waveform_times.append(current_time)
                    
                    # Calculate Heart Rate (If Buffer is Full)
                    if len(self.data_buffer) >= self.buffer_size:
                        self.calculate_heart_rate()
                    
                    # Update Buffer Status
                    buffer_percent = (len(self.data_buffer) / self.buffer_size) * 100
                    self.root.after(0, lambda: self.buffer_label.config(text = f"Buffer: {buffer_percent:.0f}%"))
                    
                    # Update Visualization
                    self.root.after(0, self.draw_waveform)
                    
                    # Display BPM Value
                    if self.bpm > 0:
                        cv2.putText(frame, f"BPM: {self.bpm:.0f}", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                        cv2.putText(frame, f"Quality: {self.signal_quality:.1f}", (10, 70),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    
                    cv2.putText(frame, f"FPS: {self.actual_fps:.1f}", (10, 110),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            else:
                cv2.putText(frame, "No face detected", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            # Convert and Display 
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img = img.resize((640, 360), Image.Resampling.LANCZOS)
            imgtk = ImageTk.PhotoImage(image = img)
            
            # Update GUI in Main Thread
            self.root.after(0, self._update_video_label, imgtk)
            
            time.sleep(0.033)  

    def _update_video_label(self, imgtk):
        # Update Video Label in Main Thread
        self.video_label.imgtk = imgtk
        self.video_label.configure(image = imgtk)
        
    def calculate_heart_rate(self):
        # Convert Buffer to Array
        data = np.array(self.data_buffer)
        
        # Calculate Signal Quality 
        signal_std = np.std(data)

        if signal_std < 0.5:  
            return
        detrended = signal.detrend(data)
        
        if np.std(detrended) > 0:
            normalized = (detrended - np.mean(detrended)) / np.std(detrended)
        else:
            return
        
        # Bandpass Filter (0.75 Hz - 3.0 Hz = 45-180 BPM) 
        fps = len(self.data_buffer) / (self.times[-1] - self.times[0])
        lowcut = 0.75   
        highcut = 3.0   
        
        # Normalize Frequencies
        nyquist = fps / 2
        low = lowcut / nyquist
        high = highcut / nyquist
        
        b, a = signal.butter(5, [low, high], btype='band')  # Increased order from 3 to 5
        filtered = signal.filtfilt(b, a, normalized)
        
        windowed = filtered * signal.windows.hamming(len(filtered))
        
        # Perform FFT (Because Affect Signal Feature from Light or Movement)
        fft_data = np.fft.rfft(windowed)
        fft_freq = np.fft.rfftfreq(len(windowed), 1.0 / fps)
        
        # Find Peak in Frequency Domain (Show Cycle Diversification)
        fft_abs = np.abs(fft_data)
        
        # Limit to Heart Rate Range
        freq_mask = (fft_freq >= lowcut) & (fft_freq <= highcut)
        masked_fft = fft_abs[freq_mask]
        masked_freq = fft_freq[freq_mask]
        
        if len(masked_fft) == 0:
            return
        
        # Find Frequency
        peak_idx = np.argmax(masked_fft)
        peak_freq = masked_freq[peak_idx]
        peak_power = masked_fft[peak_idx]
        
        # Calculate Signal Quality (SNR Metrics)
        noise_power = np.mean(masked_fft)
        if noise_power > 0:
            self.signal_quality = peak_power / noise_power
        else:
            self.signal_quality = 0
        
        # SNR threshold
        if self.signal_quality < 2.0: 
            return
        
        # Convert to BPM
        bpm = peak_freq * 60.0
        
        # Validate BPM Range 
        if 45 >= bpm and bpm <= 180:
            # Check 
            if len(self.bpm_history) > 0:
                recent_avg = np.mean(list(self.bpm_history)[-10:])
               
                if abs(bpm - recent_avg) > 30:
                    return
            
            self.bpm_smooth.append(bpm)
            
            if len(self.bpm_smooth) >= 3:
                display_bpm = np.median(self.bpm_smooth)
            else:
                display_bpm = bpm
            
            self.bpm = display_bpm
            self.bpm_history.append(display_bpm)
            self.last_valid_bpm = display_bpm
            
            # Store Spectrum Data 
            self.spectrum_freqs = masked_freq.tolist()
            self.spectrum_power = masked_fft.tolist()
            
            # Update Displays 
            self.root.after(0, lambda: self.bpm_label.config(text = f"{self.bpm:.0f} BPM"))
            self.root.after(0, lambda: self.quality_label.config(text = f"Signal Quality: {self.signal_quality:.1f}"))
            
            # Draw 
            self.root.after(0, self.draw_spectrum)
            
            # Update Statistics
            if len(self.bpm_history) > 5:
                avg_bpm = np.mean(self.bpm_history)
                min_bpm = np.min(self.bpm_history)
                max_bpm = np.max(self.bpm_history)
                
                self.root.after(0, lambda: self.avg_bpm_label.config(text = f"Average BPM: {avg_bpm:.0f}"))
                self.root.after(0, lambda: self.min_bpm_label.config(text = f"Min BPM: {min_bpm:.0f}"))
                self.root.after(0, lambda: self.max_bpm_label.config(text = f"Max BPM: {max_bpm:.0f}"))
    
    def draw_spectrum(self):
        # Draw Frequency Spectrum 
        self.spectrum_canvas.delete("all")
        
        if len(self.spectrum_freqs) == 0 or len(self.spectrum_power) == 0:
            self.spectrum_canvas.create_text(
                140, 50, text = "Waiting for Data...",
                fill = '#7f8c8d', font=('Arial', 9)
            )
            return
        
        canvas_width = 280
        canvas_height = 100
        margin_x = 30
        margin_y = 15
        plot_width = canvas_width - 2 * margin_x
        plot_height = canvas_height - 2 * margin_y
        
        # Draw Axes
        self.spectrum_canvas.create_line(
            margin_x, canvas_height - margin_y,
            canvas_width - margin_x, canvas_height - margin_y,
            fill = '#7f8c8d', width=1
        )
        
        # Draw BPM Labels
        for bpm in [60, 90, 120, 150]:
            freq_hz = bpm / 60.0
            if freq_hz >= min(self.spectrum_freqs) and freq_hz <= max(self.spectrum_freqs):
                x = margin_x + ((freq_hz - min(self.spectrum_freqs)) / 
                            (max(self.spectrum_freqs) - min(self.spectrum_freqs))) * plot_width
                self.spectrum_canvas.create_text(
                    x, canvas_height - 5, text = str(bpm),
                    fill = '#ecf0f1', font = ('Arial', 7)
                )
        
        # Normalize Spectrum
        max_power = max(self.spectrum_power)
        if max_power == 0:
            return
        
        points = []
        for freq, power in zip(self.spectrum_freqs, self.spectrum_power):
            x = margin_x + ((freq - min(self.spectrum_freqs)) / 
                        (max(self.spectrum_freqs) - min(self.spectrum_freqs))) * plot_width
            y = canvas_height - margin_y - (power / max_power) * plot_height
            points.append((x, y))
        
        # Draw Line
        for i in range(len(points) - 1):
            self.spectrum_canvas.create_line(
                points[i][0], points[i][1],
                points[i+1][0], points[i+1][1],
                fill='#3498db', width=2
            )
        
        # Highlight Peak (Current BPM)
        if self.bpm > 0:
            peak_freq = self.bpm / 60.0
            peak_x = margin_x + ((peak_freq - min(self.spectrum_freqs)) / 
                                (max(self.spectrum_freqs) - min(self.spectrum_freqs))) * plot_width
            
            idx = np.argmin(np.abs(np.array(self.spectrum_freqs) - peak_freq))
            peak_power = self.spectrum_power[idx]
            peak_y = canvas_height - margin_y - (peak_power / max_power) * plot_height
            
            self.spectrum_canvas.create_oval(
                peak_x - 3, peak_y - 3, peak_x + 3, peak_y + 3,
                fill = '#e74c3c', outline = '#c0392b', width = 2
            )

    def draw_waveform(self):
        # Draw Signal Waveform 
        self.waveform_canvas.delete("all")
        
        with self.lock:
            if len(self.waveform_data) < 2:
                self.waveform_canvas.create_text(
                    140, 40, text = "Waiting for signal...",
                    fill = '#7f8c8d', font = ('Arial', 9)
                )
                return
            
            data = np.array(self.waveform_data)
        
        canvas_width = 280
        canvas_height = 80
        margin_x = 20
        margin_y = 10
        plot_width = canvas_width - 2 * margin_x
        plot_height = canvas_height - 2 * margin_y
        
        # Draw Baseline 
        mid_y = canvas_height // 2
        self.waveform_canvas.create_line(
            margin_x, mid_y, canvas_width - margin_x, mid_y,
            fill = '#7f8c8d', width = 1, dash = (2, 2)
        )
        
        # Normalize Data
        data_mean = np.mean(data)
        data_std = np.std(data)
        if data_std == 0:
            return
        
        normalized = (data - data_mean) / data_std
        
        # Draw Waveform
        points = []
        for i, value in enumerate(normalized):
            x = margin_x + (i / len(normalized)) * plot_width
            y = mid_y - value * (plot_height / 4)
            points.append((x, y))
        
        for i in range(len(points) - 1):
            self.waveform_canvas.create_line(
                points[i][0], points[i][1],
                points[i+1][0], points[i+1][1],
                fill = '#2ecc71', width = 2
            )

    def reset_data(self):
        with self.lock:
            self.data_buffer.clear()
            self.times.clear()
            self.bpm_history.clear()
            self.bpm_smooth.clear()
            self.waveform_data.clear()
            self.waveform_times.clear()
            self.spectrum_freqs = []
            self.spectrum_power = []
        
        self.bpm = 0
        self.bpm_label.config(text = "-- BPM")
        self.fps_label.config(text = "--")
        self.quality_label.config(text = "Signal Quality: --")
        self.avg_bpm_label.config(text = "Average BPM: --")
        self.min_bpm_label.config(text = "Min BPM: --")
        self.max_bpm_label.config(text = "Max BPM: --")
        self.buffer_label.config(text = "Buffer: 0%")
        
        self.spectrum_canvas.delete("all")
        self.waveform_canvas.delete("all")
        
    def quit_app(self):
        self.stop_camera()
        self.root.quit()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = HeartRateMonitor(root)
    root.mainloop()