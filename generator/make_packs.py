# Программа рисует текстуры 16x16 в стиле Dark Fantasy
# и собирает из них ресурспаки для Minecraft 1.20.1.
# Запуск: python make_packs.py  (нужна библиотека Pillow: pip install pillow)
# Готовые zip-архивы появятся в папке ../packs, картинки для сайта в ../images

import json
import math
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


# =====================================================================
# Вспомогательные функции для цветов
# =====================================================================

def rgb(color):
    # "#2a1f3d" -> (42, 31, 61, 255)
    color = color.lstrip("#")
    return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16), 255)


def mix(c1, c2, t):
    # Смешиваем два цвета: t=0 -> c1, t=1 -> c2
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)) + (255,)


def from_ramp(ramp, value):
    # ramp - список цветов от тёмного к светлому, value от 0 до 1
    value = max(0.0, min(0.999, value))
    return rgb(ramp[int(value * len(ramp))])


def lighter(color, amount):
    # amount > 0 - светлее, amount < 0 - темнее
    if amount > 0:
        return mix(color, (255, 255, 255, 255), amount)
    return mix(color, (0, 0, 0, 255), -amount)


# =====================================================================
# Шум. Обычный случайный шум выглядит как "телевизионные помехи",
# поэтому мы его немного размываем - получаются пятна, как на настоящем камне.
# =====================================================================

def smooth_noise(seed, passes=1):
    rnd = random.Random(seed)
    grid = [[rnd.random() for _ in range(SIZE)] for _ in range(SIZE)]
    for _ in range(passes):
        new = [[0.0] * SIZE for _ in range(SIZE)]
        for x in range(SIZE):
            for y in range(SIZE):
                # среднее из самого пикселя и 4 соседей
                # % SIZE - чтобы края "склеивались" и текстура была бесшовной
                total = grid[x][y] * 2
                total += grid[(x + 1) % SIZE][y] + grid[(x - 1) % SIZE][y]
                total += grid[x][(y + 1) % SIZE] + grid[x][(y - 1) % SIZE]
                new[x][y] = total / 6
        grid = new
    # растягиваем значения, чтобы они снова были от 0 до 1
    low = min(min(row) for row in grid)
    high = max(max(row) for row in grid)
    return [[(v - low) / (high - low) for v in row] for row in grid]


def noise_texture(ramp, seed, passes=1, rough=0.25):
    # Пятнистая текстура: размытый шум + немного обычного шума для зернистости
    rnd = random.Random(seed + 7)
    n = smooth_noise(seed, passes)
    img = Image.new("RGBA", (SIZE, SIZE))
    for x in range(SIZE):
        for y in range(SIZE):
            v = n[x][y] * (1 - rough) + rnd.random() * rough
            img.putpixel((x, y), from_ramp(ramp, v))
    return img


# =====================================================================
# Блоки из "кусков" (булыжник, кирпичи, доски).
# Сначала делаем карту: в каждой клетке номер куска или -1 (шов).
# Потом раскрашиваем: у шва тёмный цвет, у куска свой оттенок,
# верхний-левый край куска светлее, нижний-правый темнее - так появляется объём.
# =====================================================================

def wrap_dist(ax, ay, bx, by):
    # расстояние с учётом того, что текстура повторяется по краям
    dx = min(abs(ax - bx), SIZE - abs(ax - bx))
    dy = min(abs(ay - by), SIZE - abs(ay - by))
    return math.sqrt(dx * dx + dy * dy)


def voronoi_map(seed, count):
    # Разбиваем квадрат на "камни" вокруг случайных точек
    rnd = random.Random(seed)
    points = [(rnd.uniform(0, SIZE), rnd.uniform(0, SIZE)) for _ in range(count)]
    cells = [[0] * SIZE for _ in range(SIZE)]
    for x in range(SIZE):
        for y in range(SIZE):
            dists = sorted((wrap_dist(x + 0.5, y + 0.5, px, py), i) for i, (px, py) in enumerate(points))
            # если две ближайшие точки почти на одном расстоянии - это граница (шов)
            if dists[1][0] - dists[0][0] < 1.0:
                cells[x][y] = -1
            else:
                cells[x][y] = dists[0][1]
    return cells


def brick_map(height, length, shift):
    # Карта кирпичей: ряды высотой height, кирпичи длиной length
    cells = [[0] * SIZE for _ in range(SIZE)]
    for x in range(SIZE):
        for y in range(SIZE):
            row = y // height
            offset = shift if row % 2 == 1 else 0
            if y % height == height - 1 or (x + offset) % length == 0:
                cells[x][y] = -1
            else:
                cells[x][y] = row * 10 + (x + offset) // length
    return cells


def paint_pieces(cells, ramp, mortar, seed, bevel=0.22):
    rnd = random.Random(seed)
    n = smooth_noise(seed + 1, 1)
    tones = {}  # у каждого куска свой оттенок
    img = Image.new("RGBA", (SIZE, SIZE))
    for x in range(SIZE):
        for y in range(SIZE):
            cell = cells[x][y]
            if cell == -1:
                img.putpixel((x, y), lighter(rgb(mortar), -0.15 * rnd.random()))
                continue
            if cell not in tones:
                tones[cell] = rnd.uniform(0.25, 0.75)
            color = from_ramp(ramp, tones[cell] * 0.6 + n[x][y] * 0.4)
            # проверяем соседей: шов сверху/слева - блик, снизу/справа - тень
            up = cells[x][(y - 1) % SIZE]
            left = cells[(x - 1) % SIZE][y]
            down = cells[x][(y + 1) % SIZE]
            right = cells[(x + 1) % SIZE][y]
            if up != cell or left != cell:
                color = lighter(color, bevel)
            elif down != cell or right != cell:
                color = lighter(color, -bevel * 1.5)
            img.putpixel((x, y), color)
    return img


# =====================================================================
# Палитры (от тёмного к светлому)
# =====================================================================

STONE = ["#16131b", "#211c28", "#2b2533", "#352e3f", "#40384b", "#4b4258"]
BLOOD_BRICK = ["#240c11", "#33111a", "#451822", "#57202c", "#6b2a36"]
WOOD = ["#1c1216", "#271a1f", "#33232a", "#3f2c34", "#4c3640"]
BARK = ["#0d090c", "#161015", "#1f171d", "#2a2027", "#352931"]
DIRT = ["#1a1212", "#241917", "#2e201c", "#392822", "#443029"]
ASH = ["#3b3740", "#47434d", "#534e5a", "#605a67", "#6d6774"]
OBSIDIAN = ["#07050b", "#0d0914", "#140e1e", "#1c1429", "#261b36"]


# =====================================================================
# Блоки
# =====================================================================

def add_cracks(img, seed, count=3):
    # Трещины: случайная "прогулка" тёмных пикселей, рядом светлый край
    rnd = random.Random(seed)
    for _ in range(count):
        x, y = rnd.randint(0, 15), rnd.randint(0, 15)
        for _ in range(rnd.randint(3, 6)):
            img.putpixel((x, y), rgb("#0c0a10"))
            img.putpixel(((x + 1) % SIZE, y), lighter(img.getpixel(((x + 1) % SIZE, y)), 0.12))
            x = (x + rnd.choice([-1, 0, 1])) % SIZE
            y = (y + 1) % SIZE
    return img


def stone(seed):
    return add_cracks(noise_texture(STONE, seed, passes=2), seed)


def cobblestone(seed):
    return paint_pieces(voronoi_map(seed, 7), STONE, "#0e0b12", seed)


def stone_bricks(seed):
    img = paint_pieces(brick_map(8, 16, 8), STONE, "#0e0b12", seed)
    return add_cracks(img, seed, 2)


def blood_bricks(seed):
    return paint_pieces(brick_map(4, 8, 4), BLOOD_BRICK, "#120709", seed)


def obsidian(seed):
    img = noise_texture(OBSIDIAN, seed, passes=2, rough=0.1)
    rnd = random.Random(seed)
    # фиолетовые искры со слабым свечением вокруг
    for _ in range(5):
        x, y = rnd.randint(0, 15), rnd.randint(0, 15)
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            p = ((x + dx) % SIZE, (y + dy) % SIZE)
            img.putpixel(p, mix(img.getpixel(p), rgb("#6b3fa0"), 0.35))
        img.putpixel((x, y), rgb("#b98aff"))
    return img


# Формы кусочков руды (координаты пикселей относительно центра)
ORE_SHAPES = [
    [(0, 0), (1, 0), (0, 1), (1, 1), (2, 1)],
    [(1, 0), (0, 1), (1, 1), (2, 1), (1, 2)],
    [(0, 0), (1, 0), (1, 1), (2, 2)],
    [(0, 0), (0, 1), (1, 1)],
]


def ore(colors, seed):
    # colors = [светлый, средний, тёмный] цвет руды
    img = stone(seed)
    rnd = random.Random(seed + 100)
    light, mid, dark = rgb(colors[0]), rgb(colors[1]), rgb(colors[2])
    for _ in range(4):
        cx, cy = rnd.randint(0, 12), rnd.randint(0, 12)
        shape = rnd.choice(ORE_SHAPES)
        # свечение: подкрашиваем камень вокруг кусочка
        for px, py in shape:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    p = ((cx + px + dx) % SIZE, (cy + py + dy) % SIZE)
                    img.putpixel(p, mix(img.getpixel(p), mid, 0.18))
        # сам кусочек: верхние пиксели светлые, нижние тёмные
        for px, py in shape:
            color = light if py == 0 else (mid if py == 1 else dark)
            img.putpixel(((cx + px) % SIZE, (cy + py) % SIZE), color)
        # тень под кусочком
        lowest = max(py for _, py in shape)
        for px, py in shape:
            if py == lowest:
                p = ((cx + px) % SIZE, (cy + py + 1) % SIZE)
                img.putpixel(p, lighter(img.getpixel(p), -0.4))
    return img


def planks(seed):
    rnd = random.Random(seed)
    # 4 доски по 4 пикселя, каждая доска поделена на 2 куска в случайном месте
    cells = [[0] * SIZE for _ in range(SIZE)]
    for row in range(4):
        cut = rnd.randint(3, 12)
        for x in range(SIZE):
            for dy in range(4):
                y = row * 4 + dy
                if dy == 3 or x == cut:
                    cells[x][y] = -1
                else:
                    cells[x][y] = row * 2 + (1 if x > cut else 0)
    img = paint_pieces(cells, WOOD, "#0f0a0c", seed, bevel=0.15)
    # древесные волокна: короткие тёмные горизонтальные чёрточки
    for _ in range(10):
        x, y = rnd.randint(0, 15), rnd.randint(0, 15)
        for dx in range(rnd.randint(2, 4)):
            p = ((x + dx) % SIZE, y)
            if cells[p[0]][y] != -1:
                img.putpixel(p, lighter(img.getpixel(p), -0.25))
    return img


def log_side(seed):
    rnd = random.Random(seed)
    img = Image.new("RGBA", (SIZE, SIZE))
    # у каждого столбца своя "высота" коры, вдоль столбца она меняется плавно
    for x in range(SIZE):
        base = rnd.random()
        for y in range(SIZE):
            base = base * 0.8 + rnd.random() * 0.2
            v = base
            if x % 4 == 0:      # глубокие борозды коры
                v *= 0.3
            elif x % 4 == 1:    # край борозды освещён
                v = min(1, v + 0.3)
            img.putpixel((x, y), from_ramp(BARK, v))
    # немного тёмно-зелёного мха снизу
    for _ in range(6):
        p = (rnd.randint(0, 15), rnd.randint(11, 15))
        img.putpixel(p, mix(img.getpixel(p), rgb("#2c3a24"), 0.6))
    return img


def log_top(seed):
    img = log_side(seed)
    rnd = random.Random(seed)
    for x in range(1, SIZE - 1):
        for y in range(1, SIZE - 1):
            # расстояние до центра - по нему рисуем годовые кольца
            d = math.sqrt((x - 7.5) ** 2 + (y - 7.5) ** 2)
            ring = int(d + rnd.random() * 0.6)
            color = rgb(WOOD[4]) if ring % 2 == 0 else rgb(WOOD[2])
            if d > 6.2:
                color = rgb(WOOD[1])    # тёмный край у коры
            img.putpixel((x, y), color)
    img.putpixel((7, 7), rgb(WOOD[0]))  # серединка
    img.putpixel((8, 8), rgb(WOOD[0]))
    return img


def dirt(seed):
    img = noise_texture(DIRT, seed, passes=1, rough=0.35)
    rnd = random.Random(seed)
    # маленькие камешки и кусочки костей (тёмное фэнтези же)
    for i in range(5):
        x, y = rnd.randint(0, 14), rnd.randint(0, 14)
        top = rgb("#8a8078") if i < 2 else rgb("#4a3a33")
        img.putpixel((x, y), top)
        img.putpixel((x + 1, y + 1), lighter(top, -0.5))
    return img


def ash_sand(seed):
    img = noise_texture(ASH, seed, passes=1, rough=0.45)
    rnd = random.Random(seed)
    # тлеющие угольки
    for _ in range(3):
        img.putpixel((rnd.randint(0, 15), rnd.randint(0, 15)), rgb("#c2451f"))
    return img


def gravel(seed):
    ramp = ["#1d1a21", "#2e2a33", "#433e4a", "#5a5463", "#726b7c"]
    return paint_pieces(voronoi_map(seed, 14), ramp, "#100e13", seed, bevel=0.3)


# =====================================================================
# Мечи. Рисуем по диагонали: рукоять внизу слева, остриё вверху справа.
# Потом автоматически обводим всё тёмным контуром, как в обычном Minecraft.
# =====================================================================

def sword(blade, edge, dark, guard, gem, rune=None):
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    # лезвие: точки центральной линии от гарды до острия
    for t in range(1, 11):
        x, y = 4 + t, 11 - t
        img.putpixel((x - 1, y), rgb(edge))          # светлая кромка
        if t < 10:
            img.putpixel((x, y + 1), rgb(dark))      # тёмная сторона
        # руны на лезвии (у "магических" мечей) или просто цвет лезвия
        if rune and 2 <= t <= 7 and t % 2 == 0:
            img.putpixel((x, y), rgb(rune))
        else:
            img.putpixel((x, y), rgb(blade))
    # гарда - поперёк лезвия
    for k in range(-3, 4):
        color = rgb(guard) if k <= 0 else lighter(rgb(guard), -0.35)
        img.putpixel((4 + k, 11 + k), color)
    img.putpixel((4, 11), rgb(gem))                  # камень в центре гарды
    # рукоять, обмотанная кожей (полоски через один пиксель)
    img.putpixel((3, 12), rgb("#3a2418"))
    img.putpixel((2, 13), rgb("#22150e"))
    img.putpixel((1, 14), rgb("#3a2418"))
    img.putpixel((0, 15), rgb(guard))                # навершие

    add_outline(img)
    return img


# =====================================================================
# Предметы. Общие функции:
# add_outline - обводит рисунок тёмным контуром,
# draw_template - рисует картинку "по клеточкам" из строк с буквами.
# =====================================================================

def add_outline(img):
    # контур: прозрачный пиксель рядом с непрозрачным становится тёмным
    outline = rgb("#0b070d")
    to_fill = []
    for x in range(SIZE):
        for y in range(SIZE):
            if img.getpixel((x, y))[3] == 0:
                for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < SIZE and 0 <= ny < SIZE and img.getpixel((nx, ny))[3] == 255:
                        to_fill.append((x, y))
                        break
    for p in to_fill:
        img.putpixel(p, outline)
    return img


def draw_template(rows, colors, outline=True):
    # rows - список из строк, каждая буква = один пиксель, точка = прозрачный.
    # colors - словарь "буква -> цвет". Строк может быть меньше 16, тогда низ пустой.
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, letter in enumerate(row):
            if letter != ".":
                img.putpixel((x, y), rgb(colors[letter]))
    if outline:
        add_outline(img)
    return img


def mirror(x, y):
    # Отражение относительно диагонали, по которой идёт рукоять (из левого нижнего
    # угла в правый верхний). Нужно, чтобы головка кирки была симметричной.
    return 15 - y, 15 - x


HANDLE = ["#4a3123", "#2c1c14"]   # цвета деревянной рукояти (светлый, тёмный)


def handle(img, length):
    # рукоять по диагонали от левого нижнего угла, полоски через один пиксель
    for x in range(1, length + 1):
        img.putpixel((x, 15 - x), rgb(HANDLE[x % 2]))


def pickaxe(light, mid, dark):
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    handle(img, 10)
    # головка - дуга в правом верхнем углу. Рисуем левую половину,
    # правая получается отражением.
    outer = [(3, 1), (4, 1), (5, 1), (6, 1), (7, 1), (8, 1), (9, 2), (10, 2), (11, 3), (12, 3)]
    inner = [(4, 2), (5, 2), (6, 2), (7, 2), (8, 2), (9, 3), (10, 3), (11, 4)]
    tips = [(2, 2), (3, 2)]
    for points, color in [(outer, light), (inner, mid), (tips, dark)]:
        for x, y in points:
            img.putpixel((x, y), rgb(color))
            img.putpixel(mirror(x, y), rgb(color))
    return add_outline(img)


def axe(light, mid, dark):
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    handle(img, 14)
    # лезвие топора слева от верхней части рукояти
    # широкое лезвие слева и узкая "шейка", которая держится за рукоять
    blade = {
        1: range(4, 7),
        2: range(3, 9),
        3: range(3, 12),
        4: range(3, 11),
        5: range(3, 9),
        6: range(4, 7),
    }
    for y, xs in blade.items():
        for x in xs:
            if x == min(xs):
                color = light        # острая кромка светлая
            elif x == max(xs):
                color = dark         # у рукояти тень
            else:
                color = mid
            img.putpixel((x, y), rgb(color))
    return add_outline(img)


def bow():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    # тетива - прямая диагональ
    for i in range(13):
        img.putpixel((2 + i, 1 + i), rgb("#bdb3c4"))
    # дуга лука (дерево), как головка у кирки
    arc = [(2, 1), (3, 0), (4, 0), (5, 0), (6, 0), (7, 0), (8, 1), (9, 1), (10, 2), (11, 2), (12, 3)]
    for x, y in arc:
        img.putpixel((x, y + 1), rgb("#3a2418"))
        img.putpixel(mirror(x, y + 1), rgb("#3a2418"))
    # кожаная обмотка посередине и красные наконечники
    for x, y in [(11, 3), (12, 4), (12, 3)]:
        img.putpixel((x, y), rgb("#7a1622"))
    img.putpixel((2, 2), rgb("#c2451f"))
    img.putpixel(mirror(2, 2), rgb("#c2451f"))
    return add_outline(img)


def torch():
    # Факел: в игре от этой картинки берётся только полоска x=7..8, y=6..15,
    # поэтому рисуем ровно там. Сверху огонь, ниже палка.
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    img.putpixel((7, 6), rgb("#ffe9a8"))
    img.putpixel((8, 6), rgb("#ffb347"))
    img.putpixel((7, 7), rgb("#ff7a2a"))
    img.putpixel((8, 7), rgb("#c2451f"))
    for y in range(8, 16):
        img.putpixel((7, y), rgb("#3a2418"))
        img.putpixel((8, y), rgb("#22150e"))
    img.putpixel((7, 8), rgb("#5a1a14"))   # обгоревший кончик
    return img


INGOT = [
    "",
    "",
    "",
    "",
    "......LLLLLLL",
    ".....LAAAAAAAL",
    "....LAAWAAAAMD",
    "...LAAAAAAAMD",
    "..LAAAAAAAMD",
    "..DMMMMMMMD",
    "...DDDDDDD",
]

GEM = [
    "",
    "",
    "....LLLLLLL",
    "...LAWLAAALA",
    "..LAWAAAAAAAL",
    ".LAAAAAAAAAAAM",
    "..MAAAAAAAAAM",
    "...MAAAAAAAM",
    "....MAAAAAM",
    ".....MAAAM",
    "......MAM",
    ".......M",
]

COAL = [
    "",
    "",
    "",
    ".....LLL",
    "...LLAAAL",
    "..LAAWAAAL",
    "..AAAAAAAMM",
    ".LAAAAAAAAM",
    ".AAAAAAAAMD",
    "..AAAAAAMMD",
    "..MAAAAMDD",
    "...MMMDD",
]

APPLE = [
    "",
    "........S",
    ".......SGG",
    "......SGG",
    "...RRR.S.RRR",
    "..RRRRRRRRRRR",
    ".RRWRRRRRRRRRR",
    ".RWRRRRRRRRRRD",
    ".RRRRRRRRRRRRD",
    ".RRRRRRRRRRRDD",
    "..RRRRRRRRRRD",
    "...RRRRRRRDD",
    "....RRR.RRD",
]

BOOK = [
    "",
    "",
    "..RRRRRRRRRRP",
    "..RRRRRRRRRRP",
    "..RRGGGGGGRRP",
    "..RRGRRRRGRRP",
    "..RRGRWWRGRRP",
    "..RRGRWWRGRRP",
    "..RRGRRRRGRRP",
    "..RRGGGGGGRRP",
    "..RRRRRRRRRRP",
    "..RRRRRRRRRRP",
    "..DDDDDDDDDDP",
]


def ender_pearl():
    # Жемчуг Края в виде тёмного глаза с бирюзовым зрачком
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    for x in range(SIZE):
        for y in range(SIZE):
            d = math.sqrt((x - 7.5) ** 2 + (y - 7.5) ** 2)
            if d < 5.5:
                # чем ближе к краю, тем темнее; сверху-слева блик
                color = mix(rgb("#1f6b5e"), rgb("#07201c"), d / 5.5)
                if x + y < 11 and d > 3.5:
                    color = lighter(color, 0.25)
                img.putpixel((x, y), color)
    for x, y in [(7, 7), (8, 7), (7, 8), (8, 8)]:
        img.putpixel((x, y), rgb("#6dffd9"))    # светящийся зрачок
    img.putpixel((7, 6), rgb("#0b2d27"))
    img.putpixel((8, 9), rgb("#0b2d27"))
    img.putpixel((5, 5), rgb("#d4fff3"))        # блик
    return add_outline(img)


# =====================================================================
# Описание паков: название, описание и какие файлы чем рисовать.
# Русские названия текстур нужны для страницы "Все текстуры".
# =====================================================================

PACKS = [
    {
        "id": "cursed_stone",
        "name": "Проклятый камень",
        "textures": {
            "block/stone.png": ("Камень", stone(1)),
            "block/cobblestone.png": ("Булыжник", cobblestone(2)),
            "block/stone_bricks.png": ("Каменные кирпичи", stone_bricks(3)),
            "block/bricks.png": ("Кровавые кирпичи", blood_bricks(4)),
            "block/obsidian.png": ("Обсидиан", obsidian(5)),
        },
    },
    {
        "id": "dark_ores",
        "name": "Светящиеся руды",
        "textures": {
            "block/coal_ore.png": ("Угольная руда", ore(["#8a8492", "#2e2a33", "#0a090b"], 11)),
            "block/iron_ore.png": ("Железная руда", ore(["#ead7c4", "#a8917c", "#5e4c3e"], 12)),
            "block/gold_ore.png": ("Золотая руда", ore(["#ffe28a", "#e0a531", "#8a5a12"], 13)),
            "block/diamond_ore.png": ("Алмазная руда", ore(["#d4ffff", "#4fe3f0", "#1a8094"], 14)),
            "block/redstone_ore.png": ("Редстоуновая руда", ore(["#ff8a7a", "#e3192b", "#7a0a14"], 15)),
            "block/emerald_ore.png": ("Изумрудная руда", ore(["#b8ffcb", "#2fd46a", "#0f6e33"], 16)),
            "block/lapis_ore.png": ("Лазуритовая руда", ore(["#b3bcff", "#4656e8", "#1d2380"], 17)),
        },
    },
    {
        "id": "dead_forest",
        "name": "Мёртвый лес",
        "textures": {
            "block/oak_planks.png": ("Дубовые доски", planks(21)),
            "block/oak_log.png": ("Дубовое бревно", log_side(22)),
            "block/oak_log_top.png": ("Срез бревна", log_top(23)),
            "block/dirt.png": ("Земля", dirt(24)),
            "block/sand.png": ("Пепельный песок", ash_sand(25)),
            "block/gravel.png": ("Гравий", gravel(26)),
        },
    },
    {
        "id": "dark_blades",
        "name": "Клинки тьмы",
        "textures": {
            "item/iron_sword.png": ("Железный меч",
                                    sword("#9ba0b0", "#e2e6f0", "#5b5f6e", "#6b1f2b", "#d63a4a")),
            "item/golden_sword.png": ("Золотой меч",
                                      sword("#d9a53a", "#fff0a8", "#8a5e14", "#3a2a3f", "#9b4dff")),
            "item/diamond_sword.png": ("Алмазный меч",
                                       sword("#3cc8d8", "#c8ffff", "#16717f", "#2a2f4a", "#ffffff")),
            "item/netherite_sword.png": ("Незеритовый меч",
                                         sword("#4f4458", "#9a8aa8", "#2a2330", "#2a2330", "#b06bff", rune="#c48aff")),
        },
    },
    {
        "id": "hero_arsenal",
        "name": "Арсенал героя",
        "textures": {
            "item/iron_pickaxe.png": ("Железная кирка", pickaxe("#e2e6f0", "#9ba0b0", "#5b5f6e")),
            "item/diamond_pickaxe.png": ("Алмазная кирка", pickaxe("#c8ffff", "#3cc8d8", "#16717f")),
            "item/netherite_pickaxe.png": ("Незеритовая кирка", pickaxe("#b98aff", "#4f4458", "#2a2330")),
            "item/iron_axe.png": ("Железный топор", axe("#e2e6f0", "#9ba0b0", "#5b5f6e")),
            "item/diamond_axe.png": ("Алмазный топор", axe("#c8ffff", "#3cc8d8", "#16717f")),
            "item/bow.png": ("Лук", bow()),
            "block/torch.png": ("Факел", torch()),
        },
    },
    {
        "id": "dungeon_treasures",
        "name": "Сокровища подземелий",
        "textures": {
            "item/diamond.png": ("Алмаз", draw_template(GEM, {"L": "#d4ffff", "A": "#3cc8d8", "M": "#16717f", "W": "#ffffff"})),
            "item/emerald.png": ("Изумруд", draw_template(GEM, {"L": "#b8ffcb", "A": "#2fd46a", "M": "#0f6e33", "W": "#ffffff"})),
            "item/iron_ingot.png": ("Железный слиток", draw_template(INGOT, {"L": "#ffffff", "A": "#c9ccd6", "M": "#8a8f9e", "D": "#4e5260", "W": "#ffffff"})),
            "item/gold_ingot.png": ("Золотой слиток", draw_template(INGOT, {"L": "#fff6c4", "A": "#f2c14e", "M": "#c08a22", "D": "#6e4a0c", "W": "#ffffff"})),
            "item/coal.png": ("Уголь", draw_template(COAL, {"L": "#55505c", "A": "#26222b", "M": "#16131a", "D": "#08070a", "W": "#8a8492"})),
            "item/apple.png": ("Кровавое яблоко", draw_template(APPLE, {"R": "#8b1424", "D": "#4a0a14", "W": "#ff8a8a", "S": "#3a2418", "G": "#2c3a24"})),
            "item/golden_apple.png": ("Золотое яблоко", draw_template(APPLE, {"R": "#e8b03a", "D": "#8a5a12", "W": "#fff6c4", "S": "#3a2418", "G": "#c08a22"})),
            "item/ender_pearl.png": ("Жемчуг Края", ender_pearl()),
            "item/book.png": ("Книга заклинаний", draw_template(BOOK, {"R": "#4a0f1a", "G": "#d9b56e", "W": "#ff8a3c", "P": "#d8cdb8", "D": "#2a070e"})),
        },
    },
]

# Общий пак: все текстуры из всех паков в одном файле
ALL_PACK = {"id": "dark_fantasy_all", "name": "Тёмное фэнтези: все текстуры", "textures": {}}
for p in PACKS:
    ALL_PACK["textures"].update(p["textures"])


# =====================================================================
# Картинки для сайта
# =====================================================================

def make_icon(textures):
    # Иконка пака 64x64: первые 4 текстуры сеткой 2x2
    icon = Image.new("RGBA", (64, 64), rgb("#120e18"))
    for i, (_, tex) in enumerate(list(textures.values())[:4]):
        big = tex.resize((32, 32), Image.NEAREST)  # NEAREST, чтобы пиксели не размылись
        icon.paste(big, ((i % 2) * 32, (i // 2) * 32), big)
    return icon


def make_preview(textures):
    # Картинка для карточки: все текстуры пака в один ряд, каждая 16x16 с отступом 2.
    # На сайте она увеличивается через CSS (image-rendering: pixelated)
    count = len(textures)
    preview = Image.new("RGBA", (count * 18 - 2, 16), (0, 0, 0, 0))
    for i, (_, tex) in enumerate(textures.values()):
        preview.paste(tex, (i * 18, 0), tex)
    return preview


def make_banner():
    # Пиксельная картинка для главной: ночь, кровавая луна и замок на скале.
    w, h = 240, 80
    rnd = random.Random(2100)
    img = Image.new("RGBA", (w, h))

    # небо: сверху почти чёрное, к горизонту фиолетовое
    for y in range(h):
        color = mix(rgb("#07050a"), rgb("#2a1435"), y / h)
        for x in range(w):
            img.putpixel((x, y), color)

    # звёзды
    for _ in range(70):
        img.putpixel((rnd.randint(0, w - 1), rnd.randint(0, 45)), rgb("#cbbfd6") if rnd.random() < 0.3 else rgb("#6e6280"))

    # луна с ореолом
    mx, my, r = 180, 22, 11
    for x in range(w):
        for y in range(h):
            d = math.sqrt((x - mx) ** 2 + (y - my) ** 2)
            if d < r:
                img.putpixel((x, y), mix(rgb("#f0c9a8"), rgb("#b8463c"), d / r * 0.7))
            elif d < r + 10:
                img.putpixel((x, y), mix(img.getpixel((x, y)), rgb("#8b1e2d"), (1 - (d - r) / 10) * 0.35))
    for cx, cy in [(176, 19), (184, 26), (182, 17)]:   # кратеры
        img.putpixel((cx, cy), rgb("#c7826b"))
        img.putpixel((cx + 1, cy), rgb("#c7826b"))

    # дальние горы (два слоя, дальний светлее)
    for layer, (color, base, amp) in enumerate([("#1d1026", 50, 14), ("#140b1b", 58, 10)]):
        height = base
        for x in range(w):
            height += rnd.choice([-1, 0, 0, 1])
            height = max(base - amp, min(base + amp // 2, height))
            for y in range(height, h):
                img.putpixel((x, y), rgb(color))

    # скала и замок (чёрный силуэт)
    black = rgb("#050307")
    for x in range(30, 130):
        top = 62 - int(8 * math.sin((x - 30) / 100 * math.pi))
        for y in range(top, h):
            img.putpixel((x, y), black)

    def rect(x1, y1, x2, y2):
        for x in range(x1, x2):
            for y in range(y1, y2):
                img.putpixel((x, y), black)

    rect(50, 38, 110, 56)                              # стена
    for x in range(50, 110, 4):                        # зубцы на стене
        rect(x, 36, x + 2, 38)
    towers = [(46, 24, 8), (66, 18, 7), (86, 10, 9), (106, 26, 8)]
    for tx, ty, tw in towers:
        rect(tx, ty, tx + tw, 56)
        # остроконечная крыша
        for i in range(tw // 2 + 4):
            rect(tx + i // 2, ty - i, tx + tw - i // 2, ty - i + 1)
    # окна, в которых горит свет
    for wx, wy in [(48, 30), (68, 24), (89, 16), (89, 26), (108, 32), (60, 44), (78, 44), (96, 44)]:
        img.putpixel((wx, wy), rgb("#ffb347"))
        img.putpixel((wx, wy + 1), rgb("#c2451f"))

    # мёртвые деревья справа
    for tx in (150, 163, 205, 222):
        top = 60 + rnd.randint(-4, 2)
        for y in range(top, h):
            img.putpixel((tx, y), black)
        for i in range(1, 6):   # ветки в стороны
            img.putpixel((tx - i // 2 - 1, top + 4 - i), black)
            img.putpixel((tx + i // 2 + 1, top + 6 - i), black)
    for x in range(130, w):                            # земля
        for y in range(68 + int(2 * math.sin(x / 9)), h):
            img.putpixel((x, y), black)

    # туман внизу
    for y in range(60, h):
        for x in range(w):
            t = (y - 60) / 20 * 0.25 * (0.7 + 0.3 * math.sin(x / 13 + y))
            img.putpixel((x, y), mix(img.getpixel((x, y)), rgb("#3a2a48"), t))
    return img


def make_background():
    # Тёмная каменная кладка для фона сайта (32x32, на сайте увеличивается)
    tile = paint_pieces(brick_map(8, 16, 8), ["#0b090e", "#0e0b12", "#110e16", "#141019"], "#060408", 99, bevel=0.08)
    bg = Image.new("RGBA", (32, 32))
    for i in range(4):
        bg.paste(tile, ((i % 2) * 16, (i // 2) * 16))
    return bg


# =====================================================================
# Сборка zip-архивов
# =====================================================================

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
        for path, (_, img) in pack["textures"].items():
            z.writestr("assets/minecraft/textures/" + path, png_bytes(img))
    print("Готово:", pack["id"] + ".zip")


if __name__ == "__main__":
    os.makedirs(PACKS_DIR, exist_ok=True)
    os.makedirs(os.path.join(IMAGES_DIR, "tex"), exist_ok=True)

    for p in PACKS:
        build_pack(p)
        make_preview(p["textures"]).save(os.path.join(IMAGES_DIR, p["id"] + ".png"))
    build_pack(ALL_PACK)

    # каждая текстура отдельной картинкой - для страницы "Все текстуры"
    for path, (_, img) in ALL_PACK["textures"].items():
        img.save(os.path.join(IMAGES_DIR, "tex", os.path.basename(path)))

    make_banner().save(os.path.join(IMAGES_DIR, "banner.png"))
    make_background().save(os.path.join(IMAGES_DIR, "bg.png"))
    ALL_PACK["textures"]["item/golden_sword.png"][1].save(os.path.join(IMAGES_DIR, "icon.png"))
    print("Картинки для сайта готовы")
