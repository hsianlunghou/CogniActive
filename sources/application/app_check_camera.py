import cv2
import time


def measure_camera_fps(camera, test_duration=2.0):
    # Measure actual camera FPS over a few seconds
    num_frames = 0
    start_time = time.time()
    
    while True:
        ret, frame = camera.read()
        if not ret:
            break
        num_frames += 1
        elapsed = time.time() - start_time
        if elapsed > test_duration:
            break
    
    actual_fps = num_frames / elapsed
    return actual_fps

def check_camera_specs():
    # Check camera specifications and capabilities
    camera = cv2.VideoCapture(0)
    
    if not camera.isOpened():
        print("❌ Cannot open camera")
        return
    
    print("=" * 50)
    print("📷 Camera Specifications")
    print("=" * 50)
    
    # Get camera properties
    width = camera.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = camera.get(cv2.CAP_PROP_FRAME_HEIGHT)
    fps = camera.get(cv2.CAP_PROP_FPS)
    brightness = camera.get(cv2.CAP_PROP_BRIGHTNESS)
    contrast = camera.get(cv2.CAP_PROP_CONTRAST)
    saturation = camera.get(cv2.CAP_PROP_SATURATION)
    
    print(f"Resolution: {int(width)} x {int(height)}")
    print(f"FPS: {fps}")
    print(f"Brightness: {brightness}")
    print(f"Contrast: {contrast}")
    print(f"Saturation: {saturation}")
    
    # Test different resolutions
    print("\n" + "=" * 50)
    print("📐 Supported Resolutions Test")
    print("=" * 50)
    
    test_resolutions = [
        (320, 240),   # QVGA
        (640, 480),   # VGA
        (800, 600),   # SVGA
        (1280, 720),  # HD
        (1920, 1080), # Full HD
    ]
    
    for w, h in test_resolutions:
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        actual_w = camera.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_h = camera.get(cv2.CAP_PROP_FRAME_HEIGHT)
        
        if actual_w == w and actual_h == h:
            print(f"✅ {w}x{h} - Supported")
        else:
            print(f"❌ {w}x{h} - Not supported (actual: {int(actual_w)}x{int(actual_h)})")
    
    # Capture a test frame
    ret, frame = camera.read()
    if ret:
        print("\n" + "=" * 50)
        print("🖼️  Test Frame Info")
        print("=" * 50)
        print(f"Frame shape: {frame.shape}")
        print(f"Frame size: {frame.size} bytes")
        print(f"Data type: {frame.dtype}")
        print(f"Color channels: {frame.shape[2] if len(frame.shape) > 2 else 1}")
    
    camera.release()
    print("\n✅ Camera check completed!")

if __name__ == "__main__":
    check_camera_specs()