from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def make_icon(size: int, output_path: str):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background: vertical gradient from #2a2a2a (top) to #080808 (bottom)
    for y in range(size):
        t = y / (size - 1)
        r = int(0x2a + (0x08 - 0x2a) * t)
        g = int(0x2a + (0x08 - 0x2a) * t)
        b = int(0x2a + (0x08 - 0x2a) * t)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    # Apply rounded corners mask
    radius = int(size * 0.23)
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    img.putalpha(mask)

    # --- Text "CUT" ---
    font_size = int(size * 0.30)
    font = None
    for font_name in [
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/Library/Fonts/Arial Black.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]:
        try:
            font = ImageFont.truetype(font_name, font_size)
            break
        except (IOError, OSError):
            continue
    if font is None:
        font = ImageFont.load_default()

    text = "CUT"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    text_x = (size - text_w) // 2 - bbox[0]
    text_y = int(size * 0.55) - text_h // 2 - bbox[1]

    # Subtle glow: draw text multiple times with low opacity
    glow_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    for offset in range(6, 0, -1):
        opacity = int(18 * (7 - offset))
        for dx in (-offset, 0, offset):
            for dy in (-offset, 0, offset):
                glow_draw.text((text_x + dx, text_y + dy), text, font=font, fill=(255, 255, 255, opacity))
    blurred = glow_layer.filter(ImageFilter.GaussianBlur(radius=max(1, size // 64)))
    img = Image.alpha_composite(img, blurred)

    # Final white text
    draw = ImageDraw.Draw(img)
    draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))

    # --- Three bars ---
    bar_x = int(size * 0.28)
    bar_h = max(2, int(size * 0.015))
    bar_gap = int(size * 0.035)
    # Start bars below text
    bars_top = text_y + text_h + int(size * 0.045)

    bars = [
        (int(size * 0.59), (0x4a, 0xde, 0x80)),
        (int(size * 0.37), (0xfb, 0xbf, 0x24)),
        (int(size * 0.22), (0x60, 0xa5, 0xfa)),
    ]

    for i, (bar_w, color) in enumerate(bars):
        by = bars_top + i * (bar_h + bar_gap)
        # Bar fill
        draw.rectangle([bar_x, by, bar_x + bar_w - 1, by + bar_h - 1], fill=(*color, 255))
        # White highlight on top 35% of bar
        hl_h = max(1, int(bar_h * 0.35))
        draw.rectangle([bar_x, by, bar_x + bar_w - 1, by + hl_h - 1], fill=(255, 255, 255, 80))

    # --- Glass gloss overlay ---
    gloss = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gloss_draw = ImageDraw.Draw(gloss)
    half = size // 2
    for y in range(half):
        t = y / (half - 1) if half > 1 else 0
        alpha = int(70 + (15 - 70) * t)
        gloss_draw.line([(0, y), (size, y)], fill=(255, 255, 255, alpha))
    img = Image.alpha_composite(img, gloss)

    # --- Thin inner border: 1px white at opacity 30 ---
    draw = ImageDraw.Draw(img)
    border_mask = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    border_draw = ImageDraw.Draw(border_mask)
    border_draw.rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=radius,
        outline=(255, 255, 255, 30), width=1
    )
    img = Image.alpha_composite(img, border_mask)

    # Re-apply rounded corner mask to keep clean edges
    final = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    final.paste(img, mask=mask)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    final.save(output_path, "PNG")
    print(f"Generated {output_path} ({size}x{size})")


if __name__ == "__main__":
    make_icon(192, "frontend/static/icon-192.png")
    make_icon(512, "frontend/static/icon-512.png")
