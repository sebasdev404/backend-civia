import os
import shutil

covers_dir = os.path.join(os.path.dirname(__file__), "static", "covers")

# Real photos from Johan Steed
# 1. Salud: 275486829735525_1599741428833940.jpg (Johan's video about health prevention in Neiva)
# 2. Infraestructura / Malla vial: 275486829735525_1629268052547944.jpg (Johan inspecting street / road work)
# 3. Malecón / Seguridad: 275486829735525_1602751481866268.jpg (Johan in community / territory)
# 4. Medio ambiente / Ceibas: 275486829735525_1600030538805029.jpg (Johan with community)

mappings = {
    "ig_cover_salud.jpg": "275486829735525_1599741428833940.jpg",
    "ig_cover_comuna6.jpg": "275486829735525_1629268052547944.jpg",
    "ig_cover_malecon.jpg": "275486829735525_1602751481866268.jpg",
    "ig_cover_ceibas.jpg": "275486829735525_1600030538805029.jpg"
}

for dest_name, src_name in mappings.items():
    src_path = os.path.join(covers_dir, src_name)
    dest_path = os.path.join(covers_dir, dest_name)
    if os.path.exists(src_path):
        shutil.copy2(src_path, dest_path)
        print(f"Copied real Johan Steed photo {src_name} -> {dest_name}")
    else:
        print(f"Source not found: {src_path}")

print("Instagram covers successfully replaced with REAL Johan Steed photos!")
