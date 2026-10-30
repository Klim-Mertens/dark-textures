# Программа рисует текстуры 16x16 в стиле Dark Fantasy
# и собирает из них ресурспаки для Minecraft 1.20.1.
# Запуск: python make_packs.py  (нужна библиотека Pillow: pip install pillow)
# Готовые zip-архивы появятся в папке ../packs, картинки для сайта в ../images

import json
import os
import random
import zipfile
from io import BytesIO

from PIL import Image

SIZE = 16          # размер одной текстуры в пикселях
PACK_FORMAT = 15   # номер формата ресурспака для версии 1.20.1

# папка, где лежит этот файл, от неё считаем остальные пути
HERE = os.path.dirname(os.path.abspath(__file__))
PACKS_DIR = os.path.join(HERE, "..", "packs")
IMAGES_DIR = os.path.join(HERE, "..", "images")


# ---------- вспомогательные функции ----------

def hex_to_rgb(color):
    # "#2a1f3d" -> (42, 31, 61)
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def noise(palette, seed):
    # Заполняем картинку случайными цветами из палитры (это "шум" камня, земли и т.д.)
    rnd = random.Random(seed)
    img = Image.new("RGBA", (SIZE, SIZE))
    colors = [hex_to_rgb(c) for c in palette]
    for x in range(SIZE):
        for y in range(SIZE):
            img.putpixel((x, y), rnd.choice(colors) + (255,))
    return img


# ---------- блоки ----------

def stone(seed):
    return noise(["#2b2733", "#332e3d", "#3b3547", "#26222d"], seed)


def cobblestone(seed):
    # Сначала шум, потом тёмные "швы" между камнями
    img = noise(["#3a3445", "#443d52", "#4d455c"], seed)
    rnd = random.Random(seed)
    dark = hex_to_rgb("#16131b") + (255,)
    for y in (0, 5, 10):
        for x in range(SIZE):
            img.putpixel((x, y), dark)
        # вертикальные швы в каждом ряду в случайных местах
        for _ in range(2):
            x = rnd.randint(0, SIZE - 1)
            for dy in range(5):
                if y + dy < SIZE:
                    img.putpixel((x, y + dy), dark)
    return img


def bricks(brick_palette, mortar, seed):
    # Кирпичи высотой 4 пикселя и длиной 8, каждый второй ряд со сдвигом
    img = noise(brick_palette, seed)
    m = hex_to_rgb(mortar) + (255,)
    for y in range(SIZE):
        for x in range(SIZE):
            row = y // 4
            shift = 4 if row % 2 == 1 else 0
            if y % 4 == 3 or (x + shift) % 8 == 0:
                img.putpixel((x, y), m)
    return img


def obsidian(seed):
    img = noise(["#0d0a14", "#140f1f", "#1b1429"], seed)
    rnd = random.Random(seed)
    # редкие фиолетовые искры
    for _ in range(6):
        img.putpixel((rnd.randint(0, 15), rnd.randint(0, 15)), hex_to_rgb("#6b3fa0") + (255,))
    return img


def ore(ore_colors, seed):
    # Руда = тёмный камень + несколько "кусочков" руды
    img = stone(seed)
    rnd = random.Random(seed + 100)
    light = hex_to_rgb(ore_colors[0]) + (255,)
    dark = hex_to_rgb(ore_colors[1]) + (255,)
    for _ in range(5):
        cx, cy = rnd.randint(1, 13), rnd.randint(1, 13)
        # маленький кусочек 2x2 и тень под ним
        img.putpixel((cx, cy), light)
        img.putpixel((cx + 1, cy), light)
        img.putpixel((cx, cy + 1), dark)
        img.putpixel((cx + 1, cy + 1), dark)
    return img


def planks(seed):
    # Доски: 4 доски по 4 пикселя, между ними тёмная полоса
    img = noise(["#3b2a2f", "#43303a", "#4a3540"], seed)
    rnd = random.Random(seed)
    line = hex_to_rgb("#1e1418") + (255,)
    for y in range(SIZE):
        if y % 4 == 3:
            for x in range(SIZE):
                img.putpixel((x, y), line)
    # стыки досок
    for row in range(4):
        x = rnd.randint(2, 13)
        for dy in range(3):
            img.putpixel((x, row * 4 + dy), line)
    return img


def log_side(seed):
    # Кора: вертикальные полосы
    img = noise(["#241c22", "#2c2229", "#1c161b"], seed)
    rnd = random.Random(seed)
    dark = hex_to_rgb("#110c10") + (255,)
    for x in range(0, SIZE, 3):
        for y in range(SIZE):
            if rnd.random() < 0.7:
                img.putpixel((x, y), dark)
    return img


def log_top(seed):
    # Срез бревна: годовые кольца (квадратные, как в Minecraft)
    img = log_side(seed)
    ring_colors = ["#4a3540", "#3b2a2f"]
    for i in range(1, 8):
        color = hex_to_rgb(ring_colors[i % 2]) + (255,)
        for x in range(i, SIZE - i):
            for y in range(i, SIZE - i):
                img.putpixel((x, y), color)
    return img


def dirt(seed):
    return noise(["#2a1e1c", "#33241f", "#3c2a24", "#22181a"], seed)


def ash_sand(seed):
    return noise(["#5a5560", "#625c68", "#6b6572", "#514c57"], seed)


def gravel(seed):
    return noise(["#2e2b33", "#47424f", "#5e5868", "#1f1c23"], seed)


# ---------- мечи (предметы) ----------

def sword(blade, edge, handle="#2a1a12", guard="#5a1f2b"):
    # Рисуем меч по диагонали из левого нижнего угла в правый верхний.
    # Фон прозрачный (alpha = 0), иначе в игре будет квадрат.
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    b = hex_to_rgb(blade) + (255,)
    e = hex_to_rgb(edge) + (255,)
    h = hex_to_rgb(handle) + (255,)
    g = hex_to_rgb(guard) + (255,)
    # лезвие
    for i in range(5, 15):
        x, y = i, 15 - i
        img.putpixel((x, y), b)
        if x - 1 >= 0:
            img.putpixel((x - 1, y), e)   # светлая кромка
    # гарда (поперечина)
    for d in range(-2, 3):
        img.putpixel((4 + d, 11 + d), g)
    # рукоять
    for i in range(1, 4):
        img.putpixel((i, 15 - i), h)
    img.putpixel((0, 15), g)  # навершие
    return img


# ---------- описание паков ----------
# Для каждого пака: название, описание, какие файлы и чем их рисовать

PACKS = [
    {
        "id": "cursed_stone",
        "name": "Проклятый камень",
        "description": "Тёмный камень, булыжник, кирпичи и обсидиан",
        "textures": {
            "block/stone.png": stone(1),
            "block/cobblestone.png": cobblestone(2),
            "block/stone_bricks.png": bricks(["#3a3445", "#413a4e"], "#16131b", 3),
            "block/bricks.png": bricks(["#4a1c24", "#561f2a", "#3f1820"], "#1a1012", 4),
            "block/obsidian.png": obsidian(5),
        },
    },
    {
        "id": "dark_ores",
        "name": "Светящиеся руды",
        "description": "Руды, которые светятся в темноте подземелий",
        "textures": {
            "block/coal_ore.png": ore(["#000000", "#6e6878"], 11),
            "block/iron_ore.png": ore(["#c9b6a5", "#7a6a5e"], 12),
            "block/gold_ore.png": ore(["#f2c14e", "#9a6b1a"], 13),
            "block/diamond_ore.png": ore(["#7ff5ff", "#2a9fb0"], 14),
            "block/redstone_ore.png": ore(["#ff3b3b", "#8a0f1a"], 15),
            "block/emerald_ore.png": ore(["#5dff8f", "#1d8a42"], 16),
            "block/lapis_ore.png": ore(["#6f7dff", "#2a2f9a"], 17),
        },
    },
    {
        "id": "dead_forest",
        "name": "Мёртвый лес",
        "description": "Мрачное дерево, земля и пепельный песок",
        "textures": {
            "block/oak_planks.png": planks(21),
            "block/oak_log.png": log_side(22),
            "block/oak_log_top.png": log_top(23),
            "block/dirt.png": dirt(24),
            "block/sand.png": ash_sand(25),
            "block/gravel.png": gravel(26),
        },
    },
    {
        "id": "dark_blades",
        "name": "Клинки тьмы",
        "description": "Новый вид для железного, золотого, алмазного и незеритового меча",
        "textures": {
            "item/iron_sword.png": sword("#8a8fa0", "#d0d4e0"),
            "item/golden_sword.png": sword("#b8862b", "#ffd36b"),
            "item/diamond_sword.png": sword("#2aa7b8", "#9ff8ff"),
            "item/netherite_sword.png": sword("#3a2f3f", "#8a3fd0"),
        },
    },
]


# ---------- сборка ----------

def make_icon(textures):
    # Иконка пака 64x64: первые 4 текстуры, увеличенные в 2 раза, сеткой 2x2
    icon = Image.new("RGBA", (64, 64), hex_to_rgb("#120e18") + (255,))
    for i, tex in enumerate(list(textures.values())[:4]):
        big = tex.resize((32, 32), Image.NEAREST)  # NEAREST, чтобы пиксели не размылись
        icon.paste(big, ((i % 2) * 32, (i // 2) * 32), big)
    return icon


def make_preview(textures):
    # Картинка для сайта: все текстуры пака в один ряд, каждая 64x64
    count = len(textures)
    preview = Image.new("RGBA", (count * 64 + (count - 1) * 8, 64), (0, 0, 0, 0))
    for i, tex in enumerate(textures.values()):
        big = tex.resize((64, 64), Image.NEAREST)
        preview.paste(big, (i * 72, 0), big)
    return preview


def png_bytes(img):
    # Превращаем картинку в байты, чтобы записать её прямо в zip
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def build_pack(pack):
    zip_path = os.path.join(PACKS_DIR, pack["id"] + ".zip")
    mcmeta = {"pack": {"pack_format": PACK_FORMAT, "description": pack["name"] + " (Dark Fantasy)"}}

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        # ensure_ascii=False, чтобы русские буквы в описании не превратились в Р...
        z.writestr("pack.mcmeta", json.dumps(mcmeta, ensure_ascii=False, indent=2))
        z.writestr("pack.png", png_bytes(make_icon(pack["textures"])))
        for path, img in pack["textures"].items():
            z.writestr("assets/minecraft/textures/" + path, png_bytes(img))

    make_preview(pack["textures"]).save(os.path.join(IMAGES_DIR, pack["id"] + ".png"))
    print("Готово:", zip_path)


if __name__ == "__main__":
    os.makedirs(PACKS_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    for p in PACKS:
        build_pack(p)
