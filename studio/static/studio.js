document.querySelectorAll('[data-open]').forEach(button => {
  button.addEventListener('click', () => document.getElementById(button.dataset.open).showModal());
});
document.querySelectorAll('[data-close]').forEach(button => {
  button.addEventListener('click', () => button.closest('dialog').close());
});
document.querySelectorAll('dialog').forEach(dialog => {
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  if (dialog.hasAttribute('data-reopen')) dialog.showModal();
});
document.querySelectorAll('.artwork img').forEach(image => {
  image.addEventListener('error', () => {
    const fallback = document.createElement('span');
    fallback.className = 'media-fallback';
    fallback.textContent = 'Preview unavailable · open work for media link';
    image.replaceWith(fallback);
  });
});
const panel = document.querySelector('.detail-panel');
if (panel) {
  document.querySelector('main').inert = true;
  document.querySelector('.topbar').inert = true;
  panel.focus();
  panel.addEventListener('keydown', event => {
    if (event.key === 'Escape') panel.querySelector('[aria-label="Close work details"]').click();
    if (event.key !== 'Tab') return;
    const focusable = [...panel.querySelectorAll('a, button, input, select, summary, textarea')]
      .filter(element => element.getClientRects().length && !element.disabled);
    const first = focusable[0], last = focusable.at(-1);
    if (event.shiftKey && (document.activeElement === first || document.activeElement === panel)) {
      event.preventDefault(); last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault(); first.focus();
    }
  });
}
