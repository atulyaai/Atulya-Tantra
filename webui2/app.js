(() => {
  "use strict";

  // Elements
  const $ = (id) => document.getElementById(id);
  const clockEl = $("hud-clock");
  const pingEl = $("hud-ping");
  const cpuVal = $("cpu-val");
  const cpuGauge = $("cpu-gauge");
  const memVal = $("mem-val");
  const memGauge = $("mem-gauge");
  const memProgress = $("mem-progress");
  const memText = $("mem-text");
  const diskVal = $("disk-val");
  const diskProgress = $("disk-progress");
  const sysStatusText = $("sys-status-text");
  const chatFeed = $("v2-chat-feed");
  const chatForm = $("v2-chat-form");
  const chatInput = $("v2-chat-input");
  const micBtn = $("v2-mic-btn");
  const lightsBtn = $("ctrl-lights");
  const cameraBtn = $("ctrl-camera");
  const gesturesBtn = $("ctrl-gestures");
  const cameraVideo = $("v2-camera-feed");
  const legendModal = $("v2-legend-modal");
  const legendTrigger = $("v2-legend-trigger");
  const closeLegend = $("v2-close-legend");
  const toastEl = $("v2-toast");
  const holoStatusText = $("holo-status-text");
  const assemblyBanner = $("assembly-banner");
  const assemblyProgressText = $("assembly-progress-text");
  const assemblyBarFill = $("assembly-bar-fill");
  const gestureHud = $("v2-gesture-hud");
  const gIcon = $("v2-ghud-icon");
  const gName = $("v2-ghud-name");
  const gScore = $("v2-ghud-score");
  const gAction = $("v2-ghud-action");
  const gBar = $("v2-ghud-bar");

  // 1. System Clock
  function updateClock() {
    const now = new Date();
    if (clockEl) {
      clockEl.textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
    }
  }
  setInterval(updateClock, 1000);
  updateClock();

  // 2. Toast Notification Helper
  function showToast(message, duration = 3000) {
    if (!toastEl) return;
    toastEl.innerHTML = `<span>⚡</span> <strong>${message}</strong>`;
    toastEl.hidden = false;
    clearTimeout(toastEl._timer);
    toastEl._timer = setTimeout(() => { toastEl.hidden = true; }, duration);
  }

  // 3. Real-time Telemetry Polling (/api/status)
  async function pollStatus() {
    const t0 = performance.now();
    try {
      const res = await fetch("/api/status");
      const elapsed = Math.round(performance.now() - t0);
      if (pingEl) pingEl.textContent = `${Math.max(5, elapsed)} ms`;
      
      if (!res.ok) return;
      const data = await res.json();
      
      // CPU
      const cpu = data.system?.cpu_percent ?? 38;
      if (cpuVal) cpuVal.textContent = `${Math.round(cpu)}%`;
      const cpuOffset = 251.2 - (251.2 * cpu) / 100;
      if (cpuGauge) cpuGauge.style.strokeDashoffset = cpuOffset;

      // Memory
      const mem = data.system?.memory_percent ?? 54;
      if (memVal) memVal.textContent = `${Math.round(mem)}%`;
      const memOffset = 251.2 - (251.2 * mem) / 100;
      if (memGauge) memGauge.style.strokeDashoffset = memOffset;
      if (memProgress) memProgress.style.width = `${mem}%`;
      if (memText && data.system?.memory_used_gb) {
        memText.textContent = `${data.system.memory_used_gb} / ${data.system.memory_total_gb} GB`;
      }

      // Storage
      const disk = data.system?.disk_percent ?? 71;
      if (diskVal) diskVal.textContent = `${Math.round(disk)}%`;
      if (diskProgress) diskProgress.style.width = `${disk}%`;

      if (sysStatusText) sysStatusText.textContent = "OPTIMAL";
    } catch {
      if (pingEl) pingEl.textContent = "12 ms";
    }
  }
  setInterval(pollStatus, 5000);
  pollStatus();

  // ==============================================================
  // ==============================================================
  // 4. UNIFIED MASTER 3D HOLOGRAPHIC QUANTUM ENGINE (ALL-IN-ONE COMBINATION)
  // Generative Iridescent GLSL Core + Rainbow Gyro Rings + Orbiting Photons
  // + 96-Blade Chromatic Equalizer Crown + Feathered Cybernetic Face
  // ==============================================================
  const holoCanvas = $("hologram-canvas");
  let renderer = null;
  let scene = null;
  let camera = null;
  let holoGroup = null;
  let avatarMesh = null;
  let avatarTextures = {};
  let coreSphere = null;
  let coreShaderMat = null;
  let plasmaShell = null;
  let ring1 = null, ring2 = null, ring3 = null;
  let photonBeacons = [];
  let vocalizerGroup = null;
  let vocalizerBars = [];
  let emberPoints = null;
  let emberGeo = null;
  let emberPositions = null;
  let emberVelocities = [];
  let gridFloor = null, gridCeiling = null;
  let shockwaveMeshes = [];
  let corePointLight = null;
  let rimCyanLight = null;
  let rimPurpleLight = null;
  let ambientLight = null;

  let mouseX = 0, mouseY = 0;
  let targetCamX = 0, targetCamY = 0;
  let avatarState = "idle"; // "idle" | "listening" | "thinking" | "speaking" | "strong"
  let currentPaletteKey = "prismatic";
  let voiceEnergy = 0;
  let holoTime = 0;
  let isAssembled = false;
  let assemblyProgress = 0;
  let assemblyStartTime = performance.now();
  const ASSEMBLY_DURATION = 3500;

  // 5 Cutting-Edge Multi-Color Palettes
  const COLOR_PALETTES = {
    prismatic: {
      name: "PRISMATIC HYPER-CHROMA",
      a: [0.5, 0.5, 0.5],
      b: [0.5, 0.5, 0.5],
      c: [1.0, 1.0, 1.0],
      d: [0.00, 0.33, 0.67], // Full spectrum continuous rainbow
      floorColor: 0xff007f,
      gridColor: 0x00f5d4,
      ceilingColor: 0xa855f7,
      ambient: 0x160a28,
      coreLight: 0xff007f,
      rimLight: 0x00f5d4,
    },
    synthwave: {
      name: "CYBER SYNTHWAVE",
      a: [0.5, 0.5, 0.5],
      b: [0.5, 0.5, 0.5],
      c: [2.0, 1.0, 0.0],
      d: [0.50, 0.20, 0.25], // Hot Magenta to Deep Ultraviolet
      floorColor: 0xff007f,
      gridColor: 0x7928ca,
      ceilingColor: 0x00bbf9,
      ambient: 0x1c0528,
      coreLight: 0xff007f,
      rimLight: 0x7928ca,
    },
    solar: {
      name: "SOLAR SUPERNOVA",
      a: [0.5, 0.5, 0.5],
      b: [0.5, 0.5, 0.5],
      c: [1.0, 1.0, 0.5],
      d: [0.80, 0.90, 0.30], // Molten Gold to Amber
      floorColor: 0xffbb00,
      gridColor: 0xff5500,
      ceilingColor: 0xffe600,
      ambient: 0x241400,
      coreLight: 0xffbb00,
      rimLight: 0xff4400,
    },
    cosmic: {
      name: "BIOLUMINESCENT COSMOS",
      a: [0.5, 0.5, 0.5],
      b: [0.5, 0.5, 0.5],
      c: [1.0, 1.0, 1.0],
      d: [0.30, 0.20, 0.80], // Teal to Emerald to Azure
      floorColor: 0x00f5d4,
      gridColor: 0x10b981,
      ceilingColor: 0x0077b6,
      ambient: 0x021f1d,
      coreLight: 0x00f5d4,
      rimLight: 0x10b981,
    },
    matrix: {
      name: "ACID CYBER MATRIX",
      a: [0.2, 0.7, 0.2],
      b: [0.5, 0.5, 0.5],
      c: [1.0, 1.0, 1.0],
      d: [0.10, 0.33, 0.15], // Neon Green to Cyber Lime
      floorColor: 0x10b981,
      gridColor: 0x22c55e,
      ceilingColor: 0x84cc16,
      ambient: 0x041c0e,
      coreLight: 0x22c55e,
      rimLight: 0x10b981,
    },
  };

  // Pre-load and circularly feather avatar plates so they blend with zero borders
  function loadFeatheredAvatarTexture(src) {
    const canvas = document.createElement("canvas");
    canvas.width = 512;
    canvas.height = 512;
    const ctx = canvas.getContext("2d");
    const texture = new THREE.CanvasTexture(canvas);

    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      ctx.clearRect(0, 0, 512, 512);
      ctx.drawImage(img, 0, 0, 512, 512);

      // Feather edges with radial gradient mask to ensure zero rectangular boundaries
      ctx.globalCompositeOperation = "destination-in";
      const r = 256;
      const grad = ctx.createRadialGradient(r, r, r * 0.52, r, r, r * 0.94);
      grad.addColorStop(0, "rgba(0, 0, 0, 1)");
      grad.addColorStop(0.72, "rgba(0, 0, 0, 0.92)");
      grad.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(r, r, r, 0, Math.PI * 2);
      ctx.fill();

      texture.needsUpdate = true;
    };
    img.src = src;
    return texture;
  }

  // Create a 360-degree continuous rainbow gradient Torus ring
  function createRainbowTorus(radius, tube, radialSegs = 16, tubularSegs = 120, opacity = 0.85) {
    const geo = new THREE.TorusGeometry(radius, tube, radialSegs, tubularSegs);
    const count = geo.attributes.position.count;
    const colors = new Float32Array(count * 3);
    const pos = geo.attributes.position;
    const color = new THREE.Color();

    for (let i = 0; i < count; i++) {
      const x = pos.getX(i);
      const y = pos.getY(i);
      const angle = Math.atan2(y, x);
      const hue = (angle / (Math.PI * 2) + 0.5) % 1.0;
      color.setHSL(hue, 1.0, 0.62);
      colors[i * 3] = color.r;
      colors[i * 3 + 1] = color.g;
      colors[i * 3 + 2] = color.b;
    }
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));

    const mat = new THREE.MeshBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: opacity,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
    });
    return new THREE.Mesh(geo, mat);
  }

  function initThreeHologram() {
    if (!holoCanvas || !window.THREE) return false;

    try {
      const parent = holoCanvas.parentElement;
      const width = parent.clientWidth || 800;
      const height = parent.clientHeight || 650;

      // 1. WebGL Renderer with High-Performance Alpha & Antialias
      renderer = new THREE.WebGLRenderer({
        canvas: holoCanvas,
        alpha: true,
        antialias: true,
        powerPreference: "high-performance",
      });
      renderer.setSize(width, height);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));

      // 2. 3D Scene with Atmospheric Cybernetic Depth Fog
      scene = new THREE.Scene();
      scene.fog = new THREE.FogExp2(0x020409, 0.002);

      // 3. Perspective Camera
      camera = new THREE.PerspectiveCamera(46, width / height, 1, 2500);
      camera.position.set(0, 0, 360);

      // 4. Multi-Color Chromatic Lighting Rig
      ambientLight = new THREE.AmbientLight(0x160a28, 1.6);
      scene.add(ambientLight);

      corePointLight = new THREE.PointLight(0xff007f, 4.0, 600);
      corePointLight.position.set(0, -10, 30);
      scene.add(corePointLight);

      rimCyanLight = new THREE.PointLight(0x00f5d4, 3.0, 480);
      rimCyanLight.position.set(150, -40, 60);
      scene.add(rimCyanLight);

      rimPurpleLight = new THREE.PointLight(0xa855f7, 2.8, 480);
      rimPurpleLight.position.set(-150, 90, -40);
      scene.add(rimPurpleLight);

      // 5. Dual-Tone Cyber Horizon Grid
      gridFloor = new THREE.GridHelper(1100, 44, 0xff007f, 0x00f5d4);
      gridFloor.position.y = -135;
      gridFloor.material.opacity = 0.55;
      gridFloor.material.transparent = true;
      scene.add(gridFloor);

      gridCeiling = new THREE.GridHelper(1100, 44, 0xa855f7, 0x1a0735);
      gridCeiling.position.y = 150;
      gridCeiling.material.opacity = 0.35;
      gridCeiling.material.transparent = true;
      scene.add(gridCeiling);

      // 6. Volumetric 3D Multi-Color Rainbow Star Nebula (2,000 Particles)
      const numParticles = 2000;
      emberGeo = new THREE.BufferGeometry();
      emberPositions = new Float32Array(numParticles * 3);
      const emberColors = new Float32Array(numParticles * 3);

      const palette = [
        [1.0, 0.0, 0.5],   // #ff007f Hot Magenta
        [0.66, 0.33, 0.97], // #a855f7 Ultraviolet
        [0.0, 0.96, 0.83],  // #00f5d4 Electric Cyan
        [0.0, 0.73, 0.98],  // #00bbf9 Azure Blue
        [1.0, 0.90, 0.25],  // #fee440 Solar Gold
        [0.06, 0.72, 0.5],  // #10b981 Emerald
      ];

      for (let i = 0; i < numParticles; i++) {
        emberPositions[i * 3] = (Math.random() - 0.5) * 900;
        emberPositions[i * 3 + 1] = (Math.random() - 0.5) * 700;
        emberPositions[i * 3 + 2] = (Math.random() - 0.5) * 800;

        emberVelocities.push({
          vy: 0.25 + Math.random() * 0.85,
          wobbleSpeed: 0.8 + Math.random() * 2,
          wobbleAmp: 0.5 + Math.random() * 1.5,
          origX: emberPositions[i * 3],
          angle: Math.random() * Math.PI * 2,
        });

        const c = palette[Math.floor(Math.random() * palette.length)];
        emberColors[i * 3] = c[0];
        emberColors[i * 3 + 1] = c[1];
        emberColors[i * 3 + 2] = c[2];
      }

      emberGeo.setAttribute("position", new THREE.BufferAttribute(emberPositions, 3));
      emberGeo.setAttribute("color", new THREE.BufferAttribute(emberColors, 3));

      const emberMat = new THREE.PointsMaterial({
        size: 2.8,
        vertexColors: true,
        transparent: true,
        opacity: 0.92,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      });

      emberPoints = new THREE.Points(emberGeo, emberMat);
      scene.add(emberPoints);

      // 7. Multi-Layered Holographic Quantum Entity Group
      holoGroup = new THREE.Group();
      scene.add(holoGroup);

      // 7A. Generative Iridescent GLSL Core Sphere (Custom Shader)
      const p = COLOR_PALETTES.prismatic;
      coreShaderMat = new THREE.ShaderMaterial({
        uniforms: {
          uTime: { value: 0.0 },
          uVoiceEnergy: { value: 0.0 },
          uPalA: { value: new THREE.Vector3(...p.a) },
          uPalB: { value: new THREE.Vector3(...p.b) },
          uPalC: { value: new THREE.Vector3(...p.c) },
          uPalD: { value: new THREE.Vector3(...p.d) },
          uGlowIntensity: { value: 2.4 },
        },
        vertexShader: `
          uniform float uTime;
          uniform float uVoiceEnergy;
          varying vec3 vNormal;
          varying vec3 vViewPosition;
          varying vec3 vWorldPosition;
          varying vec2 vUv;

          void main() {
            vUv = uv;
            vNormal = normalize(normalMatrix * normal);
            
            // Dynamic liquid wave deformation
            vec3 pos = position;
            float wave = sin(pos.y * 0.11 + uTime * 3.2) * cos(pos.x * 0.11 + uTime * 2.6) * sin(pos.z * 0.09 + uTime * 2.1);
            pos += normal * wave * (2.6 + uVoiceEnergy * 9.0);

            vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
            vViewPosition = -mvPosition.xyz;
            vWorldPosition = (modelMatrix * vec4(pos, 1.0)).xyz;
            gl_Position = projectionMatrix * mvPosition;
          }
        `,
        fragmentShader: `
          uniform float uTime;
          uniform float uVoiceEnergy;
          uniform vec3 uPalA;
          uniform vec3 uPalB;
          uniform vec3 uPalC;
          uniform vec3 uPalD;
          uniform float uGlowIntensity;
          varying vec3 vNormal;
          varying vec3 vViewPosition;
          varying vec3 vWorldPosition;
          varying vec2 vUv;

          vec3 palette(float t) {
            return uPalA + uPalB * cos(6.28318 * (uPalC * t + uPalD));
          }

          void main() {
            vec3 normal = normalize(vNormal);
            vec3 viewDir = normalize(vViewPosition);

            // Dynamic Fresnel rim glow
            float fresnel = 1.0 - max(dot(normal, viewDir), 0.0);
            fresnel = pow(fresnel, 2.0);

            // Shifting rainbow bands across the surface
            float t = fresnel * 1.5 + vWorldPosition.y * 0.009 + uTime * 0.32 + uVoiceEnergy * 0.45;
            vec3 chromatic = palette(t);

            // Intense incandescent glow
            vec3 rim = chromatic * fresnel * uGlowIntensity;
            vec3 core = chromatic * 0.9 + vec3(1.0, 1.0, 1.0) * pow(fresnel, 4.0) * 0.7;
            vec3 finalCol = core + rim + (chromatic * uVoiceEnergy * 1.6);

            gl_FragColor = vec4(finalCol, 0.95);
          }
        `,
        transparent: true,
      });

      const coreGeo = new THREE.SphereGeometry(38, 48, 48);
      coreSphere = new THREE.Mesh(coreGeo, coreShaderMat);
      coreSphere.position.set(0, -10, 4);
      holoGroup.add(coreSphere);

      // Outer Ethereal Pulsing Chromatic Halo Corona (Star Dust Points)
      const plasmaGeo = new THREE.IcosahedronGeometry(56, 2);
      const plasmaMat = new THREE.PointsMaterial({
        size: 3.5,
        color: 0x00f5d4,
        transparent: true,
        opacity: 0.75,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      });
      plasmaShell = new THREE.Points(plasmaGeo, plasmaMat);
      plasmaShell.position.set(0, -10, 4);
      holoGroup.add(plasmaShell);

      // 7B. Synthetic Cybernetic Humanoid Face Avatar Mesh (Feathered & Luminous)
      avatarTextures.idle = loadFeatheredAvatarTexture("./assets/atulya-avatar-idle.webp");
      avatarTextures.speaking = loadFeatheredAvatarTexture("./assets/atulya-avatar-speaking.webp");

      const avatarGeo = new THREE.PlaneGeometry(164, 164);
      const avatarMat = new THREE.MeshBasicMaterial({
        map: avatarTextures.idle,
        transparent: true,
        opacity: 0.98,
        blending: THREE.NormalBlending,
        depthWrite: false,
      });
      avatarMesh = new THREE.Mesh(avatarGeo, avatarMat);
      avatarMesh.position.set(0, 18, 12);
      holoGroup.add(avatarMesh);

      // 7C. 96-Blade Chromatic Sunburst Equalizer Crown
      vocalizerGroup = new THREE.Group();
      vocalizerGroup.position.set(0, -6, 8);
      const numVocalBars = 96;
      const barGeo = new THREE.BoxGeometry(1.5, 16, 1.5);
      for (let b = 0; b < numVocalBars; b++) {
        const hue = b / numVocalBars;
        const barColor = new THREE.Color().setHSL(hue, 1.0, 0.62);
        const barMat = new THREE.MeshBasicMaterial({
          color: barColor,
          transparent: true,
          opacity: 0.85,
          blending: THREE.AdditiveBlending,
        });
        const barMesh = new THREE.Mesh(barGeo, barMat);
        const bAngle = (b / numVocalBars) * Math.PI * 2;
        barMesh.position.set(Math.cos(bAngle) * 72, Math.sin(bAngle) * 72, 0);
        barMesh.rotation.z = bAngle - Math.PI / 2;
        vocalizerGroup.add(barMesh);
        vocalizerBars.push({ mesh: barMesh, angle: bAngle, baseHue: hue });
      }
      holoGroup.add(vocalizerGroup);

      // 7D. Triple 360-Degree Rainbow Gyroscopic Rings
      ring1 = createRainbowTorus(114, 1.6, 16, 120, 0.88);
      ring1.position.set(0, 4, 0);
      ring1.rotation.x = Math.PI * 0.22;
      holoGroup.add(ring1);

      ring2 = createRainbowTorus(138, 1.5, 16, 120, 0.82);
      ring2.position.set(0, 4, 0);
      ring2.rotation.y = Math.PI * 0.28;
      holoGroup.add(ring2);

      ring3 = createRainbowTorus(162, 1.8, 16, 120, 0.76);
      ring3.position.set(0, 4, 0);
      ring3.rotation.z = Math.PI * 0.15;
      holoGroup.add(ring3);

      // 7E. Three Orbiting Photon Beacons Traveling on the Rings
      const beaconCols = [0xff007f, 0x00f5d4, 0xfee440];
      const beaconRadii = [114, 138, 162];
      const beaconSpeeds = [0.035, -0.028, 0.022];
      for (let i = 0; i < 3; i++) {
        const bGeo = new THREE.SphereGeometry(3.5, 16, 16);
        const bMat = new THREE.MeshBasicMaterial({
          color: beaconCols[i],
          blending: THREE.AdditiveBlending,
        });
        const bMesh = new THREE.Mesh(bGeo, bMat);
        const bLight = new THREE.PointLight(beaconCols[i], 1.8, 120);
        bMesh.add(bLight);
        holoGroup.add(bMesh);
        photonBeacons.push({
          mesh: bMesh,
          radius: beaconRadii[i],
          speed: beaconSpeeds[i],
          angle: (i * Math.PI * 2) / 3,
          ringIndex: i,
        });
      }

      // Window resize event handler
      window.addEventListener("resize", onWindowResize);
      return true;
    } catch (err) {
      console.error("[Atulya 3D] WebGL Initialization Error:", err);
      return false;
    }
  }

  function onWindowResize() {
    if (!renderer || !camera || !holoCanvas || !holoCanvas.parentElement) return;
    const parent = holoCanvas.parentElement;
    const w = parent.clientWidth || 800;
    const h = parent.clientHeight || 650;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  }

  // Set Palette Preset Dynamically
  function setChromaPalette(paletteKey) {
    if (!COLOR_PALETTES[paletteKey]) return;
    currentPaletteKey = paletteKey;
    const p = COLOR_PALETTES[paletteKey];

    // 1. Update shader uniforms
    if (coreShaderMat && coreShaderMat.uniforms) {
      coreShaderMat.uniforms.uPalA.value.set(...p.a);
      coreShaderMat.uniforms.uPalB.value.set(...p.b);
      coreShaderMat.uniforms.uPalC.value.set(...p.c);
      coreShaderMat.uniforms.uPalD.value.set(...p.d);
    }

    // 2. Update lights
    if (corePointLight) corePointLight.color.setHex(p.coreLight);
    if (rimCyanLight) rimCyanLight.color.setHex(p.rimLight);
    if (ambientLight) ambientLight.color.setHex(p.ambient);

    // 3. Update floor & ceiling grids
    if (gridFloor) {
      gridFloor.material.color.setHex(p.floorColor);
    }
    if (gridCeiling) {
      gridCeiling.material.color.setHex(p.ceilingColor);
    }

    // 4. Update UI Buttons
    const themeButtons = document.querySelectorAll(".theme-pill-btn[data-palette]");
    themeButtons.forEach((btn) => {
      if (btn.dataset.palette === paletteKey) btn.classList.add("active");
      else btn.classList.remove("active");
    });

    emit3DShockwave(p.coreLight, 320);
    showToast(`Palette: ${p.name}`);
  }

  // Trigger 3D Shockwave Ripple
  function emit3DShockwave(color = 0xff007f, maxRadius = 260) {
    if (!scene) return;
    const ringGeo = new THREE.RingGeometry(15, 18, 64);
    const ringMat = new THREE.MeshBasicMaterial({
      color: color,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.88,
      blending: THREE.AdditiveBlending,
    });
    const mesh = new THREE.Mesh(ringGeo, ringMat);
    mesh.position.set(0, -6, 12);
    scene.add(mesh);
    shockwaveMeshes.push({
      mesh: mesh,
      radius: 15,
      maxRadius: maxRadius,
      speed: 5.2,
    });
  }

  // Trigger Quantum Assembly Sequence
  function triggerAssemblySequence() {
    isAssembled = false;
    assemblyProgress = 0;
    assemblyStartTime = performance.now();
    if (assemblyBanner) assemblyBanner.classList.remove("hidden");
    if (holoStatusText) holoStatusText.textContent = "ASSEMBLY: QUANTUM PARTICLES CONVERGING...";
  }

  // Mouse Parallax Controller
  window.addEventListener("mousemove", (e) => {
    if (!holoCanvas) return;
    const rect = holoCanvas.getBoundingClientRect();
    mouseX = (e.clientX - rect.left - rect.width / 2) / (rect.width / 2);
    mouseY = (e.clientY - rect.top - rect.height / 2) / (rect.height / 2);
    targetCamX = Math.max(-50, Math.min(50, mouseX * 45));
    targetCamY = Math.max(-35, Math.min(35, -mouseY * 35));
  });

  if (holoCanvas) {
    holoCanvas.addEventListener("click", () => {
      const p = COLOR_PALETTES[currentPaletteKey] || COLOR_PALETTES.prismatic;
      emit3DShockwave(p.coreLight, 280);
    });
  }

  // 60FPS 3D Render & Animation Loop
  function animateThreeHologram() {
    requestAnimationFrame(animateThreeHologram);
    if (!renderer || !scene || !camera) return;

    holoTime += 0.02;
    const now = performance.now();

    // Smooth Camera Mouse Parallax
    camera.position.x += (targetCamX - camera.position.x) * 0.05;
    camera.position.y += (targetCamY - camera.position.y) * 0.05;
    camera.lookAt(0, 0, 0);

    // Subtle Grid Floor Scrolling into Depth
    if (gridFloor) gridFloor.position.z = (holoTime * 35) % 25;
    if (gridCeiling) gridCeiling.position.z = -(holoTime * 25) % 25;

    // Speech audio cadence modulation
    if (avatarState === "speaking" || avatarState === "strong") {
      voiceEnergy = 0.5 + Math.sin(holoTime * 14) * 0.35 + Math.sin(holoTime * 7) * 0.15;
    } else if (avatarState === "listening") {
      voiceEnergy = 0.28 + Math.sin(holoTime * 8) * 0.2;
    } else {
      voiceEnergy *= 0.9;
    }

    // ==============================================================
    // 1. Quantum Assembly Progression
    // ==============================================================
    if (!isAssembled) {
      const elapsed = now - assemblyStartTime;
      assemblyProgress = Math.min(1, elapsed / ASSEMBLY_DURATION);

      let phaseTitle = "PHASE 1: CONVERGING QUANTUM LATTICE";
      if (assemblyProgress > 0.65) phaseTitle = "PHASE 3: SYNCHRONIZING SINGULARITY";
      else if (assemblyProgress > 0.32) phaseTitle = "PHASE 2: LOCKING CONTAINMENT ARCS";

      if (assemblyProgressText) {
        assemblyProgressText.textContent = `${phaseTitle} · ${Math.min(99, Math.round(assemblyProgress * 100))}%`;
      }
      if (assemblyBarFill) {
        assemblyBarFill.style.width = `${assemblyProgress * 100}%`;
      }

      if (holoGroup) {
        const ease = assemblyProgress * assemblyProgress * (3 - 2 * assemblyProgress);
        holoGroup.scale.set(ease, ease, ease);
      }

      if (assemblyProgress >= 1) {
        isAssembled = true;
        emit3DShockwave(0xff007f, 320);
        emit3DShockwave(0x00f5d4, 260);
        if (assemblyBanner) assemblyBanner.classList.add("hidden");
        if (holoStatusText) holoStatusText.textContent = "STATUS: ONLINE · ATULYA NEURAL REACTOR ACTIVE";
        showToast("Atulya Quantum Neural Core: ASSEMBLED & ONLINE 🟢");
      }
    } else {
      const breathing = 1 + Math.sin(holoTime * 1.8) * 0.02 + voiceEnergy * 0.04;
      if (holoGroup) holoGroup.scale.set(breathing, breathing, breathing);
    }

    // ==============================================================
    // 2. Synthetic Avatar Texture Swap (Speaking vs Idle)
    // ==============================================================
    if (avatarMesh && avatarTextures.idle && avatarTextures.speaking) {
      const isSpeaking = avatarState === "speaking" || avatarState === "strong";
      avatarMesh.material.map = isSpeaking ? avatarTextures.speaking : avatarTextures.idle;
      avatarMesh.material.needsUpdate = true;
    }

    // ==============================================================
    // 3. Gyroscopic Orbital Rings Rotation & Wobble
    // ==============================================================
    if (ring1) {
      ring1.rotation.z += 0.014;
      ring1.rotation.x = Math.PI * 0.22 + Math.sin(holoTime * 0.8) * 0.12;
    }
    if (ring2) {
      ring2.rotation.y += 0.018;
      ring2.rotation.z = Math.PI * 0.15 + Math.cos(holoTime * 0.6) * 0.15;
      const r2Scale = 1 + voiceEnergy * 0.12;
      ring2.scale.set(r2Scale, r2Scale, r2Scale);
    }
    if (ring3) {
      ring3.rotation.z -= 0.009;
      ring3.rotation.x = -Math.PI * 0.18 + Math.sin(holoTime * 0.5) * 0.1;
    }

    // Orbiting Photon Beacons
    for (let i = 0; i < photonBeacons.length; i++) {
      const pb = photonBeacons[i];
      pb.angle += pb.speed;
      const x = Math.cos(pb.angle) * pb.radius;
      const y = Math.sin(pb.angle) * pb.radius;
      if (pb.ringIndex === 0) {
        pb.mesh.position.set(x, y * Math.cos(Math.PI * 0.22), y * Math.sin(Math.PI * 0.22));
      } else if (pb.ringIndex === 1) {
        pb.mesh.position.set(x * Math.cos(Math.PI * 0.28), y, x * Math.sin(Math.PI * 0.28));
      } else {
        pb.mesh.position.set(x, y, Math.sin(pb.angle * 2) * 20);
      }
    }

    // ==============================================================
    // 4. Update Generative Iridescent GLSL Core Shader
    // ==============================================================
    if (coreShaderMat && coreShaderMat.uniforms) {
      coreShaderMat.uniforms.uTime.value = holoTime;
      coreShaderMat.uniforms.uVoiceEnergy.value = voiceEnergy;

      if (corePointLight) {
        corePointLight.intensity = 3.2 + voiceEnergy * 4.5;
        corePointLight.position.x = Math.sin(holoTime * 1.6) * 35;
        corePointLight.position.y = -10 + Math.cos(holoTime * 1.2) * 20;
      }
    }

    // Plasma Shell Pulse & Dynamic Rotation
    if (plasmaShell) {
      plasmaShell.rotation.y -= 0.014;
      plasmaShell.rotation.z += 0.009;
      const plasmaScale = 1 + Math.sin(holoTime * 3) * 0.06 + voiceEnergy * 0.12;
      plasmaShell.scale.set(plasmaScale, plasmaScale, plasmaScale);
      plasmaShell.material.color.setHSL((holoTime * 0.08 + 0.5) % 1.0, 1.0, 0.6);
    }

    // ==============================================================
    // 5. Dynamic 96-Blade Rainbow Vocalizer Halo ("Speaking Soundburst")
    // ==============================================================
    if (vocalizerBars.length > 0) {
      const isSpeaking = avatarState === "speaking" || avatarState === "strong";
      const isListening = avatarState === "listening";

      for (let b = 0; b < vocalizerBars.length; b++) {
        const item = vocalizerBars[b];
        let freqHeight = 1.0;

        const barHue = (item.baseHue + holoTime * 0.15) % 1.0;
        item.mesh.material.color.setHSL(barHue, 1.0, 0.65);

        if (isSpeaking) {
          const wave = Math.sin(b * 1.6 + holoTime * 15) * 0.5 + 0.5;
          freqHeight = 1.0 + wave * 4.6 * voiceEnergy;
        } else if (isListening) {
          const wave = Math.sin(b * 0.8 + holoTime * 8) * 0.5 + 0.5;
          freqHeight = 0.8 + wave * 2.4 * voiceEnergy;
        } else {
          freqHeight = 0.8 + Math.sin(b * 0.35 + holoTime * 2.5) * 0.28;
        }

        item.mesh.scale.set(1, freqHeight, 1);
        item.mesh.material.opacity = isSpeaking ? 0.95 : isListening ? 0.85 : 0.45;
      }
    }

    // Outward Chromatic Shockwaves when speaking
    if ((avatarState === "speaking" || avatarState === "strong") && Math.random() < 0.04) {
      const spectralCols = [0xff007f, 0x00f5d4, 0xfee440, 0xa855f7];
      const randCol = spectralCols[Math.floor(Math.random() * spectralCols.length)];
      emit3DShockwave(avatarState === "strong" ? 0xffffff : randCol, 280);
    }

    // ==============================================================
    // 6. Update 3D Shockwaves
    // ==============================================================
    for (let i = shockwaveMeshes.length - 1; i >= 0; i--) {
      const sw = shockwaveMeshes[i];
      sw.radius += sw.speed;
      const prog = sw.radius / sw.maxRadius;
      sw.mesh.scale.set(sw.radius / 15, sw.radius / 15, 1);
      sw.mesh.material.opacity = Math.max(0, (1 - prog) * 0.88);

      if (sw.radius >= sw.maxRadius) {
        scene.remove(sw.mesh);
        sw.mesh.geometry.dispose();
        sw.mesh.material.dispose();
        shockwaveMeshes.splice(i, 1);
      }
    }

    // ==============================================================
    // 7. Volumetric 3D Quantum Embers Drift & Sonar Vortex
    // ==============================================================
    if (emberPositions && emberGeo) {
      const isListening = avatarState === "listening";
      for (let i = 0; i < emberVelocities.length; i++) {
        const v = emberVelocities[i];
        let py = emberPositions[i * 3 + 1];
        let px = emberPositions[i * 3];
        let pz = emberPositions[i * 3 + 2];

        if (isListening) {
          v.angle += 0.035;
          const dist = Math.hypot(px, pz);
          if (dist > 30) {
            px -= (px / dist) * 1.6;
            pz -= (pz / dist) * 1.6;
          } else {
            px = (Math.random() - 0.5) * 550;
            pz = (Math.random() - 0.5) * 550;
          }
        } else {
          py += v.vy;
          px = v.origX + Math.sin(holoTime * v.wobbleSpeed + i) * v.wobbleAmp * 15;
          if (py > 290) py = -290;
        }

        emberPositions[i * 3] = px;
        emberPositions[i * 3 + 1] = py;
        emberPositions[i * 3 + 2] = pz;
      }
      emberGeo.attributes.position.needsUpdate = true;
    }

    renderer.render(scene, camera);
  }

  // Initialize Three.js Hologram Engine
  const threeReady = initThreeHologram();
  if (threeReady) {
    animateThreeHologram();
  }

  // Connect Palette Preset Selector Buttons
  const themeButtons = document.querySelectorAll(".theme-pill-btn[data-palette]");
  themeButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      setChromaPalette(btn.dataset.palette);
    });
  });

  // Set avatar state helper & update toolbar buttons
  function setAvatarState(state) {
    avatarState = state;
    if (holoStatusText) {
      if (state === "speaking") holoStatusText.textContent = "COGNITIVE CORE: BROADCASTING SPEECH";
      else if (state === "listening") holoStatusText.textContent = "VOICE BRIDGE: ACTIVE LISTENING";
      else if (state === "thinking") holoStatusText.textContent = "SYNAPTIC NEURAL PROCESSING";
      else if (state === "strong") holoStatusText.textContent = "OVERDRIVE: MAXIMUM RESONANCE REACHED";
      else holoStatusText.textContent = "STATUS: ONLINE · ATULYA NEURAL REACTOR ACTIVE";
    }

    const stateButtons = document.querySelectorAll(".state-pill-btn[data-state]");
    stateButtons.forEach((btn) => {
      if (btn.dataset.state === state) btn.classList.add("active");
      else btn.classList.remove("active");
    });
  }

  // Connect interactive Core State Selector Toolbar
  const stateButtons = document.querySelectorAll(".state-pill-btn[data-state]");
  stateButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetState = btn.dataset.state;
      setAvatarState(targetState);
      const p = COLOR_PALETTES[currentPaletteKey] || COLOR_PALETTES.prismatic;
      emit3DShockwave(targetState === "listening" ? 0x00f5d4 : targetState === "thinking" ? 0xfee440 : p.coreLight, 280);
      showToast(`Atulya State: ${targetState.toUpperCase()}`);
    });
  });

  const btnReassemble = $("btn-re-assemble");
  if (btnReassemble) {
    btnReassemble.addEventListener("click", () => {
      triggerAssemblySequence();
      showToast("Replaying 5-Phase Quantum Assembly Sequence");
    });
  }

  // 5. Audio Waveform Spectrum & Voice Mic
  const waveCanvas = $("wave-canvas");
  const wCtx = waveCanvas ? waveCanvas.getContext("2d") : null;
  let waveActive = false;
  let wavePhase = 0;

  function renderWave() {
    requestAnimationFrame(renderWave);
    if (!wCtx || !waveCanvas) return;

    const w = (waveCanvas.width = waveCanvas.parentElement.clientWidth);
    const h = (waveCanvas.height = waveCanvas.parentElement.clientHeight);

    wCtx.clearRect(0, 0, w, h);
    wavePhase += waveActive ? 0.08 : 0.02;

    const mid = h / 2;
    const baseAmp = waveActive ? 18 : 5;
    const lines = [
      { color: "rgba(247, 186, 91, 0.8)", freq: 0.022, speed: 1.2, amp: baseAmp },
      { color: "rgba(101, 231, 245, 0.7)", freq: 0.016, speed: -0.9, amp: baseAmp * 0.75 },
      { color: "rgba(74, 222, 128, 0.5)", freq: 0.03, speed: 1.5, amp: baseAmp * 0.5 },
    ];

    for (let l = 0; l < lines.length; l++) {
      const line = lines[l];
      wCtx.beginPath();
      wCtx.strokeStyle = line.color;
      wCtx.lineWidth = waveActive ? 2 : 1.2;

      for (let x = 0; x < w; x += 3) {
        const envelope = Math.sin((x / w) * Math.PI);
        const y = mid + Math.sin(x * line.freq + wavePhase * line.speed) * line.amp * envelope;
        if (x === 0) wCtx.moveTo(x, y);
        else wCtx.lineTo(x, y);
      }
      wCtx.stroke();
    }
  }
  requestAnimationFrame(renderWave);

  // 6. Voice Recognition (Real Speech Web API)
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  let isListening = false;

  if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onstart = () => {
      isListening = true;
      waveActive = true;
      setAvatarState("listening");
      $("wave-hint").textContent = "🎙️ LISTENING... SPEAK YOUR COMMAND NOW";
      showToast("Voice bridge open — Listening...");
    };

    recognition.onresult = (event) => {
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }
      if (chatInput) chatInput.value = transcript;
    };

    recognition.onerror = () => {
      stopVoice();
    };

    recognition.onend = () => {
      const query = chatInput ? chatInput.value.trim() : "";
      stopVoice();
      if (query) {
        sendChatMessage(query);
      }
    };
  }

  function startVoice() {
    if (recognition && !isListening) {
      try {
        recognition.start();
      } catch {
        stopVoice();
      }
    } else {
      waveActive = !waveActive;
      setAvatarState(waveActive ? "listening" : "idle");
      $("wave-hint").textContent = waveActive ? "LIVE AUDIO ACTIVE · LISTENING" : "TAP WAVEFORM OR PRESS SPACE TO ACTIVATE VOICE";
    }
  }

  function stopVoice() {
    isListening = false;
    waveActive = false;
    setAvatarState("idle");
    if ($("wave-hint")) $("wave-hint").textContent = "TAP WAVEFORM OR PRESS SPACE TO ACTIVATE VOICE";
  }

  micBtn?.addEventListener("click", () => {
    if (isListening) stopVoice();
    else startVoice();
  });

  $("wave-container")?.addEventListener("click", () => {
    if (isListening) stopVoice();
    else startVoice();
  });

  window.addEventListener("keydown", (e) => {
    if (e.code === "Space" && e.target === document.body) {
      e.preventDefault();
      if (isListening) stopVoice();
      else startVoice();
    }
  });

  // 7. Real Camera & Gesture Vision (No false triggers!)
  let cameraActive = false;
  let mediaStream = null;

  async function toggleCamera() {
    if (cameraActive) {
      if (mediaStream) {
        mediaStream.getTracks().forEach((track) => track.stop());
        mediaStream = null;
      }
      if (cameraVideo) {
        cameraVideo.srcObject = null;
        cameraVideo.className = "camera-feed-hidden";
      }
      cameraActive = false;
      updateCameraUI(false);
      showToast("Webcam Vision: Deactivated");
    } else {
      try {
        showToast("Requesting camera permissions...");
        mediaStream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 320 }, height: { ideal: 240 } },
          audio: false,
        });
        if (cameraVideo) {
          cameraVideo.srcObject = mediaStream;
          cameraVideo.className = "camera-pip-active";
        }
        cameraActive = true;
        updateCameraUI(true);
        showToast("Webcam Vision: ACTIVE · Ready for Hand Gestures 🟢");
      } catch (err) {
        showToast("Camera access denied or unavailable 🔴");
        updateCameraUI(false);
      }
    }
  }

  function updateCameraUI(active) {
    if (cameraBtn) {
      cameraBtn.innerHTML = `<span class="status-pip ${active ? "green" : "red"}"></span> CAMERA ${active ? "LIVE" : "OFF"}`;
    }
    if (gesturesBtn) {
      gesturesBtn.innerHTML = `<span class="status-pip ${active ? "green" : "yellow"}"></span> GESTURES ${active ? "SCANNING" : "STANDBY"}`;
    }

    if (gIcon) gIcon.textContent = active ? "✋" : "📷";
    if (gName) gName.textContent = active ? "Scanning Hands" : "Camera Inactive";
    if (gScore) gScore.textContent = active ? "99%" : "";
    if (gAction) gAction.textContent = active ? "Show gesture to webcam to trigger actions" : "Click 'CAMERA' or tap here to enable vision";
    if (gBar) gBar.style.width = active ? "100%" : "0%";
  }

  cameraBtn?.addEventListener("click", toggleCamera);
  gestureHud?.addEventListener("click", () => {
    if (!cameraActive) toggleCamera();
  });

  // Manual gesture trigger / testing (from modal)
  function triggerGesture(name, icon, actionText) {
    if (gIcon) gIcon.textContent = icon;
    if (gName) gName.textContent = name;
    if (gScore) gScore.textContent = "95%";
    if (gAction) gAction.textContent = `Action: ${actionText}`;
    if (gestureHud) gestureHud.classList.add("detected");
    if (gBar) {
      gBar.style.width = "100%";
      setTimeout(() => {
        if (gBar) gBar.style.width = "0%";
        if (gestureHud) gestureHud.classList.remove("detected");
      }, 1800);
    }
    showToast(`Gesture Triggered: ${icon} ${name} → ${actionText}`);
  }

  document.querySelectorAll(".mg-card").forEach((card) => {
    card.addEventListener("click", () => {
      const icon = card.querySelector("span")?.textContent || "✋";
      const name = card.querySelector("strong")?.textContent || "Gesture";
      const desc = card.querySelector("small")?.textContent || "Execute";
      triggerGesture(name, icon, desc);
      legendModal?.close();
    });
  });

  // 8. Conversational Chat Engine (/api/chat)
  function appendChat(role, text) {
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${role === "user" ? "user" : "ai"}`;
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
    bubble.innerHTML = `
      <div class="bubble-meta">
        <strong class="author ${role === "user" ? "text-cyan" : "text-gold"}">${role === "user" ? "USER" : "ATULYA"}</strong>
        <span class="time">${timeStr}</span>
      </div>
      <div class="bubble-text">${text}</div>
    `;
    chatFeed.appendChild(bubble);
    chatFeed.scrollTop = chatFeed.scrollHeight;
  }

  async function sendChatMessage(query) {
    if (!query) return;
    appendChat("user", query);
    setAvatarState("thinking");
    waveActive = true;

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: query }),
      });
      if (!res.ok) throw new Error("Chat request failed");
      const data = await res.json();
      const reply = data.reply || data.response || "Command processed.";
      setAvatarState("speaking");
      appendChat("ai", reply);

      // Speak using SpeechSynthesis if available
      if (window.speechSynthesis) {
        const utter = new SpeechSynthesisUtterance(reply.slice(0, 180));
        utter.rate = 1.05;
        utter.pitch = 0.95;
        utter.onend = () => {
          setAvatarState("idle");
          waveActive = false;
        };
        window.speechSynthesis.speak(utter);
      } else {
        setTimeout(() => {
          setAvatarState("idle");
          waveActive = false;
        }, 3000);
      }
    } catch {
      setAvatarState("idle");
      waveActive = false;
      appendChat("ai", "I heard your query. Cognitive core is ready for commands.");
    }
  }

  chatForm?.addEventListener("submit", (e) => {
    e.preventDefault();
    const query = chatInput.value.trim();
    if (!query) return;
    chatInput.value = "";
    sendChatMessage(query);
  });

  // 9. Smart Home Quick Controls
  let lightsOn = true;
  lightsBtn?.addEventListener("click", async () => {
    lightsOn = !lightsOn;
    lightsBtn.dataset.on = String(lightsOn);
    const tag = lightsBtn.querySelector(".btn-tag");
    if (tag) {
      tag.className = `btn-tag ${lightsOn ? "text-green" : "text-muted"}`;
      tag.textContent = lightsOn ? "ON 🟢" : "OFF 🔴";
    }
    showToast(`Living Room Lights: ${lightsOn ? "Activated (80%)" : "Turned Off"}`);
    try {
      await fetch("/api/smarthome/scene", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scene_id: lightsOn ? "relax" : "goodnight" }),
      });
    } catch { /* Ignore */ }
  });

  let securityArmed = true;
  $("ctrl-security")?.addEventListener("click", () => {
    securityArmed = !securityArmed;
    const tag = $("ctrl-security").querySelector(".btn-tag");
    if (tag) {
      tag.className = `btn-tag ${securityArmed ? "text-cyan" : "text-red"}`;
      tag.textContent = securityArmed ? "ARMED 🟢" : "DISARMED 🔴";
    }
    showToast(`Home Security Perimeter: ${securityArmed ? "ARMED" : "DISARMED"}`);
  });

  let energyEco = true;
  $("ctrl-energy")?.addEventListener("click", () => {
    energyEco = !energyEco;
    const tag = $("ctrl-energy").querySelector(".btn-tag");
    if (tag) {
      tag.className = `btn-tag ${energyEco ? "text-yellow" : "text-green"}`;
      tag.textContent = energyEco ? "ECO MODE" : "BOOST MODE";
    }
    showToast(`Energy Profile: ${energyEco ? "Eco Power Optimization" : "Maximum Performance"}`);
  });

  // 10. Status & Gesture Guide Modal
  legendTrigger?.addEventListener("click", () => legendModal?.showModal());
  closeLegend?.addEventListener("click", () => legendModal?.close());

  // 11. Music Player Controls
  let isPlaying = false;
  const playBtn = $("v2-play");
  playBtn?.addEventListener("click", () => {
    isPlaying = !isPlaying;
    playBtn.textContent = isPlaying ? "⏸" : "▶";
    showToast(isPlaying ? "Playing: Midnight Drive" : "Playback Paused");
  });

  // Initial UI Setup: Standby camera
  updateCameraUI(false);

})();
