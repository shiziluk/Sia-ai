import { spawn } from "node:child_process";
import { once } from "node:events";

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const PORT = 9337;
const URL = "http://127.0.0.1:8765/prototypes/live2d-p0/face-redraw.html";
const PROFILE = `D:\\dev-tools\\temp\\edge-sia-p0-smoke-${process.pid}`;

const browser = spawn(
  EDGE,
  [
    "--headless",
    "--disable-gpu",
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${PROFILE}`,
    "--window-size=1280,960",
    URL,
  ],
  { stdio: "ignore" }
);

async function sleep(ms) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function findPage() {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const pages = await fetch(`http://127.0.0.1:${PORT}/json/list`).then((r) => r.json());
      const page = pages.find((item) => item.type === "page" && item.url.includes("live2d-p0"));
      if (page?.webSocketDebuggerUrl) return page;
    } catch {
      // Browser is still starting.
    }
    await sleep(250);
  }
  throw new Error("Could not connect to Edge CDP");
}

const page = await findPage();
const socket = new WebSocket(page.webSocketDebuggerUrl);
await once(socket, "open");

let id = 0;
const pending = new Map();
socket.addEventListener("message", (event) => {
  const payload = JSON.parse(event.data);
  if (!payload.id || !pending.has(payload.id)) return;
  const { resolve, reject } = pending.get(payload.id);
  pending.delete(payload.id);
  if (payload.error) reject(new Error(payload.error.message));
  else resolve(payload.result);
});

function call(method, params = {}) {
  const messageId = ++id;
  socket.send(JSON.stringify({ id: messageId, method, params }));
  return new Promise((resolve, reject) => pending.set(messageId, { resolve, reject }));
}

async function evaluate(expression) {
  const result = await call("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text);
  }
  return result.result.value;
}

let passed = false;
try {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const ready = await evaluate("Boolean(window.__SIA_P0_CHECK__?.().ready)");
    if (ready) break;
    await sleep(250);
  }

  const initial = await evaluate("window.__SIA_P0_CHECK__()");
  await evaluate(`(() => {
    const mood = document.querySelector('#mood');
    mood.value = 'shy';
    mood.dispatchEvent(new Event('change'));
    const talk = document.querySelector('#talk');
    talk.value = '0.8';
    talk.dispatchEvent(new Event('input'));
    return true;
  })()`);
  await sleep(180);
  const animated = await evaluate("window.__SIA_P0_CHECK__()");

  await evaluate(`(() => {
    const blink = document.querySelector('#blink');
    blink.value = '0';
    blink.dispatchEvent(new Event('input'));
    return true;
  })()`);
  await sleep(80);
  const closed = await evaluate("window.__SIA_P0_CHECK__()");

  const report = { initial, animated, closed };
  passed =
    initial.ready &&
    initial.openness >= 0.9 &&
    initial.nonBlackSamples > 1000 &&
    animated.mood === "shy" &&
    animated.talk >= 0.7 &&
    closed.openness <= 0.1;

  console.log(JSON.stringify({ passed, report }, null, 2));
} finally {
  socket.close();
  browser.kill();
  await sleep(200);
  browser.kill("SIGKILL");
  process.exit(passed ? 0 : 1);
}
