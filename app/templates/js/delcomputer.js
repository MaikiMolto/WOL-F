// ---
// Delete Computer
let deleteForm;

function setDeleteForm(action, name, value, message) {
  // Store the form element in a variable
  deleteForm = document.createElement('form');
  deleteForm.method = 'POST';
  deleteForm.action = action;

  // Create a hidden input
  const input = document.createElement('input');
  input.type = 'hidden';
  input.name = name;
  input.value = value;

  // Append the input to the form
  deleteForm.appendChild(input);

  // CSRF token for the dynamically-built form
  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  if (csrfMeta) {
    var csrfInput = document.createElement('input');
    csrfInput.type = 'hidden';
    csrfInput.name = 'csrf_token';
    csrfInput.value = csrfMeta.content;
    deleteForm.appendChild(csrfInput);
  }

  document.getElementById('deleteMessage').textContent = message;
}

document.getElementById('confirmDelete').addEventListener('click', function() {
  document.body.appendChild(deleteForm);
  deleteForm.submit();
});
