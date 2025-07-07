---
layout: home
title: Beranda
pagination:
  enabled: true
---

# Postingan Terbaru

<ul class="space-y-4">
  {% for post in paginator.posts %}
    <li class="border-b pb-3">
      <a href="{{ post.url | relative_url }}" class="text-lg font-semibold text-blue-600 hover:underline">
        {{ post.title }}
      </a>
      <p class="text-sm text-gray-500">{{ post.date | date: "%d %B %Y" }}</p>
    </li>
  {% endfor %}
</ul>

<div class="mt-8 flex justify-between text-sm text-blue-700">
  {% if paginator.previous_page %}
    <a href="{{ paginator.previous_page_path | relative_url }}" class="hover:underline">← Halaman Sebelumnya</a>
  {% else %}
    <span></span>
  {% endif %}

  {% if paginator.next_page %}
    <a href="{{ paginator.next_page_path | relative_url }}" class="hover:underline">Halaman Berikutnya →</a>
  {% endif %}
</div>
