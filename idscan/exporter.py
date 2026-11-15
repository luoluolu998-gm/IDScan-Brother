from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader


def save_output(image, path, fmt, dpi=300):

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fmt = fmt.upper()

    if fmt == "PDF":

        pdf = canvas.Canvas(
            str(path),
            pagesize=A4
        )

        page_w, page_h = A4

        pdf.drawImage(
            ImageReader(image),
            0,
            0,
            width=page_w,
            height=page_h
        )

        pdf.showPage()
        pdf.save()

    elif fmt == "JPG":

        image.convert("RGB").save(
            path,
            "JPEG",
            quality=95,
            dpi=(dpi, dpi)
        )

    elif fmt == "PNG":

        image.save(
            path,
            "PNG",
            dpi=(dpi, dpi)
        )

    else:
        raise ValueError("不支持的输出格式")

    return path