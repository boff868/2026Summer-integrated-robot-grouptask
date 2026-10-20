#!/usr/bin/env python3
"""Build the Chinese MIT VNAV Lab 3 report from the recorded ROS CSV data."""
import csv
import math
import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "lab3_report.pdf"
RESULTS = ROOT / "results"
W, H = A4
LEFT, RIGHT = 46, 46
CONTENT_W = W - LEFT - RIGHT
INK = colors.HexColor("#172B4D")
MUTED = colors.HexColor("#56657A")
BLUE = colors.HexColor("#1976D2")
TEAL = colors.HexColor("#00897B")
ORANGE = colors.HexColor("#F08C32")
GRID = colors.HexColor("#DCE4EE")
PALE = colors.HexColor("#F3F7FB")
RED = colors.HexColor("#C84C4C")
FONT = "STSong-Light"

pdfmetrics.registerFont(UnicodeCIDFont(FONT))
styles = {
    "body": ParagraphStyle("body", fontName=FONT, fontSize=9.2, leading=14.0,
                            textColor=INK, spaceAfter=4, wordWrap="CJK"),
    "small": ParagraphStyle("small", fontName=FONT, fontSize=7.7, leading=11.3,
                             textColor=MUTED, wordWrap="CJK"),
    "tiny": ParagraphStyle("tiny", fontName=FONT, fontSize=6.8, leading=9.1,
                            textColor=MUTED, wordWrap="CJK"),
    "cell": ParagraphStyle("cell", fontName=FONT, fontSize=8.1, leading=11.0,
                            textColor=INK, wordWrap="CJK"),
    "cellhead": ParagraphStyle("cellhead", fontName=FONT, fontSize=8.1,
                                leading=11.0, textColor=colors.white,
                                wordWrap="CJK"),
    "center": ParagraphStyle("center", fontName=FONT, fontSize=9.0, leading=13,
                              alignment=TA_CENTER, textColor=INK, wordWrap="CJK"),
}


def rows(name):
    with open(RESULTS / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


circle = rows("circle_moderate2.csv")
hover = rows("static_hover_final.csv")
circle_metrics = __import__("json").loads((RESULTS / "circle_moderate2_metrics.json").read_text())
hover_metrics = __import__("json").loads((RESULTS / "static_hover_final_metrics.json").read_text())


def p(c, text, x, y, width=CONTENT_W, style="body"):
    para = Paragraph(text, styles[style])
    _, height = para.wrap(width, H)
    para.drawOn(c, x, y - height)
    return y - height


def heading(c, title, y):
    c.setFillColor(INK)
    c.setFont(FONT, 17)
    c.drawString(LEFT, y, title)
    c.setStrokeColor(BLUE)
    c.setLineWidth(2)
    c.line(LEFT, y - 8, LEFT + 54, y - 8)
    return y - 25


def subheading(c, title, y):
    c.setFillColor(BLUE)
    c.setFont(FONT, 11.2)
    c.drawString(LEFT, y, title)
    return y - 17


def footer(c, n):
    c.setStrokeColor(GRID)
    c.setLineWidth(0.6)
    c.line(LEFT, 31, W - RIGHT, 31)
    c.setFont(FONT, 7.2)
    c.setFillColor(MUTED)
    c.drawString(LEFT, 19, "MIT VNAV Lab 3 · 无人机路径规划与轨迹跟踪")
    c.drawRightString(W - RIGHT, 19, f"{n} / 6")


def new_page(c, n, title=None):
    if title:
        c.setFillColor(MUTED)
        c.setFont(FONT, 7.5)
        c.drawString(LEFT, H - 27, title)
    footer(c, n)


def draw_table(c, data, x, top, widths, row_heights=None, font_size=None):
    cooked = []
    for ri, row in enumerate(data):
        style_name = "cellhead" if ri == 0 else "cell"
        cooked.append([Paragraph(str(v), styles[style_name]) for v in row])
    tbl = Table(cooked, colWidths=widths, rowHeights=row_heights, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.45, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
    ]))
    tw, th = tbl.wrapOn(c, W, H)
    tbl.drawOn(c, x, top - th)
    return top - th


def polyline(c, points, color, width=1.7):
    if len(points) < 2:
        return
    path = c.beginPath()
    path.moveTo(points[0][0], points[0][1])
    for xx, yy in points[1:]:
        path.lineTo(xx, yy)
    c.setStrokeColor(color)
    c.setLineWidth(width)
    c.drawPath(path)


def chart_xy(c, data, x, y, w, h, title="俯视轨迹（最后一个参考周期）"):
    c.setFillColor(INK)
    c.setFont(FONT, 9.2)
    c.drawString(x, y + h + 17, title)
    # A square coordinate area, with x/y from -6 to 6 m.
    size = min(w - 45, h - 31)
    ox = x + (w - size) / 2 + 8
    oy = y + (h - size) / 2
    scale = size / 12.0
    c.setStrokeColor(GRID)
    c.setLineWidth(0.5)
    for k in range(-6, 7, 2):
        xx, yy = ox + (k + 6) * scale, oy + (k + 6) * scale
        c.line(xx, oy, xx, oy + size)
        c.line(ox, yy, ox + size, yy)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 6.5)
        c.drawCentredString(xx, oy - 11, str(k))
        c.drawRightString(ox - 4, yy - 2, str(k))
    c.setStrokeColor(colors.HexColor("#AAB7C6"))
    c.rect(ox, oy, size, size, stroke=1, fill=0)
    c.setFillColor(MUTED)
    c.setFont(FONT, 7)
    c.drawCentredString(ox + size / 2, oy - 23, "x 位置 / m")
    c.saveState()
    c.translate(ox - 27, oy + size / 2)
    c.rotate(90)
    c.drawCentredString(0, 0, "y 位置 / m")
    c.restoreState()
    cutoff = max(float(r["t_s"]) for r in data) - 12.57
    section = [r for r in data if float(r["t_s"]) >= cutoff]
    target, actual = [], []
    for r in section:
        target.append((ox + (float(r["xd_m"]) + 6) * scale,
                       oy + (float(r["yd_m"]) + 6) * scale))
        actual.append((ox + (float(r["x_m"]) + 6) * scale,
                       oy + (float(r["y_m"]) + 6) * scale))
    polyline(c, target, BLUE, 1.7)
    polyline(c, actual, ORANGE, 1.3)
    # Legend
    ly = y + 2
    c.setStrokeColor(BLUE); c.setLineWidth(2); c.line(x + w/2 - 58, ly, x + w/2 - 42, ly)
    c.setFillColor(MUTED); c.setFont(FONT, 7.3); c.drawString(x + w/2 - 37, ly - 2.5, "参考")
    c.setStrokeColor(ORANGE); c.line(x + w/2 + 12, ly, x + w/2 + 28, ly)
    c.setFillColor(MUTED); c.drawString(x + w/2 + 33, ly - 2.5, "实测")


def chart_series(c, data, series, x, y, w, h, title, y_min, y_max, time_window=None,
                 target_line=None, y_label="误差 / m"):
    c.setFillColor(INK)
    c.setFont(FONT, 9.2)
    c.drawString(x, y + h + 17, title)
    lx, rx, by, ty = x + 45, x + w - 12, y + 28, y + h - 7
    c.setStrokeColor(GRID); c.setLineWidth(0.5)
    for i in range(5):
        yy = by + (ty-by)*i/4
        val = y_min + (y_max-y_min)*i/4
        c.line(lx, yy, rx, yy)
        c.setFillColor(MUTED); c.setFont("Helvetica", 6.5)
        c.drawRightString(lx - 5, yy - 2, f"{val:.1f}")
    t0 = min(float(r["t_s"]) for r in data)
    t1 = max(float(r["t_s"]) for r in data)
    if time_window is not None:
        t0 = max(t0, t1 - time_window)
    subset = [r for r in data if float(r["t_s"]) >= t0]
    denom_t = max(1e-9, max(float(r["t_s"]) for r in subset) - t0)
    colorset = [BLUE, ORANGE, TEAL, RED]
    for j, key in enumerate(series):
        pts = []
        for r in subset:
            tv = float(r["t_s"])-t0
            vv = float(r[key])
            px = lx + tv/denom_t*(rx-lx)
            py = by + (max(y_min, min(y_max, vv))-y_min)/(y_max-y_min)*(ty-by)
            pts.append((px, py))
        polyline(c, pts, colorset[j], 1.15)
    c.setStrokeColor(colors.HexColor("#AAB7C6")); c.setLineWidth(.7)
    c.line(lx, by, lx, ty); c.line(lx, by, rx, by)
    c.setFillColor(MUTED); c.setFont(FONT, 6.7)
    c.drawCentredString((lx+rx)/2, y + 6, "周期内时间 / s")
    c.saveState(); c.translate(x + 5, (by+ty)/2); c.rotate(90)
    c.drawCentredString(0, 0, y_label); c.restoreState()
    # Legend underneath plot.
    total_w = len(series) * 68
    sx = x + (w-total_w)/2
    for j, key in enumerate(series):
        c.setStrokeColor(colorset[j]); c.setLineWidth(2); c.line(sx+j*68, y-4, sx+j*68+10, y-4)
        c.setFillColor(MUTED); c.setFont(FONT, 6.8)
        labels = {"ex_m":"x", "ey_m":"y", "ez_m":"z", "z_m":"实测 z", "zd_m":"目标 z"}
        c.drawString(sx+j*68+13, y-6.5, labels.get(key, key))


def draw_callout(c, x, y, w, h, label, value, detail, accent=BLUE):
    c.setFillColor(PALE); c.roundRect(x, y, w, h, 8, stroke=0, fill=1)
    c.setFillColor(accent); c.rect(x, y, 4, h, stroke=0, fill=1)
    c.setFillColor(MUTED); c.setFont(FONT, 7.5); c.drawString(x+12, y+h-16, label)
    c.setFillColor(INK); c.setFont("Helvetica-Bold", 18); c.drawString(x+12, y+h-39, value)
    c.setFillColor(MUTED); c.setFont(FONT, 7); c.drawString(x+12, y+8, detail)


c = canvas.Canvas(str(OUT), pagesize=A4)
c.setTitle("MIT VNAV Lab 3：无人机路径规划与轨迹跟踪")
c.setAuthor("VNAV Lab 3 submission")

# Page 1 — overview and measured outcome.
c.setFillColor(PALE); c.rect(0, H-230, W, 230, stroke=0, fill=1)
c.setFillColor(BLUE); c.setFont(FONT, 9.5); c.drawString(LEFT, H-54, "课程实验报告  /  LAB 3")
c.setFillColor(INK); c.setFont(FONT, 24); c.drawString(LEFT, H-95, "无人机路径规划与轨迹跟踪")
c.setFillColor(MUTED); c.setFont(FONT, 10); c.drawString(LEFT, H-119, "MIT VNAV · 几何控制器、圆轨迹生成与实测评估")
c.setFillColor(MUTED); c.setFont(FONT, 8)
c.drawString(LEFT, H-151, "实验环境：ROS Noetic + TESSE/Unity 仿真（Docker 隔离网络）")
c.drawString(LEFT, H-168, "参考轨迹：半径 5 m、目标高度 2 m、角速度 0.5 rad/s")
c.drawString(LEFT, H-185, "记录日期：2026-10-19（本地运行记录）")
y = H-260
y = p(c, "<b>摘要。</b> 本实验实现并运行基于 SE(3) 的四旋翼几何位置/姿态控制器，生成并跟踪定高圆轨迹；另完成旋翼旋向改变后的分配矩阵秩分析，以及机体二次阻力补偿推导。仿真记录显示，圆轨迹连续运行 46.38 s（约 3.69 个周期），全程三维位置 RMSE 为 0.658 m；静态悬停在去除前 5 s 后的三维 RMSE 为 0.154 m。实验仍存在约 0.12–0.16 m 的稳态高度偏差，报告保留该误差并据此讨论改进方向。", LEFT, y)
y -= 20
draw_callout(c, LEFT, y-57, 155, 55, "圆轨迹 · 全程位置 RMSE", "0.658 m", "46.38 s / 2274 状态样本", BLUE)
draw_callout(c, LEFT+170, y-57, 155, 55, "静态悬停 · 稳定段 RMSE", "0.154 m", "去除起始 5 s / 1885 样本", TEAL)
draw_callout(c, LEFT+340, y-57, 155, 55, "圆轨迹 · 完成周期数", "≈ 3.69", "T = 2π / 0.5 = 12.57 s", ORANGE)
chart_xy(c, circle, LEFT+5, 115, CONTENT_W-10, 270)
p(c, "图 1. 最后一个参考周期的俯视轨迹。橙色实测曲线总体跟随蓝色目标圆；图中保留短时偏差，定量误差见第 3 页。", LEFT, 94, CONTENT_W, "small")
new_page(c, 1)
c.showPage()

# Page 2 — method and implementation.
new_page(c, 2, "实验方法")
y = heading(c, "控制器与轨迹生成", H-56)
y = p(c, "系统以位置、速度、姿态和机体系角速度为状态，输入为四个旋翼的带符号角速度。控制循环按 100 Hz 运行，订阅 <font name='Courier'>/desired_state</font> 与 <font name='Courier'>/current_state</font>，发布 <font name='Courier'>/rotor_speed_cmds</font>。轨迹节点以 500 Hz 发布期望状态。", LEFT, y)
y -= 10
# Four-stage implementation diagram.
box_y = y-49
labels = [("期望轨迹", "位置 / 速度 / 加速度 / yaw"),
          ("位置控制", "误差反馈 + 重力 + 阻力补偿"),
          ("姿态控制", "构造 R*，计算 eR 与 eΩ"),
          ("控制分配", "4×4 分配矩阵 → 转子速度")]
box_w = 116
for i, (title, desc) in enumerate(labels):
    bx = LEFT+i*(box_w+12)
    c.setFillColor(PALE); c.roundRect(bx, box_y, box_w, 42, 6, stroke=0, fill=1)
    c.setFillColor(BLUE if i < 3 else TEAL); c.setFont(FONT, 8.5); c.drawCentredString(bx+box_w/2, box_y+27, title)
    c.setFillColor(MUTED); c.setFont(FONT, 6.1); c.drawCentredString(bx+box_w/2, box_y+12, desc)
    if i < 3:
        c.setStrokeColor(MUTED); c.setLineWidth(1); c.line(bx+box_w+2, box_y+21, bx+box_w+9, box_y+21)
        c.line(bx+box_w+6, box_y+24, bx+box_w+9, box_y+21); c.line(bx+box_w+6, box_y+18, bx+box_w+9, box_y+21)
y = box_y-22
y = subheading(c, "参考圆轨迹", y)
y = p(c, "以 ROS 单调时间 t 定义：", LEFT, y)
c.setFillColor(PALE); c.roundRect(LEFT, y-50, CONTENT_W, 43, 5, stroke=0, fill=1)
c.setFillColor(INK); c.setFont("Helvetica", 10)
c.drawString(LEFT+12, y-23, "x_d=5*sin(0.5*t),  y_d=5*cos(0.5*t),  z_d=2,  psi_d=-0.5*t")
c.drawString(LEFT+12, y-40, "v_d=[2.5*cos(0.5*t), -2.5*sin(0.5*t), 0]^T;  a_d=[-1.25*sin(0.5*t), -1.25*cos(0.5*t), 0]^T")
y -= 67
y = p(c, "因此圆轨迹周期 T = 4π ≈ 12.57 s。控制器用期望合力方向构造期望姿态 R*，结合期望 yaw 约束航向；几何姿态误差用于计算机体系力矩，再经分配矩阵反解到旋翼。转速输出使用 signed-sqrt 将有符号平方转速换回有符号角速度。", LEFT, y)
y -= 10
y = subheading(c, "控制律与实现要点", y)
y = p(c, "位置误差 ex = x - xd、速度误差 ev = v - vd。名义期望合力为 -Kx*ex - Kv*ev + m*g*e3 + m*ad；实现中在 z 轴增加限幅积分项，用于减轻悬停高度偏差。阻力模型依据机体系速度逐轴计算，并加入合力前馈补偿。姿态力矩包含几何误差反馈、角速度反馈和 omega x J*omega 项。", LEFT, y)
y -= 5
y = p(c, "实验参数：Kx = 2.5，Kv = 2.0，KR = 4.0，Komega = 1.2，Ki_z = 0.15；控制频率 100 Hz，旋翼速度限幅 500 rad/s。该限幅来自 launch 参数；实测常态旋翼指令约 46-54 rad/s。", LEFT, y)
new_page(c, 2)
c.showPage()

# Page 3 — circle result.
new_page(c, 3, "实验结果 · 圆轨迹")
y = heading(c, "圆轨迹跟踪结果", H-56)
y = p(c, "圆轨迹记录 46.38 s，参考周期 12.57 s，包含约 3.69 个完整周期。为同时呈现起始过渡与稳定跟踪表现，下表给出全程、起飞后 5 s 至结束、以及最后一个参考周期三种窗口。位置误差按 e = x - xd 计算，RMSE3D = sqrt(mean(ex^2 + ey^2 + ez^2))。", LEFT, y)
chart_xy(c, circle, LEFT+90, y-254, CONTENT_W-180, 220)
y -= 280
chart_series(c, circle, ["ex_m", "ey_m", "ez_m"], LEFT, y-185, CONTENT_W, 145,
             "最后周期内的位置误差", -2.5, 2.5, 12.57)
y -= 204
data = [["统计窗口", "样本数", "RMSE x / m", "RMSE y / m", "RMSE z / m", "RMSE 3D / m"],
        ["全程 46.38 s", "2274", "0.481", "0.346", "0.286", "0.658"],
        ["去除前 5 s", "2020", "0.502", "0.351", "0.303", "0.684"],
        ["最后周期 12.56 s", "608", "0.650", "0.352", "0.257", "0.782"]]
y = draw_table(c, data, LEFT, y, [115, 60, 78, 78, 78, 90])
y -= 12
y = p(c, "最后周期误差峰值 2.157 m；稳定段平均高度误差 −0.158 m（实测低于目标）。误差曲线的短时峰值会明显抬高最后周期 RMSE，因此图 1 中的总体形状与统计指标需一起解读。", LEFT, y, CONTENT_W, "small")
new_page(c, 3)
c.showPage()

# Page 4 — hover and discussion.
new_page(c, 4, "实验结果 · 静态悬停")
y = heading(c, "静态悬停与结果分析", H-56)
y = p(c, "静态测试目标为位置 (0, -0.24, 2) m、yaw = 0.785 rad。记录持续 42.74 s，共 2136 个状态样本。去除开始 5 s 的启动过渡后，水平位置误差近乎为零，主要误差来自高度方向。", LEFT, y)
chart_series(c, hover, ["z_m", "zd_m"], LEFT+4, y-240, CONTENT_W-8, 190,
             "静态悬停高度（稳定段）", 1.0, 2.25, 37.74, y_label="高度 / m")
y -= 276
data = [["统计窗口", "RMSE x / m", "RMSE y / m", "RMSE z / m", "RMSE 3D / m", "平均 z 误差 / m"],
        ["全程", "0.0270", "0.0258", "0.1599", "0.1642", "−0.1182"],
        ["去除前 5 s", "0.0008", "0.0009", "0.1539", "0.1539", "−0.1195"],
        ["最后 12.56 s", "<0.001", "<0.001", "0.1260", "0.1260", "-0.1067"]]
y = draw_table(c, data, LEFT, y, [104, 80, 80, 80, 80, 95])
y -= 15
y = subheading(c, "讨论与局限", y)
y = p(c, "水平悬停稳定，而垂直误差长期为负，说明当前积分补偿只能部分抵消仿真模型偏差。圆轨迹的高度均值误差也为负；可进一步核对质量/推力参数、积分状态初始化与限幅，并检查模拟器的旋翼推力映射。增加位置增益并非首选，因为高增益试验曾出现姿态翻转；当前参数下圆轨迹能连续完成多个周期。", LEFT, y)
y -= 6
y = p(c, "本报告以 ROS 仿真状态话题的采样记录计算指标；图表为 ROS bag 导出 CSV 后离线绘制。它们反映该次仿真的闭环跟踪性能，不代表真实无人机飞行性能。", LEFT, y, CONTENT_W, "small")
new_page(c, 4)
c.showPage()

# Page 5 — D1 and allocation rank proof.
new_page(c, 5, "附录 · 书面题")
y = heading(c, "附录 A：Deliverable 1 — ROS / Eigen 转换", H-56)
y = subheading(c, "A. Quaternion 转换", y)
y = p(c, "A1. 将 geometry_msgs 四元数转为 tf2 四元数：", LEFT, y)
c.setFillColor(PALE); c.roundRect(LEFT, y-31, CONTENT_W, 24, 4, stroke=0, fill=1)
c.setFillColor(INK); c.setFont("Courier", 8.4); c.drawString(LEFT+10, y-22, "tf2::fromMsg(quat_msg, quat_tf);")
y -= 42
y = p(c, "A2. 将 tf2 四元数转为 geometry_msgs 消息：", LEFT, y)
c.setFillColor(PALE); c.roundRect(LEFT, y-31, CONTENT_W, 24, 4, stroke=0, fill=1)
c.setFillColor(INK); c.setFont("Courier", 8.4); c.drawString(LEFT+10, y-22, "geometry_msgs::Quaternion quat_msg = tf2::toMsg(quat_tf);")
y -= 42
y = p(c, "A3. 提取 tf2 四元数的 w 分量：", LEFT, y)
c.setFillColor(PALE); c.roundRect(LEFT, y-31, CONTENT_W, 24, 4, stroke=0, fill=1)
c.setFillColor(INK); c.setFont("Courier", 8.4); c.drawString(LEFT+10, y-22, "quat_tf.getW();")
y -= 42
y = p(c, "B1. 单函数提取 yaw：", LEFT, y)
c.setFillColor(PALE); c.roundRect(LEFT, y-31, CONTENT_W, 24, 4, stroke=0, fill=1)
c.setFillColor(INK); c.setFont("Courier", 8.4); c.drawString(LEFT+10, y-22, "const double yaw = tf2::getYaw(quat_t);")
y -= 42
y = p(c, "B2. 转为 Eigen 3×3 旋转矩阵（tf2_eigen / tf2_geometry_msgs）：", LEFT, y)
c.setFillColor(PALE); c.roundRect(LEFT, y-48, CONTENT_W, 40, 4, stroke=0, fill=1)
c.setFillColor(INK); c.setFont("Courier", 8.1)
c.drawString(LEFT+10, y-22, "Eigen::Quaterniond q; tf2::fromMsg(quat_msg, q);")
c.drawString(LEFT+10, y-37, "const Eigen::Matrix3d R = q.toRotationMatrix();")
y -= 64
y = heading(c, "附录 B：旋向变化与控制分配矩阵", y-3)
y = p(c, "令 u_i = omega_i*abs(omega_i)，l = d/sqrt(2)，四个旋翼位置为 (l,l)、(-l,l)、(-l,-l)、(l,-l)。按讲义的 45 度机体系和阻力矩符号约定，正常构型：", LEFT, y)
c.setFillColor(PALE); c.roundRect(LEFT, y-65, CONTENT_W, 58, 4, stroke=0, fill=1)
c.setFillColor(INK); c.setFont("Courier", 8.2)
c.drawString(LEFT+9, y-22, "[f, taux, tauy, tauz]^T = Fa * u")
c.drawString(LEFT+9, y-38, "Fa = [ cf cf cf cf ; lcf lcf -lcf -lcf ;")
c.drawString(LEFT+9, y-53, "       -lcf lcf lcf -lcf ; cd -cd cd -cd ]")
y -= 79
y = p(c, "det(Fa) = -16*l^2*cf^3*cd，因此在 l、cf、cd 非零时 rank(Fa)=4。将旋翼 3、4 反向旋转只改变它们的 yaw 阻力矩符号，得到 Fb 的最后一行 [cd, -cd, -cd, cd]。该行恰为 pitch 行的 -cd/(l*cf) 倍，所以 rank(Fb)=3：pitch 与 yaw 不能独立指定，无法实现任意位置和 yaw 组合。", LEFT, y)
new_page(c, 5)
c.showPage()

# Page 6 — drag compensation and reproducibility.
new_page(c, 6, "附录 · 阻力补偿与复现")
y = heading(c, "附录 C：机体阻力补偿", H-56)
y = p(c, "题目给出的阻力在机体系中与速度平方成正比，并与速度方向相反。令 vb = R^T*v，则：", LEFT, y)
c.setFillColor(PALE); c.roundRect(LEFT, y-66, CONTENT_W, 59, 4, stroke=0, fill=1)
c.setFillColor(INK); c.setFont("Helvetica", 9.2)
c.drawString(LEFT+12, y-25, "D = diag(0.1, 0.1, 0.2)")
c.drawString(LEFT+12, y-45, "Fd_b = -D*(vb .* abs(vb));  m*vdot = R*f*e3 - m*g*e3 + R*Fd_b")
y -= 83
y = p(c, "因此期望合力可写成 Fdes = -Kx*ex - Kv*ev + m*g*e3 + m*ad - R*Fd_b（实现还叠加 z 轴积分项）。由于 Fd_b 本身指向速度反方向，减去预测阻力就相当于增加所需推力，以抵消这项扰动。代码在每个控制周期用当前里程计速度和姿态更新补偿。", LEFT, y)
y -= 18
y = heading(c, "复现实验与交付结构", y)
data = [["文件 / 目录", "用途"],
        ["controller_pkg/", "ROS catkin 包：控制器、轨迹节点、静态目标发布器、launch 与 RViz 配置"],
        ["results/*.bag", "原始 ROS bag：圆轨迹与静态悬停"],
        ["results/*.csv + *_metrics.json", "状态时序与本报告使用的统计结果"],
        ["deliverable_1.txt / deliverable_2.md", "单独提交的书面题答案；报告附录含同一内容"],
        ["circle_tracking.mp4 / .gif", "最后一个参考周期的俯视轨迹视频与 GIF 预览"],
        ["flight_3d_replay.mp4", "基于 ROS bag 实测位置的 3D 回放；机体朝向按期望 yaw 示意"],
        ["rviz_circle_tracking.mp4", "Docker 中 RViz2 窗口录屏；回放 circle_moderate2.csv 实测轨迹"],
        ["rviz_drone_flight.txt", "课程要求的公开视频链接文件；登录云盘并上传后填写链接"]]
y = draw_table(c, data, LEFT, y, [175, CONTENT_W-175])
y -= 15
y = p(c, "复现：在 ROS Noetic catkin 工作空间中将 controller_pkg 放入 src，执行 catkin_make；source devel/setup.bash 后运行 roslaunch controller_pkg codex_circle.launch。静态悬停可运行 roslaunch controller_pkg codex_static.launch。实验启动文件含控制器参数；修改参数后需重新记录 bag 再计算误差。", LEFT, y)
y -= 8
y = p(c, "参考资料：[1] MIT VNAV, Lab 3 Exercises, https://vnav.mit.edu/labs_2023/lab3/exercises.html；[2] MIT VNAV, Lecture 6: Quadrotor Dynamics, https://vnav.mit.edu/material/06-Control1-notes.pdf；[3] VNAV-labs code release VNAV2021, https://github.com/MIT-SPARK/VNAV-labs/releases/tag/VNAV2021；[4] T. Lee, M. Leok, N. H. McClamroch, “Geometric Tracking Control of a Quadrotor UAV on SE(3),” CDC 2010。", LEFT, y, CONTENT_W, "small")
y -= 10
y = p(c, "RViz 录屏说明：该视频在当前 Docker（Ubuntu 22.04、ROS 2 Humble）中运行 RViz2 并采集窗口画面，回放 circle_moderate2.csv 中已有的实测轨迹；绿色为参考轨迹，蓝色为实测路径，橙色为机体标记。它展示已有 ROS bag 数据，不代表本次新增的 TESSE 实时仿真。课程还要求将视频上传至 Google Drive 或 Dropbox 并设置公开访问链接；提交包附有本地 MP4，公开链接需在上传后填写。3D 回放中的机体朝向按期望 yaw 示意。", LEFT, y, CONTENT_W, "small")
new_page(c, 6)
c.save()
print(OUT)
