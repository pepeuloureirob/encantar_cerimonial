document.addEventListener("DOMContentLoaded", () => {
  const menu = document.querySelector(".menu-toggle");
  const nav = document.querySelector(".site-nav");
  if (menu && nav) {
    menu.addEventListener("click", () => nav.classList.toggle("open"));
  }

  const reveal = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) entry.target.classList.add("visible");
      });
    }, {threshold: .12});
    reveal.forEach(el => observer.observe(el));
  } else {
    reveal.forEach(el => el.classList.add("visible"));
  }
});
