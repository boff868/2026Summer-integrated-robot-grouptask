#!/usr/bin/env python3
"""Render a 3-D telemetry replay from the measured circle-tracking CSV."""
import csv, math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent
rows=list(csv.DictReader(open(ROOT/'results/circle_moderate2.csv',newline='')))
tmax=max(float(r['t_s']) for r in rows)
rows=[r for r in rows if float(r['t_s'])>=tmax-12.57]
frames_data=rows[::7]
if float(frames_data[-1]['t_s']) != float(rows[-1]['t_s']): frames_data.append(rows[-1])
W,H=960,640
font_path='/System/Library/Fonts/STHeiti Medium.ttc'
font=ImageFont.truetype(font_path,22)
small=ImageFont.truetype(font_path,16)
mini=ImageFont.truetype(font_path,14)
scale=31.0
cx,base=480,440
sqrt2=math.sqrt(2)

def proj(x,y,z):
    # Axonometric world view: x/y form the floor plane; z points upward.
    return (cx+(x-y)/sqrt2*scale, base-(x+y)/sqrt2*0.43*scale-z*0.82*scale)

def draw_path(draw, pts, fill, width):
    if len(pts)>1: draw.line(pts,fill=fill,width=width,joint='curve')

frames=[]
# Target loop projected at z=2 m.
target=[proj(5*math.sin(i*2*math.pi/400),5*math.cos(i*2*math.pi/400),2.0) for i in range(401)]
for idx,r in enumerate(frames_data):
    im=Image.new('RGB',(W,H),'#F8FAFD')
    d=ImageDraw.Draw(im)
    d.rectangle((0,0,W,58),fill='#172B4D')
    d.text((34,14),'VNAV LAB 3  |  3D FLIGHT REPLAY',font=font,fill='white')
    # Floor plane and grid.
    floor=[proj(-6,-6,0),proj(6,-6,0),proj(6,6,0),proj(-6,6,0)]
    d.polygon(floor,fill='#F0F4F8',outline='#AAB7C6')
    for k in range(-6,7,2):
        draw_path(d,[proj(k,-6,0),proj(k,6,0)],'#D5DEE8',1)
        draw_path(d,[proj(-6,k,0),proj(6,k,0)],'#D5DEE8',1)
    # World axes.
    origin=proj(0,0,0)
    for end,color,label in [((3,0,0),'#D94F4F','X'),((0,3,0),'#2B9B70','Y'),((0,0,3),'#3679C8','Z')]:
        q=proj(*end)
        d.line((origin,q),fill=color,width=4)
        d.text((q[0]+5,q[1]-5),label,font=small,fill=color)
    # Desired and measured paths.
    draw_path(d,target,'#1976D2',4)
    measured=[proj(float(q['x_m']),float(q['y_m']),float(q['z_m'])) for q in frames_data[:idx+1]]
    draw_path(d,measured,'#F08C32',4)
    # Current drone marker, using desired yaw for icon heading because attitude is
    # not included in this compact CSV export.
    x,y,z=(float(r[k]) for k in ('x_m','y_m','z_m'))
    dx,dy=float(r['xd_m']),float(r['yd_m'])
    theta=math.atan2(dx,dy)
    yaw=-theta
    center=proj(x,y,z)
    l=0.24
    rotor_offsets=[(l,l),(-l,l),(-l,-l),(l,-l)]
    rotors=[]
    for bx,by in rotor_offsets:
        wx=x+bx*math.cos(yaw)-by*math.sin(yaw)
        wy=y+bx*math.sin(yaw)+by*math.cos(yaw)
        rotors.append(proj(wx,wy,z))
    d.line((rotors[0],rotors[2]),fill='#23364D',width=5)
    d.line((rotors[1],rotors[3]),fill='#23364D',width=5)
    for pnt in rotors:
        rx,ry=pnt
        d.ellipse((rx-8,ry-8,rx+8,ry+8),fill='#45A1F5',outline='white',width=2)
    d.ellipse((center[0]-6,center[1]-6,center[0]+6,center[1]+6),fill='#D94F4F',outline='white',width=2)
    # Compact status panel.
    d.rounded_rectangle((675,84,930,256),radius=12,fill='white',outline='#DCE4EE',width=2)
    t=float(r['t_s'])-(tmax-12.57)
    err=math.sqrt(float(r['ex_m'])**2+float(r['ey_m'])**2+float(r['ez_m'])**2)
    d.text((695,103),'BAG TELEMETRY',font=small,fill='#1976D2')
    d.text((695,137),f'period time  {t:4.1f} / 12.6 s',font=mini,fill='#172B4D')
    d.text((695,165),f'position  ({x: .2f}, {y: .2f}, {z: .2f}) m',font=mini,fill='#172B4D')
    d.text((695,193),f'position error  {err:.2f} m',font=mini,fill='#172B4D')
    d.text((695,221),f'target altitude  {float(r["zd_m"]):.1f} m',font=mini,fill='#172B4D')
    # Legend and honesty note.
    d.line((690,303,725,303),fill='#1976D2',width=4); d.text((735,294),'Desired path',font=mini,fill='#56657A')
    d.line((690,333,725,333),fill='#F08C32',width=4); d.text((735,324),'Measured path',font=mini,fill='#56657A')
    d.text((690,380),'Measured positions from ROS bag',font=mini,fill='#172B4D')
    d.text((690,405),'Attitude icon follows commanded yaw',font=mini,fill='#56657A')
    d.text((690,430),'3-D replay, not an RViz screen capture',font=mini,fill='#B24A4A')
    # Footer note.
    d.text((36,600),'One full reference period · measured trajectory orange · commanded circle blue',font=mini,fill='#56657A')
    frames.append(im)
out=ROOT/'flight_3d_replay.mp4'
# Save frames for the native AVFoundation encoder.
frame_dir=Path('/tmp/lab3_flight3d_frames')
frame_dir.mkdir(exist_ok=True)
for i,im in enumerate(frames): im.save(frame_dir/f'{i:05d}.png')
print(f'frames={len(frames)} duration={len(frames)/7:.3f}s dir={frame_dir}')
