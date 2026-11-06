// Keep slow movie lookups from being submitted more than once.
document.querySelectorAll('form[data-loading]').forEach((form) => {
    form.addEventListener('submit', () => {
        const button = form.querySelector('button[type="submit"]');
        button.dataset.originalText = button.innerHTML;
        button.textContent = form.dataset.loading;
        button.disabled = true;
        form.setAttribute('aria-busy', 'true');
    });
});

// Browsers may restore a page from cache when the user navigates back.
window.addEventListener('pageshow', () => {
    document.querySelectorAll('button[data-original-text]').forEach((button) => {
        button.innerHTML = button.dataset.originalText;
        button.disabled = false;
        button.closest('form').removeAttribute('aria-busy');
    });
});
