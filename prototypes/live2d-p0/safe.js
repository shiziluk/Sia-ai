const IMAGE_URL = "../../frontend/public/avatars/stage-realistic-night.png";
const canvas = document.querySelector("#canvas");
const ctx = canvas.getContext("2d");
const hud = document.querySelector("#hud");
const moodInput = document.querySelector("#mood");
const toggleMotion = document.querySelector("#toggle-motion");
const query = new URLSearchParams(location.search);
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

const state = {
  mood: "neutral",
  motion: !reducedMotion,
  pointerX: 0,
  pointerY: 0,
  breath: 0,
  ready: false,
};

const initialMood = query.get("mood");
if (initialMood) {
  state.mood = initialMood;
  moodInput.value = initialMood;
}
if (query.get("motion") === "0") state.motion = false;
const initialGaze = query.get("gaze")?.split(",").map(Number);
if (initialGaze?.length === 2 && initialGaze.every(Number.isFinite)) {
  state.pointerX = Math.max(-1, Math.min(1, initialGaze[0]));
  state.pointerY = Math.max(-1, Math.min(1, initialGaze[1]));
}

toggleMotion.textContent = state.motion ? "暂停微动效" : "恢复微动效";

const moodTint = {
  neutral: null,
  happy: "rgba(255,196,110,.07)",
  sad: "rgba(86,125,170,.12)",
  angry: "rgba(190,74,74,.09)",
  anxious: "rgba(100,135,160,.09)",
  sleepy: "rgba(76,86,122,.12)",
  shy: "rgba(230,111,148,.1)",
  surprised: "rgba(124,199,222,.07)",
  tsundere: "rgba(190,91,109,.07)",
};

const image = new Image();
image.src = IMAGE_URL;

function render(now) {
  if (!state.ready) return;
  const motionScale = state.motion ? 1 : 0;
  const cycle = ((now % 11000) / 11000) * Math.PI * 2;
  state.breath = Math.sin(cycle * 1.35) * motionScale;
  const bodySway = Math.sin(cycle) * 0.18 * motionScale;
  const secondarySway = Math.sin(cycle * 2 + 0.7) * 0.045 * motionScale;
  const tilt = (state.pointerX * 0.32 + bodySway + secondarySway) * motionScale;
  const offsetX = (state.pointerX * 3.2 + Math.sin(cycle + 0.4) * 1.1) * motionScale;
  const offsetY = (state.pointerY * 2.2 + state.breath * 1.4 + Math.sin(cycle * 2) * 0.35) * motionScale;
  const scaleX = 1.004 + state.breath * 0.002 * motionScale;
  const scaleY = 1.008 - state.breath * 0.002 * motionScale;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const shadow = ctx.createRadialGradient(
    canvas.width / 2,
    canvas.height * 0.94,
    2,
    canvas.width / 2,
    canvas.height * 0.94,
    canvas.width * 0.32,
  );
  shadow.addColorStop(0, "rgba(0,0,0,.34)");
  shadow.addColorStop(0.55, "rgba(0,0,0,.12)");
  shadow.addColorStop(1, "rgba(0,0,0,0)");
  ctx.save();
  ctx.scale(1, 0.18);
  ctx.fillStyle = shadow;
  ctx.fillRect(0, canvas.height * 4.4, canvas.width, canvas.height * 1.2);
  ctx.restore();
  ctx.save();
  ctx.translate(canvas.width / 2 + offsetX, canvas.height / 2 + offsetY);
  ctx.rotate((tilt * Math.PI) / 180);
  ctx.scale(scaleX, scaleY);
  ctx.drawImage(image, -canvas.width / 2, -canvas.height / 2, canvas.width, canvas.height);
  ctx.restore();

  const tint = moodTint[state.mood];
  if (tint) {
    ctx.save();
    ctx.globalCompositeOperation = "source-atop";
    ctx.fillStyle = tint;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.restore();
  }

  hud.textContent = [
    "mode: safe-2.5d",
    `source: stage-realistic-night`,
    `mood: ${state.mood}`,
    `motion: ${state.motion}`,
    `gaze: ${state.pointerX.toFixed(2)}, ${state.pointerY.toFixed(2)}`,
  ].join("\n");

  window.__SIA_SAFE_STATE__ = {
    ready: true,
    mood: state.mood,
    motion: state.motion,
    pointerX: state.pointerX,
    pointerY: state.pointerY,
    reducedMotion,
  };
  requestAnimationFrame(render);
}

image.addEventListener("load", () => {
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;
  state.ready = true;
  requestAnimationFrame(render);
});

image.addEventListener("error", () => {
  hud.textContent = "LOAD ERROR\nsia_char_cutout.png";
});

window.addEventListener("pointermove", (event) => {
  const rect = canvas.getBoundingClientRect();
  state.pointerX = Math.max(-1, Math.min(1, ((event.clientX - rect.left) / rect.width) * 2 - 1));
  state.pointerY = Math.max(-1, Math.min(1, ((event.clientY - rect.top) / rect.height) * 2 - 1));
});

moodInput.addEventListener("change", () => {
  state.mood = moodInput.value;
});

toggleMotion.addEventListener("click", () => {
  state.motion = !state.motion;
  toggleMotion.textContent = state.motion ? "暂停微动效" : "恢复微动效";
});

window.__SIA_SAFE_CHECK__ = () => {
  const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
  const rect = canvas.getBoundingClientRect();
  let opaqueSamples = 0;
  for (let i = 3; i < pixels.length; i += 400) {
    if (pixels[i] > 8) opaqueSamples += 1;
  }
  return {
    ...window.__SIA_SAFE_STATE__,
    canvasSize: [canvas.width, canvas.height],
    opaqueSamples,
    imageWidth: image.naturalWidth,
    imageHeight: image.naturalHeight,
    cssRect: [rect.x, rect.y, rect.width, rect.height],
  };
};
