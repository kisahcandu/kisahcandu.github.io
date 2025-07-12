const POSTS_PER_PAGE = 10;
let currentPage = 1;
let allPosts = [];

async function fetchPosts() {
  const res = await fetch('data/posts.json');
  allPosts = await res.json();
  renderPage(currentPage);
}

function renderPage(page) {
  const list = document.getElementById('story-list');
  list.innerHTML = "";

  const start = (page - 1) * POSTS_PER_PAGE;
  const end = start + POSTS_PER_PAGE;
  const pagePosts = allPosts.slice(start, end);

  pagePosts.forEach(post => {
    const div = document.createElement('div');
    div.className = "p-4 bg-gray-800 rounded";

    div.innerHTML = `
      <h2 class="text-lg font-semibold mb-2">${post.title}</h2>
      <a href="post.html?id=${post.ID}" class="text-blue-400 underline">📖 Baca Cerita</a>
    `;
    list.appendChild(div);
  });

  document.getElementById("prev-btn").disabled = (page === 1);
  document.getElementById("next-btn").disabled = (end >= allPosts.length);
}

document.getElementById("prev-btn").addEventListener("click", () => {
  if (currentPage > 1) {
    currentPage--;
    renderPage(currentPage);
  }
});

document.getElementById("next-btn").addEventListener("click", () => {
  if ((currentPage * POSTS_PER_PAGE) < allPosts.length) {
    currentPage++;
    renderPage(currentPage);
  }
});

document.getElementById("random-btn").addEventListener("click", () => {
  const random = allPosts[Math.floor(Math.random() * allPosts.length)];
  location.href = `post.html?id=${random.ID}`;
});

fetchPosts();
