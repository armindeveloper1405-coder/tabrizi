document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-auto-dismiss]").forEach((element) => {
    window.setTimeout(() => element.remove(), 5000);
  });

  const revealItems = document.querySelectorAll(
    ".rate-card, .empty-state, .notice-card"
  );

  const quantityInput = document.querySelector("[data-quantity]");
  const itemSelect = document.querySelector("[data-price-select]");
  const totalOutput = document.querySelector("[data-total]");
  const renderTotal = () => {
    if (!quantityInput || !itemSelect || !totalOutput) return;
    const price = Number(itemSelect.selectedOptions[0]?.dataset.price || 0);
    const quantity = Number(quantityInput.value || 0);
    totalOutput.textContent = new Intl.NumberFormat("fa-IR").format(price * quantity);
  };
  quantityInput?.addEventListener("input", renderTotal);
  itemSelect?.addEventListener("change", renderTotal);
  renderTotal();

  const timer = document.querySelector("[data-countdown]");
  if (timer) {
    let remaining = Number(timer.dataset.countdown);
    const tick = () => {
      timer.textContent = new Intl.NumberFormat("fa-IR").format(Math.max(remaining, 0));
      if (remaining-- <= 0) {
        window.location.reload();
        return;
      }
      window.setTimeout(tick, 1000);
    };
    tick();
  }

  if (
    window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
    !("IntersectionObserver" in window)
  ) {
    return;
  }

  document.body.classList.add("js-motion");

  const observer = new IntersectionObserver(
    (entries, currentObserver) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          currentObserver.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );

  revealItems.forEach((item) => observer.observe(item));
});
