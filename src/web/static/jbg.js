/* JBG web interface (293c): the first script, plain JavaScript, no library.
   The forms also work without it; the server applies the same "All" rules. */
(function () {
  "use strict";

  /* "All" choices (agreed 2026-11-06):
     - ticking All ticks every option; unticking All unticks them all
       (otherwise "every option ticked" would tick All again at once);
     - ticking the last unticked option ticks All;
     - unticking an option while All is ticked unticks All.
     When All is ticked only ALL is saved (server-side rule). */
  function wireAllGroup(group) {
    var all = group.querySelector("input[data-all]");
    var others = Array.prototype.slice.call(
      group.querySelectorAll("input[type=checkbox]:not([data-all])"));
    if (!all) { return; }
    all.addEventListener("change", function () {
      others.forEach(function (box) { box.checked = all.checked; });
      updateCombinations();
    });
    others.forEach(function (box) {
      box.addEventListener("change", function () {
        all.checked = others.every(function (other) { return other.checked; });
        updateCombinations();
      });
    });
  }

  /* 299l: "select all" / "clear" for one group of choices (the algorithms);
     a change event per box keeps "All" and the combination count in step. */
  function wireChoiceGroup(group) {
    group.querySelectorAll("[data-group-set]").forEach(function (button) {
      button.addEventListener("click", function () {
        var on = button.getAttribute("data-group-set") === "1";
        group.querySelectorAll("input[type=checkbox]").forEach(function (box) {
          if (box.checked !== on) {
            box.checked = on;
            box.dispatchEvent(new Event("change", { bubbles: true }));
          }
        });
      });
    });
  }

  /* Combinations to spot-check: product over the "All" groups of the number
     of ticked options (a group with nothing ticked counts as one). */
  function updateCombinations() {
    var target = document.querySelector(".combinations b");
    if (!target) { return; }
    var total = 1;
    document.querySelectorAll("[data-all-group]").forEach(function (group) {
      var ticked = group.querySelectorAll("input[type=checkbox]:not([data-all]):checked").length;
      total *= Math.max(ticked, 1);
    });
    target.textContent = String(total);
  }

  /* 297a: the inner progress under the stage bar ("12 of 40" algorithm
     combinations); hidden while the run has none. Text only via textContent. */
  function showInner(panel, inner) {
    var box = panel.querySelector("[data-run-inner]");
    if (!box) { return; }
    var labels = JSON.parse(box.getAttribute("data-inner-labels") || "{}");
    var ok = inner && typeof inner.done === "number" && typeof inner.total === "number" &&
             inner.total > 0 && Object.prototype.hasOwnProperty.call(labels, inner.kind);
    if (!ok) { box.hidden = true; return; }
    var percent = Math.round(Math.min(Math.max(inner.done / inner.total, 0), 1) * 100);
    box.querySelector("[data-inner-label]").textContent = labels[inner.kind];
    var of = box.getAttribute("data-inner-of") || "/";
    if (inner.kind === box.getAttribute("data-inner-timed")) {
      /* 300s: seconds elapsed of the estimated seconds, as minutes. */
      var under = box.getAttribute("data-inner-under-minute") || "< 1 min";
      var minutes = function (s) { return s < 60 ? under : Math.round(s / 60) + " min"; };
      box.querySelector("[data-inner-count]").textContent = minutes(inner.done) + " " + of +
        " " + (box.getAttribute("data-inner-about") || "") + " " + minutes(inner.total);
    } else {
      box.querySelector("[data-inner-count]").textContent = inner.done + " " + of + " " + inner.total;
    }
    box.querySelector("[data-inner-bar]").style.width = percent + "%";
    box.querySelector("[data-inner-meter]").setAttribute("aria-valuenow", String(percent));
    box.hidden = false;
  }

  /* 294a: follow a run. Polls the run's overview every few seconds and
     reloads the page once the run has ended, so the server renders results. */
  function followRun(panel) {
    var runId = panel.getAttribute("data-run-poll");
    var labels = JSON.parse(panel.getAttribute("data-stage-labels") || "{}");
    var terminal = JSON.parse(panel.getAttribute("data-terminal") || "[]");
    function tick() {
      fetch("/api/runs/" + encodeURIComponent(runId) + "/overview", { credentials: "same-origin" })
        .then(function (response) { return response.ok ? response.json() : null; })
        .then(function (overview) {
          if (!overview) { setTimeout(tick, 5000); return; }
          if (terminal.indexOf(overview.status) >= 0) { window.location.reload(); return; }
          /* 299j: the run's status in the list beside the panel follows too
             (it was drawn once and stayed "Queued"). */
          document.querySelectorAll('[data-run-status="' + runId + '"] .badge').forEach(function (badge) {
            badge.textContent = labels[overview.status] || overview.status;
          });
          var stage = overview.stage || {};
          var label = panel.querySelector("[data-run-stage]");
          if (label) { label.textContent = labels[stage.name] || stage.name || ""; }
          var bar = panel.querySelector("[data-run-bar]");
          if (bar && typeof stage.percent === "number") {
            var percent = Math.round(stage.percent * 100);
            bar.style.width = percent + "%";
            var meter = panel.querySelector("[data-run-meter]");
            if (meter) { meter.setAttribute("aria-valuenow", String(percent)); }
          }
          showInner(panel, stage.inner);
          setTimeout(tick, 3000);
        })
        .catch(function () { setTimeout(tick, 5000); });
    }
    setTimeout(tick, 3000);
  }

  /* 298c: the Dark Numbers formula follows the form, as in the Voila GUI:
     method and alpha choose the formula (non-linear has no separated alpha);
     the target class and the fallback are named; the card fades when the
     estimate is off. Nothing is saved until the form is. */
  function wireDarkFormula(card) {
    var form = card.closest("form");
    var types = JSON.parse(card.getAttribute("data-types") || "{}");
    function field(key) { return form.querySelector('[name="f:' + key + '"]'); }
    var enabled = field("mode.calculate_dark_numbers");
    var method = field("mode.dark_number_method");
    var alpha = field("mode.dark_number_alpha");
    var target = field("mode.dark_number_target");
    var fallback = field("mode.experimental_perturbed_dark_number_fallback");
    function update() {
      if (method && alpha) {
        var separated = alpha.querySelector('option[value="SEPARATED"]');
        if (separated) {
          separated.disabled = !types[method.value + ":SEPARATED"];
          if (separated.disabled && alpha.value === "SEPARATED") { alpha.value = "NONE"; }
        }
      }
      var type = method && alpha ? (types[method.value + ":" + alpha.value] || "") : "";
      card.querySelectorAll("[data-formula]").forEach(function (box) {
        box.hidden = box.getAttribute("data-formula") !== type;
      });
      card.querySelector("[data-formula-missing]").hidden = Boolean(type);
      if (target) {
        var chosen = target.options[target.selectedIndex];
        card.querySelector("[data-formula-target]").textContent = chosen ? chosen.textContent : "";
      }
      if (fallback) {
        var label = card.querySelector("[data-formula-fallback]");
        label.textContent = label.getAttribute(fallback.checked ? "data-yes" : "data-no");
      }
      var on = !enabled || enabled.checked;
      card.classList.toggle("off", !on);
      card.querySelector("[data-formula-off]").hidden = on;
    }
    [enabled, method, alpha, target, fallback].forEach(function (control) {
      if (control) { control.addEventListener("change", update); }
    });
    form.addEventListener("jbg:classes", update);
    update();
  }

  /* 298c: the target classes, from the class column of the active training
     dataset, read once when the section is first opened. Class names go
     into the page only (textContent). */
  function wireClassChoice(select) {
    var url = select.getAttribute("data-classes-url");
    var section = select.closest("details");
    var status = select.parentNode.querySelector("[data-class-status]");
    if (!url || !section) { return; }
    var loaded = false;
    function say(text) { status.textContent = text || ""; status.hidden = !text; }
    function load() {
      if (loaded || !section.open) { return; }
      loaded = true;
      say(select.getAttribute("data-loading"));
      fetch(url, { credentials: "same-origin" })
        .then(function (response) {
          if (!response.ok) { throw new Error(String(response.status)); }
          return response.json();
        })
        .then(function (data) {
          var current = select.value;
          var known = Array.prototype.map.call(select.options, function (o) { return o.value; });
          (data.classes || []).forEach(function (entry) {
            var value = String(entry.value);
            if (value === "" || known.indexOf(value) >= 0) { return; }
            var option = document.createElement("option");
            option.value = value;
            option.textContent = value;
            select.appendChild(option);
            known.push(value);
          });
          select.value = current;
          say(data.more_classes ? select.getAttribute("data-more") : "");
          select.form.dispatchEvent(new Event("jbg:classes"));
        })
        .catch(function () { say(select.getAttribute("data-failed")); });
    }
    section.addEventListener("toggle", load);
    load();
  }

  /* 301a (specified 2026-11-24): the share sliders. The range runs from the
     class's current share towards 50 %: oversampling raises the smallest class,
     undersampling lowers the largest. The hidden field carries the value that
     is saved. It stays empty until the slider is moved, so an untouched slider
     is caught when the configuration is saved. */
  function wireShareSlider(box) {
    var url = box.getAttribute("data-classes-url");
    var section = box.closest("details");
    var range = box.querySelector("input[type=range]");
    var hidden = box.querySelector("[data-share-value]");
    var output = box.querySelector("[data-share-output]");
    var status = box.parentNode.querySelector("[data-share-status]");
    var role = box.getAttribute("data-role");
    var comma = box.getAttribute("data-decimal") === ",";
    if (!url || !section || !range || !hidden) { return; }
    function text(value) {
      var shown = (Math.round(value * 10) / 10).toFixed(1);
      return (comma ? shown.replace(".", ",") : shown) + " %";
    }
    function say(message) { if (status) { status.textContent = message || ""; status.hidden = !message; } }
    var loaded = false;
    function load() {
      if (loaded || !section.open) { return; }
      loaded = true;
      say(box.getAttribute("data-loading"));
      fetch(url, { credentials: "same-origin" })
        .then(function (response) {
          if (!response.ok) { throw new Error(String(response.status)); }
          return response.json();
        })
        .then(function (data) {
          var counts = (data.classes || []).map(function (entry) { return Number(entry.count) || 0; })
            .filter(function (count) { return count > 0; });
          var total = counts.reduce(function (sum, count) { return sum + count; }, 0);
          if (counts.length < 2 || !total) { say(box.getAttribute("data-unavailable")); return; }
          var shares = counts.map(function (count) { return 100 * count / total; })
            .sort(function (a, b) { return a - b; });
          var current = role === "over" ? shares[0] : shares[shares.length - 1];
          if (Math.abs(current - 50) < 0.05) { say(box.getAttribute("data-balanced")); return; }
          var low = role === "over" ? current : 50;
          var high = role === "over" ? 50 : current;
          var stored = parseFloat(String(hidden.value || "").replace(",", "."));
          var start = isNaN(stored) ? current : Math.min(Math.max(stored, low), high);
          range.min = String(low);
          range.max = String(high);
          range.value = String(start);
          range.disabled = false;
          output.textContent = text(start);
          say(box.getAttribute("data-now") + " " + text(current) + ". " + box.getAttribute("data-towards"));
          range.addEventListener("input", function () {
            var value = Number(range.value);
            hidden.value = (Math.round(value * 10) / 10).toFixed(1);
            output.textContent = text(value);
            hidden.dispatchEvent(new Event("input", { bubbles: true }));
          });
        })
        .catch(function () { say(box.getAttribute("data-failed")); });
    }
    section.addEventListener("toggle", load);
    load();
  }

  /* 298c: every section starts closed; the ones open when the form is saved
     open again on the page that follows (also after a refused save). */
  function keepOpenSections(form) {
    var key = "jbg-open-sections:" + form.getAttribute("action");
    var stored = null;
    try { stored = window.sessionStorage.getItem(key); window.sessionStorage.removeItem(key); }
    catch (error) { stored = null; }
    (stored ? JSON.parse(stored) : []).forEach(function (id) {
      var section = document.getElementById(id);
      if (section) { section.open = true; }
    });
    form.addEventListener("submit", function () {
      var open = Array.prototype.map.call(
        form.querySelectorAll("details.group[open]"), function (d) { return d.id; });
      try { window.sessionStorage.setItem(key, JSON.stringify(open)); } catch (error) { /* none */ }
    });
  }

  /* 298e: a step of the pipeline picture opens its section of the form;
     so does an address ending in #section-... */
  function wireSectionLinks() {
    document.querySelectorAll("a[data-open-section]").forEach(function (link) {
      link.addEventListener("click", function () {
        var section = document.getElementById(link.getAttribute("data-open-section"));
        if (section) { section.open = true; }
      });
    });
    var target = window.location.hash ? document.getElementById(window.location.hash.slice(1)) : null;
    if (target && target.tagName === "DETAILS") { target.open = true; }
  }

  /* 298j: a wide table (in a .scroll box) gets a second horizontal scrollbar
     above it, kept in step with the one below; hidden while nothing overflows
     (also when a closed section opens: the box is watched for size changes). */
  function addTopScrollbar(box) {
    var top = document.createElement("div");
    top.className = "scroll-top";
    top.setAttribute("aria-hidden", "true");
    var inner = document.createElement("div");
    top.appendChild(inner);
    box.parentNode.insertBefore(top, box);
    function size() {
      inner.style.width = box.scrollWidth + "px";
      top.hidden = box.scrollWidth <= box.clientWidth + 1;
    }
    top.addEventListener("scroll", function () {
      if (box.scrollLeft !== top.scrollLeft) { box.scrollLeft = top.scrollLeft; }
    });
    box.addEventListener("scroll", function () {
      if (top.scrollLeft !== box.scrollLeft) { top.scrollLeft = box.scrollLeft; }
    });
    size();
    if (window.ResizeObserver) {
      var watcher = new ResizeObserver(size);
      watcher.observe(box);
      if (box.firstElementChild) { watcher.observe(box.firstElementChild); }
    } else {
      window.addEventListener("resize", size);
    }
  }

  /* 299d (asked 2026-11-13): an action button follows the traffic lights
     (design decision: ready green, blocked red with the reason on hover)
     while there is nothing to do yet:
       data-wait="change"      until the form differs from how it was shown
                               (data-wait-dirty: ready from the start, e.g.
                               an unsaved suggestion or a refused save);
       data-wait="fields"      until every field in data-wait-fields is filled;
       data-wait-fields-any    ("fields-any") until one of them is.
       data-wait="match"       (299f) until the field in data-wait-fields holds
                               exactly data-wait-match (a project's name).
     A warning (orange) button turns orange, not green, when it is ready (299f).
     A waiting button stays focusable and shows its reason; clicking it, or
     pressing Enter in the form, does nothing. Without JavaScript the buttons
     work as before and the server checks everything. */
  function formState(form) {
    var parts = [];
    Array.prototype.forEach.call(form.elements, function (field) {
      if (!field.name || field.type === "submit" || field.type === "button") { return; }
      if ((field.type === "checkbox" || field.type === "radio") && !field.checked) { return; }
      if (field.type === "file") { parts.push(field.name + "=" + field.files.length); return; }
      if (field.multiple && field.options) {
        Array.prototype.forEach.call(field.selectedOptions, function (o) { parts.push(field.name + "=" + o.value); });
        return;
      }
      parts.push(field.name + "=" + field.value);
    });
    return parts.join("&");
  }

  function filled(field) {
    return field.type === "file" ? field.files.length > 0 : String(field.value || "").trim() !== "";
  }

  function wireWaiting(button) {
    var form = button.form;
    if (!form) { return; }
    var mode = button.getAttribute("data-wait");
    var reason = button.getAttribute("data-wait-reason") || "";
    var title = button.getAttribute("title") || "";
    var readyClass = button.classList.contains("warning") ? "warning" : "ready";
    var initial = formState(form);
    function fields() {
      // form.elements also holds controls tied to the form with form="...".
      var selector = button.getAttribute("data-wait-fields") || "";
      return Array.prototype.filter.call(form.elements, function (field) {
        return selector && field.matches(selector);
      });
    }
    function ready() {
      if (mode === "change") { return button.hasAttribute("data-wait-dirty") || formState(form) !== initial; }
      var list = fields();
      if (mode === "fields") { return list.length > 0 && list.every(filled); }
      if (mode === "fields-any") { return list.some(filled); }
      if (mode === "match") {
        var wanted = button.getAttribute("data-wait-match") || "";
        return list.length > 0 && list.every(function (field) {
          return String(field.value || "").trim() === wanted;
        });
      }
      return true;
    }
    function update() {
      var ok = ready();
      button.classList.toggle(readyClass, ok);
      button.classList.toggle("blocked", !ok);
      button.setAttribute("aria-disabled", ok ? "false" : "true");
      button.title = ok ? title : reason;
    }
    form.addEventListener("input", update);
    form.addEventListener("change", update);
    button.addEventListener("click", function (event) {
      if (button.getAttribute("aria-disabled") === "true") { event.preventDefault(); }
    });
    form.addEventListener("submit", function (event) {
      if (event.submitter === button && button.getAttribute("aria-disabled") === "true") {
        event.preventDefault();
      }
    });
    update();
  }

  /* 299d: the footer's actions also at the top, on pages longer than the window. */
  function wireTopActions(top) {
    function update() {
      top.hidden = document.documentElement.scrollHeight <= window.innerHeight + 120;
    }
    update();
    window.addEventListener("resize", update);
    if (window.ResizeObserver) { new ResizeObserver(update).observe(document.body); }
  }

  /* 300s (asked 2026-11-23): a new dataset's name starts as its file's or
     table's name, without ".csv" or the schema, and can be edited. It follows
     the chosen file or table until the user types a name of their own. */
  function wireDefaultName(input) {
    var source = document.querySelector(input.getAttribute("data-name-from"));
    if (!source) { return; }
    var filled = input.value;
    function suggestion() {
      if (source.type === "file") {
        var file = source.files && source.files[0];
        return file ? file.name.replace(/\.csv$/i, "") : "";
      }
      var value = source.value || "";
      return value.slice(value.lastIndexOf(".") + 1);
    }
    source.addEventListener("change", function () {
      if (input.value !== "" && input.value !== filled) { return; }
      filled = suggestion().slice(0, 200);
      input.value = filled;
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".scroll").forEach(addTopScrollbar);
    document.querySelectorAll("[data-all-group]").forEach(wireAllGroup);
    document.querySelectorAll("[data-choice-group]").forEach(wireChoiceGroup);   /* 299l */
    document.querySelectorAll("[data-run-poll]").forEach(followRun);
    var configuration = document.getElementById("config-form");
    if (configuration) { keepOpenSections(configuration); }
    document.querySelectorAll("[data-dark-formula]").forEach(wireDarkFormula);
    document.querySelectorAll("select[data-class-choice]").forEach(wireClassChoice);
    document.querySelectorAll("[data-share-slider]").forEach(wireShareSlider);     /* 301a */
    wireSectionLinks();
    document.querySelectorAll("[data-top-actions]").forEach(wireTopActions);
    document.querySelectorAll("input[data-name-from]").forEach(wireDefaultName);   /* 300s */
    document.querySelectorAll("button[data-wait]").forEach(wireWaiting);
  });
})();
