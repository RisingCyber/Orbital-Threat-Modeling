// Progressive enhancement only - the app is fully usable with this file
// absent. No use of innerHTML/eval/document.write anywhere in this file,
// deliberately, since anything rendering user-influenced strings here
// would bypass Jinja2's autoescaping and reopen an XSS path.
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".flash").forEach((el) => {
    el.addEventListener("click", () => el.remove());
  });

  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const message = form.getAttribute("data-confirm");
      if (message && !window.confirm(message)) {
        event.preventDefault();
      }
    });
  });
});
