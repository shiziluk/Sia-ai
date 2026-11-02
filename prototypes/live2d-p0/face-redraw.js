// Experimental layer-separation page. The default prototype uses safe.js.
const ASSET_ROOT = "../../sia_out/sia_face_p0/layers";
const MANIFEST_URL = "../../sia_out/sia_face_p0/layers.manifest.json";

const canvas = document.querySelector("#canvas");
const ctx = canvas.getContext("2d");
const hud = document.querySelector("#hud");
const moodInput = document.querySelector("#mood");
const blinkInput = document.querySelector("#blink");
const talkInput = document.querySelector("#talk");
const playTalk = document.querySelector("#play-talk");
const toggleBlink = document.querySelector("#toggle-blink");

// Browsers may restore a prior range value at refresh. Reset the visual
// baseline before applying explicit URL overrides.
blinkInput.value = "1";
talkInput.value = "0";

const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const query = new URLSearchParams(location.search);
const debugMode = query.has("debug");

const state = {
  mood: "neutral",
  talk: 0,
  blink: 1,
  gazeX: 0,
  gazeY: 0,
  breath: 0,
  autoBlink: !reducedMotion,
  nextBlinkAt: performance.now() + 2800,
  blinkAge: 9999,
  blinkDuration: 260,
};

const initialMood = query.get("mood");
if (initialMood) {
  state.mood = initialMood;
  moodInput.value = initialMood;
}
const initialGaze = query.get("gaze")?.split(",").map(Number);
if (initialGaze?.length === 2 && initialGaze.every(Number.isFinite)) {
  state.gazeX = Math.max(-0.3, Math.min(0.3, initialGaze[0]));
  state.gazeY = Math.max(-0.3, Math.min(0.3, initialGaze[1]));
}
const blinkParam = query.get("blink");
const initialBlink = blinkParam === null ? NaN : Number(blinkParam);
if (Number.isFinite(initialBlink)) {
  blinkInput.value = String(Math.max(0, Math.min(1, initialBlink)));
}
if (query.get("autoblink") === "0") {
  state.autoBlink = false;
  toggleBlink.textContent = "恢复自动眨眼";
}

const images = {};
let manifest;

async function loadImage(path) {
  const image = new Image();
  image.src = path;
  await image.decode();
  return image;
}

async function loadAssets() {
  manifest = await fetch(MANIFEST_URL).then((response) => {
    if (!response.ok) throw new Error(`manifest ${response.status}`);
    return response.json();
  });
  const entries = {
    face: `${ASSET_ROOT}/face_base.png`,
    eyeL: `${ASSET_ROOT}/eye_viewer_left_base.png`,
    irisL: `${ASSET_ROOT}/eye_viewer_left_iris.png`,
    eyeR: `${ASSET_ROOT}/eye_viewer_right_base.png`,
    irisR: `${ASSET_ROOT}/eye_viewer_right_iris.png`,
    mouth: `${ASSET_ROOT}/mouth.png`,
  };
  await Promise.all(
    Object.entries(entries).map(async ([key, path]) => {
      images[key] = await loadImage(path);
    })
  );
}

function moodParams(mood) {
  const table = {
    neutral: { lid: 1, tint: null, gazeY: 0 },
    happy: { lid: 0.86, tint: "rgba(255,195,105,.08)", gazeY: -0.05 },
    sad: { lid: 0.72, tint: "rgba(92,132,180,.16)", gazeY: 0.25 },
    angry: { lid: 0.72, tint: "rgba(206,92,91,.12)", gazeY: 0 },
    anxious: { lid: 0.88, tint: "rgba(108,145,170,.12)", gazeY: 0.1 },
    sleepy: { lid: 0.28, tint: "rgba(91,104,139,.16)", gazeY: 0.22 },
    shy: { lid: 0.78, tint: "rgba(235,118,154,.13)", gazeY: 0.28 },
    surprised: { lid: 1.12, tint: "rgba(150,217,238,.08)", gazeY: -0.12 },
    tsundere: { lid: 0.66, tint: "rgba(201,103,119,.1)", gazeY: -0.08 },
  };
  return table[mood] ?? table.neutral;
}

function drawEyeBox(box, base, iris, irisBox, openness, gazeX, gazeY) {
  const [x, y, w, h] = box;
  const [ix, iy, iw, ih] = irisBox;
  const visibleHeight = Math.max(0, h * openness);
  ctx.save();
  ctx.beginPath();
  ctx.rect(x, y, w, visibleHeight);
  ctx.clip();
  ctx.drawImage(base, x, y, w, h);
  ctx.drawImage(iris, ix + gazeX, iy + gazeY, iw, ih);
  ctx.restore();
}

function drawMouth() {
  const box = manifest.mouth.source_box;
  const [x, y, w, h] = box;
  const scaleY = 0.9 + state.talk * 0.35;
  ctx.save();
  ctx.translate(x + w / 2, y + h);
  ctx.scale(1, scaleY);
  ctx.drawImage(images.mouth, -w / 2, -h, w, h);
  ctx.restore();
}

function drawBlush() {
  const alpha = state.mood === "shy" ? 0.14 : state.mood === "happy" ? 0.05 : 0;
  if (!alpha) return;
  const gradient = ctx.createRadialGradient(365, 545, 10, 365, 545, 140);
  gradient.addColorStop(0, `rgba(244,122,151,${alpha})`);
  gradient.addColorStop(1, "rgba(244,122,151,0)");
  ctx.fillStyle = gradient;
  ctx.fillRect(220, 410, 300, 250);
  const second = ctx.createRadialGradient(720, 545, 10, 720, 545, 140);
  second.addColorStop(0, `rgba(244,122,151,${alpha})`);
  second.addColorStop(1, "rgba(244,122,151,0)");
  ctx.fillStyle = second;
  ctx.fillRect(575, 410, 300, 250);
}

function render() {
  const params = moodParams(state.mood);
  const naturalBlink = state.blinkAge < state.blinkDuration
    ? Math.abs(Math.cos((state.blinkAge / state.blinkDuration) * Math.PI))
    : 1;
  const manualBlink = Number(blinkInput.value);
  const openness = Math.max(0.02, Math.min(1.15, Math.min(naturalBlink, manualBlink) * params.lid));
  // The iris disk is intentionally moved only a small amount. Larger shifts
  // expose the reconstructed socket and look like a detached eye.
  const gazeX = state.gazeX * 2;
  const gazeY = (state.gazeY + params.gazeY) * 1.8;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(images.face, 0, 0);
  drawEyeBox(
    manifest.eyes.viewer_left_gold.source_box,
    images.eyeL,
    images.irisL,
    manifest.eyes.viewer_left_gold.iris_source_box,
    openness,
    gazeX,
    gazeY
  );
  drawEyeBox(
    manifest.eyes.viewer_right_red.source_box,
    images.eyeR,
    images.irisR,
    manifest.eyes.viewer_right_red.iris_source_box,
    openness,
    gazeX * 0.75,
    gazeY * 0.75
  );
  drawMouth();
  drawBlush();
  if (params.tint) {
    ctx.fillStyle = params.tint;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }

  hud.textContent = [
    `mood: ${state.mood}`,
    `blink: ${openness.toFixed(2)}`,
    `talk: ${state.talk.toFixed(2)}`,
    `gaze: ${state.gazeX.toFixed(2)}, ${state.gazeY.toFixed(2)}`,
    `reduced: ${reducedMotion}`,
  ].join("\n");

  window.__SIA_P0_STATE__ = {
    mood: state.mood,
    openness,
    talk: state.talk,
    gazeX: state.gazeX,
    gazeY: state.gazeY,
    reducedMotion,
    ready: true,
  };
}

let last = performance.now();
function frame(now) {
  const dt = Math.min(50, now - last);
  last = now;
  state.breath = Math.sin(now / 900) * 0.2;
  if (state.autoBlink && now >= state.nextBlinkAt) {
    state.blinkAge = 0;
    state.nextBlinkAt = now + 2200 + Math.random() * 3000;
  }
  state.blinkAge += dt;
  render();
  requestAnimationFrame(frame);
}

window.addEventListener("pointermove", (event) => {
  const rect = canvas.getBoundingClientRect();
  state.gazeX = Math.max(-1, Math.min(1, ((event.clientX - rect.left) / rect.width) * 2 - 1));
  state.gazeY = Math.max(-1, Math.min(1, ((event.clientY - rect.top) / rect.height) * 2 - 1));
});

moodInput.addEventListener("change", () => {
  state.mood = moodInput.value;
});

toggleBlink.addEventListener("click", () => {
  state.autoBlink = !state.autoBlink;
  toggleBlink.textContent = state.autoBlink ? "暂停自动眨眼" : "恢复自动眨眼";
});

talkInput.addEventListener("input", () => {
  state.talk = Number(talkInput.value);
});

let audioContext;
let analyser;
let audioData;
let source;

function smoothTalk(next) {
  state.talk = state.talk * 0.72 + next * 0.28;
  talkInput.value = String(state.talk.toFixed(2));
}

async function startTalkTest() {
  audioContext ??= new AudioContext();
  await audioContext.resume();
  analyser = audioContext.createAnalyser();
  analyser.fftSize = 256;
  audioData = new Uint8Array(analyser.fftSize);

  source?.stop();
  source = audioContext.createOscillator();
  const gain = audioContext.createGain();
  const lfo = audioContext.createOscillator();
  const lfoGain = audioContext.createGain();
  source.frequency.value = 196;
  gain.gain.value = 0.018;
  lfo.frequency.value = 5.2;
  lfoGain.gain.value = 0.014;
  lfo.connect(lfoGain).connect(gain.gain);
  source.connect(gain).connect(analyser).connect(audioContext.destination);
  source.start();
  lfo.start();
  const endAt = audioContext.currentTime + 2.2;
  source.stop(endAt + 0.2);
  lfo.stop(endAt + 0.2);

  const tick = () => {
    analyser.getByteTimeDomainData(audioData);
    let sum = 0;
    for (const value of audioData) {
      const centered = (value - 128) / 128;
      sum += centered * centered;
    }
    const rms = Math.min(1, Math.sqrt(sum / audioData.length) * 8);
    smoothTalk(rms);
    if (audioContext.currentTime < endAt && source.playbackState !== "finished") {
      requestAnimationFrame(tick);
    } else {
      smoothTalk(0);
    }
  };
  requestAnimationFrame(tick);
}

playTalk.addEventListener("click", () => {
  void startTalkTest();
});

async function boot() {
  try {
    await loadAssets();
    if (debugMode) {
      const moods = ["neutral", "happy", "shy", "surprised", "sleepy", "tsundere"];
      let index = 0;
      setInterval(() => {
        index = (index + 1) % moods.length;
        state.mood = moods[index];
        moodInput.value = state.mood;
      }, 1200);
    }
    requestAnimationFrame(frame);
  } catch (error) {
    hud.textContent = `LOAD ERROR\n${error}`;
    window.__SIA_P0_STATE__ = { ready: false, error: String(error) };
  }
}

window.__SIA_P0_CHECK__ = () => {
  const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
  let nonBlack = 0;
  for (let i = 0; i < pixels.length; i += 400) {
    if (pixels[i] + pixels[i + 1] + pixels[i + 2] > 50) nonBlack += 1;
  }
  return {
    ...window.__SIA_P0_STATE__,
    nonBlackSamples: nonBlack,
    manifestSize: manifest?.source_size,
    imageCount: Object.keys(images).length,
  };
};

void boot();
