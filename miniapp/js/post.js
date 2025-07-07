function getQueryParam(name) {
  const params = new URLSearchParams(location.search);
  return params.get(name);
}

async function loadPost() {
  const id = getQueryParam('id');
  const res = await fetch('data/posts.json');
  const posts = await res.json();
  const post = posts.find(p => String(p.ID) === id);

  if (!post) {
    document.getElementById("title").textContent = "Cerita tidak ditemukan.";
    document.getElementById("content").innerHTML = "<p>Ups, ID cerita tidak valid.</p>";
    return;
  }

  document.getElementById("title").textContent = post.title;
  document.getElementById("content").innerHTML = post.content;
}

document.getElementById("random-btn").addEventListener("click", async () => {
  const res = await fetch('data/posts.json');
  const posts = await res.json();
  const random = posts[Math.floor(Math.random() * posts.length)];
  location.href = `post.html?id=${random.ID}`;
});

loadPost();
