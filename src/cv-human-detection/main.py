"""
main.py
-------
Entry point. Wires video_stream -> detector -> visualizer -> fps_counter
together into a run loop. Nothing about detection or drawing logic lives
here — this file only orchestrates the modules.

Usage:
    python main.py                        # default webcam (source 0)
    python main.py --source 1              # a different camera index
    python main.py --source video.mp4      # a recorded video file
    python main.py --source rtsp://IP/stream  # drone IP camera stream
    python main.py --no-display            # headless run (prints FPS only)
"""

import argparse
import sys

import cv2

import config
from detector import PersonDetector
from video_stream import VideoStream
from fps_counter import FPSCounter
import visualizer


def parse_args():
    parser = argparse.ArgumentParser(description="Multi-person detector")
    parser.add_argument("--source", default=config.VIDEO_SOURCE,
                         help="Camera index, video file path, or RTSP URL")
    parser.add_argument("--conf", type=float, default=config.CONF_THRESHOLD)
    parser.add_argument("--max-persons", type=int, default=config.MAX_PERSONS)
    parser.add_argument("--no-display", action="store_true",
                         help="Run headless, just print FPS to the console")
    args = parser.parse_args()

    # allow --source 0 to be passed as a webcam index rather than a string
    if isinstance(args.source, str) and args.source.isdigit():
        args.source = int(args.source)
    return args


def main():
    args = parse_args()

    print(f"[INFO] Loading model on device...")
    detector = PersonDetector(conf_threshold=args.conf, max_persons=args.max_persons)
    print(f"[INFO] Model loaded on: {detector.device}")

    stream = VideoStream(source=args.source)
    fps_counter = FPSCounter()

    print("[INFO] Starting detection loop. Press 'q' to quit.")
    try:
        while True:
            ok, frame = stream.read()
            if not ok or frame is None:
                print("[WARN] Frame grab failed, retrying...")
                continue

            detections = detector.detect(frame)
            fps = fps_counter.tick()

            if not args.no_display:
                visualizer.draw_detections(frame, detections)
                visualizer.draw_status(frame, fps, len(detections))
                cv2.imshow("Person Detection", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            else:
                print(f"\rFPS: {fps:5.1f} | Persons: {len(detections)}", end="")

    except KeyboardInterrupt:
        pass
    finally:
        stream.stop()
        cv2.destroyAllWindows()
        print("\n[INFO] Stopped.")


if __name__ == "__main__":
    sys.exit(main())
