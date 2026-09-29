// Chat page behaviour. Replies are not streamed in the MVP, so while the form
// posts (the proxy can take 30 s+) we lock the form and show "Thinking…".
(function () {
  var messages = document.getElementById('chat-messages');
  var form = document.getElementById('message-form');
  var thinking = document.getElementById('thinking-indicator');

  function scrollToBottom() {
    if (messages) messages.scrollTop = messages.scrollHeight;
    window.scrollTo(0, document.body.scrollHeight);
  }

  scrollToBottom();

  if (!form) return;
  var textarea = form.querySelector('textarea');
  var button = form.querySelector('button[type="submit"]');
  var submitting = false;

  form.addEventListener('submit', function (event) {
    if (submitting) {
      event.preventDefault();
      return;
    }
    submitting = true;
    // readOnly, not disabled: disabled fields are not submitted.
    textarea.readOnly = true;
    button.disabled = true;
    button.textContent = 'Thinking…';
    if (thinking) thinking.hidden = false;
    scrollToBottom();
  });
})();
