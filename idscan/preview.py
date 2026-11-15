from PIL import Image


def fit_preview(image, size, background="#F1F4F8"):
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    canvas = Image.new("RGB", (width, height), background)
    if image is None:
        return canvas
    thumb = image.convert("RGB").copy()
    thumb.thumbnail((max(1, width - 16), max(1, height - 16)), Image.Resampling.LANCZOS)
    canvas.paste(thumb, ((width - thumb.width) // 2, (height - thumb.height) // 2))
    return canvas
