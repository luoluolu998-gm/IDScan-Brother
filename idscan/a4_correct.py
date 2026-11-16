"""对整张 A4 扫描图做保守的小角度校正，不裁切、不做 90/180 度旋转。"""
import math
import cv2
import numpy as np
from PIL import Image


def estimate_skew(image, max_angle=3.0):
    rgb = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape

    scale = min(1.0, 1600.0 / max(h, w))
    if scale < 1:
        gray = cv2.resize(
            gray, None,
            fx=scale, fy=scale,
            interpolation=cv2.INTER_AREA
        )

    edges = cv2.Canny(
        cv2.GaussianBlur(gray, (5, 5), 0),
        50, 150
    )

    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 1800,
        threshold=max(40, min(gray.shape) // 8),
        minLineLength=max(80, min(gray.shape) // 5),
        maxLineGap=20,
    )

    if lines is None:
        return 0.0

    # 统一为 N×4，兼容 OpenCV 返回的不同数组形状
    lines = np.asarray(lines).reshape(-1, 4)

    angles = []
    weights = []

    for x1, y1, x2, y2 in lines:
        x1, y1, x2, y2 = map(float, (x1, y1, x2, y2))

        length = math.hypot(x2 - x1, y2 - y1)
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        angle = ((angle + 45) % 90) - 45

        if abs(angle) <= max_angle and length >= min(gray.shape) * 0.12:
            angles.append(angle)
            weights.append(length)

    if not angles:
        return 0.0

    angle = float(np.average(angles, weights=weights))

    return angle if abs(angle) <= max_angle else 0.0


def correct_a4(image, max_angle=3.0):
    image = image.convert("RGB")

    angle = estimate_skew(image, max_angle=max_angle)

    if abs(angle) < 0.25:
        return image, angle

    # 保持原页面像素尺寸；边缘用白色补齐，不裁切内容。
    corrected = image.rotate(
        angle,
        resample=Image.Resampling.BICUBIC,
        expand=False,
        fillcolor="white"
    )

    return corrected, angle