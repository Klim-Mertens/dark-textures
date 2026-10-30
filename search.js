// Поиск по карточкам на странице "Текстуры".
// Когда пользователь печатает в поле, мы проверяем каждую карточку:
// если в её тексте есть введённое слово - показываем, если нет - прячем.

let searchInput = document.getElementById("search");
let cards = document.querySelectorAll(".card");
let notFound = document.getElementById("not-found");

searchInput.addEventListener("input", function () {
    // toLowerCase, чтобы "Руды" и "руды" считались одинаковыми
    let text = searchInput.value.toLowerCase().trim();
    let shown = 0;

    for (let card of cards) {
        // textContent - это просто текст карточки, без HTML-тегов
        let cardText = card.textContent.toLowerCase();
        if (cardText.includes(text)) {
            card.style.display = "block";
            shown++;
        } else {
            card.style.display = "none";
        }
    }

    // если ни одна карточка не подошла, пишем "Ничего не найдено"
    if (shown === 0) {
        notFound.style.display = "block";
    } else {
        notFound.style.display = "none";
    }
});
