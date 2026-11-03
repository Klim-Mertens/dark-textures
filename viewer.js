// Просмотр текстур на странице "Все текстуры".
//
// Что умеет:
// - блоки показываются 3D-кубом, у брёвен, травы, печи и т.д. разные грани, как в игре;
// - куб крутится сам, а ещё его можно крутить мышкой или пальцем и приближать колёсиком;
// - стрелки на экране и на клавиатуре листают текстуры;
// - "Сетка 3×3" показывает, как текстура выглядит, если положить много блоков рядом;
// - фильтр "Блоки / Предметы" и кнопка "Случайная текстура".

let viewer = document.getElementById("viewer");
let scene = document.getElementById("scene");
let cube = document.getElementById("cube");
let flat = document.getElementById("viewer-flat");
let tiles = document.getElementById("tiles");
let packText = document.getElementById("viewer-pack");
let nameText = document.getElementById("viewer-name");
let countText = document.getElementById("viewer-count");
let spinButton = document.getElementById("btn-spin");
let tilesButton = document.getElementById("btn-tiles");
let downloadLink = document.getElementById("btn-download");

let allTextures = Array.from(document.querySelectorAll(".tex"));
let current = 0;          // номер открытой текстуры в списке видимых
let showTiles = false;    // включена ли сетка 3x3

// ---------- вращение куба ----------

let rotX = -25;           // наклон вверх-вниз (в градусах)
let rotY = 35;            // поворот влево-вправо
let zoom = 1;             // приближение
let spinning = true;      // крутится ли куб сам
let dragging = false;
let lastX = 0;
let lastY = 0;

// Эта функция вызывается браузером примерно 60 раз в секунду
function animate() {
    if (spinning && !dragging) {
        rotY += 0.4;
    }
    cube.style.transform = "scale(" + zoom + ") rotateX(" + rotX + "deg) rotateY(" + rotY + "deg)";
    requestAnimationFrame(animate);
}
requestAnimationFrame(animate);

// pointer-события работают и для мыши, и для пальца на телефоне
scene.addEventListener("pointerdown", function (event) {
    dragging = true;
    lastX = event.clientX;
    lastY = event.clientY;
    scene.setPointerCapture(event.pointerId);
});

scene.addEventListener("pointermove", function (event) {
    if (!dragging) {
        return;
    }
    rotY += (event.clientX - lastX) * 0.5;
    rotX -= (event.clientY - lastY) * 0.5;
    // не даём перевернуть куб вверх ногами
    rotX = Math.max(-90, Math.min(90, rotX));
    lastX = event.clientX;
    lastY = event.clientY;
});

function stopDrag() {
    dragging = false;
}

scene.addEventListener("pointerup", stopDrag);
// pointercancel бывает, если браузер сам прервал касание (например, телефон начал прокрутку),
// без него куб "залипал" бы в режиме перетаскивания
scene.addEventListener("pointercancel", stopDrag);

// колёсико мыши - приблизить или отдалить
scene.addEventListener("wheel", function (event) {
    event.preventDefault();
    zoom -= event.deltaY * 0.001;
    zoom = Math.max(0.6, Math.min(1.6, zoom));
});

// ---------- открыть текстуру ----------

function visibleTextures() {
    // только те текстуры, которые не спрятаны фильтром
    return allTextures.filter(function (tex) {
        return tex.style.display !== "none";
    });
}

function setFace(selector, src) {
    cube.querySelector(selector).style.backgroundImage = "url('" + src + "')";
}

function openTexture(index) {
    let list = visibleTextures();
    if (list.length === 0) {
        return;
    }
    // если ушли за край списка - переходим на другой конец
    current = (index + list.length) % list.length;
    let img = list[current].querySelector("img");

    // textContent, а не innerHTML - так текст не может стать HTML-кодом
    nameText.textContent = img.alt;
    packText.textContent = list[current].closest(".box").querySelector("h2").textContent;
    countText.textContent = (current + 1) + " / " + list.length;
    downloadLink.href = img.src;
    tiles.style.backgroundImage = "url('" + img.src + "')";

    let isItem = img.classList.contains("item");

    if (!isItem) {
        // если у блока есть отдельные картинки для граней - берём их (data-атрибуты),
        // иначе на всех гранях одна и та же текстура
        let side = img.dataset.side || img.src;
        setFace(".front", img.dataset.front || side);
        setFace(".back", side);
        setFace(".left", side);
        setFace(".right", side);
        setFace(".top", img.dataset.top || img.src);
        setFace(".bottom", img.dataset.bottom || img.src);
    }
    flat.src = img.src;
    flat.alt = img.alt;

    // что показать: сетку, картинку предмета или куб
    tiles.style.display = showTiles ? "block" : "none";
    flat.style.display = (!showTiles && isItem) ? "inline-block" : "none";
    scene.style.display = (!showTiles && !isItem) ? "block" : "none";

    viewer.classList.add("open");
}

for (let tex of allTextures) {
    tex.addEventListener("click", function () {
        openTexture(visibleTextures().indexOf(tex));
    });
}

// ---------- кнопки в окне ----------

document.getElementById("prev").addEventListener("click", function () {
    openTexture(current - 1);
});

document.getElementById("next").addEventListener("click", function () {
    openTexture(current + 1);
});

spinButton.addEventListener("click", function () {
    spinning = !spinning;
    spinButton.textContent = spinning ? "Пауза" : "Вращать";
});

tilesButton.addEventListener("click", function () {
    showTiles = !showTiles;
    tilesButton.classList.toggle("active", showTiles);
    openTexture(current);   // перерисовать окно
});

function closeViewer() {
    viewer.classList.remove("open");
}

document.getElementById("viewer-close").addEventListener("click", closeViewer);

// нажатие на тёмный фон (но не на сам блок или кнопки) тоже закрывает окно
viewer.addEventListener("click", function (event) {
    if (event.target === viewer) {
        closeViewer();
    }
});

document.addEventListener("keydown", function (event) {
    if (!viewer.classList.contains("open")) {
        return;
    }
    if (event.key === "Escape") {
        closeViewer();
    } else if (event.key === "ArrowLeft") {
        openTexture(current - 1);
    } else if (event.key === "ArrowRight") {
        openTexture(current + 1);
    }
});

// ---------- фильтр и случайная текстура ----------

let filterButtons = document.querySelectorAll(".filter[data-filter]");

for (let button of filterButtons) {
    button.addEventListener("click", function () {
        let filter = button.dataset.filter;

        for (let b of filterButtons) {
            b.classList.remove("active");
        }
        button.classList.add("active");

        for (let tex of allTextures) {
            let isItem = tex.querySelector("img").classList.contains("item");
            let show = filter === "all" || (filter === "item" && isItem) || (filter === "block" && !isItem);
            tex.style.display = show ? "" : "none";
        }

        // прячем целый пак, если в нём не осталось видимых текстур
        for (let pack of document.querySelectorAll(".pack")) {
            let anyVisible = Array.from(pack.querySelectorAll(".tex")).some(function (tex) {
                return tex.style.display !== "none";
            });
            pack.style.display = anyVisible ? "" : "none";
        }
    });
}

document.getElementById("random").addEventListener("click", function () {
    let list = visibleTextures();
    if (list.length === 0) {
        return;
    }
    openTexture(Math.floor(Math.random() * list.length));
});
