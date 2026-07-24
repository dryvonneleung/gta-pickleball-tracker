/* ============================================================
   GTA PickleCourts — Pickleball Skill Level Assessment
   Self-assessment questionnaire → DUPR/USAPA-style rating band.
   Section 2 (technical, 10 skills × 1–5) drives the band;
   Sections 3 & 4 add tactical/composure context.
   ============================================================ */

// ---- Section 1: Background & Experience (context, not scored) ----
const SECTION1 = [
  { q: "How long have you been playing pickleball?",
    options: ["Less than 3 months", "3–12 months", "1–3 years", "3+ years"] },
  { q: "How often do you play?",
    options: ["Rarely (a few times a year)", "Occasionally (1–2×/month)", "Regularly (1–2×/week)", "Frequently (3+×/week)"] },
  { q: "Have you played other racquet/paddle sports (tennis, badminton, table tennis, squash)?",
    options: ["No", "Recreationally", "Competitively"] },
  { q: "Have you taken lessons or clinics?",
    options: ["No", "A few beginner lessons", "Ongoing lessons/coaching", "Certified instruction + strategy training"] },
  { q: "Have you played in organized play (leagues, ladders, tournaments)?",
    options: ["No", "Casual/local round robins only", "League play", "Sanctioned tournaments"] },
];

// ---- Section 2: Technical skills (each 1–5) ----
const SKILLS = [
  "Forehand groundstroke",
  "Backhand groundstroke",
  "Serve (deep, consistent)",
  "Return of serve",
  "Dinking (cross-court control)",
  "Third shot drop",
  "Volley (forehand/backhand)",
  "Overhead / put-away smash",
  "Lob and defensive lob",
  "Reset shot under pressure",
];
const SKILL_SCALE = ["1 — can't do", "2", "3", "4", "5 — reliable under pressure"];

// ---- Section 3: Tactical & Court Awareness (each 0–3) ----
const SECTION3 = [
  { q: "Do you move to the non-volley zone (kitchen line) with your partner?",
    options: ["Not familiar with this concept", "Aware but inconsistent", "Do this most points", "Automatic, adjusts to the situation"] },
  { q: "Can you identify and exploit an opponent's weaker side or a soft-shot opportunity?",
    options: ["No", "Sometimes, if obvious", "Yes, regularly", "Yes, and adapt strategy mid-game"] },
  { q: "Do you understand stacking, poaching, or shot selection based on score/position?",
    options: ["Not familiar", "Basic understanding", "Apply regularly", "Coach/teach this to others"] },
  { q: "How do you handle fast exchanges at the net (hands battles)?",
    options: ["Avoid them / struggle", "Survive but often lose the point", "Competitive, win my share", "Consistently win these exchanges"] },
];

// ---- Section 4: Physical & Mental Game (each 0–3) ----
const SECTION4 = [
  { q: "Movement and footwork on court:",
    options: ["Limited mobility / slow recovery", "Adequate for casual play", "Good recovery and positioning", "Excellent — anticipates and covers court efficiently"] },
  { q: "Composure under pressure (close games, tiebreaks):",
    options: ["Nervous, error-prone", "Manages most of the time", "Stays composed, executes game plan", "Thrives under pressure"] },
];

// ---- Scoring bands (Section 2 total 10–50) ----
const BANDS = [
  { min: 10, max: 19, level: "2.0–2.5", label: "Beginner" },
  { min: 20, max: 29, level: "3.0", label: "Novice / Low Intermediate" },
  { min: 30, max: 37, level: "3.5", label: "Intermediate" },
  { min: 38, max: 44, level: "4.0", label: "Advanced Intermediate" },
  { min: 45, max: 50, level: "4.5–5.0+", label: "Advanced / Competitive" },
];

function bandFor(total) {
  return BANDS.find(b => total >= b.min && total <= b.max) || BANDS[0];
}

const $ = sel => document.querySelector(sel);
const $$ = sel => Array.from(document.querySelectorAll(sel));

/* ============================================================
   Render
   ============================================================ */
function optionRow(name, options, startValue = 0) {
  // radio group; value is the option index (0-based)
  return `<div class="opt-group" role="radiogroup">` + options.map((opt, i) => `
    <label class="opt">
      <input type="radio" name="${name}" value="${i + startValue}">
      <span>${opt}</span>
    </label>`).join("") + `</div>`;
}

function renderQuestionList(prefix, arr) {
  return arr.map((item, idx) => `
    <div class="question" data-q="${prefix}${idx}">
      <p class="q-text">${item.q}</p>
      ${optionRow(`${prefix}${idx}`, item.options, 0)}
    </div>`).join("");
}

function renderSkills() {
  return `<div class="skill-grid">
    <div class="skill-head">
      <span></span>
      ${SKILL_SCALE.map(s => `<span class="scale-label">${s}</span>`).join("")}
    </div>
    ${SKILLS.map((skill, i) => `
      <div class="skill-row" data-skill="${i}">
        <span class="skill-name">${skill}</span>
        ${[1,2,3,4,5].map(v => `
          <label class="skill-cell">
            <input type="radio" name="skill${i}" value="${v}">
            <span>${v}</span>
          </label>`).join("")}
      </div>`).join("")}
  </div>`;
}

function init() {
  $("#section1").innerHTML = renderQuestionList("s1_", SECTION1);
  $("#skills").innerHTML = renderSkills();
  $("#section3").innerHTML = renderQuestionList("s3_", SECTION3);
  $("#section4").innerHTML = renderQuestionList("s4_", SECTION4);

  $("#calc-btn").addEventListener("click", calculate);
  $("#reset-btn").addEventListener("click", () => {
    $("#assess-form").reset();
    $("#result").classList.add("hidden");
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
  $("#print-btn").addEventListener("click", () => window.print());

  // Live count of technical skills rated
  $("#skills").addEventListener("change", updateProgress);
  updateProgress();
}

function ratedSkillCount() {
  return SKILLS.filter((_, i) => $(`input[name="skill${i}"]:checked`)).length;
}

function updateProgress() {
  const n = ratedSkillCount();
  $("#skill-progress").textContent = `${n} / ${SKILLS.length} skills rated`;
  $("#calc-btn").disabled = n < SKILLS.length;
}

/* ============================================================
   Calculate
   ============================================================ */
function sumGroup(prefix, count) {
  let sum = 0, answered = 0;
  for (let i = 0; i < count; i++) {
    const el = $(`input[name="${prefix}${i}"]:checked`);
    if (el) { sum += Number(el.value); answered++; }
  }
  return { sum, answered, count };
}

function calculate() {
  // Section 2 — required
  let s2 = 0;
  for (let i = 0; i < SKILLS.length; i++) {
    const el = $(`input[name="skill${i}"]:checked`);
    if (!el) { updateProgress(); return; }
    s2 += Number(el.value);
  }
  const band = bandFor(s2);

  // Sections 3 & 4 — optional context (0–3 each)
  const s3 = sumGroup("s3_", SECTION3.length);   // 0–12
  const s4 = sumGroup("s4_", SECTION4.length);   // 0–6
  const tacticalMax = SECTION3.length * 3 + SECTION4.length * 3; // 18
  const tacticalRaw = s3.sum + s4.sum;
  const tacticalAnswered = s3.answered + s4.answered;

  const techPct = (s2 - 10) / 40;                       // 0–1 within band range
  const tacticalPct = tacticalAnswered ? tacticalRaw / (tacticalAnswered * 3) : null;

  renderResult({ s2, band, s3, s4, tacticalRaw, tacticalMax, tacticalAnswered, techPct, tacticalPct });
}

function renderResult(r) {
  const { s2, band, tacticalRaw, tacticalMax, tacticalAnswered, techPct, tacticalPct } = r;

  // Tactical/composure caveat
  let caveat = "";
  if (tacticalPct !== null) {
    if (tacticalPct + 0.2 < techPct) {
      caveat = `Your technique is ahead of your tactics &amp; composure — in competitive play you may perform toward the <strong>lower end</strong> of this band until strategy and pressure-handling catch up.`;
    } else if (tacticalPct > techPct + 0.2) {
      caveat = `Your court smarts and composure are strong relative to your shot inventory — you likely <strong>compete above</strong> your raw technical rating. Tightening technique could push you up a band.`;
    } else {
      caveat = `Your technical, tactical, and mental games are well balanced — a good sign you'll play at this level consistently.`;
    }
  } else {
    caveat = `Answer Sections 3 &amp; 4 for a tactical/composure read — technique alone doesn't tell the whole story in competition.`;
  }

  const name = $("#p-name").value.trim();
  const heading = name ? `${escapeHtml(name)} — suggested level` : "Your suggested level";

  $("#result").innerHTML = `
    <h2>${heading}</h2>
    <div class="result-band">
      <span class="band-level">${band.level}</span>
      <span class="band-label">${band.label}</span>
    </div>
    <div class="meter" aria-hidden="true">
      <div class="meter-fill" style="width:${Math.round(((s2 - 10) / 40) * 100)}%"></div>
    </div>
    <p class="result-score">Technical score: <strong>${s2} / 50</strong>${
      tacticalAnswered ? ` · Tactical &amp; mental: <strong>${tacticalRaw} / ${tacticalMax}</strong>` : ""
    }</p>
    <p class="result-caveat">${caveat}</p>
    <div class="result-actions">
      <button type="button" class="btn btn-secondary" id="print-btn2">Print / Save</button>
    </div>
    <p class="result-disclaimer">This is a self-assessment estimate. For an official rating, pair it with live
      play — rally with a partner and play a game to 11 — or use a DUPR-verified match. Ratings shift with form.</p>`;

  $("#result").classList.remove("hidden");
  $("#print-btn2").addEventListener("click", () => window.print());
  $("#result").scrollIntoView({ behavior: "smooth", block: "start" });
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

document.addEventListener("DOMContentLoaded", init);
