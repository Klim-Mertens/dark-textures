// Просмотр текстуры на странице "Все текстуры".
// При нажатии на текстуру открывается окно:
// блоки показываются вращающимся 3D-кубом, предметы - большой картинкой.

let viewer = document.getElementById("viewer");
let cube = document.getElementById("cube");
let faces = document.querySelectorAll(".face");
let flat = document.getElementById("viewer-flat");
let nameText = document.getElementById("viewer-name");

let textures = document.querySelectorAll(".tex");

for (let tex of textures) {
    tex.addEventListener("click", function () {
        let img = tex.querySelector("img");
        nameText.textContent = img.alt;

        if (img.classList.contains("item")) {
            // предмет: прячем куб, показываем картинку
            cube.parentElement.style.display = "none";
            flat.src = img.src;
            flat.alt = img.alt;
            flat.style.display = "inline-block";
        } else {
            // блок: ставим текстуру на все 6 граней куба
            for (let face of faces) {
                face.style.backgroundImage = "url('" + img.src + "')";
            }
            flat.style.display = "none";
            cube.parentElement.style.display = "block";
        }

        viewer.classList.add("open");
    });
}

// закрыть окно: нажатие в любом месте или клавиша Esc
function closeViewer() {
    viewer.classList.remove("open");
}

viewer.addEventListener("click", closeViewer);

document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
        closeViewer();
    }
});
