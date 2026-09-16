# Detection <-> Drone Integration Contract

This defines the exact interface between the survivor-detection module and
the drone model, so Navigation can build the real drone on their own
timeline and detection will work the moment it's ready -- no coordination
needed beyond this document.

## What Navigation needs to provide

**One thing**: a camera sensor on the drone's body link, publishing to the
Gazebo topic named exactly `cam`.

The exact sensor definition to paste into the drone's SDF is in
`camera_sensor_snippet.sdf` in this same folder. Don't rename the topic
without updating `detection_bringup.launch.py` to match.

Mounting orientation (downward vs. forward-facing) is Navigation's call,
but flag the choice to the perception side once decided -- it affects
`geotag.py`'s accuracy assumptions (see that module's docstring).

## What the detection/perception side provides

- `detection_bringup.launch.py` -- one launch command that bridges the
  `cam` Gazebo topic into ROS2 and starts the detection node. Works
  identically no matter what model publishes `cam`.
- `survivor_detection_node.py` -- subscribes to `/cam`, publishes
  annotated frames on `/survivor_detection/annotated` and detections as
  JSON on `/survivor_detection/detections`.

## How to swap the test rig for the real drone

Today (real drone not ready): spawn `detection_test_camera_rig.sdf`
into the world, run `detection_bringup.launch.py`, detection works.

Once the real drone model exists: don't spawn the test rig, spawn the
real drone (with `camera_sensor_snippet.sdf` added to its body link)
instead. Run the exact same `detection_bringup.launch.py`. No changes to
any detection code, the launch file, or the bridge.

## Who owns what going forward

- **Navigation**: drone model, flight control, PX4 SITL integration,
  camera mounting/orientation decision
- **Perception (this module)**: everything downstream of the `cam` topic
  -- detection, tracking, annotation, publishing results
- **Mapping**: consumes `/survivor_detection/detections` (or the raw
  `/cam` feed independently) for occupancy grid / SLAM -- separate
  integration, not covered by this document