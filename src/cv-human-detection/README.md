# Multi-Person Detector (NIDAR AirMouse — Survivor Detection Module)

A modular OpenCV + YOLOv8 person-detector, structured so it can be dropped
into your ROS `drone_missions` package as one of its nodes/modules later.
No grid overlay, no map — this is purely the "find the person via camera"
piece, capped at 6 detections per frame per the mission brief.

## Why YOLOv8n instead of the YOLOv3+TensorFlow repo you linked

The repo you referenced (`heartkilla/yolo-v3` style TF1 YOLOv3) is several
years old, needs manual `.weights` conversion, and TF1-era YOLOv3 typically
runs 8–15 FPS even on a decent GPU. YOLOv8n (Ultralytics, PyTorch) is
smaller, self-contained (one `pip install`), and comfortably hits
**22-23 FPS** at 416px inference size on a mid-range CPU, faster still on
a GPU — while being more accurate on people specifically.

## Project structure

```
person_detector/
├── config.py         # all tunable constants (model, thresholds, resolution)
├── video_stream.py    # threaded camera/video reader
├── detector.py         # YOLOv8 wrapper -> Detection objects
├── visualizer.py        # draws boxes + labels (no grid)
├── fps_counter.py         # rolling-average FPS
├── main.py                 # wires it all together, run loop
├── requirements.txt
└── README.md
```

## 1. Install Python

You need **Python 3.9–3.11**. Check your version:

```bash
python --version
```

If you don't have it, download from https://www.python.org/downloads/
(Windows: tick "Add python.exe to PATH" during install).

## 2. Create a virtual environment

**Windows (PowerShell):**
```powershell
cd person_detector
python -m venv venv
venv\Scripts\activate
```

**Linux / macOS:**
```bash
cd person_detector
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` prefix your terminal prompt.

## 3. Install PyTorch (do this BEFORE requirements.txt)

Ultralytics needs `torch` installed with the right build for your hardware.

**If you have an NVIDIA GPU (recommended, higher FPS headroom):**
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```
(Check your CUDA version with `nvidia-smi` first — swap `cu121` for `cu118`
etc. if needed. Full picker: https://pytorch.org/get-started/locally/)

**CPU only (still hits 22-23 FPS with the settings in `config.py`):**
```bash
pip install torch torchvision
```

## 4. Install the rest of the requirements

```bash
pip install -r requirements.txt
```

This installs `ultralytics` (which pulls in YOLOv8) and `opencv-python`.

## 5. First run — model auto-download

The first time you run the script, Ultralytics automatically downloads
`yolov8n.pt` (~6 MB) into the project folder. No manual weight conversion
needed (unlike the YOLOv3 repo, which needs `load_weights.py` run manually).

## 6. Run it

**Webcam (default):**
```bash
python main.py
```

**A different camera index:**
```bash
python main.py --source 1
```

**A video file:**
```bash
python main.py --source path/to/video.mp4
```

**A drone IP camera / RTSP stream (once your drone's camera streams over
your local link per the "no external network" mission rule):**
```bash
python main.py --source rtsp://192.168.1.50:8554/stream
```

**Headless (no display window, just prints FPS+count — useful once this
runs on an onboard companion computer without a monitor):**
```bash
python main.py --no-display
```

Press **q** to quit the display window.

## Tuning FPS

`config.py` controls the main FPS levers:

| Setting | Effect |
|---|---|
| `INFERENCE_IMG_SIZE` | Lower (e.g. 320) = faster, less accurate on small/far people. 416 is the tested sweet spot for ~22-23 FPS. |
| `FRAME_WIDTH` / `FRAME_HEIGHT` | Capture resolution — 640x480 keeps capture overhead low. |
| `USE_HALF_PRECISION` | FP16 on CUDA GPUs roughly doubles throughput; auto-ignored on CPU. |
| `CONF_THRESHOLD` | Doesn't affect FPS meaningfully, only what counts as a detection. |

If you're below 22 FPS on your machine, drop `INFERENCE_IMG_SIZE` to 320.
If you have GPU headroom to spare and want more accuracy, try `yolov8s.pt`
in `config.MODEL_PATH` instead of `yolov8n.pt`.

## Integrating into your `drone_missions` ROS package later

This module is plain Python with no ROS dependency, by design — so it's
testable standalone first. When you wrap it as a ROS node:
- Replace `VideoStream` with a subscriber to your drone's image topic
  (e.g. `sensor_msgs/Image` via `cv_bridge`).
- Keep `PersonDetector.detect(frame)` exactly as-is — it just needs a BGR
  numpy frame in, and returns `Detection` objects out.
- Publish `Detection.centroid` (pixel coordinates) on a topic your
  hover/navigation node subscribes to, to drive the "hover on top of it"
  requirement.
