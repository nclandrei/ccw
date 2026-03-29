(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => [...document.querySelectorAll(sel)];

  const allToolchains = ["node", "python", "go", "rust", "ruby", "java"];
  const allExtras = ["gh", "uv", "pnpm", "yarn", "bun", "browser"];

  function getSelected(group) {
    return $$(`.grid[data-group="${group}"] input:checked`).map(
      (el) => el.value
    );
  }

  function buildCommand() {
    const tc = getSelected("toolchains");
    const ex = getSelected("extras");

    let cmd = "uvx ccweb init";

    // Only add flags if not "all"
    if (tc.length > 0 && tc.length < allToolchains.length) {
      cmd += ` --toolchains ${tc.join(",")}`;
    }
    if (ex.length > 0 && ex.length < allExtras.length) {
      cmd += ` --extras ${ex.join(",")}`;
    }

    return cmd;
  }

  function update() {
    const cmd = buildCommand();
    $("#command-text").textContent = cmd;
  }

  // Event listeners
  document.addEventListener("DOMContentLoaded", () => {
    // Check all by default
    $$('.grid input[type="checkbox"]').forEach((el) => {
      el.checked = true;
      el.addEventListener("change", update);
    });

    update();

    // Copy button
    $("#copy-btn").addEventListener("click", () => {
      const cmd = buildCommand();
      navigator.clipboard.writeText(cmd).then(() => {
        const btn = $("#copy-btn");
        const orig = btn.textContent;
        btn.textContent = "Copied!";
        setTimeout(() => (btn.textContent = orig), 1500);
      });
    });

    // Select all / none helpers
    $$(".select-all").forEach((btn) => {
      btn.addEventListener("click", () => {
        const group = btn.dataset.group;
        $$(`.grid[data-group="${group}"] input`).forEach(
          (el) => (el.checked = true)
        );
        update();
      });
    });

    $$(".select-none").forEach((btn) => {
      btn.addEventListener("click", () => {
        const group = btn.dataset.group;
        $$(`.grid[data-group="${group}"] input`).forEach(
          (el) => (el.checked = false)
        );
        update();
      });
    });
  });
})();
