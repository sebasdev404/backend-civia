import os
import urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter

COVERS_DIR = os.path.join(os.path.dirname(__file__), "static", "covers")
os.makedirs(COVERS_DIR, exist_ok=True)

# Unsplash thematic photography for civic posts
THEMES = [
    {
        "filename": "ig_cover_comuna6.jpg",
        "url": "https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?w=800&auto=format&fit=crop&q=80",
        "fallback_color": (30, 60, 110),
        "badge": "VÍAS Y MALLA VIAL",
        "title": "Recorrido Comuna 6: El Limonar y Timanco",
        "subtitle": "Deterioro de la malla vial e intervención"
    },
    {
        "filename": "ig_cover_malecon.jpg",
        "url": "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=800&auto=format&fit=crop&q=80",
        "fallback_color": (90, 20, 20),
        "badge": "SEGURIDAD Y ALUMBRADO",
        "title": "Malecón del Río Magdalena",
        "subtitle": "Inspección de luminarias y convivencia"
    },
    {
        "filename": "ig_cover_ceibas.jpg",
        "url": "https://images.unsplash.com/photo-1530587191325-3db32d826c18?w=800&auto=format&fit=crop&q=80",
        "fallback_color": (20, 80, 50),
        "badge": "MEDIO AMBIENTE",
        "title": "Río Las Ceibas y La Toma",
        "subtitle": "Control ambiental y recolección de residuos"
    },
    {
        "filename": "ig_cover_salud.jpg",
        "url": "https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?w=800&auto=format&fit=crop&q=80",
        "fallback_color": (70, 25, 90),
        "badge": "SALUD PÚBLICA",
        "title": "Red de Centros de Salud de Neiva",
        "subtitle": "ESE Carmen Emilia Ospina y Hospital"
    },
    {
        "filename": "default_cover.jpg",
        "url": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800&auto=format&fit=crop&q=80",
        "fallback_color": (25, 35, 55),
        "badge": "CIVIA INTELIGENCIA",
        "title": "Johan Steed Ortiz Fernández",
        "subtitle": "Monitoreo Ciudadano Alcaldía de Neiva 2026"
    }
]

def load_system_font(size: int, bold: bool = False):
    font_names = [
        "C:\\Windows\\Fonts\\segoeuib.ttf" if bold else "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\calibrib.ttf" if bold else "C:\\Windows\\Fonts\\calibri.ttf"
    ]
    for fn in font_names:
        if os.path.exists(fn):
            try:
                return ImageFont.truetype(fn, size)
            except Exception:
                continue
    return ImageFont.load_default()

def process_cover(item):
    filename = item["filename"]
    filepath = os.path.join(COVERS_DIR, filename)
    img = None

    # Try downloading real photography
    try:
        req = urllib.request.Request(
            item["url"], 
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = resp.read()
            from io import BytesIO
            img = Image.open(BytesIO(data)).convert("RGB")
            img = img.resize((800, 500), Image.Resampling.LANCZOS)
            print(f"Downloaded real photo for {filename}")
    except Exception as e:
        print(f"Could not download photo for {filename} ({e}), creating high-res graphic cover.")

    if img is None:
        # Create stylish graphic background
        img = Image.new("RGB", (800, 500), color=item["fallback_color"])
        draw = ImageDraw.Draw(img)
        # Gradient effect
        for y in range(500):
            alpha = int(120 * (y / 500))
            draw.line([(0, y), (800, y)], fill=(alpha // 2, alpha // 3, alpha // 2))

    # Add dark gradient overlay at the bottom so text is crystal clear
    overlay = Image.new("RGBA", (800, 500), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    # Top header subtle dark band
    for y in range(80):
        opacity = int(160 * (1 - (y / 80)))
        overlay_draw.line([(0, y), (800, y)], fill=(0, 0, 0, opacity))

    # Bottom dark gradient
    for y in range(220, 500):
        factor = (y - 220) / 280
        opacity = int(220 * factor)
        overlay_draw.line([(0, y), (800, y)], fill=(10, 15, 26, opacity))

    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    font_badge = load_system_font(18, bold=True)
    font_title = load_system_font(30, bold=True)
    font_sub = load_system_font(20, bold=False)
    font_tag = load_system_font(15, bold=False)

    # Pill badge
    badge_text = f"  {item['badge']}  "
    draw.rounded_rectangle([(40, 270), (40 + len(badge_text) * 11 + 20, 305)], radius=6, fill=(234, 88, 12, 230))
    draw.text((48, 276), badge_text.strip(), font=font_badge, fill=(255, 255, 255))

    # Title
    draw.text((40, 320), item["title"], font=font_title, fill=(255, 255, 255))

    # Subtitle
    draw.text((40, 365), item["subtitle"], font=font_sub, fill=(226, 232, 240))

    # Footer channel info
    draw.text((40, 445), "CIVIA • Monitoreo Multicanal Alcaldía de Neiva • Meta Graph API", font=font_tag, fill=(148, 163, 184))

    img.save(filepath, "JPEG", quality=92)
    print(f"Generated clean, sharp cover: {filepath} ({os.path.getsize(filepath)} bytes)")

if __name__ == "__main__":
    for theme in THEMES:
        process_cover(theme)
    print("All covers updated successfully!")
