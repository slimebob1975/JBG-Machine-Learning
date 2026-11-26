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

  /* 301d (asked 2026-11-24): the dataset picture. The server returns the
     points of a 2D projection of a sample; this draws them as SVG, classes and
     K-means clusters as colour and shape (switchable without recomputing), and
     shows a row's values on hover. Built with DOM methods, so values are text. */
  var VIZ_COLOURS = ["#005293", "#e07b24", "#1e8c5a", "#c0392b", "#7b4fb0",
                     "#8c6d31", "#d6619f", "#17a2b8", "#b5a300", "#5b6b7c"];
  var VIZ_NONE = "#b8c0c8";
  var VIZ_SHAPES = ["circle", "square", "triangle", "diamond", "down", "plus", "cross", "star",
                    "pentagon", "hexagon"];                                     /* 301f: ten */
  var SVG = "http://www.w3.org/2000/svg";

  function vizMark(shape, x, y, size, colour) {
    var s = size, el;
    function poly(points) {
      el = document.createElementNS(SVG, "polygon");
      el.setAttribute("points", points.map(function (p) { return (x + p[0] * s) + "," + (y + p[1] * s); }).join(" "));
    }
    if (shape === "square") {
      el = document.createElementNS(SVG, "rect");
      el.setAttribute("x", x - s * 0.85); el.setAttribute("y", y - s * 0.85);
      el.setAttribute("width", s * 1.7); el.setAttribute("height", s * 1.7);
    } else if (shape === "triangle") { poly([[0, -1.15], [1.05, 0.8], [-1.05, 0.8]]); }
    else if (shape === "down") { poly([[0, 1.15], [1.05, -0.8], [-1.05, -0.8]]); }
    else if (shape === "diamond") { poly([[0, -1.25], [1.1, 0], [0, 1.25], [-1.1, 0]]); }
    else if (shape === "plus") { poly([[-0.35, -1.1], [0.35, -1.1], [0.35, -0.35], [1.1, -0.35], [1.1, 0.35], [0.35, 0.35],
                                       [0.35, 1.1], [-0.35, 1.1], [-0.35, 0.35], [-1.1, 0.35], [-1.1, -0.35], [-0.35, -0.35]]); }
    else if (shape === "cross") { poly([[-1, -0.6], [-0.6, -1], [0, -0.4], [0.6, -1], [1, -0.6], [0.4, 0], [1, 0.6], [0.6, 1],
                                        [0, 0.4], [-0.6, 1], [-1, 0.6], [-0.4, 0]]); }
    else if (shape === "pentagon" || shape === "hexagon") {                  /* 301f */
      var corners = shape === "pentagon" ? 5 : 6, around = [];
      for (var c = 0; c < corners; c++) {
        var angle = -Math.PI / 2 + c * 2 * Math.PI / corners;
        around.push([1.15 * Math.cos(angle), 1.15 * Math.sin(angle)]);
      }
      poly(around);
    }
    else if (shape === "star") { poly([[0, -1.25], [0.3, -0.4], [1.2, -0.4], [0.5, 0.15], [0.75, 1.05], [0, 0.5], [-0.75, 1.05],
                                       [-0.5, 0.15], [-1.2, -0.4], [-0.3, -0.4]]); }
    else {
      el = document.createElementNS(SVG, "circle");
      el.setAttribute("cx", x); el.setAttribute("cy", y); el.setAttribute("r", s);
    }
    el.setAttribute("fill", colour);
    el.setAttribute("fill-opacity", "0.8");
    el.setAttribute("stroke", "#ffffff");
    el.setAttribute("stroke-width", "0.6");
    return el;
  }

  function wireVisualisation(form) {
    var box = form.parentNode;
    var plot = box.querySelector("[data-viz-plot]");
    var legend = box.querySelector("[data-viz-legend]");
    var status = box.querySelector("[data-viz-status]");
    var colourBy = form.querySelector("[data-viz-colour]");
    var comma = form.getAttribute("data-decimal") === ",";
    var data = null;
    function number(value, digits) {
      var text = value.toFixed(digits);
      return comma ? text.replace(".", ",") : text;
    }
    function say(text) { status.textContent = text || ""; }

    function encode() {
      var byCluster = colourBy.value === "cluster" && data.clusters > 0;
      var classIndex = {};
      data.classes.forEach(function (name, i) { classIndex[name] = i; });
      /* 301f: "no class" gets the shape after the known classes, so every
         class value, missing included, has a shape of its own. */
      function classShape(name) {
        var index = name === null ? data.classes.length : classIndex[name];
        return VIZ_SHAPES[index % VIZ_SHAPES.length];
      }
      return {
        byCluster: byCluster,
        colour: function (p) {
          if (byCluster) { return VIZ_COLOURS[p.cluster % VIZ_COLOURS.length]; }
          return p["class"] === null ? VIZ_NONE : VIZ_COLOURS[classIndex[p["class"]] % VIZ_COLOURS.length];
        },
        shape: function (p) {
          if (byCluster) { return classShape(p["class"]); }
          return p.cluster === null ? "circle" : VIZ_SHAPES[p.cluster % VIZ_SHAPES.length];
        }
      };
    }

    function drawLegend(code) {
      legend.textContent = "";
      function entry(mark, label) {
        var item = document.createElement("span");
        item.className = "viz-key";
        var icon = document.createElementNS(SVG, "svg");
        icon.setAttribute("width", "16"); icon.setAttribute("height", "16");
        icon.appendChild(mark);
        item.appendChild(icon);
        item.appendChild(document.createTextNode(label));
        legend.appendChild(item);
      }
      var classLabel = form.getAttribute("data-class-label");
      var clusterLabel = form.getAttribute("data-cluster-label");
      data.classes.forEach(function (name, i) {
        var p = { "class": name, cluster: null };
        entry(vizMark(code.byCluster ? code.shape(p) : "circle", 8, 8, 5,
                      code.byCluster ? "#5b6b7c" : code.colour(p)), classLabel + ": " + name);
      });
      if (data.unclassified) {
        entry(vizMark(code.byCluster ? code.shape({ "class": null, cluster: null }) : "circle", 8, 8, 5,
                      code.byCluster ? "#5b6b7c" : VIZ_NONE), form.getAttribute("data-none"));
      }
      if (data.outlier_count) {                                                     /* 301g */
        var ring = document.createElementNS(SVG, "circle");
        ring.setAttribute("cx", 8); ring.setAttribute("cy", 8); ring.setAttribute("r", 6);
        ring.setAttribute("class", "viz-outlier");
        entry(ring, form.getAttribute("data-outlier-label") + " (" + data.outlier_count + ")");
      }
      if (data.boundaries && data.boundaries.length) {
        var dash = document.createElementNS(SVG, "path");
        dash.setAttribute("d", "M1 8 L15 8");
        dash.setAttribute("class", "viz-boundary");
        entry(dash, form.getAttribute("data-boundary-label"));
      }
      for (var k = 0; k < data.clusters; k++) {
        var q = { "class": null, cluster: k };
        entry(vizMark(code.byCluster ? "circle" : code.shape(q), 8, 8, 5,
                      code.byCluster ? code.colour(q) : "#5b6b7c"), clusterLabel + " " + (k + 1));
      }
    }

    function draw() {
      if (!data) { return; }
      var width = 760, height = 520, margin = 28;
      var xs = data.points.map(function (p) { return p.x; });
      var ys = data.points.map(function (p) { return p.y; });
      var x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs);
      var y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
      var sx = (width - 2 * margin) / ((x1 - x0) || 1), sy = (height - 2 * margin) / ((y1 - y0) || 1);
      var code = encode();
      var svg = document.createElementNS(SVG, "svg");
      svg.setAttribute("viewBox", "0 0 " + width + " " + height);
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", status.textContent);
      var frame = document.createElementNS(SVG, "rect");
      frame.setAttribute("x", 0.5); frame.setAttribute("y", 0.5);
      frame.setAttribute("width", width - 1); frame.setAttribute("height", height - 1);
      frame.setAttribute("fill", "none"); frame.setAttribute("stroke", "#d5dde6");
      svg.appendChild(frame);
      /* 301g: dashed lines between the K-means clusters, under the points. */
      function place(x, y) { return [margin + (x - x0) * sx, height - margin - (y - y0) * sy]; }
      (data.boundaries || []).forEach(function (line) {
        var path = document.createElementNS(SVG, "path");
        path.setAttribute("d", line.map(function (point, k) {
          var at = place(point[0], point[1]);
          return (k ? "L" : "M") + at[0].toFixed(1) + " " + at[1].toFixed(1);
        }).join(" "));
        path.setAttribute("class", "viz-boundary");
        svg.appendChild(path);
      });
      data.points.forEach(function (p, i) {
        var mark = vizMark(code.shape(p), margin + (p.x - x0) * sx, height - margin - (p.y - y0) * sy, pointSize(), code.colour(p));
        mark.setAttribute("data-i", String(i));
        svg.appendChild(mark);
      });
      /* 301g: the outliers ringed in red, over the points. */
      data.points.forEach(function (p, i) {
        if (!p.outlier) { return; }
        var at = place(p.x, p.y);
        var ring = document.createElementNS(SVG, "circle");
        ring.setAttribute("cx", at[0]); ring.setAttribute("cy", at[1]);
        ring.setAttribute("r", pointSize() * 1.9);
        ring.setAttribute("class", "viz-outlier");
        ring.setAttribute("data-i", String(i));
        svg.appendChild(ring);
      });
      plot.textContent = "";
      plot.appendChild(svg);
      var tip = document.createElement("div");
      tip.className = "viz-tip";
      tip.hidden = true;
      plot.appendChild(tip);
      svg.addEventListener("mouseover", function (event) {
        var i = event.target.getAttribute && event.target.getAttribute("data-i");
        if (i === null || i === undefined) { return; }
        var point = data.points[Number(i)];
        tip.textContent = "";
        var table = document.createElement("table");
        data.hover_columns.forEach(function (name, j) {
          var row = table.insertRow();
          row.insertCell().textContent = name;
          row.insertCell().textContent = point.values[j];
        });
        if (point.cluster !== null) {
          var row = table.insertRow();
          row.insertCell().textContent = form.getAttribute("data-cluster-label");
          row.insertCell().textContent = String(point.cluster + 1);
        }
        if (point.outlier_score !== null && point.outlier_score !== undefined) {      /* 301g */
          var scored = table.insertRow();
          scored.insertCell().textContent = form.getAttribute("data-score-label");
          scored.insertCell().textContent = number(point.outlier_score, 3) +
            (point.outlier ? " (" + form.getAttribute("data-outlier-label") + ")" : "");
        }
        tip.appendChild(table);
        var area = plot.getBoundingClientRect();
        tip.style.left = Math.min(event.clientX - area.left + 12, area.width - 260) + "px";
        tip.style.top = (event.clientY - area.top + 12) + "px";
        tip.hidden = false;
      });
      svg.addEventListener("mouseout", function () { tip.hidden = true; });
      drawLegend(code);
    }

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var fields = new FormData(form);
      var query = ["method", "clusters", "sample_size", "sampling", "outliers", "outlier_share"].map(function (name) {
        return name + "=" + encodeURIComponent(String(fields.get(name) || "").replace(",", "."));
      }).join("&") + "&boundaries=" + (fields.get("boundaries") ? "true" : "false");   /* 301g */
      say(form.getAttribute("data-loading"));
      plot.setAttribute("aria-busy", "true");
      fetch(form.getAttribute("data-url") + "?" + query, { credentials: "same-origin" })
        .then(function (response) {
          return response.json().then(function (body) { return { ok: response.ok, status: response.status, body: body }; });
        })
        .then(function (answer) {
          plot.removeAttribute("aria-busy");
          if (!answer.ok) {
            var reason = String((answer.body && answer.body.detail) || "");
            var text = reason === "SQL sign-in required" ? form.getAttribute("data-reason-signin")
              : form.getAttribute("data-reason-" + reason);
            data = null; plot.textContent = ""; legend.textContent = "";
            say(text || form.getAttribute("data-failed"));
            return;
          }
          data = answer.body;
          var text = data.rows + " " + form.getAttribute("data-done") + ".";
          if (data.explained) {
            text += " " + form.getAttribute("data-explained") + ": " + data.explained.map(function (v) {
              return number(v * 100, 1) + " %"; }).join(", ") + ".";
          }
          say(text);
          draw();
        })
        .catch(function () { plot.removeAttribute("aria-busy"); say(form.getAttribute("data-failed")); });
    });
    colourBy.addEventListener("change", draw);
    /* 301f (asked 2026-11-24): the point size, redrawn without recomputing. */
    var sizer = form.querySelector("[data-viz-size]");
    function pointSize() { return sizer ? Number(sizer.value) || 5.5 : 5.5; }
    if (sizer) { sizer.addEventListener("input", draw); }

    /* 301j (asked 2026-11-26): the last picture's settings are remembered per
       dataset in the browser, and the picture is drawn again when the view is
       opened. The server keeps the computed picture, so it comes back at once. */
    var memory = "jbg-viz:" + form.getAttribute("data-url");
    var kept = ["method", "clusters", "sample_size", "sampling", "outliers", "outlier_share"];
    function remember() {
      var settings = { colour: colourBy.value, size: sizer ? sizer.value : "",
                       boundaries: !!(form.querySelector("[name=boundaries]") || {}).checked };
      kept.forEach(function (name) {
        var field = form.querySelector("[name=" + name + "]");
        if (field) { settings[name] = field.value; }
      });
      try { window.localStorage.setItem(memory, JSON.stringify(settings)); } catch (error) { /* full or off */ }
    }
    form.addEventListener("submit", remember);
    colourBy.addEventListener("change", remember);
    if (sizer) { sizer.addEventListener("change", remember); }
    var saved = null;
    try { saved = JSON.parse(window.localStorage.getItem(memory) || "null"); } catch (error) { saved = null; }
    if (saved) {
      kept.forEach(function (name) {
        var field = form.querySelector("[name=" + name + "]");
        if (field && saved[name] !== undefined) { field.value = saved[name]; }
      });
      var lines = form.querySelector("[name=boundaries]");
      if (lines && saved.boundaries !== undefined) { lines.checked = !!saved.boundaries; }
      if (saved.colour) { colourBy.value = saved.colour; }
      if (sizer && saved.size) { sizer.value = saved.size; }
      form.dispatchEvent(new Event("submit", { cancelable: true }));
    }
  }

  /* 301e (asked 2026-11-24): long lists in the left panels show a page at a
     time (seven rows, ten on Run History), the newest first, with buttons to
     the previous and next page. The page with the selected row is shown first.
     Without the script every row shows, as before. */
  function wirePager(table) {
    var size = parseInt(table.getAttribute("data-pager"), 10) || 7;
    var body = table.tBodies[0];
    if (!body) { return; }
    var rows = Array.prototype.slice.call(body.rows);
    if (rows.length <= size) { return; }
    var pages = Math.ceil(rows.length / size);
    var marked = rows.findIndex(function (row) { return row.classList.contains("hl"); });
    var page = marked >= 0 ? Math.floor(marked / size) : 0;
    var bar = document.createElement("div");
    bar.className = "pager";
    var previous = document.createElement("button");
    previous.type = "button";
    previous.className = "btn sub";
    previous.textContent = "\u2039 " + table.getAttribute("data-pager-previous");
    var where = document.createElement("span");
    where.className = "pager-where";
    var next = document.createElement("button");
    next.type = "button";
    next.className = "btn sub";
    next.textContent = table.getAttribute("data-pager-next") + " \u203a";
    bar.appendChild(previous);
    bar.appendChild(where);
    bar.appendChild(next);
    var holder = table.parentNode.classList.contains("scroll") ? table.parentNode : table;
    holder.parentNode.insertBefore(bar, holder.nextSibling);
    function show() {
      rows.forEach(function (row, i) { row.hidden = Math.floor(i / size) !== page; });
      var first = page * size + 1, last = Math.min(rows.length, (page + 1) * size);
      where.textContent = first + "\u2013" + last + " " + table.getAttribute("data-pager-of") + " " + rows.length;
      previous.disabled = page === 0;
      next.disabled = page >= pages - 1;
    }
    previous.addEventListener("click", function () { if (page > 0) { page -= 1; show(); } });
    next.addEventListener("click", function () { if (page < pages - 1) { page += 1; show(); } });
    show();
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
    document.querySelectorAll("form[data-viz-form]").forEach(wireVisualisation);   /* 301d */
    document.querySelectorAll("table[data-pager]").forEach(wirePager);             /* 301e */
    wireSectionLinks();
    document.querySelectorAll("[data-top-actions]").forEach(wireTopActions);
    document.querySelectorAll("input[data-name-from]").forEach(wireDefaultName);   /* 300s */
    document.querySelectorAll("button[data-wait]").forEach(wireWaiting);
  });
})();
