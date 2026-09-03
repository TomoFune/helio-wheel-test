// engine.js -- Pyodide bootstrap + a clean JS<->Python bridge for the
// Helio Wheel UI, reusing the exact boot sequence already validated in
// app.js (7.8-7.18: package install, timezonefinder stub, helio/*.py
// source loading, de440s kernel, fonts, IDBFS persistence for
// storage.py) but stripped of the old bare-bones test form's own
// wiring. This file is meant to sit alongside a real UI (wheel.html)
// and drive it via HelioEngine.boot()/HelioEngine.computeChart(...)
// instead of app.js's matplotlib-PNG single-shot form.
//
// Rendering stays entirely on the JS/SVG side (the Helio Wheel UI
// already does this, fast and interactive) -- Python's only job here
// is to hand back real numbers (a lons dict), never an image. This is
// the "keep the JS UI, keep the Python calculation, bridge with
// Pyodide" architecture decided 2026-09-01/02 (see HANDOFF 7.45).
const HelioEngine = (() => {
  const HELIO_MODULES = [
    "__init__.py", "config.py", "degrees.py", "ephemeris.py", "stars.py",
    "deep_sky.py", "reference_points.py", "conjunctions.py", "chart.py",
    "eclipses.py", "time_resolve.py", "minor_bodies.py", "storage.py",
  ];

  let pyodide = null;
  let bootPromise = null;

  function syncIDBFS(populate) {
    return new Promise((resolve, reject) => {
      pyodide.FS.syncfs(populate, (err) => (err ? reject(err) : resolve()));
    });
  }

  async function bootOnce(onProgress) {
    const log = (msg) => { try { onProgress && onProgress(msg); } catch (_) {} };
    const t0 = performance.now();
    log("Pyodideを起動しています...");
    pyodide = await loadPyodide();
    await pyodide.loadPackage(["numpy", "matplotlib", "sqlite3"]);
    await pyodide.loadPackage("micropip");
    const micropip = pyodide.pyimport("micropip");
    await micropip.install(["astropy", "jplephem", "tzdata", "certifi", "astroquery"]);
    log("Pythonパッケージの準備完了 (" + Math.round(performance.now() - t0) + "ms)");

    // See app.js's identical stub for the full rationale: h3 (a
    // timezonefinder dependency) has no WASM wheel, so lat/lon->tz
    // resolution happens on the JS side (tz-lookup) and gets passed
    // in as an explicit tz_name -- this stub only exists so the
    // module-level `from timezonefinder import TimezoneFinder` import
    // in time_resolve.py doesn't raise.
    pyodide.runPython(`
import sys, types
_stub = types.ModuleType("timezonefinder")
class _StubTimezoneFinder:
    def __init__(self, *a, **kw):
        pass
    def timezone_at(self, *a, **kw):
        raise NotImplementedError(
            "lat/lon -> timezone lookup isn't available in-browser; "
            "the JS side must resolve the IANA zone name and pass tz_name= explicitly"
        )
_stub.TimezoneFinder = _StubTimezoneFinder
sys.modules["timezonefinder"] = _stub
`);

    log("helio本体のソースコードを読み込んでいます...");
    pyodide.FS.mkdirTree("/home/pyodide/pkg/helio");
    for (const name of HELIO_MODULES) {
      const resp = await fetch("/src/helio/" + name);
      if (!resp.ok) throw new Error("failed to fetch " + name + ": " + resp.status);
      const text = await resp.text();
      pyodide.FS.writeFile("/home/pyodide/pkg/helio/" + name, text);
    }
    log("helio本体のソースコード読み込み完了 (" + HELIO_MODULES.length + "ファイル)");

    log("天体暦データ(de440s、約31MB、初回のみ)を読み込んでいます...");
    const t1 = performance.now();
    const kernelResp = await fetch("/web/assets/de440s.bsp");
    const kernelBytes = new Uint8Array(await kernelResp.arrayBuffer());
    pyodide.FS.writeFile("/home/pyodide/de440s.bsp", kernelBytes);
    log("天体暦データ読み込み完了 (" + Math.round(performance.now() - t1) + "ms)");

    pyodide.FS.mkdirTree("/home/pyodide/data");
    pyodide.FS.mount(pyodide.FS.filesystems.IDBFS, {}, "/home/pyodide/data");
    await syncIDBFS(true);

    pyodide.runPython(`
import sys
sys.path.insert(0, "/home/pyodide/pkg")

from helio import config
config.EPHEMERIS_KERNEL = "/home/pyodide/de440s.bsp"  # local file, not the "de440s" auto-download name
`);

    log("計算エンジンの準備完了 (合計 " + Math.round(performance.now() - t0) + "ms)");
  }

  // 呼び出し側が何度呼んでも、実際のブート処理は1回しか走らない(2回目
  // 以降は同じPromiseを返すだけ)。UIの複数箇所が「エンジンが要る」と
  // 思ったタイミングでそれぞれ呼んでも安全にするため。
  function boot(onProgress) {
    if (!bootPromise) bootPromise = bootOnce(onProgress);
    return bootPromise;
  }

  // 天体の位置(主要9天体、度)を実際にPythonで計算して返す。
  // starKey が null/undefined ならトロピカル(回転なし)。
  // 戻り値: { mercury: 12.34, venus: ..., ... }(PLANET_META/JSのキー名と一致)
  async function computeMainLongitudes({ year, month, day, hour, minute, second = 0, tzName, starKey }) {
    if (!pyodide) throw new Error("HelioEngine.boot() がまだ完了していません");
    pyodide.globals.set("_year", year);
    pyodide.globals.set("_month", month);
    pyodide.globals.set("_day", day);
    pyodide.globals.set("_hour", hour);
    pyodide.globals.set("_minute", minute);
    pyodide.globals.set("_second", second);
    pyodide.globals.set("_tz_name", tzName);
    pyodide.globals.set("_star_key", starKey || null);
    const json = await pyodide.runPythonAsync(`
import json
from helio.time_resolve import resolve_birth_time
from helio.ephemeris import heliocentric_longitudes
from helio.reference_points import resolve_reference_longitude

resolved = resolve_birth_time(_year, _month, _day, _hour, _minute, _second, tz_name=_tz_name)
lons = heliocentric_longitudes(resolved.time)
if _star_key:
    ref_lon = resolve_reference_longitude(_star_key, resolved.time)
    lons = {k: (v - ref_lon) % 360 for k, v in lons.items()}
json.dumps(lons)
`);
    return JSON.parse(json);
  }

  return { boot, computeMainLongitudes };
})();
