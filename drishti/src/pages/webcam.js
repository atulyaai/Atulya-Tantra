// The webcam as a sense. Everything below runs in your browser: frames are never sent anywhere
// unless you ask Atulya to look at something ("what do you see?"), and then only one picture.
//
//   presence  you moved in front of the camera in the last few seconds
//   gaze      where you are in the frame, -1..1 (x: right, y: down), so the hologram can look at you
//   snapshot  one JPEG (base64) for the vision brain

const W = 80;
const H = 60;
const STEP_MS = 160;

// Plain-language reason a camera could not start (the browser's error names are not helpful).
export function explainCameraError(err) {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    return 'The browser only allows the camera on http://localhost or https. Open Atulya at http://localhost:8501 on this PC. From a phone or another computer, set ATULYA_HTTPS=on in .env, restart, and open the https:// address (accept the one-time certificate warning).';
  }
  switch (err?.name) {
    case 'NotAllowedError': return 'Camera is blocked. Click the camera icon in the address bar and choose Allow, then try again. On Windows also check Settings > Privacy > Camera.';
    case 'NotFoundError': return 'No camera was found on this computer.';
    case 'NotReadableError': return 'The camera is busy. Close other apps or tabs using it (Teams, Zoom, Camera app) and try again.';
    case 'OverconstrainedError': return 'This camera does not support the requested size.';
    default: return `Could not start the camera (${err?.name || 'unknown error'}).`;
  }
}

// What the browser says about cameras without asking: how many, and whether permission is already decided.
export async function detectCameras() {
  if (!navigator.mediaDevices?.enumerateDevices) return { state: 'unsupported', devices: [] };
  let devices = [];
  try {
    devices = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'videoinput');
  } catch { /* treated as none */ }
  let state = 'prompt';
  try { state = (await navigator.permissions.query({ name: 'camera' })).state; } catch { /* Safari/Firefox: unknown, so we just ask */ }
  if (!devices.length) state = 'none'; // no hardware: permission is beside the point
  return { state, devices: devices.map((d, i) => ({ id: d.deviceId, label: d.label || `Camera ${i + 1}` })) };
}

export function createWebcam({ onPresence, onGaze, onLight } = {}) {
  let stream = null;
  let video = null;
  let timer = 0;
  let prev = null;
  let lastMotion = 0;
  let present = false;
  const small = document.createElement('canvas');
  small.width = W;
  small.height = H;
  const ctx = small.getContext('2d', { willReadFrequently: true });
  let gx = 0;
  let gy = 0;
  let light = 0.5;

  function step() {
    if (!video || video.readyState < 2) return;
    ctx.drawImage(video, 0, 0, W, H);
    const data = ctx.getImageData(0, 0, W, H).data;
    const grey = new Uint8Array(W * H);
    for (let i = 0; i < grey.length; i += 1) grey[i] = (data[i * 4] * 3 + data[i * 4 + 1] * 6 + data[i * 4 + 2]) / 10;
    if (prev) {
      let n = 0;
      let sx = 0;
      let sy = 0;
      for (let i = 0; i < grey.length; i += 1) {
        if (Math.abs(grey[i] - prev[i]) > 24) { n += 1; sx += i % W; sy += Math.floor(i / W); }
      }
      const now = performance.now();
      if (n > W * H * 0.012) { // enough of the picture changed to be a person, not sensor noise
        lastMotion = now;
        // The picture is mirrored for the user, so flip x.
        const tx = -((sx / n / W) * 2 - 1);
        const ty = (sy / n / H) * 2 - 1;
        gx += (tx - gx) * 0.35;
        gy += (ty - gy) * 0.35;
        onGaze?.(gx, gy);
      }
      const nowPresent = now - lastMotion < 12000;
      if (nowPresent !== present) { present = nowPresent; onPresence?.(present); if (!present) onGaze?.(0, 0); }
    }
    // How bright the room is (0 dark .. 1 bright), smoothed so a passing hand does not flicker it.
    let sum = 0;
    for (let i = 0; i < grey.length; i += 1) sum += grey[i];
    light += (sum / grey.length / 255 - light) * 0.1;
    onLight?.(light);
    prev = grey;
  }

  return {
    get active() { return Boolean(stream); },
    // The element to show as a small preview so you can always see that the camera is on.
    get video() { return video; },
    async start(deviceId) {
      if (stream) return video;
      try {
        const base = deviceId ? { deviceId: { exact: deviceId } } : { facingMode: 'user' };
        stream = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240, ...base }, audio: false });
      } catch (err) {
        if (err?.name !== 'OverconstrainedError' && err?.name !== 'NotFoundError') throw err;
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false }); // any camera, any size
      }
      video = document.createElement('video');
      video.srcObject = stream;
      video.muted = true;
      video.playsInline = true;
      await video.play();
      timer = setInterval(step, STEP_MS);
      return video;
    },
    stop() {
      clearInterval(timer);
      stream?.getTracks().forEach((t) => t.stop());
      stream = null;
      video = null;
      prev = null;
      if (present) { present = false; onPresence?.(false); }
      onGaze?.(0, 0);
    },
    // One picture for Atulya's vision, as a data URL.
    snapshot() {
      if (!video) return null;
      const c = document.createElement('canvas');
      c.width = video.videoWidth || 320;
      c.height = video.videoHeight || 240;
      c.getContext('2d').drawImage(video, 0, 0, c.width, c.height);
      return c.toDataURL('image/jpeg', 0.8);
    },
  };
}
