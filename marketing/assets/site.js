const menuButton = document.querySelector("[data-menu-button]");
const menu = document.querySelector("[data-menu]");

if (menuButton && menu) {
  menuButton.addEventListener("click", () => {
    const open = menu.dataset.open !== "true";
    menu.dataset.open = String(open);
    menuButton.setAttribute("aria-expanded", String(open));
  });

  menu.addEventListener("click", (event) => {
    if (event.target.closest("a")) {
      menu.dataset.open = "false";
      menuButton.setAttribute("aria-expanded", "false");
    }
  });
}

document.querySelectorAll("[data-year]").forEach((item) => {
  item.textContent = String(new Date().getFullYear());
});

const waitlistForm = document.querySelector("[data-waitlist-form]");

if (waitlistForm) {
  const status = waitlistForm.querySelector("[data-form-status]");
  const submitButton = waitlistForm.querySelector("button[type='submit']");
  const action = waitlistForm.dataset.googleFormAction || "";
  const emailEntry = waitlistForm.dataset.googleEmailEntry || "";
  const isGoogleConfigured = action.startsWith("https://docs.google.com/forms/") && /^entry\.\d+$/.test(emailEntry);

  waitlistForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const emailInput = waitlistForm.querySelector("input[type='email']");

    if (!emailInput.checkValidity()) {
      emailInput.reportValidity();
      return;
    }

    submitButton.disabled = true;
    submitButton.textContent = "Reserving…";
    status.dataset.state = "";
    status.textContent = "";

    try {
      if (isGoogleConfigured) {
        const payload = new FormData();
        payload.append(emailEntry, emailInput.value);
        await fetch(action, { method: "POST", mode: "no-cors", body: payload });
        status.dataset.state = "success";
        status.textContent = "You’re on the list — we’ll email you at launch with an exclusive founding-member discount.";
        waitlistForm.reset();
      } else {
        // Submit directly to native server endpoint
        const response = await fetch("/waitlist.php", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: emailInput.value.trim() })
        });
        const result = await response.json();
        if (result.success) {
          status.dataset.state = "success";
          status.textContent = result.message || "You’re on the list — we’ll email you at launch with an exclusive founding-member discount.";
          waitlistForm.reset();
        } else {
          status.dataset.state = "error";
          status.textContent = result.error || "We couldn’t reserve your spot. Please try again later.";
        }
      }
    } catch (err) {
      status.dataset.state = "error";
      status.textContent = "Unable to submit. Please try again later.";
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = "Reserve Your Spot";
    }
  });
}
