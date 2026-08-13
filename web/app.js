let state = {
  data: null,
  lang: "hi",
  selectedStoryId: null,
  search: "",
  category: "",
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
  },
  en: {
    allCategories: "All categories",
    noStories: "Stories will appear here after OCR and segmentation.",
    needsOcr: "Needs OCR",
    pages: "pages",
    stories: "stories",
    review: "review",
    category: "Category",
  },
};

function label(item, key) {
  return state.lang === "hi" ? item[`${key}_hi`] || item[`${key}_en`] : item[`${key}_en`] || item[`${key}_hi`];
}

function storyTitle(story) {
  return state.lang === "hi" ? story.title_hi || story.title_en : story.title_en || story.title_hi;
}

function storyContent(story) {
  return state.lang === "hi" ? story.content_hi || story.content_en : story.content_en || story.content_hi;
}

function renderBooks() {
  const root = document.querySelector("#books");
  root.innerHTML = state.data.books
    .map((book) => {
      const ocrPages = book.ocr_pages || 0;
      const extractedPages = book.extracted_pages || 0;
      const statusClass = ocrPages > 0 ? "status warn" : "status";
      const statusText = ocrPages > 0 ? `${ocrPages} ${text[state.lang].needsOcr}` : `${extractedPages} extracted`;
      return `
        <div class="book-card">
          <strong>${label(book, "title")}</strong>
          <div class="meta">${book.total_pages || book.page_count || 0} ${text[state.lang].pages}</div>
          <div class="${statusClass}">${statusText}</div>
        </div>
      `;
    })
    .join("");
}

function renderCategories() {
  const root = document.querySelector("#categories");
  const storyCounts = new Map();
  state.data.stories.forEach((story) => {
    storyCounts.set(story.category_slug || "uncategorized", (storyCounts.get(story.category_slug || "uncategorized") || 0) + 1);
  });

  root.innerHTML = state.data.categories
    .map((category) => `
      <button class="category-row" type="button" data-category="${category.slug}">
        <strong>${label(category, "name")}</strong>
        <div class="meta">${storyCounts.get(category.slug) || 0} ${text[state.lang].stories}</div>
      </button>
    `)
    .join("");

  document.querySelectorAll(".category-row").forEach((button) => {
    button.addEventListener("click", () => {
      state.category = button.dataset.category;
      document.querySelector("#categoryFilter").value = state.category;
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

function filteredStories() {
  const query = state.search.trim().toLowerCase();
  return state.data.stories.filter((story) => {
    const categoryMatch = !state.category || (story.category_slug || "uncategorized") === state.category;
    const haystack = [story.title_hi, story.title_en, story.content_hi, story.content_en].join(" ").toLowerCase();
    return categoryMatch && (!query || haystack.includes(query));
  });
}

function renderStories() {
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
        <div class="status">${story.review_status || text[state.lang].review}</div>
      </button>
    `)
    .join("");

  document.querySelectorAll(".story-row").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedStoryId = Number(button.dataset.storyId);
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
    <h2>${storyTitle(story)}</h2>
    <p class="meta">
      ${story.book_title_hi || story.book_title_en}
      ${pages ? ` · ${pages} ${text[state.lang].pages}` : ""}
    </p>
    <div class="status">${story.review_status}</div>
    <hr />
    <div class="story-body">${storyContent(story) || text[state.lang].noStories}</div>
  `;
}

function render() {
  renderBooks();
  renderCategoryFilter();
  renderCategories();
  renderStories();
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
    renderStories();
  });

  document.querySelector("#categoryFilter").addEventListener("change", (event) => {
    state.category = event.target.value;
    renderStories();
  });

  render();
}

boot().catch((error) => {
  document.body.innerHTML = `<main class="content"><h1>Could not load review data</h1><p>${error.message}</p></main>`;
});

