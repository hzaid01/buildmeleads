const form = document.getElementById('authForm');
const errorBox = document.getElementById('authError');
const isSignup = location.pathname === '/signup';

form.addEventListener('submit', async event => {
  event.preventDefault();
  const button = form.querySelector('button[type="submit"]');
  const data = Object.fromEntries(new FormData(form));
  button.disabled = true;
  button.textContent = isSignup ? 'Creating account…' : 'Logging in…';
  errorBox.classList.add('hidden');
  try {
    const response = await fetch(`/api/auth/${isSignup ? 'register' : 'login'}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
    });
    const payload = await response.json();
    if (!response.ok || !payload.success) throw new Error(payload.error || 'Authentication failed');
    location.assign('/');
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.classList.remove('hidden');
    button.disabled = false;
    button.textContent = isSignup ? 'Create account' : 'Log in';
  }
});
