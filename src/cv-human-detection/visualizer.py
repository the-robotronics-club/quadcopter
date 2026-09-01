"""
visualizer.py
-------------
Pure drawing functions. No grid overlay, no map logic — just bounding
boxes, per-person labels, and a small status readout, per the request.
Kept separate from detector.py so you can change how detections are
displayed (or swap this out for a ROS image publisher) without touching
detection logic.
"""

import cv2

BOX_COLOR = (0, 255, 0)
TEXT_COLOR = (255, 255, 255)
TEXT_BG_COLOR = (0, 140, 0)


def draw_detections(frame, detections):
    for idx, det in enumerate(detections, start=1):
        cv2.rectangle(frame, (det.x1, det.y1), (det.x2, det.y2), BOX_COLOR, 2)

        label = f"Person {idx}: {det.confidence * 100:.1f}%"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(
            frame,
            (det.x1, det.y1 - th - 8),
            (det.x1 + tw + 6, det.y1),
            TEXT_BG_COLOR,
            -1,
        )
        cv2.putText(
            frame, label, (det.x1 + 3, det.y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, TEXT_COLOR, 1, cv2.LINE_AA,
        )

        cx, cy = det.centroid
        cv2.circle(frame, (cx, cy), 3, (0, 0, 255), -1)

    return frame


def draw_status(frame, fps, person_count):
    text = f"FPS: {fps:.1f}  |  Persons detected: {person_count}"
    cv2.putText(
        frame, text, (10, 25),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2, cv2.LINE_AA,
    )
    return frame
