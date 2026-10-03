// A 3D person whose lips move with Atulya's voice (TalkingHead + three.js).
// Loaded lazily by Orb.jsx; if the avatar file or WebGL is missing, the orb
// is shown instead.
import { TalkingHead } from '@met4citizen/talkinghead';
import { LipsyncEn } from '@met4citizen/talkinghead/modules/lipsync-en.mjs';

// Fitting tweaks for the two bundled avatars (from TalkingHead's site config).
const AVATARS = {
  female: {
    url: '/avatars/female.glb',
    body: 'F',
    avatarMood: 'happy',
    retarget: {
      Hips: { y: 0.03 }, Spine: { y: 0.02 }, Spine1: { y: 0.02, z: 0.01 },
      Spine2: { y: 0.02, z: 0.01 }, Neck: { z: 0.02, y: 0.01 }, Head: { z: 0.02 },
      LeftShoulder: { rx: -0.5 }, RightShoulder: { rx: -0.5 },
      scaleToHipsLevel: 1.0,
    },
    baseline: { headRotateX: -0.05, eyeBlinkLeft: 0.15, eyeBlinkRight: 0.15 },
  },
  male: {
    url: '/avatars/male.glb',
    body: 'M',
    avatarMood: 'neutral',
    retarget: {
      Neck: { z: -0.01, rx: -0.15 }, Neck1: { z: -0.01, rx: -0.15 }, Neck2: { z: -0.01, rx: -0.15 },
      LeftShoulder: { rz: -0.3 }, RightShoulder: { rz: 0.3 },
      scaleToEyesLevel: 1.0, origin: { y: -0.1 },
    },
    baseline: { headRotateX: -0.04, eyeBlinkLeft: 0.05, eyeBlinkRight: 0.05 },
  },
};

const DEVANAGARI = /[ऀ-ॿ]/;

function base64ToArrayBuffer(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

// Without word timings (Hindi, or no edge-tts), open the mouth with the loudness.
function loudnessAnim(buffer) {
  const data = buffer.getChannelData(0);
  const frameMs = 40;
  const step = Math.floor((buffer.sampleRate * frameMs) / 1000);
  const dt = [];
  const jaw = [];
  const aa = [];
  for (let i = 0; i < data.length; i += step) {
    let sum = 0;
    const end = Math.min(data.length, i + step);
    for (let j = i; j < end; j += 1) sum += data[j] * data[j];
    const level = Math.min(1, Math.sqrt(sum / Math.max(1, end - i)) * 6);
    dt.push(frameMs);
    jaw.push(level * 0.35);
    aa.push(level * 0.8);
  }
  return { name: 'loudness', dt, vs: { jawOpen: jaw, viseme_aa: aa } };
}

export async function createPerson(container, gender, onProgress) {
  const head = new TalkingHead(container, {
    lipsyncModules: [], // loaded below: the library's own dynamic import doesn't survive bundling
    lipsyncLang: 'en',
    cameraView: 'upper',
    cameraRotateEnable: false,
    cameraPanEnable: false,
    cameraZoomEnable: false,
    avatarIdleEyeContact: 0.6,
    avatarSpeakingEyeContact: 0.8,
    avatarListeningEyeContact: 0.9,
    lightAmbientIntensity: 2,
    lightDirectIntensity: 30,
  });
  head.lipsync.en = new LipsyncEn();

  async function show(which) {
    await head.showAvatar({ ...AVATARS[which], lipsyncLang: 'en' }, onProgress);
  }
  await show(gender);
  let finishSpeech = null; // resolves the current speak() if it's interrupted

  return {
    show,
    resume() { head.audioCtx?.resume?.().catch(() => {}); },
    // Resolves when the person has finished saying it.
    async speak(audioBase64, words, text) {
      const buffer = await head.audioCtx.decodeAudioData(base64ToArrayBuffer(audioBase64));
      const timed = Array.isArray(words) && words.length && !DEVANAGARI.test(text || '');
      const audio = timed
        ? {
          audio: buffer,
          words: words.map((w) => w.text),
          wtimes: words.map((w) => w.start_ms),
          wdurations: words.map((w) => w.duration_ms),
        }
        : { audio: buffer, anim: loudnessAnim(buffer) };
      head.audioCtx.resume().catch(() => {});
      await new Promise((resolve) => {
        finishSpeech = resolve;
        head.speakAudio(audio, { lipsyncLang: 'en' });
        head.speakMarker(resolve);
      });
      finishSpeech = null;
    },
    stop() {
      head.stopSpeaking();
      finishSpeech?.(); // stopSpeaking drops the queued end marker
    },
    listening() { head.makeEyeContact(4000); },
    thinking() { head.lookAhead?.(1500); },
    dispose() {
      try { head.stop(); } catch {}
      container.replaceChildren();
    },
  };
}
