// Service worker for the real Helio Wheel app (wheel.html / gh_upload's
// index.html) -- 2026-09-10, HANDOFF 7.89. Replaces the previous sw.js,
// which was actually wired to the old, now-unused web/index.html+app.js
// test-form page and never covered the real app at all (discovered in
// HANDOFF 7.83).
//
// Goal: fix two things at once (they turned out to be the same root
// cause) -- (1) "オフライン(PWA)対応" was requested, and (2) every visit
// was re-downloading the Pyodide runtime, its science packages
// (astropy/jplephem/etc.), and the ~31MB ephemeris kernel from scratch,
// which is what made the app feel "おそろしくおそい" (frighteningly
// slow) even when just reopening it.
//
// Two different caching strategies for two different kinds of request,
// same idea as the old sw.js's own comment but split into two named
// caches this time:
//  - ASSET_CACHE (cache-first): big, effectively-immutable files -- the
//    ephemeris kernel, and anything from the Pyodide/tz-lookup/Google
//    Fonts CDNs (the Pyodide runtime itself, and every .whl/.wasm
//    package file it fetches internally during loadPyodide()/
//    loadPackage() -- those all go through fetch() too, so this
//    service worker sees and can cache them even though engine.js never
//    names them directly). Once cached, repeat visits skip the network
//    for these entirely.
//  - APP_CACHE (network-first, cache as a fallback): the actual page,
//    engine.js, wheel_integration.js, and the helio/*.py source -- these
//    are the files under active development, so a visit that's online
//    always gets the latest version; only a visit that's actually
//    offline falls back to whatever was cached last.
//
// No fixed precache list -- everything gets cached organically the
// first time it's actually fetched during normal use (same reasoning as
// the old sw.js: keeps this file free of any hardcoded path, so it
// doesn't care whether it's sitting next to web/wheel.html (local dev)
// or gh_upload's index.html (GitHub Pages) -- it only ever reacts to
// whatever URL the page itself already resolved correctly).
const CACHE_VERSION = "v1";
const APP_CACHE = "helio-wheel-app-" + CACHE_VERSION;
const ASSET_CACHE = "helio-wheel-assets-" + CACHE_VERSION;

// 固定のホスト名リストだと取りこぼす(2026-09-10、実機検証でastroquery
// の依存(jplephem/keyring/jaraco.*/pyvo、pypi.org/files.pythonhosted.org
// 経由)がAPP_CACHE(network-first)側に紛れ込んでいるのを発見) -- 実際は
// 「同じオリジンかどうか」で分ければ十分きれいに分かれる: このアプリが
// 積極的に手を入れる同一オリジンのファイル(ページ本体・engine.js・
// wheel_integration.js・src/helio/*.py)以外は、Pyodide本体もCDN経由の
// 各種パッケージもフォントも全部「バージョン固定でほぼ不変」なので、
// クロスオリジンかどうかだけで判定する。同一オリジンでも天体暦カーネル
// (.bsp)だけは例外的にこちら(cache-first)に含める。
function isHeavyAsset(url) {
  return url.pathname.endsWith(".bsp") || url.origin !== self.location.origin;
}

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names
          .filter((name) => name.startsWith("helio-wheel-") && name !== APP_CACHE && name !== ASSET_CACHE)
          .map((name) => caches.delete(name))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);

  if (isHeavyAsset(url)) {
    event.respondWith(
      caches.open(ASSET_CACHE).then(async (cache) => {
        const cached = await cache.match(event.request);
        if (cached) return cached;
        const resp = await fetch(event.request);
        // opaque(cross-origin no-cors)も含め、成功した応答は保存する
        // -- Pyodideの内部fetchの一部はno-corsで飛ぶことがあるため。
        if (resp && (resp.ok || resp.type === "opaque")) {
          cache.put(event.request, resp.clone());
        }
        return resp;
      })
    );
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((resp) => {
        if (resp && resp.ok) {
          const copy = resp.clone();
          caches.open(APP_CACHE).then((cache) => cache.put(event.request, copy));
        }
        return resp;
      })
      .catch(() => caches.match(event.request))
  );
});
