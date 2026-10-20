# MIT VNAV Lab 3 — UAV trajectory tracking

This folder contains the ROS implementation, recorded simulator data, written deliverables, and a Chinese experiment report.

## Contents

- `controller_pkg/`: ROS Noetic catkin package with the SE(3) controller, circular trajectory publisher, static-pose publisher, launch files, and RViz configuration.
- `results/`: original ROS bag recordings, CSV exports, and the computed tracking metrics for circle tracking and hover.
- `deliverable_1.txt`, `deliverable_2.md`: standalone answers for the individual exercises.
- `lab3_report.pdf`: experiment method, plots, metrics, analysis, and appendices for Deliverables 1 and 2.
- `circle_tracking.mp4`: H.264 top-view plot of the final reference period.
- `flight_3d_replay.mp4`: 3D visualization reconstructed from measured ROS bag positions; the drone icon uses commanded yaw.
- `rviz_circle_tracking.mp4`: RViz2 window recording from the connected Docker, replaying the measured circle trajectory CSV.
- `rviz_drone_flight.txt`: submission file prepared for the required public video URL; complete it after uploading the MP4 to Google Drive or Dropbox.
- `rviz_recording/`: ROS 2 replay node and RViz2 config used to produce that recording.
- `circle_tracking.gif`: animated preview of the top-view plot.

## Build and run

In the ROS Noetic catkin workspace, place `controller_pkg` under `src/`, then run:

```bash
cd ~/vnav_ws
catkin_make
source devel/setup.bash
roslaunch controller_pkg codex_circle.launch
```

For the static hover target, use:

```bash
roslaunch controller_pkg codex_static.launch
```

The circle is centered at the world origin with radius 5 m, altitude 2 m, and angular rate 0.5 rad/s. The launch file sets the controller rate to 100 Hz and gains `kx=2.5`, `kv=2.0`, `kr=4.0`, `komega=1.2`, and `ki_z=0.15`.

## Recorded performance

The circle bag contains 46.38 s of flight-state data (about 3.69 reference periods). Position RMSE over the full recording is 0.658 m; the static hover RMSE after the first 5 s is 0.154 m. The hover data shows a residual vertical bias of about -0.12 m, which is discussed in the report.

## Reproducibility notes

These are simulator results from the isolated Docker environment used for this run. Build and launch require the VNAV/TESSE dependencies and ROS Noetic. The CSV files are time-aligned exports of desired and measured position, velocity, and rotor commands; the JSON files document the windows and metrics used in the report.

The MIT lab asks for an RViz video showing the circular flight and a publicly viewable Google Drive or Dropbox link. The included 54-second `rviz_circle_tracking.mp4` is an actual RViz2 window capture recorded in the connected Ubuntu 22.04 / ROS 2 Humble Docker. It replays the previously recorded `circle_moderate2.csv` data (46.38 seconds of measured flight); green is the reference path, blue is the measured path, and orange marks the vehicle. This visualization replays existing measurements and is not a new live TESSE simulation. Upload the MP4 to Google Drive or Dropbox and set public viewing before submission; this package contains the local recording but no public link.

Source references: [MIT Lab 3 exercises](https://vnav.mit.edu/labs_2023/lab3/exercises.html) and the [VNAV2021 lab code release](https://github.com/MIT-SPARK/VNAV-labs/releases/tag/VNAV2021).

## License

This submission's original software and accompanying documentation are released under the MIT License; see `LICENSE`. The ROS package also declares MIT in `controller_pkg/package.xml`. MIT VNAV course materials and third-party dependencies remain subject to their respective terms.

The RViz recording is publicly available in this repository: [rviz_circle_tracking.mp4](rviz_circle_tracking.mp4). The MIT exercise page specifically requests a Google Drive or Dropbox share URL; if the course submission system requires one of those hosts, upload the same MP4 there as well.
