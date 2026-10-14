// Atulya service worker: makes the WebUI installable and opens the shell fast.
// API calls, voice, and auth always go to the network and are never cached.
const CACHE = "atulya-shell-v4";
const SHELL = ["./", "./index.html", "./renderer.css", "./assistant.js", "./controls.js", "./controls.css", "./music.js", "./manifest.webmanifest", "./icons/icon-192.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch { data = { title: "Atulya", body: event.data?.text() }; }
  event.waitUntil(self.registration.showNotification(data.title || "Atulya", {
    body: data.body || "", icon: "./icons/icon-192.png", badge: "./icons/icon-192.png",
    data: { url: data.url || "./" }, tag: data.title || "atulya", renotify: true,
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || "./", self.location.origin).href;
  event.waitUntil(clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
    const open = windows.find((client) => client.url.startsWith(self.location.origin));
    return open ? open.focus() : clients.openWindow(target);
  }));
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;
  // Network first so updates appear immediately; the cache only covers offline/slow starts.
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok && response.type === "basic") {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        }
        return response;
      })
      .catch(() => caches.match(event.request).then((hit) => hit || (event.request.mode === "navigate" ? caches.match("./index.html") : Response.error()))),
  );
});
