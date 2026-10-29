(() => {
  "use strict";

  const ACCOUNTS_KEY = "wisi.portal.accounts.v1";
  const PASSWORD_ITERATIONS = 210000;
  const PASSWORD_SCHEME = "PBKDF2-SHA-256";
  const DASHBOARD_URL = "Mainpage.html";

  const logoutButton = document.getElementById("logoutButton");
  if (logoutButton) {
    logoutButton.addEventListener("click", () => {
      window.location.assign("index.html");
    });
  }

  const accountForm = document.getElementById("accountForm");
  if (!accountForm) return;

  const resetForm = document.getElementById("resetForm");
  if (!resetForm) return;

  const accountView = document.getElementById("accountView");
  const resetView = document.getElementById("resetView");
  const accountMessage = document.getElementById("accountMessage");
  const resetMessage = document.getElementById("resetMessage");
  const loginTab = document.getElementById("loginTab");
  const signupTab = document.getElementById("signupTab");
  const emailInput = document.getElementById("email");
  const passwordInput = document.getElementById("password");
  const confirmPasswordInput = document.getElementById("confirmPassword");
  const accountSubmit = document.getElementById("submitButton");
  const accountSubmitText = document.getElementById("submitText");
  const resetSubmit = resetForm.querySelector('button[type="submit"]');
  const resetSubmitText = resetSubmit.querySelector("span");
  const defaultResetButtonText = resetSubmitText.textContent;
  const modeFields = {
    name: document.getElementById("nameField"),
    company: document.getElementById("companyField"),
    confirm: document.getElementById("confirmField"),
    options: document.getElementById("loginOptions"),
    terms: document.getElementById("termsField"),
    strength: document.getElementById("passwordStrength")
  };
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
    confirmPasswordInput.required = isSignup;
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
    const bar = document.getElementById("strengthBar");

    bar.style.width = value ? `${Math.max(14, score * 25)}%` : "0";
    bar.style.background = levels[score].color;
    document.getElementById("strengthLabel").textContent = value ? levels[score].label : "";
    modeFields.strength.classList.toggle("is-visible", mode === "signup" && value.length > 0);
  }

  function getWebCrypto() {
    if (!window.isSecureContext || !window.crypto?.subtle) {
      throw new Error("Open this site over HTTPS (or localhost) in a modern browser to create and check passwords.");
    }
    return window.crypto;
  }

  function getAccountRecords() {
    let storedRecords;
    try {
      storedRecords = window.localStorage.getItem(ACCOUNTS_KEY);
    } catch {
      throw new Error("This browser does not allow access to local storage. Enable it and try again.");
    }

    if (storedRecords === null) return [];

    let records;
    try {
      records = JSON.parse(storedRecords);
    } catch {
      throw new Error("Saved account records are damaged. Do not clear them automatically; contact your portal administrator.");
    }

    if (!Array.isArray(records) || records.some((account) =>
      !account ||
      typeof account.email !== "string" ||
      typeof account.name !== "string" ||
      typeof account.company !== "string" ||
      account.passwordScheme !== PASSWORD_SCHEME ||
      !Number.isInteger(account.passwordIterations) ||
      typeof account.salt !== "string" ||
      typeof account.passwordHash !== "string"
    )) {
      throw new Error("Saved account records have an unsupported format. Contact your portal administrator.");
    }

    return records;
  }

  function saveAccountRecords(records) {
    try {
      window.localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(records));
    } catch {
      throw new Error("This browser could not save the account. Check available storage and browser privacy settings.");
    }
  }

  function bytesToHex(bytes) {
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  }

  function hexToBytes(hex) {
    if (hex.length % 2 !== 0 || !/^[\da-f]+$/i.test(hex)) {
      throw new Error("This saved account has an invalid password record. Contact your portal administrator.");
    }

    const bytes = new Uint8Array(hex.length / 2);
    for (let index = 0; index < bytes.length; index++) {
      bytes[index] = Number.parseInt(hex.slice(index * 2, index * 2 + 2), 16);
    }
    return bytes;
  }

  async function createPasswordHash(password, salt) {
    const crypto = getWebCrypto();
    const key = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(password),
      "PBKDF2",
      false,
      ["deriveBits"]
    );
    const derivedBits = await crypto.subtle.deriveBits(
      {
        name: "PBKDF2",
        salt,
        iterations: PASSWORD_ITERATIONS,
        hash: "SHA-256"
      },
      key,
      256
    );
    return bytesToHex(new Uint8Array(derivedBits));
  }

  function hashesMatch(first, second) {
    if (first.length !== second.length) return false;
    let difference = 0;
    for (let index = 0; index < first.length; index++) {
      difference |= first.charCodeAt(index) ^ second.charCodeAt(index);
    }
    return difference === 0;
  }

  function setBusy(button, label, isBusy, idleText) {
    button.disabled = isBusy;
    button.setAttribute("aria-busy", String(isBusy));
    label.textContent = isBusy ? "Please wait..." : idleText;
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
    const confirmInput = confirmPasswordInput;

    if (isSignup) {
      const name = document.getElementById("fullName").value.trim();
      const company = document.getElementById("company").value.trim();
      if (name.length < 2 || name.length > 120 || !company || company.length > 160) {
        showMessage(accountMessage, "Enter a full name (2–120 characters) and a company name (up to 160 characters).", true);
        document.getElementById(name.length < 2 || name.length > 120 ? "fullName" : "company").focus();
        return;
      }
      if (email.length > 254 || password.length > 128) {
        showMessage(accountMessage, "The email or password is longer than allowed. Please shorten it and try again.", true);
        return;
      }
    }

    if (isSignup && password !== confirmInput.value) {
      showMessage(accountMessage, "Those passwords don’t match. Please check and try again.", true);
      confirmInput.focus();
      return;
    }

    const idleText = isSignup ? "Create your account" : "Sign in to your workspace";
    setBusy(accountSubmit, accountSubmitText, true, idleText);

    try {
      const accounts = getAccountRecords();

      if (isSignup) {
        const name = document.getElementById("fullName").value.trim();
        const company = document.getElementById("company").value.trim();

        if (accounts.some((account) => account.email === email)) {
          throw new Error("An account with that email already exists. Switch to Sign in instead.");
        }

        const salt = getWebCrypto().getRandomValues(new Uint8Array(16));
        const passwordHash = await createPasswordHash(password, salt);
        const account = {
          name,
          company,
          email,
          passwordScheme: PASSWORD_SCHEME,
          passwordIterations: PASSWORD_ITERATIONS,
          salt: bytesToHex(salt),
          passwordHash,
          createdAt: new Date().toISOString()
        };

        saveAccountRecords(accounts.concat(account));
        accountForm.reset();
        setMode("login");
        emailInput.value = email;
        showMessage(accountMessage, "Your account has been created. Sign in with your new credentials.", false);
        emailInput.focus();
        return;
      }

      const account = accounts.find((record) => record.email === email);
      if (!account) {
        throw new Error("No saved account was found for this email in this browser. Create an account first.");
      }
      if (password.length > 128 ||
          account.passwordIterations < 100000 ||
          account.passwordIterations > PASSWORD_ITERATIONS) {
        throw new Error("This account's saved password record is invalid. Create a new account and try again.");
      }

      const crypto = getWebCrypto();
      const key = await crypto.subtle.importKey(
        "raw",
        new TextEncoder().encode(password),
        "PBKDF2",
        false,
        ["deriveBits"]
      );
      const derivedBits = await crypto.subtle.deriveBits(
        {
          name: "PBKDF2",
          salt: hexToBytes(account.salt),
          iterations: account.passwordIterations,
          hash: "SHA-256"
        },
        key,
        256
      );

      if (!hashesMatch(bytesToHex(new Uint8Array(derivedBits)), account.passwordHash)) {
        throw new Error("The password is incorrect. Check it and try again.");
      }

      window.location.assign(DASHBOARD_URL);
    } catch (error) {
      showAccountError(error);
    } finally {
      setBusy(
        accountSubmit,
        accountSubmitText,
        false,
        mode === "signup" ? "Create your account" : "Sign in to your workspace"
      );
    }
  });

  resetForm.addEventListener("submit", (event) => {
    event.preventDefault();
    clearMessage(resetMessage);
    if (!resetForm.reportValidity()) return;

    showMessage(
      resetMessage,
      "Password reset by email is not available for browser-only accounts. Create a new account in this browser or contact your portal administrator.",
      true
    );
  });
})();
