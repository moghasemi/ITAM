/* رفتارهای سبک سامانه — بدون وابستگی به کتابخانه بیرونی */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    setupSidebar();
    setupUserMenu();
    setupAlerts();
    setupConfirm();
    setupFormsets();
    setupJalaliInputs();
    setupTabs();
    setupPrintButtons();
  });

  /* --------------------------- منوی کناری --------------------------- */
  function setupSidebar() {
    var toggles = document.querySelectorAll("[data-toggle='sidebar']");
    var sidebar = document.getElementById("sidebar");
    if (!sidebar) return;
    toggles.forEach(function (button) {
      button.addEventListener("click", function () {
        sidebar.classList.toggle("open");
      });
    });
    document.addEventListener("click", function (event) {
      if (!sidebar.classList.contains("open")) return;
      if (sidebar.contains(event.target)) return;
      if (event.target.closest("[data-toggle='sidebar']")) return;
      sidebar.classList.remove("open");
    });
  }

  /* --------------------------- منوی کاربر --------------------------- */
  function setupUserMenu() {
    var chip = document.querySelector(".user-chip");
    var menu = document.querySelector(".user-menu");
    if (!chip || !menu) return;
    chip.style.cursor = "pointer";
    chip.addEventListener("click", function (event) {
      event.stopPropagation();
      menu.classList.toggle("open");
    });
    document.addEventListener("click", function () {
      menu.classList.remove("open");
    });
  }

  /* ---------------------------- پیام‌ها ----------------------------- */
  function setupAlerts() {
    document.querySelectorAll("[data-dismiss='alert']").forEach(function (button) {
      button.addEventListener("click", function () {
        var alert = button.closest(".alert");
        if (alert) alert.remove();
      });
    });
    window.setTimeout(function () {
      document.querySelectorAll(".messages .alert-success").forEach(function (alert) {
        alert.style.transition = "opacity .4s";
        alert.style.opacity = "0";
        window.setTimeout(function () { alert.remove(); }, 450);
      });
    }, 6000);
  }

  /* ------------------------- تاییدیه اقدام‌ها ------------------------ */
  function setupConfirm() {
    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        if (!window.confirm(form.getAttribute("data-confirm"))) {
          event.preventDefault();
        }
      });
    });
  }

  /* ------------------------ فرم‌های وابسته (Formset) ---------------- */
  function setupFormsets() {
    document.querySelectorAll("[data-formset]").forEach(function (container) {
      var prefix = container.getAttribute("data-prefix") || "form";
      var totalInput = container.querySelector("input[name='" + prefix + "-TOTAL_FORMS']");
      var rowsContainer = container.querySelector(".formset-rows");
      var template = container.querySelector("template[data-formset-empty]");
      var addButton = container.querySelector("[data-formset-add]");
      if (!totalInput || !rowsContainer || !template || !addButton) return;

      addButton.addEventListener("click", function () {
        var index = parseInt(totalInput.value, 10) || 0;
        var html = template.innerHTML.split("__prefix__").join(index);
        var wrapper = document.createElement("div");
        wrapper.innerHTML = html.trim();
        var row = wrapper.firstElementChild;
        if (row) {
          rowsContainer.appendChild(row);
          totalInput.value = index + 1;
        }
      });

      rowsContainer.addEventListener("click", function (event) {
        var removeButton = event.target.closest("[data-formset-remove]");
        if (!removeButton) return;
        var row = removeButton.closest("[data-formset-row]");
        if (row) row.remove();
      });
    });
  }

  /* --------------------- ورودی تاریخ شمسی -------------------------- */
  function setupJalaliInputs() {
    document.querySelectorAll("input.jalali-date, input.jalali-datetime").forEach(function (input) {
      input.setAttribute("autocomplete", "off");
      input.addEventListener("input", function () {
        var withTime = input.classList.contains("jalali-datetime");
        var digits = toLatinDigits(input.value).replace(/[^\d]/g, "");
        var out = "";
        if (digits.length > 0) out += digits.substring(0, 4);
        if (digits.length > 4) out += "/" + digits.substring(4, 6);
        if (digits.length > 6) out += "/" + digits.substring(6, 8);
        if (withTime && digits.length > 8) {
          out += " " + digits.substring(8, 10);
          if (digits.length > 10) out += ":" + digits.substring(10, 12);
        }
        input.value = out;
      });
    });
  }

  function toLatinDigits(text) {
    var persian = "۰۱۲۳۴۵۶۷۸۹";
    var arabic = "٠١٢٣٤٥٦٧٨٩";
    return String(text || "").replace(/[۰-۹٠-٩]/g, function (char) {
      var index = persian.indexOf(char);
      if (index === -1) index = arabic.indexOf(char);
      return index === -1 ? char : String(index);
    });
  }

  /* ----------------------------- زبانه‌ها --------------------------- */
  function setupTabs() {
    document.querySelectorAll("[data-tabs]").forEach(function (group) {
      var buttons = group.querySelectorAll(".tab");
      buttons.forEach(function (button) {
        button.addEventListener("click", function () {
          var target = button.getAttribute("data-tab-target");
          buttons.forEach(function (item) { item.classList.remove("active"); });
          button.classList.add("active");
          document.querySelectorAll("[data-tab-panel]").forEach(function (panel) {
            if (panel.closest("[data-tabs-scope]") !== group.closest("[data-tabs-scope]")) return;
            panel.classList.toggle("active", panel.getAttribute("data-tab-panel") === target);
          });
        });
      });
      // فعال‌سازی زبانه از طریق پارامتر نشانی: ?focus=hardware
      try {
        var focus = new URLSearchParams(window.location.search).get("focus");
        if (focus) {
          var target = group.querySelector(".tab[data-tab-target='" + focus + "']");
          if (target) target.click();
        }
      } catch (error) { /* بی‌اهمیت */ }
    });
  }

  /* ---------------------------- چاپ --------------------------------- */
  function setupPrintButtons() {
    document.querySelectorAll("[data-print]").forEach(function (button) {
      button.addEventListener("click", function (event) {
        event.preventDefault();
        window.print();
      });
    });
  }
})();
