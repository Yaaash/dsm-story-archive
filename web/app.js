let state = {
  data: null,
  lang: "hi",
  selectedStoryId: null,
  mobileDetailOpen: false,
  search: "",
  category: "",
  bookSlug: "",
};

const text = {
  hi: {
    allCategories: "सभी श्रेणियां",
    noStories: "OCR और segmentation के बाद कहानियां यहां दिखाई देंगी।",
    needsOcr: "OCR बाकी",
    pages: "पृष्ठ",
    stories: "कहानियां",
    review: "समीक्षा",
    category: "श्रेणी",
    rawOcr: "Raw OCR",
    corrected: "सुधारा हुआ",
    translated: "English",
    translationPending: "English translation pending",
    allStories: "सभी कहानियां",
    extracted: "OCR text",
    backToStories: "कहानियों पर वापस",
  },
  en: {
    allCategories: "All categories",
    noStories: "Stories will appear here after OCR and segmentation.",
    needsOcr: "Needs OCR",
    pages: "pages",
    stories: "stories",
    review: "review",
    category: "Category",
    rawOcr: "Raw OCR",
    corrected: "Corrected",
    translated: "English",
    translationPending: "English translation pending",
    allStories: "All stories",
    extracted: "OCR text",
    backToStories: "Back to stories",
  },
};

function label(item, key) {
  return state.lang === "hi" ? item[`${key}_hi`] || item[`${key}_en`] : item[`${key}_en`] || item[`${key}_hi`];
}

function storyTitle(story) {
  return state.lang === "hi" ? story.display_title_hi || story.title_hi || story.title_en : story.title_en || story.display_title_hi || story.title_hi;
}

function storyContent(story) {
  return state.lang === "hi" ? story.display_content_hi || story.content_hi || story.content_en : story.content_en || story.display_content_hi || story.content_hi;
}

function hasEnglishTranslation(story) {
  return Boolean((story.content_en || "").trim());
}

function renderBooks() {
  const root = document.querySelector("#books");
  root.innerHTML = state.data.books
    .map((book) => {
      const ocrPages = book.ocr_pages || 0;
      const extractedPages = book.extracted_pages || 0;
      const storyCount = book.story_count || 0;
      const correctedCount = book.corrected_story_count || 0;
      const translatedCount = book.translated_story_count || 0;
      const statusClass = ocrPages > 0 ? "status warn" : "status";
      const statusText = `${storyCount} ${text[state.lang].stories}`;
      return `
        <button class="book-card ${state.bookSlug === book.slug ? "active" : ""}" type="button" data-book-slug="${book.slug}">
          <strong>${label(book, "title")}</strong>
          <div class="meta">${book.total_pages || book.page_count || 0} ${text[state.lang].pages}</div>
          <div class="meta">${extractedPages} ${text[state.lang].extracted} · ${correctedCount} ${text[state.lang].corrected} · ${translatedCount} ${text[state.lang].translated}</div>
          <div class="${statusClass}">${statusText}</div>
        </button>
      `;
    })
    .join("");

  document.querySelectorAll(".book-card").forEach((button) => {
    button.addEventListener("click", () => {
      state.bookSlug = button.dataset.bookSlug;
      state.category = "";
      state.selectedStoryId = null;
      state.mobileDetailOpen = false;
      document.querySelector("#categoryFilter").value = "";
      render();
    });
  });
}

function renderCategories() {
  const root = document.querySelector("#categories");
  const storyCounts = new Map();
  state.data.stories.filter(matchesBook).forEach((story) => {
    storyCounts.set(story.category_slug || "uncategorized", (storyCounts.get(story.category_slug || "uncategorized") || 0) + 1);
  });

  const allCount = state.data.stories.filter(matchesBook).length;
  root.innerHTML = `
      <button class="category-row ${state.category === "" ? "active" : ""}" type="button" data-category="">
        <strong>${text[state.lang].allStories}</strong>
        <div class="meta">${allCount} ${text[state.lang].stories}</div>
      </button>
    ` + state.data.categories
    .map((category) => `
      <button class="category-row ${state.category === category.slug ? "active" : ""}" type="button" data-category="${category.slug}">
        <strong>${label(category, "name")}</strong>
        <div class="meta">${storyCounts.get(category.slug) || 0} ${text[state.lang].stories}</div>
      </button>
    `)
    .join("");

  document.querySelectorAll(".category-row").forEach((button) => {
    button.addEventListener("click", () => {
      state.category = button.dataset.category;
      document.querySelector("#categoryFilter").value = state.category;
      state.mobileDetailOpen = false;
      renderStories();
    });
  });
}

function renderCategoryFilter() {
  const select = document.querySelector("#categoryFilter");
  select.innerHTML = `<option value="">${text[state.lang].allCategories}</option>`;
  state.data.categories.forEach((category) => {
    const option = document.createElement("option");
    option.value = category.slug;
    option.textContent = label(category, "name");
    select.appendChild(option);
  });
  select.value = state.category;
}

function matchesBook(story) {
  return !state.bookSlug || story.book_slug === state.bookSlug;
}

function filteredStories() {
  const query = state.search.trim().toLowerCase();
  return state.data.stories.filter((story) => {
    const bookMatch = matchesBook(story);
    const categoryMatch = !state.category || (story.category_slug || "uncategorized") === state.category;
    const haystack = [
      story.title_hi,
      story.display_title_hi,
      story.title_en,
      story.content_hi,
      story.display_content_hi,
      story.content_en,
    ].join(" ").toLowerCase();
    return bookMatch && categoryMatch && (!query || haystack.includes(query));
  }).sort((left, right) => {
    return (left.sort_order || 0) - (right.sort_order || 0) || left.id - right.id;
  });
}

function renderStories() {
  syncMobileState();
  const root = document.querySelector("#stories");
  const stories = filteredStories();
  if (!stories.length) {
    root.innerHTML = `<p class="empty">${text[state.lang].noStories}</p>`;
    renderDetail(null);
    return;
  }

  if (!state.selectedStoryId || !stories.some((story) => story.id === state.selectedStoryId)) {
    state.selectedStoryId = stories[0].id;
  }

  root.innerHTML = stories
    .map((story) => `
      <button class="story-row ${story.id === state.selectedStoryId ? "active" : ""}" type="button" data-story-id="${story.id}">
        <strong>${storyTitle(story)}</strong>
        <div class="meta">${story.category_hi || story.category_en || text[state.lang].category}</div>
        <div class="status">${state.lang === "en" && !hasEnglishTranslation(story) ? text[state.lang].translationPending : story.translation_status || story.correction_status || story.review_status || text[state.lang].review}</div>
      </button>
    `)
    .join("");

  document.querySelectorAll(".story-row").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedStoryId = Number(button.dataset.storyId);
      state.mobileDetailOpen = true;
      renderStories();
    });
  });

  renderDetail(stories.find((story) => story.id === state.selectedStoryId));
}

function renderDetail(story) {
  const root = document.querySelector("#storyDetail");
  if (!story) {
    root.innerHTML = `<p class="empty">${text[state.lang].noStories}</p>`;
    return;
  }

  const pages = story.start_page && story.end_page ? `${story.start_page}-${story.end_page}` : "";
  root.innerHTML = `
    <button class="mobile-back" type="button" data-back-to-stories>‹ ${text[state.lang].backToStories}</button>
    <h2>${storyTitle(story)}</h2>
    <p class="meta">
      ${story.book_title_hi || story.book_title_en}
      ${pages ? ` · ${pages} ${text[state.lang].pages}` : ""}
    </p>
    <div class="status">${story.correction_status || story.review_status}</div>
    ${state.lang === "en" && !hasEnglishTranslation(story) ? `<div class="translation-note">${text[state.lang].translationPending}</div>` : ""}
    <hr />
    <div class="story-body">${storyContent(story) || text[state.lang].noStories}</div>
    ${
      state.lang === "hi" && story.corrected_content_hi
        ? `<details class="raw-ocr"><summary>${text[state.lang].rawOcr}</summary><div class="story-body">${story.raw_content_hi || story.content_hi}</div></details>`
        : ""
    }
  `;

  const backButton = root.querySelector("[data-back-to-stories]");
  if (backButton) {
    backButton.addEventListener("click", () => {
      state.mobileDetailOpen = false;
      renderStories();
    });
  }
}

function render() {
  if (!state.bookSlug && state.data.books.length) {
    state.bookSlug = state.data.books[0].slug;
  }
  renderBooks();
  renderCategoryFilter();
  renderCategories();
  renderStories();
}

function syncMobileState() {
  document.body.classList.toggle("story-open", state.mobileDetailOpen);
}

async function boot() {
  const response = await fetch("/data/exports/review-data.json");
  state.data = await response.json();

  document.querySelectorAll("[data-lang]").forEach((button) => {
    button.addEventListener("click", () => {
      state.lang = button.dataset.lang;
    document.querySelectorAll("[data-lang]").forEach((item) => item.classList.toggle("active", item.dataset.lang === state.lang));
      render();
    });
  });

  document.querySelector("#search").addEventListener("input", (event) => {
    state.search = event.target.value;
    state.mobileDetailOpen = false;
    renderStories();
  });

  document.querySelector("#categoryFilter").addEventListener("change", (event) => {
    state.category = event.target.value;
    state.mobileDetailOpen = false;
    renderStories();
  });

  render();
}

boot().catch((error) => {
  document.body.innerHTML = `<main class="content"><h1>Could not load review data</h1><p>${error.message}</p></main>`;
});
