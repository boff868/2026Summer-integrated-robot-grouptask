#!/usr/bin/env bash
set -eo pipefail

source /opt/ros/humble/setup.bash
export DISPLAY=:99
export LIBGL_ALWAYS_SOFTWARE=1
export QT_X11_NO_MITSHM=1

if ! pgrep -x Xvfb >/dev/null; then
  nohup Xvfb :99 -screen 0 1280x900x24 +extension GLX -ac >/tmp/lab3_xvfb.log 2>&1 &
  sleep 2
fi

# Stop only processes started for this recording.
ps -eo pid=,comm=,args= | awk '$2 == "python3" && index($0, "/root/lab3_rviz/replay_rviz2.py") {print $1}' | xargs -r kill -9
ps -eo pid=,comm=,args= | awk '$2 == "rviz2" && index($0, "/root/lab3_rviz/lab3_circle.rviz") {print $1}' | xargs -r kill -9
sleep 2

RVIZ_PID=
REPLAY_PID=
cleanup() {
  [ -z "$REPLAY_PID" ] || kill -9 "$REPLAY_PID" 2>/dev/null || true
  [ -z "$RVIZ_PID" ] || kill -9 "$RVIZ_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

nohup rviz2 -d /root/lab3_rviz/lab3_circle.rviz >/tmp/lab3_rviz.log 2>&1 &
RVIZ_PID=$!
sleep 8
kill -0 "$RVIZ_PID"

OUT=/root/lab3_rviz/rviz_circle_tracking.mp4
ffmpeg -y -hide_banner -loglevel error \
  -f x11grab -framerate 24 -video_size 1280x900 -draw_mouse 0 -i :99.0 \
  -t 54 -an -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p \
  -movflags +faststart "$OUT" >/tmp/lab3_ffmpeg.log 2>&1 &
FFMPEG_PID=$!
sleep 1.5

python3 /root/lab3_rviz/replay_rviz2.py >/tmp/lab3_replay.log 2>&1 &
REPLAY_PID=$!
echo "$REPLAY_PID" >/tmp/lab3_replay.pid

wait "$FFMPEG_PID"
kill -9 "$REPLAY_PID" 2>/dev/null || true
wait "$REPLAY_PID" 2>/dev/null || true
REPLAY_PID=
kill -9 "$RVIZ_PID" 2>/dev/null || true
wait "$RVIZ_PID" 2>/dev/null || true
RVIZ_PID=

ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,width,height,avg_frame_rate \
  -show_entries format=duration,size -of default=nw=1 "$OUT"
ls -lh "$OUT"
