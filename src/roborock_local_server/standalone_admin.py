"""Standalone admin/dashboard adapter routes."""

from __future__ import annotations

import json
from textwrap import dedent
import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .security import verify_password
from .web_theme import HEAD_ASSETS, NAV_HTML, SCRIPT_ASSETS, register_theme_routes


def _admin_login_html() -> str:
    return (
        dedent(
            """\
            <!doctype html><html><head><meta charset="utf-8">
            <title>Roborock Local Server</title>
            """
        )
        + HEAD_ASSETS
        + dedent(
            """\
            </head><body>
            """
        )
        + NAV_HTML
        + dedent(
            """\
            <div class="container" style="max-width:420px">
              <p class="rls-muted">Sign in to manage the stack.</p>
              <div class="row">
                <div class="input-field col s12">
                  <input id="password" type="password">
                  <label for="password">Admin password</label>
                </div>
              </div>
              <button id="login" class="btn waves-effect waves-light" style="width:100%">
                Sign In<i class="material-icons right">login</i>
              </button>
              <div id="result" class="alert-banner error"></div>
            </div>
            """
        )
        + SCRIPT_ASSETS
        + dedent(
            """\
            <script>
            const resultEl = document.getElementById("result");
            document.getElementById("login").addEventListener("click", async () => {
              const response = await fetch("/admin/api/login", {
                method: "POST",
                headers: {"Content-Type":"application/json"},
                body: JSON.stringify({password: document.getElementById("password").value})
              });
              const payload = await response.json().catch(() => ({error: "Invalid response"}));
              if (!response.ok) {
                resultEl.textContent = payload.error || "Sign-in failed";
                resultEl.classList.add("shown");
                return;
              }
              window.location.reload();
            });
            </script></body></html>
            """
        )
    )


def _admin_dashboard_html(project_support: dict[str, Any]) -> str:
    support_payload = json.dumps(project_support)
    return dedent(
        f"""\
        <!doctype html><html><head><meta charset="utf-8">
        <title>Roborock Local Server</title>
        {HEAD_ASSETS}
        </head><body>
        <nav>
          <div class="nav-wrapper container">
            <a href="#" class="brand-logo"><i class="material-icons">smart_toy</i>Roborock Local Server</a>
            <span style="flex:1"></span>
            <span id="overall" style="color:#fff;margin-right:16px">Loading</span>
            <button id="logout" class="btn-flat" style="color:#fff">Sign Out<i class="material-icons right">logout</i></button>
          </div>
        </nav>

        <div class="container">
          <div id="deviceTabs" class="rls-chips">Loading vacuums...</div>
        </div>

        <div id="devicePanel" class="hidden">
          <div class="container">
            <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
              <h4 id="deviceTitle" class="header rls-heading" style="margin:0"></h4>
              <span id="deviceState" class="rls-badge http"></span>
            </div>
            <div id="deviceFacts" class="rls-facts" style="margin-top:14px"></div>
            <div id="deviceNotice" class="alert-banner"></div>
          </div>

          <div class="container">
            <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
              <h4 class="header rls-heading" style="margin:0">Schedules</h4>
              <span id="scheduleZone" class="rls-muted"></span>
              <span style="flex:1"></span>
              <button id="addSchedule" type="button" class="btn waves-effect waves-light">
                Add schedule<i class="material-icons right">add</i>
              </button>
            </div>
            <div id="scheduleError" class="alert-banner error"></div>
            <div id="scheduleList" style="margin-top:12px"></div>

            <div id="scheduleForm" class="rls-schedule-form hidden">
              <div id="scheduleFormTitle" style="font-weight:600;margin-bottom:10px"></div>
              <div class="rls-form-grid">
                <label class="rls-field">
                  <span class="rls-fact-label">Time</span>
                  <input id="schedTime" type="time" class="browser-default" value="07:00">
                </label>
                <label class="rls-field">
                  <span class="rls-fact-label">Cleaning</span>
                  <select id="schedMode" class="browser-default">
                    <option value="keep">Use the vacuum's current settings</option>
                    <option value="vacuum">Vacuum only</option>
                    <option value="vac_mop">Vacuum and mop</option>
                    <option value="mop">Mop only</option>
                  </select>
                </label>
                <label class="rls-field">
                  <span class="rls-fact-label">Suction</span>
                  <select id="schedSuction" class="browser-default"></select>
                </label>
                <label class="rls-field">
                  <span class="rls-fact-label">Water level</span>
                  <select id="schedWater" class="browser-default"></select>
                </label>
                <label class="rls-field">
                  <span class="rls-fact-label">Mop route</span>
                  <select id="schedRoute" class="browser-default"></select>
                </label>
                <label class="rls-field">
                  <span class="rls-fact-label">Passes</span>
                  <select id="schedRepeat" class="browser-default">
                    <option value="1">1</option><option value="2">2</option><option value="3">3</option>
                  </select>
                </label>
              </div>
              <div class="rls-fact-label" style="margin-top:12px">Days (none selected means every day)</div>
              <div id="schedDays" class="rls-chips" style="margin-top:6px"></div>
              <p style="margin:12px 0 0">
                <label><input id="schedEnabled" type="checkbox" checked><span>Enabled</span></label>
              </p>
              <div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap">
                <button id="saveSchedule" type="button" class="btn waves-effect waves-light">Save</button>
                <button id="cancelSchedule" type="button" class="btn-flat waves-effect">Cancel</button>
              </div>
            </div>
          </div>

          <div class="container">
            <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
              <h4 class="header rls-heading" style="margin:0">Map backups</h4>
              <span class="rls-muted">Asks the robot what it has stored. Nothing is changed.</span>
              <span style="flex:1"></span>
              <button id="checkMaps" type="button" class="btn waves-effect waves-light">Check backups</button>
            </div>
            <div id="mapsError" class="alert-banner error"></div>
            <div id="mapsResult" class="rls-muted" style="margin-top:12px">Not checked yet.</div>
            <details class="rls-details" style="margin-top:10px">
              <summary>Raw answer from the robot</summary>
              <pre id="mapsRaw" class="rls-pre" style="margin-top:10px"></pre>
            </details>
          </div>

          <div class="container">
            <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
              <h4 class="header rls-heading" style="margin:0">Dock and robot capabilities</h4>
              <span class="rls-muted">Asks the robot which options it supports and their values. Nothing is changed.</span>
              <span style="flex:1"></span>
              <button id="checkCaps" type="button" class="btn waves-effect waves-light">Read capabilities</button>
            </div>
            <div id="capsError" class="alert-banner error"></div>
            <div id="capsResult" class="rls-muted" style="margin-top:12px">Not read yet.</div>
            <details class="rls-details" style="margin-top:10px">
              <summary>Raw answers from the robot</summary>
              <pre id="capsRaw" class="rls-pre" style="margin-top:10px"></pre>
            </details>
          </div>

          <div class="container">
            <h4 class="header rls-heading">Activity</h4>
            <div id="activityMeta" class="rls-muted" style="margin-bottom:10px"></div>
            <div id="activityList" class="rls-activity-list"></div>
          </div>

          <div class="container">
            <details class="rls-details">
              <summary>Raw details</summary>
              <pre id="deviceRaw" class="rls-pre" style="margin-top:10px"></pre>
            </details>
          </div>
        </div>

        <div id="serverPanel" class="hidden">
        <div class="container">
          <h4 id="supportTitle" class="header rls-heading"></h4>
          <p id="supportText" class="rls-muted"></p>
          <div id="supportLinks" style="display:flex;gap:12px;flex-wrap:wrap"></div>
        </div>

        <div class="container">
          <h4 class="header rls-heading">Cloud Import</h4>
          <div class="row" style="margin-bottom:0">
            <div class="input-field col s12 m6">
              <input id="email" type="email">
              <label for="email">Roborock account email</label>
            </div>
            <div class="input-field col s12 m6">
              <button id="sendCode" class="btn waves-effect waves-light">Send Code</button>
            </div>
          </div>
          <div class="row">
            <div class="input-field col s12 m6">
              <input id="code" type="text">
              <label for="code">Email code</label>
            </div>
            <div class="input-field col s12 m6">
              <button id="fetchData" class="btn waves-effect waves-light">Fetch Data</button>
            </div>
          </div>
          <pre id="cloudResult" class="rls-pre">No cloud request yet.</pre>
        </div>

        <div class="container">
          <h4 class="header rls-heading">New Connections</h4>
          <p>
            <label><input id="newConnectionsEnabled" type="checkbox" /><span>Allow new app logins, onboarding, and first-time vacuum connections</span></label>
          </p>
          <button id="saveConnections" class="btn waves-effect waves-light">Save</button>
          <div id="authMeta" class="rls-muted" style="margin-top:10px">Loading connection state...</div>
          <div style="margin-top:18px">
            <div style="font-weight:600">Protocol Sync Secret</div>
            <div class="row" style="margin-top:6px;margin-bottom:0">
              <div class="input-field col s12 m9">
                <input id="adminSessionSecret" readonly>
              </div>
              <div class="input-field col s12 m3">
                <button id="copySessionSecret" class="btn-flat waves-effect">Copy<i class="material-icons right">content_copy</i></button>
              </div>
            </div>
            <div id="syncSecretMeta" class="rls-muted">Use this with <code>mitm_redirect.py --local-api YOUR_SERVER_HOST --sync-secret &lt;secret above&gt; --activity-sync</code>.</div>
          </div>
          <div id="pendingRecovery" class="rls-muted" style="margin-top:10px"></div>
          <div style="margin-top:16px;font-weight:600">Protocol Sessions</div>
          <div id="sessionList" style="display:grid;gap:8px;margin-top:12px">Loading sessions...</div>
        </div>

        <div class="container">
          <h4 class="header rls-heading">Health</h4>
          <pre id="health" class="rls-pre"></pre>
        </div>
        </div>
        {SCRIPT_ASSETS}
        <script>
        const support = {support_payload};
        let cloudSessionId = "";
        document.getElementById("supportTitle").textContent = support.title || "Support This Project";
        document.getElementById("supportText").textContent = support.text || "";
        const supportLinks = document.getElementById("supportLinks");
        for (const link of (support.links || [])) {{
          const anchor = document.createElement("a");
          anchor.href = link.url;
          anchor.target = "_blank";
          anchor.rel = "noreferrer";
          anchor.textContent = link.label || link.url;
          anchor.style.display = "inline-block";
          anchor.style.padding = "8px 12px";
          anchor.style.border = "1px solid var(--rls-border)";
          anchor.style.borderRadius = "7px";
          anchor.style.textDecoration = "none";
          anchor.style.color = "inherit";
          supportLinks.appendChild(anchor);
        }}
        async function fetchJson(url, options) {{
          const response = await fetch(url, options);
          const raw = await response.text();
          const payload = raw ? JSON.parse(raw) : {{}};
          if (!response.ok) throw new Error(payload.error || `HTTP ${{response.status}}`);
          return payload;
        }}
        function yesNo(value) {{
          return value ? "Yes" : "No";
        }}
        let vacuumList = [];
        const deviceKey = (vac) => vac.duid || vac.did || "";
        const vacuumLabel = (vac) => vac.name || vac.did || vac.duid || "Unknown vacuum";
        function currentSelection() {{
          const hash = decodeURIComponent(window.location.hash.replace(/^#/, ""));
          if (hash === "server") return "server";
          const wanted = hash.startsWith("device=") ? hash.slice(7) : "";
          if (wanted && vacuumList.some((vac) => deviceKey(vac) === wanted || vac.did === wanted)) return wanted;
          // Nothing (valid) selected: open the first vacuum, or the Server view if there are none.
          return vacuumList.length ? deviceKey(vacuumList[0]) : "server";
        }}
        function renderDeviceTabs(selected) {{
          const tabs = document.getElementById("deviceTabs");
          tabs.innerHTML = "";
          const addChip = (key, label, state) => {{
            const chip = document.createElement("button");
            chip.type = "button";
            chip.className = "rls-chip" + (key === selected ? " active" : "");
            const dot = document.createElement("span");
            dot.className = "rls-dot " + state;
            chip.appendChild(dot);
            chip.appendChild(document.createTextNode(label));
            chip.addEventListener("click", () => {{
              window.location.hash = key === "server" ? "server" : `device=${{encodeURIComponent(key)}}`;
            }});
            tabs.appendChild(chip);
          }};
          for (const vac of vacuumList) {{
            addChip(deviceKey(vac), vacuumLabel(vac), vac.connected ? "ok" : "wait");
          }}
          addChip("server", "Server", "");
          if (!vacuumList.length) {{
            const hint = document.createElement("span");
            hint.className = "rls-muted";
            hint.textContent = "No vacuums yet. Use Cloud Import under Server to fetch yours.";
            tabs.appendChild(hint);
          }}
        }}
        function renderDevice(vac) {{
          document.getElementById("deviceTitle").textContent = vacuumLabel(vac);
          const state = document.getElementById("deviceState");
          state.textContent = vac.connected ? "Connected" : "Not connected";
          state.className = "rls-badge " + (vac.connected ? "mqtt" : "http");

          const onboarding = vac.onboarding || {{}};
          const keyState = onboarding.key_state || {{}};
          const lastMessage = vac.last_message_at
            ? `${{vac.last_message_at}} (${{vac.last_message_source || "unknown"}})`
            : "None yet";
          const rows = [
            ["Model", vac.model || "Unknown"],
            ["DUID", vac.duid || "-"],
            ["DID", vac.did || "-"],
            ["Product ID", vac.product_id || "-"],
            ["Last message", lastMessage],
            ["Mqtt connected", yesNo(Boolean(vac.connected))],
            ["Num query samples", Number(keyState.query_samples || 0)],
            ["Public Key determined", yesNo(Boolean(onboarding.has_public_key))],
          ];
          const facts = document.getElementById("deviceFacts");
          facts.innerHTML = "";
          for (const [label, value] of rows) {{
            const cell = document.createElement("div");
            const labelEl = document.createElement("div");
            labelEl.className = "rls-fact-label";
            labelEl.textContent = label;
            const valueEl = document.createElement("div");
            valueEl.className = "rls-fact-value";
            valueEl.textContent = String(value);
            cell.appendChild(labelEl);
            cell.appendChild(valueEl);
            facts.appendChild(cell);
          }}

          const notice = document.getElementById("deviceNotice");
          if (onboarding.unsupported) {{
            notice.textContent =
              onboarding.guidance || "This vacuum is not supported by the current onboarding flow.";
            notice.className = "alert-banner shown error";
          }} else {{
            notice.textContent = "";
            notice.className = "alert-banner";
          }}
          // The local key is a credential; never render it, even in the raw view.
          const redacted = Object.assign({{}}, vac, {{local_key: vac.local_key ? "<redacted>" : ""}});
          document.getElementById("deviceRaw").textContent = JSON.stringify(redacted, null, 2);
        }}

        // ---- Schedules -------------------------------------------------------------
        const WEEKDAYS = [[1, "Mon"], [2, "Tue"], [3, "Wed"], [4, "Thu"], [5, "Fri"], [6, "Sat"], [0, "Sun"]];
        const KEEP = "Keep the vacuum's setting";
        const SUCTION = [["", KEEP], ["101", "Quiet"], ["102", "Balanced"], ["103", "Turbo"], ["104", "Max"],
                         ["108", "Max+"], ["110", "Smart"]];
        const WATER = [["", KEEP], ["201", "Low"], ["202", "Medium"], ["203", "High"], ["209", "Smart"]];
        const ROUTE = [["", KEEP], ["300", "Standard"], ["301", "Deep"], ["303", "Deep+"], ["304", "Fast"],
                       ["306", "Smart"]];
        let schedulesDevice = "";
        let schedulesLoadedAt = 0;
        let scheduleZone = "";
        let editingScheduleId = null;
        const field = (id) => document.getElementById(id);
        const formOpen = () => !field("scheduleForm").classList.contains("hidden");

        function fillSelect(id, options) {{
          const select = field(id);
          select.innerHTML = "";
          for (const [value, label] of options) {{
            const option = document.createElement("option");
            option.value = value;
            option.textContent = label;
            select.appendChild(option);
          }}
        }}
        function showScheduleError(message) {{
          const banner = field("scheduleError");
          banner.textContent = message || "";
          banner.classList.toggle("shown", Boolean(message));
        }}
        function modeFromSettings(settings) {{
          if (settings.water_box_mode === 200) return "vacuum";
          if (settings.fan_power === 105) return "mop";
          if (settings.water_box_mode !== undefined) return "vac_mop";
          return "keep";
        }}
        function describeSettings(settings) {{
          const label = (list, value) => (list.find(([key]) => key === String(value)) || [])[1];
          const mode = modeFromSettings(settings);
          const parts = [{{keep: "Vacuum's current settings", vacuum: "Vacuum only", vac_mop: "Vacuum and mop",
                           mop: "Mop only"}}[mode]];
          if (settings.fan_power !== undefined && mode !== "mop") {{
            const name = label(SUCTION, settings.fan_power);
            if (name) parts.push(`${{name}} suction`);
          }}
          if (settings.water_box_mode !== undefined && mode !== "vacuum") {{
            const name = label(WATER, settings.water_box_mode);
            if (name) parts.push(`${{name}} water`);
          }}
          if (settings.mop_mode !== undefined && mode !== "vacuum") {{
            const name = label(ROUTE, settings.mop_mode);
            if (name) parts.push(`${{name}} route`);
          }}
          if (Number(settings.repeat) > 1) parts.push(`${{settings.repeat}} passes`);
          if (settings.segments && settings.segments !== "0") parts.push("selected rooms");
          return parts.join(", ");
        }}
        function describeDays(weekdays) {{
          if (!weekdays || !weekdays.length) return "Every day";
          return WEEKDAYS.filter(([day]) => weekdays.includes(day)).map(([, name]) => name).join(", ");
        }}
        function describeNextRun(schedule) {{
          if (!schedule.enabled) return "Off";
          if (!schedule.next_fire_time) return "Not scheduled";
          const options = {{weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"}};
          try {{
            return new Date(schedule.next_fire_time).toLocaleString([], Object.assign(
              options, {{timeZone: schedule.time_zone || scheduleZone || undefined}}));
          }} catch (error) {{
            return new Date(schedule.next_fire_time).toLocaleString();
          }}
        }}
        function updateScheduleFormState() {{
          // Only the options that apply to the chosen cleaning mode are editable.
          const mode = field("schedMode").value;
          const keep = mode === "keep";
          field("schedSuction").disabled = keep || mode === "mop";
          field("schedWater").disabled = keep || mode === "vacuum";
          field("schedRoute").disabled = keep || mode === "vacuum";
        }}
        function openScheduleForm(schedule) {{
          editingScheduleId = schedule ? schedule.id : null;
          const settings = schedule ? schedule.settings || {{}} : {{}};
          field("scheduleFormTitle").textContent = schedule ? "Edit schedule" : "New schedule";
          field("schedTime").value = (schedule && schedule.time) || "07:00";
          field("schedMode").value = modeFromSettings(settings);
          field("schedSuction").value = settings.fan_power !== undefined && settings.fan_power !== 105
            ? String(settings.fan_power) : "";
          field("schedWater").value = settings.water_box_mode !== undefined && settings.water_box_mode !== 200
            ? String(settings.water_box_mode) : "";
          field("schedRoute").value = settings.mop_mode !== undefined ? String(settings.mop_mode) : "";
          field("schedRepeat").value = String(Math.min(3, Math.max(1, Number(settings.repeat) || 1)));
          field("schedEnabled").checked = schedule ? Boolean(schedule.enabled) : true;
          const chosen = new Set((schedule && schedule.weekdays) || []);
          for (const [day] of WEEKDAYS) field(`schedDay${{day}}`).checked = chosen.has(day);
          updateScheduleFormState();
          showScheduleError("");
          const form = field("scheduleForm");
          form.classList.remove("hidden");
          form.scrollIntoView({{block: "nearest", behavior: "smooth"}});
        }}
        function closeScheduleForm() {{
          editingScheduleId = null;
          field("scheduleForm").classList.add("hidden");
        }}
        function settingsFromForm() {{
          const number = (value) => (value === "" ? null : Number(value));
          const mode = field("schedMode").value;
          const settings = {{
            repeat: Number(field("schedRepeat").value),
            fan_power: number(field("schedSuction").value),
            water_box_mode: number(field("schedWater").value),
            mop_mode: number(field("schedRoute").value),
          }};
          if (mode === "keep") {{
            settings.fan_power = null;
            settings.water_box_mode = null;
            settings.mop_mode = null;
          }} else if (mode === "vacuum") {{
            settings.water_box_mode = 200;
            settings.mop_mode = null;
          }} else if (mode === "mop") {{
            settings.fan_power = 105;
            if (settings.water_box_mode === null) settings.water_box_mode = 202;
          }} else if (settings.water_box_mode === null) {{
            settings.water_box_mode = 202;
          }}
          return settings;
        }}
        async function scheduleRequest(deviceRef, method, scheduleId, body) {{
          const base = `/admin/api/vacuums/${{encodeURIComponent(deviceRef)}}/schedules`;
          const url = scheduleId === null ? base : `${{base}}/${{encodeURIComponent(scheduleId)}}`;
          return fetchJson(url, {{
            method,
            headers: {{"Content-Type": "application/json"}},
            body: body === undefined ? undefined : JSON.stringify(body),
          }});
        }}
        function currentDeviceRef() {{
          return schedulesDevice;
        }}
        function renderSchedules(payload) {{
          scheduleZone = payload.time_zone || "";
          field("scheduleZone").textContent = scheduleZone ? `Times are in ${{scheduleZone}}` : "";
          const list = field("scheduleList");
          list.innerHTML = "";
          const schedules = Array.isArray(payload.schedules) ? payload.schedules : [];
          if (!schedules.length) {{
            const empty = document.createElement("div");
            empty.className = "rls-muted";
            empty.textContent = "No schedules yet.";
            list.appendChild(empty);
            return;
          }}
          for (const schedule of schedules) {{
            const row = document.createElement("div");
            row.className = "rls-schedule-row" + (schedule.enabled ? "" : " off");

            const when = document.createElement("div");
            const time = document.createElement("div");
            time.className = "rls-schedule-time";
            time.textContent = schedule.simple ? schedule.time : schedule.cron;
            const days = document.createElement("div");
            days.className = "rls-muted";
            days.textContent = schedule.simple ? describeDays(schedule.weekdays) : "Custom schedule (edit not supported)";
            when.appendChild(time);
            when.appendChild(days);

            const what = document.createElement("div");
            const summary = document.createElement("div");
            summary.textContent = describeSettings(schedule.settings || {{}});
            const next = document.createElement("div");
            next.className = "rls-muted";
            next.textContent = `Next: ${{describeNextRun(schedule)}}`;
            what.appendChild(summary);
            what.appendChild(next);

            const actions = document.createElement("div");
            actions.className = "rls-schedule-actions";
            // Materialize's switch is div.switch > label > input + span.lever.
            const toggle = document.createElement("div");
            toggle.className = "switch";
            const toggleLabel = document.createElement("label");
            toggleLabel.title = schedule.enabled ? "Turn off" : "Turn on";
            const box = document.createElement("input");
            box.type = "checkbox";
            box.checked = Boolean(schedule.enabled);
            const lever = document.createElement("span");
            lever.className = "lever";
            toggleLabel.appendChild(box);
            toggleLabel.appendChild(lever);
            toggle.appendChild(toggleLabel);
            box.addEventListener("change", async () => {{
              try {{
                await scheduleRequest(currentDeviceRef(), "PUT", schedule.id, {{enabled: box.checked}});
                await loadSchedules(currentDeviceRef());
              }} catch (error) {{
                showScheduleError(error.message);
                box.checked = !box.checked;
              }}
            }});
            actions.appendChild(toggle);

            if (schedule.simple) {{
              const edit = document.createElement("button");
              edit.type = "button";
              edit.className = "btn-flat waves-effect";
              edit.textContent = "Edit";
              edit.addEventListener("click", () => openScheduleForm(schedule));
              actions.appendChild(edit);
            }}

            const remove = document.createElement("button");
            remove.type = "button";
            remove.className = "btn-flat waves-effect";
            remove.textContent = "Delete";
            let armed = false;
            remove.addEventListener("click", async () => {{
              if (!armed) {{
                armed = true;
                remove.textContent = "Confirm delete";
                setTimeout(() => {{ armed = false; remove.textContent = "Delete"; }}, 3000);
                return;
              }}
              try {{
                await scheduleRequest(currentDeviceRef(), "DELETE", schedule.id);
                await loadSchedules(currentDeviceRef());
              }} catch (error) {{
                showScheduleError(error.message);
              }}
            }});
            actions.appendChild(remove);

            row.appendChild(when);
            row.appendChild(what);
            row.appendChild(actions);
            list.appendChild(row);
          }}
        }}
        async function loadSchedules(deviceRef) {{
          try {{
            const payload = await fetchJson(`/admin/api/vacuums/${{encodeURIComponent(deviceRef)}}/schedules`);
            if (deviceRef !== schedulesDevice) return;
            showScheduleError("");
            renderSchedules(payload);
          }} catch (error) {{
            field("scheduleList").innerHTML = "";
            showScheduleError(error.message);
          }}
          schedulesLoadedAt = Date.now();
        }}
        fillSelect("schedSuction", SUCTION);
        fillSelect("schedWater", WATER);
        fillSelect("schedRoute", ROUTE);
        for (const [day, name] of WEEKDAYS) {{
          const label = document.createElement("label");
          const input = document.createElement("input");
          input.type = "checkbox";
          input.id = `schedDay${{day}}`;
          const text = document.createElement("span");
          text.textContent = name;
          label.appendChild(input);
          label.appendChild(text);
          field("schedDays").appendChild(label);
        }}
        field("schedMode").addEventListener("change", updateScheduleFormState);
        field("addSchedule").addEventListener("click", () => openScheduleForm(null));
        field("cancelSchedule").addEventListener("click", closeScheduleForm);
        field("saveSchedule").addEventListener("click", async () => {{
          const body = {{
            time: field("schedTime").value,
            weekdays: WEEKDAYS.map(([day]) => day).filter((day) => field(`schedDay${{day}}`).checked),
            enabled: field("schedEnabled").checked,
            settings: settingsFromForm(),
          }};
          try {{
            await scheduleRequest(
              currentDeviceRef(), editingScheduleId === null ? "POST" : "PUT", editingScheduleId, body);
            closeScheduleForm();
            await loadSchedules(currentDeviceRef());
          }} catch (error) {{
            showScheduleError(error.message);
          }}
        }});
        // ---- Map backups (read-only probe) -------------------------------------------
        function formatRobotTime(value) {{
          const seconds = Number(value);
          if (!Number.isFinite(seconds) || seconds <= 0) return "unknown time";
          return new Date(seconds * 1000).toLocaleString();
        }}
        function renderMaps(payload) {{
          const summary = payload.summary || {{}};
          const result = field("mapsResult");
          result.innerHTML = "";
          const addLine = (text, strong) => {{
            const line = document.createElement("div");
            line.textContent = text;
            if (strong) line.style.fontWeight = "600";
            result.appendChild(line);
          }};
          const stored = summary.multi_map_count ?? (summary.maps || []).length;
          addLine(
            `Maps stored: ${{stored}} of ${{summary.max_multi_map ?? "?"}}. ` +
              `Backups kept per map: up to ${{summary.max_bak_map ?? "?"}}.`,
            true
          );
          for (const map of summary.maps || []) {{
            const label = map.name ? `${{map.name}} (map ${{map.map_flag}})` : `Map ${{map.map_flag}}`;
            const rooms = map.room_count === null || map.room_count === undefined ? "" : `, ${{map.room_count}} rooms`;
            addLine(`${{label}}${{rooms}}, saved ${{formatRobotTime(map.add_time)}}`);
            if (!map.backups.length) {{
              addLine("    No backups.");
            }}
            for (const backup of map.backups) {{
              addLine(`    Backup (flag ${{backup.map_flag}}) from ${{formatRobotTime(backup.add_time)}}`);
            }}
          }}
          field("mapsRaw").textContent = JSON.stringify(payload.raw || {{}}, null, 2);
        }}
        field("checkMaps").addEventListener("click", async () => {{
          const button = field("checkMaps");
          const ref = schedulesDevice;
          if (!ref) return;
          button.disabled = true;
          const label = button.textContent;
          button.textContent = "Asking the robot...";
          field("mapsError").classList.remove("shown");
          try {{
            renderMaps(await fetchJson(`/admin/api/vacuums/${{encodeURIComponent(ref)}}/maps`));
          }} catch (error) {{
            const banner = field("mapsError");
            banner.textContent = error.message;
            banner.classList.add("shown");
          }} finally {{
            button.disabled = false;
            button.textContent = label;
          }}
        }});

        // ---- Dock and robot capabilities (read-only probe) ---------------------------
        function renderCapabilities(payload) {{
          const result = field("capsResult");
          result.innerHTML = "";
          const addLine = (text, strong) => {{
            const line = document.createElement("div");
            line.textContent = text;
            if (strong) line.style.fontWeight = "600";
            result.appendChild(line);
          }};
          const dock = payload.dock || {{}};
          const dockName = dock.name ? `${{dock.name}} (type ${{dock.dock_type}})` : String(dock.dock_type ?? "not reported");
          addLine(`Dock: ${{dockName}}`, true);
          if ((dock.capabilities || []).length) addLine(`Dock can: ${{dock.capabilities.join(", ")}}`);
          const features = payload.features || {{}};
          addLine(`Robot features reported: ${{(features.supported || []).length}}`, true);
          if ((features.supported || []).length) addLine((features.supported || []).join(", "));
          for (const [name, message] of Object.entries(payload.errors || {{}})) {{
            addLine(`${{name}}: ${{message}}`);
          }}
          field("capsRaw").textContent = JSON.stringify(payload.raw || {{}}, null, 2);
        }}
        field("checkCaps").addEventListener("click", async () => {{
          const button = field("checkCaps");
          const ref = schedulesDevice;
          if (!ref) return;
          button.disabled = true;
          const label = button.textContent;
          button.textContent = "Asking the robot...";
          field("capsError").classList.remove("shown");
          try {{
            renderCapabilities(await fetchJson(`/admin/api/vacuums/${{encodeURIComponent(ref)}}/capabilities`));
          }} catch (error) {{
            const banner = field("capsError");
            banner.textContent = error.message;
            banner.classList.add("shown");
          }} finally {{
            button.disabled = false;
            button.textContent = label;
          }}
        }});

        function renderAuth(auth) {{
          const enabled = Boolean(auth.new_connections_enabled);
          document.getElementById("newConnectionsEnabled").checked = enabled;
          document.getElementById("authMeta").textContent =
            `New connections: ${{enabled ? "Allowed" : "Blocked"}}. Persisted sessions: ${{Number(auth.protocol_session_count || 0)}}.`;
          const sessionSecret = String(auth.admin_session_secret || "");
          document.getElementById("adminSessionSecret").value = sessionSecret;
          document.getElementById("syncSecretMeta").textContent = sessionSecret
            ? `Use this with mitm_redirect.py --local-api YOUR_SERVER_HOST --sync-secret ${{sessionSecret}} --activity-sync`
            : "No protocol sync secret is configured.";

          const pendingContainer = document.getElementById("pendingRecovery");
          const pendingItems = Array.isArray(auth.pending_device_mqtt_recovery) ? auth.pending_device_mqtt_recovery : [];
          if (!pendingItems.length) {{
            pendingContainer.textContent = "No devices are waiting for MQTT password recovery.";
          }} else {{
            pendingContainer.textContent =
              "Devices waiting for first reconnect MQTT password recovery: " +
              pendingItems.map((item) => item.name || item.duid || item.did || item.device_mqtt_usr).join(", ");
          }}

          const sessionList = document.getElementById("sessionList");
          sessionList.innerHTML = "";
          const sessions = Array.isArray(auth.protocol_sessions) ? auth.protocol_sessions : [];
          if (!sessions.length) {{
            const empty = document.createElement("div");
            empty.textContent = "No persisted protocol sessions.";
            empty.style.color = "var(--rls-text-muted)";
            sessionList.appendChild(empty);
            return;
          }}
          for (const session of sessions) {{
            const card = document.createElement("div");
            card.style.border = "1px solid var(--rls-border)";
            card.style.borderRadius = "8px";
            card.style.padding = "10px";
            card.style.background = "var(--rls-bg)";
            const label = document.createElement("div");
            label.textContent = session.rruid || session.hawk_id || "Protocol session";
            label.style.fontWeight = "600";
            card.appendChild(label);

            const detail = document.createElement("div");
            detail.textContent = `source=${{session.source || "unknown"}} updated=${{session.updated_at_utc || "unknown"}} hawk_id=${{session.hawk_id || ""}}`;
            detail.style.marginTop = "6px";
            detail.style.fontSize = "12px";
            card.appendChild(detail);

            const remove = document.createElement("button");
            remove.textContent = "Remove";
            remove.className = "btn-flat waves-effect";
            remove.style.marginTop = "8px";
            remove.style.padding = "0 8px";
            remove.addEventListener("click", async () => {{
              try {{
                await fetchJson(
                  `/admin/api/auth/sessions/${{encodeURIComponent(session.hawk_id || "")}}/${{encodeURIComponent(session.hawk_session || "")}}`,
                  {{method: "DELETE"}}
                );
                await refresh();
              }} catch (error) {{
                document.getElementById("authMeta").textContent = error.message;
              }}
            }});
            card.appendChild(remove);
            sessionList.appendChild(card);
          }}
        }}

        function renderActivity(payload) {{
          document.getElementById("activityMeta").textContent = payload.raw
            ? "Showing full raw entries (ROBOROCK_SERVER_ACTIVITY_RAW is enabled) - headers/bodies/payloads are not redacted."
            : "Showing redacted summaries. Set ROBOROCK_SERVER_ACTIVITY_RAW=1 to see full raw entries.";
          const list = document.getElementById("activityList");
          list.innerHTML = "";
          const entries = Array.isArray(payload.entries) ? payload.entries : [];
          if (!entries.length) {{
            const empty = document.createElement("div");
            empty.textContent = "No recent activity.";
            empty.style.color = "var(--rls-text-muted)";
            list.appendChild(empty);
            return;
          }}
          const makeBadge = (source) => {{
            const span = document.createElement("span");
            span.className = `rls-badge ${{source}}`;
            span.textContent = source;
            return span;
          }};
          const appendText = (parent, text) => {{
            parent.appendChild(document.createTextNode(text));
          }};
          for (const entry of entries) {{
            const row = document.createElement("div");
            row.className = "rls-activity-entry";
            const time = document.createElement("span");
            time.className = "rls-activity-time";
            time.textContent = entry.time || "";
            row.appendChild(time);
            const detail = document.createElement("span");
            detail.className = "rls-activity-detail";
            if (payload.raw) {{
              detail.appendChild(makeBadge(entry.source || "http"));
              row.appendChild(detail);
              const pre = document.createElement("pre");
              pre.className = "rls-activity-raw";
              pre.textContent = JSON.stringify(entry, null, 2);
              row.appendChild(pre);
            }} else if (entry.source === "mqtt") {{
              const methods = (entry.rpc_methods || []).join(", ");
              detail.appendChild(makeBadge("mqtt"));
              appendText(detail, ` ${{entry.direction || ""}} ${{entry.topic || ""}}` + (methods ? ` - ${{methods}}` : ""));
              row.appendChild(detail);
            }} else if (entry.source === "mitm") {{
              detail.appendChild(makeBadge("mitm"));
              appendText(
                detail,
                ` ${{entry.method || ""}} ${{entry.host || ""}}${{entry.path || ""}}` +
                  (entry.status ? ` -> ${{entry.status}}` : "") +
                  (entry.rewritten ? " (rewritten to local)" : "")
              );
              row.appendChild(detail);
            }} else {{
              detail.appendChild(makeBadge("http"));
              appendText(detail, ` ${{entry.method || ""}} ${{entry.path || ""}}` + (entry.route ? ` (${{entry.route}})` : ""));
              row.appendChild(detail);
            }}
            list.appendChild(row);
          }}
        }}

        async function refresh() {{
          const status = await fetchJson("/admin/api/status");
          document.getElementById("overall").textContent = status.health.overall_ok ? "Healthy" : "Needs Attention";
          document.getElementById("health").textContent = JSON.stringify(status.health, null, 2);
          renderAuth(await fetchJson("/admin/api/auth"));
          const vacuums = await fetchJson("/admin/api/vacuums");
          vacuumList = Array.isArray(vacuums.vacuums) ? vacuums.vacuums : [];

          const selected = currentSelection();
          renderDeviceTabs(selected);
          const showServer = selected === "server";
          document.getElementById("serverPanel").classList.toggle("hidden", !showServer);
          document.getElementById("devicePanel").classList.toggle("hidden", showServer);
          if (showServer) return;
          const vac = vacuumList.find((item) => deviceKey(item) === selected || item.did === selected);
          if (!vac) return;
          renderDevice(vac);
          const ref = deviceKey(vac);
          if (schedulesDevice !== ref) {{
            schedulesDevice = ref;
            closeScheduleForm();
            field("scheduleList").innerHTML = "";
            await loadSchedules(ref);
          }} else if (!formOpen() && Date.now() - schedulesLoadedAt > 15000) {{
            // Never re-render while the form is open, or an edit in progress would be lost.
            await loadSchedules(ref);
          }}
          renderActivity(await fetchJson(`/admin/api/activity?device=${{encodeURIComponent(ref)}}`));
        }}
        window.addEventListener("hashchange", () => refresh().catch(() => {{}}));
        document.getElementById("sendCode").addEventListener("click", async () => {{
          try {{
            const payload = await fetchJson("/admin/api/cloud/request-code", {{
              method: "POST",
              headers: {{"Content-Type":"application/json"}},
              body: JSON.stringify({{email: document.getElementById("email").value}})
            }});
            cloudSessionId = payload.session_id || "";
            document.getElementById("cloudResult").textContent = JSON.stringify(payload, null, 2);
          }} catch (error) {{
            document.getElementById("cloudResult").textContent = error.message;
          }}
        }});
        document.getElementById("fetchData").addEventListener("click", async () => {{
          try {{
            const payload = await fetchJson("/admin/api/cloud/submit-code", {{
              method: "POST",
              headers: {{"Content-Type":"application/json"}},
              body: JSON.stringify({{session_id: cloudSessionId, code: document.getElementById("code").value}})
            }});
            cloudSessionId = "";
            document.getElementById("cloudResult").textContent = JSON.stringify(payload, null, 2);
            await refresh();
          }} catch (error) {{
            document.getElementById("cloudResult").textContent = error.message;
          }}
        }});
        document.getElementById("saveConnections").addEventListener("click", async () => {{
          try {{
            const payload = await fetchJson("/admin/api/auth", {{
              method: "POST",
              headers: {{"Content-Type":"application/json"}},
              body: JSON.stringify({{
                new_connections_enabled: document.getElementById("newConnectionsEnabled").checked
              }})
            }});
            renderAuth(payload);
            await refresh();
          }} catch (error) {{
            document.getElementById("authMeta").textContent = error.message;
          }}
        }});
        document.getElementById("copySessionSecret").addEventListener("click", async () => {{
          const input = document.getElementById("adminSessionSecret");
          if (!input.value) {{
            document.getElementById("syncSecretMeta").textContent = "No protocol sync secret is configured.";
            return;
          }}
          try {{
            if (navigator.clipboard && navigator.clipboard.writeText) {{
              await navigator.clipboard.writeText(input.value);
            }} else {{
              input.focus();
              input.select();
              document.execCommand("copy");
            }}
            document.getElementById("syncSecretMeta").textContent = "Copied protocol sync secret.";
          }} catch (error) {{
            document.getElementById("syncSecretMeta").textContent = "Copy failed. Select the field and copy it manually.";
          }}
        }});

        document.getElementById("logout").addEventListener("click", async () => {{
          await fetch("/admin/api/logout", {{method:"POST"}});
          window.location.reload();
        }});
        refresh().catch((error) => document.getElementById("overall").textContent = error.message);
        setInterval(() => refresh().catch(() => {{}}), 2000);
        </script></body></html>
        """
    )


def register_standalone_admin_routes(
    *,
    app: FastAPI,
    supervisor: Any,
    project_support: dict[str, Any],
) -> None:
    register_theme_routes(app)

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_page(request: Request) -> HTMLResponse:
        if not supervisor._authenticated(request):
            return HTMLResponse(_admin_login_html())
        return HTMLResponse(_admin_dashboard_html(project_support))

    @app.post("/admin/api/login")
    async def admin_login(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except json.JSONDecodeError:
            body = {}
        password = str((body or {}).get("password") or "")
        if not verify_password(password, supervisor.config.admin.password_hash):
            return JSONResponse({"error": "Invalid password"}, status_code=401)
        response = JSONResponse({"ok": True})
        response.set_cookie(
            supervisor.session_manager.cookie_name,
            supervisor.session_manager.issue(),
            httponly=True,
            secure=supervisor.cookie_secure(request),
            samesite="lax",
            max_age=supervisor.config.admin.session_ttl_seconds,
            path="/",
        )
        return response

    @app.post("/admin/api/logout")
    async def admin_logout() -> JSONResponse:
        response = JSONResponse({"ok": True})
        response.delete_cookie(supervisor.session_manager.cookie_name, path="/")
        return response

    @app.get("/admin/api/status")
    async def admin_status(request: Request) -> JSONResponse:
        supervisor._require_admin(request)
        return JSONResponse(supervisor._status_payload())

    @app.get("/admin/api/vacuums")
    async def admin_vacuums(request: Request) -> JSONResponse:
        supervisor._require_admin(request)
        return JSONResponse(supervisor._vacuums_payload())

    @app.get("/admin/api/auth")
    async def admin_auth(request: Request) -> JSONResponse:
        supervisor._require_admin(request)
        return JSONResponse(supervisor._auth_payload())

    @app.get("/admin/api/activity")
    async def admin_activity(request: Request) -> JSONResponse:
        supervisor._require_admin(request)
        raw_limit = request.query_params.get("limit")
        try:
            limit = int(raw_limit) if raw_limit else 200
        except ValueError:
            return JSONResponse({"error": "limit must be an integer"}, status_code=400)
        limit = max(1, min(limit, 500))
        device = str(request.query_params.get("device") or "").strip()
        payload = supervisor._activity_payload(limit=limit, device=device)
        if device and not payload["device_known"]:
            return JSONResponse({"error": f"Unknown vacuum {device!r}"}, status_code=404)
        return JSONResponse(payload)

    # Imported here, not at module level: `shared` only lands on sys.path once the
    # backend package has been imported, which happens after this module loads.
    from shared.constants import DEFAULT_TIMEZONE
    from shared.schedule_store import SettingsError, delete_job, list_jobs, merge_job_settings, upsert_job
    from shared.schedule_view import ScheduleInputError, build_cron, job_view

    def _schedule_zone() -> str:
        return str(
            getattr(supervisor.context, "timezone", "") or supervisor.config.network.timezone or DEFAULT_TIMEZONE
        )

    def _vacuum_duid(ref: str) -> tuple[str, JSONResponse | None]:
        """The inventory DUID schedules are filed under for this vacuum, or an error response."""
        reference = ref.strip()
        for vacuum in supervisor._vacuums_payload()["vacuums"]:
            keys = {
                str(vacuum.get(key) or "").strip()
                for key in ("duid", "did", "runtime_did", "linked_inventory_duid")
            }
            if reference not in keys:
                continue
            duid = str(vacuum.get("duid") or "").strip() if vacuum.get("id_kind", "duid") == "duid" else ""
            if not duid:
                return "", JSONResponse(
                    {"error": "This vacuum has no DUID yet; finish the cloud import first."}, status_code=409
                )
            return duid, None
        return "", JSONResponse({"error": f"Unknown vacuum {reference!r}"}, status_code=404)

    async def _json_object(request: Request) -> tuple[dict[str, Any], JSONResponse | None]:
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return {}, JSONResponse({"error": "Invalid JSON body"}, status_code=400)
        if not isinstance(body, dict):
            return {}, JSONResponse({"error": "JSON body must be an object"}, status_code=400)
        return body, None

    @app.get("/admin/api/vacuums/{ref}/schedules")
    async def admin_schedules(ref: str, request: Request) -> JSONResponse:
        supervisor._require_admin(request)
        duid, error = _vacuum_duid(ref)
        if error is not None:
            return error
        zone = _schedule_zone()
        return JSONResponse(
            {
                "duid": duid,
                "time_zone": zone,
                "schedules": [
                    job_view(job, default_timezone=zone) for job in list_jobs(supervisor.context, duid)
                ],
            }
        )

    @app.post("/admin/api/vacuums/{ref}/schedules")
    async def admin_schedule_create(ref: str, request: Request) -> JSONResponse:
        supervisor._require_admin(request)
        duid, error = _vacuum_duid(ref)
        if error is not None:
            return error
        body, error = await _json_object(request)
        if error is not None:
            return error
        try:
            cron = build_cron(body.get("time"), body.get("weekdays") or [])
            param = merge_job_settings(None, body.get("settings") or {})
        except (ScheduleInputError, SettingsError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        zone = _schedule_zone()
        job = upsert_job(
            supervisor.context,
            duid,
            job_id=int(time.time()),
            cron=cron,
            enabled=bool(body.get("enabled", True)),
            time_zone=zone,
            param=param,
        )
        return JSONResponse({"schedule": job_view(job, default_timezone=zone)})

    @app.put("/admin/api/vacuums/{ref}/schedules/{job_id}")
    async def admin_schedule_update(ref: str, job_id: str, request: Request) -> JSONResponse:
        supervisor._require_admin(request)
        duid, error = _vacuum_duid(ref)
        if error is not None:
            return error
        existing = next((job for job in list_jobs(supervisor.context, duid) if str(job.get("id")) == job_id), None)
        if existing is None:
            return JSONResponse({"error": "Schedule not found"}, status_code=404)
        body, error = await _json_object(request)
        if error is not None:
            return error
        try:
            if "time" in body or "weekdays" in body:
                if "time" not in body or "weekdays" not in body:
                    raise ScheduleInputError("time and weekdays must be sent together")
                cron = build_cron(body.get("time"), body.get("weekdays") or [])
            else:
                cron = str(existing.get("cron") or "")
            param = merge_job_settings(existing.get("param"), body["settings"]) if "settings" in body else None
        except (ScheduleInputError, SettingsError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        zone = _schedule_zone()
        job = upsert_job(
            supervisor.context,
            duid,
            job_id=job_id,
            cron=cron,
            enabled=bool(body.get("enabled", existing.get("enabled", True))),
            param=param,
        )
        return JSONResponse({"schedule": job_view(job, default_timezone=zone)})

    @app.delete("/admin/api/vacuums/{ref}/schedules/{job_id}")
    async def admin_schedule_delete(ref: str, job_id: str, request: Request) -> JSONResponse:
        supervisor._require_admin(request)
        duid, error = _vacuum_duid(ref)
        if error is not None:
            return error
        if not delete_job(supervisor.context, duid, job_id):
            return JSONResponse({"error": "Schedule not found"}, status_code=404)
        return JSONResponse({"ok": True})

    @app.get("/admin/api/vacuums/{ref}/maps")
    async def admin_map_backups(ref: str, request: Request) -> JSONResponse:
        """What maps and map backups the robot holds. Read-only, and it asks the robot, so it is
        only called when the page's button is pressed, never from the refresh loop."""
        supervisor._require_admin(request)
        from shared import map_backups
        from shared.routine_runner import RoutineExecutionError

        duid, error = _vacuum_duid(ref)
        if error is not None:
            return error
        try:
            payload = await map_backups.read_map_backups(supervisor.context, duid)
        except RoutineExecutionError as exc:
            return JSONResponse({"error": str(exc)}, status_code=504)
        return JSONResponse({"duid": duid, **payload})

    @app.get("/admin/api/vacuums/{ref}/capabilities")
    async def admin_capabilities(ref: str, request: Request) -> JSONResponse:
        """The robot's feature flags, dock type and the values behind its dock and robot settings.
        Read-only; it asks the robot, so like the map probe it only runs when the button is pressed."""
        supervisor._require_admin(request)
        from shared import capabilities
        from shared.routine_runner import RoutineExecutionError

        duid, error = _vacuum_duid(ref)
        if error is not None:
            return error
        try:
            payload = await capabilities.read_capabilities(supervisor.context, duid)
        except RoutineExecutionError as exc:
            return JSONResponse({"error": str(exc)}, status_code=504)
        return JSONResponse({"duid": duid, **payload})

    @app.post("/admin/api/auth")
    async def admin_auth_update(request: Request) -> JSONResponse:
        supervisor._require_admin(request)
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
        if not isinstance(body, dict):
            return JSONResponse({"error": "JSON body must be an object"}, status_code=400)
        if "new_connections_enabled" in body:
            new_connections_enabled = body.get("new_connections_enabled")
            if not isinstance(new_connections_enabled, bool):
                return JSONResponse({"error": "new_connections_enabled must be a boolean"}, status_code=400)
            try:
                payload = supervisor.set_new_connections_enabled(new_connections_enabled)
            except Exception as exc:  # noqa: BLE001
                return JSONResponse({"error": str(exc)}, status_code=500)
            return JSONResponse(payload)
        if "protocol_auth_enabled" in body:
            protocol_auth_enabled = body.get("protocol_auth_enabled")
            if not isinstance(protocol_auth_enabled, bool):
                return JSONResponse({"error": "protocol_auth_enabled must be a boolean"}, status_code=400)
            try:
                payload = supervisor.set_protocol_auth_enabled(protocol_auth_enabled)
            except Exception as exc:  # noqa: BLE001
                return JSONResponse({"error": str(exc)}, status_code=500)
            return JSONResponse(payload)
        return JSONResponse(
            {"error": "new_connections_enabled or protocol_auth_enabled is required"},
            status_code=400,
        )

    @app.delete("/admin/api/auth/sessions/{hawk_id}/{hawk_session}")
    async def admin_auth_delete_session(hawk_id: str, hawk_session: str, request: Request) -> JSONResponse:
        supervisor._require_admin(request)
        if not supervisor.remove_protocol_session(hawk_id=hawk_id, hawk_session=hawk_session):
            return JSONResponse({"error": "Protocol session not found"}, status_code=404)
        return JSONResponse({"ok": True, "auth": supervisor._auth_payload()})

    @app.get("/admin/api/onboarding/devices")
    async def admin_onboarding_devices(request: Request) -> JSONResponse:
        supervisor._require_admin(request)
        return JSONResponse(supervisor._onboarding_devices_payload())

    @app.post("/admin/api/onboarding/sessions")
    async def admin_onboarding_start(request: Request) -> JSONResponse:
        supervisor._require_admin(request)
        try:
            body = await request.json()
        except json.JSONDecodeError:
            body = {}
        duid = str((body or {}).get("duid") or "").strip()
        new_vacuum = bool((body or {}).get("new_vacuum"))
        name = str((body or {}).get("name") or "").strip()
        model = str((body or {}).get("model") or "").strip()
        try:
            payload = supervisor.start_onboarding_session(
                duid=duid,
                new_vacuum=new_vacuum,
                name=name,
                model=model,
            )
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except KeyError:
            return JSONResponse({"error": "Unknown onboarding device"}, status_code=404)
        return JSONResponse(payload)

    @app.get("/admin/api/onboarding/sessions/{session_id}")
    async def admin_onboarding_status(session_id: str, request: Request) -> JSONResponse:
        supervisor._require_admin(request)
        try:
            payload = supervisor.onboarding_session_snapshot(session_id=session_id)
        except KeyError:
            return JSONResponse({"error": "Onboarding session not found"}, status_code=404)
        return JSONResponse(payload)

    @app.delete("/admin/api/onboarding/sessions/{session_id}")
    async def admin_onboarding_delete(session_id: str, request: Request) -> JSONResponse:
        supervisor._require_admin(request)
        try:
            payload = supervisor.clear_onboarding_session(session_id=session_id)
        except KeyError:
            return JSONResponse({"error": "Onboarding session not found"}, status_code=404)
        return JSONResponse(payload)


    @app.post("/admin/api/cloud/request-code")
    async def admin_cloud_request_code(request: Request) -> JSONResponse:
        supervisor._require_admin(request)
        try:
            body = await request.json()
        except json.JSONDecodeError:
            body = {}
        try:
            result = await supervisor.cloud_manager.request_code(
                email=str((body or {}).get("email") or ""),
                base_url=str((body or {}).get("base_url") or ""),
            )
        except Exception as exc:  # noqa: BLE001
            result = {"success": False, "step": "code_request_failed", "error": str(exc)}
        supervisor.runtime_state.record_cloud_request(result)
        return JSONResponse(result, status_code=200 if result.get("success") else 400)

    @app.post("/admin/api/cloud/submit-code")
    async def admin_cloud_submit_code(request: Request) -> JSONResponse:
        supervisor._require_admin(request)
        try:
            body = await request.json()
        except json.JSONDecodeError:
            body = {}
        try:
            result = await supervisor.cloud_manager.submit_code(
                session_id=str((body or {}).get("session_id") or ""),
                code=str((body or {}).get("code") or ""),
            )
            supervisor.refresh_inventory_state()
        except Exception as exc:  # noqa: BLE001
            result = {"success": False, "step": "code_submit_failed", "error": str(exc)}
        supervisor.runtime_state.record_cloud_request(result)
        return JSONResponse(result, status_code=200 if result.get("success") else 400)
