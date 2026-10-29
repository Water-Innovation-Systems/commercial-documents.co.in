(() => {
  "use strict";

  const API = {
    login: "/api/auth/login",
    signup: "/api/auth/signup",
    passwordReset: "/api/auth/password-reset"
  };
  const DASHBOARD_URL = "Mainpage.html";

  const accountForm = document.getElementById("accountForm");
  const resetForm = document.getElementById("resetForm");
  const accountView = document.getElementById("accountView");
  const resetView = document.getElementById("resetView");
  const accountMessage = document.getElementById("accountMessage");
  const resetMessage = document.getElementById("resetMessage");
  const loginTab = document.getElementById("loginTab");
  const signupTab = document.getElementById("signupTab");
  const emailInput = document.getElementById("email");
  const passwordInput = document.getElementById("password");
  const accountSubmit = document.getElementById("submitButton");
  const accountSubmitText = document.getElementById("submitText");
  const resetSubmit = resetForm.querySelector('button[type="submit"]');
  const modeFields = {
    name: document.getElementById("nameField"),
    company: document.getElementById("companyField"),
    confirm: document.getElementById("confirmField"),
    options: document.getElementById("loginOptions"),
    terms: document.getElementById("termsField"),
    strength: document.getElementById("passwordStrength")
  };
  const defaultResetButtonText = resetSubmit.querySelector("span").textContent;
  let mode = "login";

  function showMessage(element, message, isError) {
    element.textContent = message;
    element.classList.add("is-visible");
    element.classList.toggle("is-error", isError);
  }

  function clearMessage(element) {
    element.textContent = "";
    element.classList.remove("is-visible", "is-error");
  }

  function setMode(nextMode) {
    mode = nextMode;
    const isSignup = mode === "signup";

    loginTab.setAttribute("aria-selected", String(!isSignup));
    signupTab.setAttribute("aria-selected", String(isSignup));
    loginTab.tabIndex = isSignup ? -1 : 0;
    signupTab.tabIndex = isSignup ? 0 : -1;
    modeFields.name.hidden = !isSignup;
    modeFields.company.hidden = !isSignup;
    modeFields.confirm.hidden = !isSignup;
    modeFields.options.hidden = isSignup;
    modeFields.terms.hidden = !isSignup;
    modeFields.strength.classList.toggle("is-visible", isSignup && passwordInput.value.length > 0);

    document.getElementById("formTitle").textContent = isSignup ? "Create your account" : "Welcome back";
    document.getElementById("formSubtitle").textContent = isSignup
      ? "Set up your workspace and keep business moving."
      : "Sign in to your commercial documents workspace.";
    accountSubmitText.textContent = isSignup ? "Create your account" : "Sign in to your workspace";
    document.getElementById("fullName").required = isSignup;
    document.getElementById("company").required = isSignup;
    document.getElementById("confirmPassword").required = isSignup;
    document.getElementById("acceptTerms").required = isSignup;
    passwordInput.autocomplete = isSignup ? "new-password" : "current-password";
    passwordInput.minLength = isSignup ? 8 : 0;
    clearMessage(accountMessage);
  }

  function displayPasswordStrength(value) {
    let score = 0;
    if (value.length >= 8) score++;
    if (/[A-Z]/.test(value) && /[a-z]/.test(value)) score++;
    if (/\d/.test(value)) score++;
    if (/[^A-Za-z0-9]/.test(value)) score++;

    const levels = [
      { label: "Use at least 8 characters", color: "#e47763" },
      { label: "Weak password", color: "#e47763" },
      { label: "Fair password", color: "#dfa849" },
      { label: "Good password", color: "#63a878" },
      { label: "Strong password", color: "#168778" }
    ];

    document.getElementById("strengthBar").style.width = value ? `${Math.max(14, score * 25)}%` : "0";
    document.getElementById("strengthBar").style.background = levels[score].color;
    document.getElementById("strengthLabel").textContent = value ? levels[score].label : "";
    modeFields.strength.classList.toggle("is-visible", mode === "signup" && value.length > 0);
  }

  function setBusy(button, isBusy, idleText) {
    button.disabled = isBusy;
    button.setAttribute("aria-busy", String(isBusy));
    button.querySelector("span").textContent = isBusy ? "Please wait..." : idleText;
  }

  function getRequestError(status, code) {
    const errors = {
      invalid_request: "Check your details. Passwords must contain at least 8 characters, and all required fields must be completed.",
      invalid_credentials: "We couldn't sign you in with those details. Check your email and password.",
      account_exists: "An account with that email already exists. Sign in with your existing account.",
      too_many_attempts: "There have been too many attempts. Wait 15 minutes before trying again.",
      password_reset_not_configured: "Password reset is unavailable because email delivery has not been configured.",
      not_found: "The authentication service is not configured at this address. Start the portal using auth_server.py.",
      method_not_allowed: "This account request is not supported.",
      unsupported_media_type: "The authentication service received an unsupported request.",
      payload_too_large: "The form contains too much information. Check the fields and try again.",
      account_service_error: "The account service encountered an error. Check the server logs and try again."
    };

    if (typeof code === "string" && Object.hasOwn(errors, code)) return errors[code];
    if (status === 404 || status === 405) return "The authentication service is not configured at this address. Start the portal using auth_server.py.";
    if (status === 400 || status === 413 || status === 415 || status === 422) return "Check your details and try again.";
    if (status === 401) return "We couldn't sign you in with those details. Check your email and password.";
    if (status === 403) return "This account request was rejected. Reload the page and try again.";
    if (status === 409) return "An account with that email already exists. Sign in with your existing account.";
    if (status === 429) return "There have been too many attempts. Wait 15 minutes before trying again.";
    if (status === 503) return "This account service is temporarily unavailable. Please try again later.";
    if (status >= 500) return "The account service encountered an error. Check the server logs and try again.";
    return "The account request could not be completed. Please try again.";
  }

  async function sendRequest(path, payload) {
    if (window.location.protocol === "file:") {
      throw new Error("Open this page through your website or a local web server. Sign-in cannot work from a file:// page.");
    }

    if (window.location.protocol !== "https:" &&
        window.location.hostname !== "localhost" &&
        window.location.hostname !== "127.0.0.1") {
      throw new Error("Sign-in requires a secure HTTPS connection.");
    }

    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 15000);

    try {
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        credentials: "same-origin",
        cache: "no-store",
        redirect: "error",
        signal: controller.signal,
        body: JSON.stringify(payload)
      });

      let result;
      try {
        result = await response.json();
      } catch {
        if (!response.ok) {
          throw new Error(getRequestError(response.status));
        }
        throw new Error("The account service returned an invalid response. Please try again later.");
      }

      if (!result || typeof result !== "object" || Array.isArray(result)) {
        throw new Error("The account service returned an invalid response. Please try again later.");
      }

      if (!response.ok) {
        throw new Error(getRequestError(response.status, result.error));
      }

      return result;
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        throw new Error("The account service took too long to respond. Please try again.");
      }
      if (error instanceof TypeError) {
        throw new Error("Couldn't reach the account service. Check your connection and try again.");
      }
      throw error;
    } finally {
      window.clearTimeout(timeoutId);
    }
  }

  function showAccountError(error) {
    showMessage(
      accountMessage,
      error instanceof Error ? error.message : "Something went wrong. Please try again.",
      true
    );
  }

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => setMode(tab.dataset.mode));
    tab.addEventListener("keydown", (event) => {
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        const nextTab = tab === loginTab ? signupTab : loginTab;
        setMode(nextTab.dataset.mode);
        nextTab.focus();
      }
    });
  });

  document.querySelectorAll("[data-toggle-password]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = document.getElementById(button.dataset.togglePassword);
      if (!input) return;

      const showPassword = input.type === "password";
      input.type = showPassword ? "text" : "password";
      button.setAttribute("aria-pressed", String(showPassword));
      button.setAttribute("aria-label", showPassword ? "Hide password" : "Show password");
    });
  });

  passwordInput.addEventListener("input", () => displayPasswordStrength(passwordInput.value));

  document.getElementById("forgotButton").addEventListener("click", () => {
    clearMessage(resetMessage);
    document.getElementById("resetEmail").value = emailInput.value.trim();
    accountView.hidden = true;
    resetView.hidden = false;
    document.getElementById("resetEmail").focus();
  });

  document.getElementById("backButton").addEventListener("click", () => {
    resetView.hidden = true;
    accountView.hidden = false;
    clearMessage(accountMessage);
    emailInput.focus();
  });

  accountForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearMessage(accountMessage);

    if (!accountForm.reportValidity()) return;

    const email = emailInput.value.trim().toLowerCase();
    const password = passwordInput.value;
    const isSignup = mode === "signup";
    const confirmPassword = document.getElementById("confirmPassword");

    if (isSignup && password !== confirmPassword.value) {
      showMessage(accountMessage, "Those passwords don’t match. Please check and try again.", true);
      confirmPassword.focus();
      return;
    }

    const payload = isSignup
      ? {
          name: document.getElementById("fullName").value.trim(),
          company: document.getElementById("company").value.trim(),
          email,
          password,
          acceptTerms: document.getElementById("acceptTerms").checked
        }
      : {
          email,
          password,
          remember: accountForm.elements.remember.checked
        };

    const idleText = isSignup ? "Create your account" : "Sign in to your workspace";
    setBusy(accountSubmit, true, idleText);

    try {
      const result = await sendRequest(isSignup ? API.signup : API.login, payload);

      if (isSignup) {
        if (result.authenticated === true) {
          window.location.assign(DASHBOARD_URL);
          return;
        }

        if (result.created !== true) {
          throw new Error("The account service couldn't confirm account creation. Please try again.");
        }

        accountForm.reset();
        setMode("login");
        emailInput.value = email;
        showMessage(accountMessage, "Your account was created. Sign in with your new credentials.", false);
        emailInput.focus();
        return;
      }

      if (result.authenticated !== true) {
        throw new Error("We couldn't verify your sign-in. Please check your details and try again.");
      }

      window.location.assign(DASHBOARD_URL);
    } catch (error) {
      showAccountError(error);
    } finally {
      setBusy(accountSubmit, false, mode === "signup" ? "Create your account" : "Sign in to your workspace");
    }
  });

  resetForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearMessage(resetMessage);
    if (!resetForm.reportValidity()) return;

    const resetEmail = document.getElementById("resetEmail");
    setBusy(resetSubmit, true, defaultResetButtonText);

    try {
      const result = await sendRequest(API.passwordReset, {
        email: resetEmail.value.trim().toLowerCase()
      });

      if (result.accepted !== true) {
        throw new Error("The account service couldn't accept this request. Please try again later.");
      }

      showMessage(
        resetMessage,
        "If an account matches that email, password-reset instructions will be sent.",
        false
      );
    } catch (error) {
      showMessage(
        resetMessage,
        error instanceof Error ? error.message : "Something went wrong. Please try again.",
        true
      );
    } finally {
      setBusy(resetSubmit, false, defaultResetButtonText);
    }
  });
})();