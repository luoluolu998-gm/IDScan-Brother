
from PIL import Image
from .imaging import mm_size

A4_W_MM = 210.0
A4_H_MM = 297.0


def px(mm, dpi):
    return round(mm / 25.4 * dpi)


def compose_a4(
    front,
    back,
    dpi_front,
    dpi_back,
    arrangement,
    output_dpi=300,
    margin_mm=8,
    gap_mm=8
):

    front_size = mm_size(front, *dpi_front)
    back_size = mm_size(back, *dpi_back)

    fw, fh = front_size
    bw, bh = back_size

    # 统一排列名称，避免空格影响判断
    arrangement = str(arrangement).strip()

    # 左右排列
    if arrangement == "左右排列":

        total_w = fw + gap_mm + bw
        max_h = max(fh, bh)

        if (
            total_w + 2 * margin_mm > A4_W_MM
            or max_h + 2 * margin_mm > A4_H_MM
        ):
            raise ValueError(
                "正反面无法按原始尺寸左右放入 A4 竖向页面。\n\n"
                f"正面尺寸：{fw:.1f} × {fh:.1f} mm\n"
                f"反面尺寸：{bw:.1f} × {bh:.1f} mm\n"
                f"左右总宽度：{total_w:.1f} mm\n"
                f"页面可用宽度：{A4_W_MM - 2 * margin_mm:.1f} mm\n"
                f"页面可用高度：{A4_H_MM - 2 * margin_mm:.1f} mm\n\n"
                "请尝试上下排列。"
            )

        x0 = (A4_W_MM - total_w) / 2

        positions = [
            (x0, (A4_H_MM - fh) / 2),
            (x0 + fw + gap_mm, (A4_H_MM - bh) / 2)
        ]

    # 上下排列
    elif arrangement == "上下排列":

        total_h = fh + gap_mm + bh
        max_w = max(fw, bw)

        if (
            max_w + 2 * margin_mm > A4_W_MM
            or total_h + 2 * margin_mm > A4_H_MM
        ):
            raise ValueError(
                "正反面无法按原始尺寸上下放入 A4 竖向页面。\n\n"
                f"正面尺寸：{fw:.1f} × {fh:.1f} mm\n"
                f"反面尺寸：{bw:.1f} × {bh:.1f} mm\n"
                f"上下总高度：{total_h:.1f} mm\n"
                f"页面可用宽度：{A4_W_MM - 2 * margin_mm:.1f} mm\n"
                f"页面可用高度：{A4_H_MM - 2 * margin_mm:.1f} mm\n\n"
                "请检查扫描图片是否正确去白边，或尝试左右排列。"
            )

        y0 = (A4_H_MM - total_h) / 2

        positions = [
            ((A4_W_MM - fw) / 2, y0 + bh + gap_mm),
            ((A4_W_MM - bw) / 2, y0)
        ]

    else:
        raise ValueError(
            f"未知排列方式：{arrangement!r}"
        )

    # 创建 A4 竖向画布
    canvas = Image.new(
        "RGB",
        (
            px(A4_W_MM, output_dpi),
            px(A4_H_MM, output_dpi)
        ),
        "white"
    )

    for img, pos, size in zip(
        (front, back),
        positions,
        (front_size, back_size)
    ):

        width_mm, height_mm = size

        target_w = px(width_mm, output_dpi)
        target_h = px(height_mm, output_dpi)

        # 只调整像素密度，保持物理尺寸和比例
        if img.size != (target_w, target_h):
            img = img.resize(
                (target_w, target_h),
                Image.Resampling.LANCZOS
            )

        x = px(pos[0], output_dpi)

        y = (
            canvas.height
            - px(pos[1], output_dpi)
            - target_h
        )

        canvas.paste(img, (x, y))

    return canvas
