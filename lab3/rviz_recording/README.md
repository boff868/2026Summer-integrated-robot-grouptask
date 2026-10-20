# RViz2 recording replay

`rviz_circle_tracking.mp4` is a 54-second screen capture of RViz2 running in the connected Ubuntu 22.04 / ROS 2 Humble Docker. The replay node reads the measured `circle_moderate2.csv` ROS bag export, draws the reference path in green and the measured path in blue, and marks the vehicle in orange. The video replays existing measurements; it is not a fresh TESSE simulator run.

To reproduce inside that Docker, place `circle_moderate2.csv`, `replay_rviz2.py`, `lab3_circle.rviz`, and `record_rviz.sh` in `/root/lab3_rviz/`, install ROS 2 Humble RViz2 and ffmpeg, and run:

```bash
bash /root/lab3_rviz/record_rviz.sh
```

The script records an X11 desktop at 1280x900 and 24 fps. The video includes a short setup lead-in and tail around the 46.38-second measured trajectory.
