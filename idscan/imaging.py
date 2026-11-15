
from PIL import Image
import numpy as np
import cv2
import math


def _get_rect_angle(box):
    """根据矩形最长边计算倾斜角度。"""

    longest_length = 0
    angle = 0

    for i in range(4):
        p1 = box[i].astype(float)
        p2 = box[(i + 1) % 4].astype(float)

        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]

        length = math.hypot(dx, dy)

        if length > longest_length:
            longest_length = length
            angle = math.degrees(math.atan2(dy, dx))

    return (angle + 90) % 180 - 90


def find_card_contour(img):
    """
    多方法识别身份证主体。

    方法：
    1. Canny 边缘检测，适合灰色边框。
    2. 白色背景差异检测，适合正面图案丰富的身份证。
    3. 形态学连接，允许局部边缘断开。

    返回：
        angle：证件倾斜角度
        box：证件外接旋转矩形
    """

    image = np.array(img.convert("RGB"))

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_RGB2GRAY
    )

    image_h, image_w = gray.shape
    image_area = image_w * image_h

    if image_area <= 0:
        return None

    # 局部对比度增强
    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8)
    )

    enhanced = clahe.apply(gray)

    enhanced = cv2.GaussianBlur(
        enhanced,
        (5, 5),
        0
    )

    candidates = []

    # 根据图片尺寸自动调整连接范围
    kernel_size = max(
        9,
        min(41, round(min(image_w, image_h) * 0.01))
    )

    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (kernel_size, kernel_size)
    )

    # -------------------------------------------------
    # 方法一：Canny 边缘检测
    # 适合反面存在灰色轮廓的情况
    # -------------------------------------------------

    canny_settings = [
        (20, 60),
        (35, 100),
        (50, 150),
        (70, 200)
    ]

    for low, high in canny_settings:

        edges = cv2.Canny(
            enhanced,
            low,
            high
        )

        edges = cv2.morphologyEx(
            edges,
            cv2.MORPH_CLOSE,
            kernel,
            iterations=2
        )

        contours, _ = cv2.findContours(
            edges,
            cv2.RETR_LIST,
            cv2.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:

            if len(contour) < 4:
                continue

            rect = cv2.minAreaRect(contour)

            rect_w, rect_h = rect[1]

            if rect_w <= 0 or rect_h <= 0:
                continue

            short_side = min(rect_w, rect_h)
            long_side = max(rect_w, rect_h)

            ratio = long_side / short_side

            if not 1.35 <= ratio <= 1.90:
                continue

            rect_area = rect_w * rect_h
            area_ratio = rect_area / image_area

            if area_ratio < 0.008:
                continue

            if area_ratio > 0.30:
                continue

            contour_area = cv2.contourArea(contour)

            rectangularity = contour_area / rect_area

            # 不再要求轮廓非常完整
            if rectangularity < 0.08:
                continue

            box = cv2.boxPoints(rect)

            # 轮廓面积作为辅助评分
            score = rect_area * (
                0.3 + min(rectangularity, 1.0)
            )

            candidates.append({
                "score": score,
                "box": box
            })

    # -------------------------------------------------
    # 方法二：识别白色背景中的非白色区域
    # 适合正面颜色、文字、照片比较丰富的情况
    # -------------------------------------------------

    hsv = cv2.cvtColor(
        image,
        cv2.COLOR_RGB2HSV
    )

    saturation = hsv[:, :, 1]

    # 灰度明显低于白色，或者颜色饱和度明显高于背景
    dark_mask = cv2.threshold(
        gray,
        235,
        255,
        cv2.THRESH_BINARY_INV
    )[1]

    color_mask = cv2.threshold(
        saturation,
        22,
        255,
        cv2.THRESH_BINARY
    )[1]

    foreground = cv2.bitwise_or(
        dark_mask,
        color_mask
    )

    # 去除零散噪点
    small_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (3, 3)
    )

    foreground = cv2.morphologyEx(
        foreground,
        cv2.MORPH_OPEN,
        small_kernel,
        iterations=1
    )

    # 连接身份证内部文字、照片和图案形成的区域
    foreground = cv2.morphologyEx(
        foreground,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=3
    )

    contours, _ = cv2.findContours(
        foreground,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    for contour in contours:

        if len(contour) < 4:
            continue

        rect = cv2.minAreaRect(contour)

        rect_w, rect_h = rect[1]

        if rect_w <= 0 or rect_h <= 0:
            continue

        short_side = min(rect_w, rect_h)
        long_side = max(rect_w, rect_h)

        ratio = long_side / short_side

        if not 1.35 <= ratio <= 1.90:
            continue

        rect_area = rect_w * rect_h
        area_ratio = rect_area / image_area

        if area_ratio < 0.008:
            continue

        if area_ratio > 0.30:
            continue

        contour_area = cv2.contourArea(contour)

        if contour_area <= 0:
            continue

        rectangularity = contour_area / rect_area

        # 前景区域不一定填满整个身份证
        if rectangularity < 0.06:
            continue

        box = cv2.boxPoints(rect)

        score = rect_area * (
            0.4 + min(rectangularity, 1.0)
        )

        candidates.append({
            "score": score,
            "box": box
        })

    # -------------------------------------------------
    # 综合选择最合适的候选区域
    # -------------------------------------------------

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    best = candidates[0]

    box = np.int32(
        np.round(best["box"])
    )

    angle = _get_rect_angle(box)

    return {
        "angle": angle,
        "box": box
    }


def rotate_card(img, angle):
    """
    自动旋转证件。
    不拉伸图片，不改变原始比例。
    """

    if abs(angle) < 1.0:
        return img

    return img.rotate(
        angle,
        resample=Image.Resampling.BICUBIC,
        expand=True,
        fillcolor="white"
    )


def crop_card(img, threshold=245):
    """
    旋转后重新寻找证件区域并裁剪。
    """

    result = find_card_contour(img)

    if result is None:
        raise ValueError(
            "旋转后没有识别到身份证主体。\n\n"
            "请检查扫描图片，确保身份证没有被裁掉。"
        )

    box = result["box"]

    x_min = int(np.min(box[:, 0]))
    y_min = int(np.min(box[:, 1]))
    x_max = int(np.max(box[:, 0]))
    y_max = int(np.max(box[:, 1]))

    short_side = min(
        x_max - x_min,
        y_max - y_min
    )

    pad = max(
        3,
        round(short_side * 0.008)
    )

    left = max(0, x_min - pad)
    top = max(0, y_min - pad)

    right = min(img.width, x_max + pad)
    bottom = min(img.height, y_max + pad)

    if right <= left or bottom <= top:
        raise ValueError("身份证裁剪范围异常。")

    return img.crop(
        (left, top, right, bottom)
    )


def load_and_trim(path, threshold=245):

    source = Image.open(path)

    dpi = source.info.get(
        "dpi",
        (300, 300)
    )

    img = source.convert("RGB")

    try:
        dx = float(dpi[0]) if dpi[0] else 300.0
        dy = float(dpi[1]) if dpi[1] else 300.0

    except Exception:
        dx = dy = 300.0

    # 第一步：寻找身份证主体
    result = find_card_contour(img)

    if result is None:
        raise ValueError(
            "没有找到身份证主体。\n\n"
            "本次已尝试边缘检测和背景差异检测，"
            "仍然无法确定身份证位置。\n\n"
            "请检查图片是否完整，"
            "以及身份证是否与扫描背景过于接近。"
        )

    # 第二步：自动旋转
    angle = result["angle"]

    img = rotate_card(
        img,
        angle
    )

    # 第三步：重新识别并裁剪
    img = crop_card(
        img,
        threshold
    )

    return img, dx, dy


def mm_size(image, dpi_x, dpi_y):

    width_mm = image.width / dpi_x * 25.4
    height_mm = image.height / dpi_y * 25.4

    return width_mm, height_mm
