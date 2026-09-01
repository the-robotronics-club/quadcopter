"""
config.py
---------
Central configuration for the person-detection module.
Keeping every tunable value in one file is what makes the rest of the
package "modular" — swap a model, a resolution, or a threshold here
without touching detector.py / video_stream.py / main.py.
"""

# ---- Model ----
# yolov8n.pt = "nano" variant -> smallest / fastest YOLOv8 model.
# Ultralytics auto-downloads it on first run if it isn't found locally.
MODEL_PATH = "yolov8n.pt"

# COCO class id 0 = "person". We only ever keep this class.
PERSON_CLASS_ID = 0

# ---- Detection thresholds ----
CONF_THRESHOLD = 0.45   # minimum confidence to accept a detection
IOU_THRESHOLD = 0.45    # NMS overlap threshold

# ---- Mission constraint ----
# NIDAR brief: "up to 6 survivors". We cap displayed/reported detections
# at 6, keeping the highest-confidence ones if more are found.
MAX_PERSONS = 6

# ---- Video / performance ----
# Smaller inference resolution = higher FPS. 416 is the sweet spot for
# yolov8n on a mid-range CPU/GPU to land around 22-23 FPS at 640x480 input.
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
INFERENCE_IMG_SIZE = 416

# Camera source: 0 = default webcam. Use an RTSP/HTTP URL string for a
# drone's IP camera, or a file path for a recorded video.
VIDEO_SOURCE = 0

# Use half-precision (FP16) inference when a CUDA GPU is available.
# Ignored automatically on CPU.
USE_HALF_PRECISION = True

# Rolling window size (in frames) for the FPS counter's moving average.
FPS_SMOOTHING_WINDOW = 30
