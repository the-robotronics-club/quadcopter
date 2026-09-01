"""
detector.py
-----------
Wraps a YOLOv8 model and exposes ONE method: detect(frame) -> list[Detection].
Everything else in the package (video capture, drawing, FPS, main loop)
talks to this class only through that method, so the model itself
(YOLOv8n today) can be swapped for another backend later without
touching the rest of the codebase.
"""

from dataclasses import dataclass
from typing import List

import torch
from ultralytics import YOLO

import config


@dataclass
class Detection:
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float

    @property
    def centroid(self):
        return (self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2


class PersonDetector:
    def __init__(self,
                 model_path: str = config.MODEL_PATH,
                 conf_threshold: float = config.CONF_THRESHOLD,
                 iou_threshold: float = config.IOU_THRESHOLD,
                 max_persons: int = config.MAX_PERSONS,
                 img_size: int = config.INFERENCE_IMG_SIZE):
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.max_persons = max_persons
        self.img_size = img_size

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = YOLO(model_path)
        self.model.to(self.device)

        self.half = config.USE_HALF_PRECISION and self.device == "cuda"
        if self.half:
            self.model.model.half()

    def detect(self, frame) -> List[Detection]:
        """Runs inference on a single BGR frame and returns up to
        `max_persons` Detection objects, sorted by confidence descending."""
        results = self.model.predict(
            source=frame,
            imgsz=self.img_size,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            classes=[config.PERSON_CLASS_ID],  # only ever look for people
            device=self.device,
            verbose=False,
        )

        detections: List[Detection] = []
        for box in results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])
            detections.append(Detection(x1, y1, x2, y2, conf))

        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections[: self.max_persons]
