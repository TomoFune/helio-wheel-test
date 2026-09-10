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
    "eclipses.py", "seasons.py", "time_resolve.py", "minor_bodies.py", "storage.py",
  ];

  // (2026-09-07) src/helio/*.py と web/assets/de440s.bsp を、以前は
  // fetch("/src/...")のような絶対パス(サイト直下からの絶対パス)で
  // 取得していた -- ローカル開発サーバー(helio-appのプロジェクト直下を
  // ルートとして配信、ページ自体はweb/wheel.htmlに1段ネストされている)
  // ではこれでもたまたま正しく解決していたが、GitHub Pagesのプロジェクト
  // ページ(https://tomofune.github.io/helio-wheel-test/、リポジトリ名の
  // サブパス配下で配信される)では絶対パスがドメイン直下(/src/...)を
  // 指してしまい404になっていた(ユーザー報告「failed to fetch
  // __init__.py: 404」で発覚)。gh_upload(index.htmlがリポジトリ直下)と
  // ローカル(wheel.htmlがweb/配下)とでは、ページ自身からsrc/web-assets
  // までの相対的な深さが異なる(前者は"src/helio/"、後者は"../src/helio/"
  // が正しい)ため、単純な相対パス1本には統一できない -- 両方のパターン
  // を順に試し、成功した方を使う。
  // noCache: true for the small, actively-edited python source files --
  // without it, the browser's own heuristic HTTP cache (separate from,
  // and not bypassed by, sw.js's network-first strategy -- that still
  // calls plain fetch() under the hood) can silently keep serving an
  // old cached copy of a .py file across page loads even though a
  // network request nominally went out and "succeeded" (2026-09-10,
  // discovered while verifying an eclipses.py performance fix: the old
  // algorithm kept running after the file was edited and the page was
  // reloaded, with no error of any kind -- just silently stale code).
  // Left off for the ~31MB kernel, where the opposite is wanted (let
  // the browser/SW cache do its job, see sw.js's ASSET_CACHE).
  async function fetchAsset(relPathFromSiteRoot, { noCache = false } = {}) {
    const candidates = [relPathFromSiteRoot, "../" + relPathFromSiteRoot];
    const init = noCache ? { cache: "no-store" } : undefined;
    let lastErr;
    for (const path of candidates) {
      try {
        const resp = await fetch(path, init);
        if (resp.ok) return resp;
        lastErr = new Error("failed to fetch " + path + ": " + resp.status);
      } catch (err) {
        lastErr = err;
      }
    }
    throw lastErr;
  }

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
      const resp = await fetchAsset("src/helio/" + name, { noCache: true });
      const text = await resp.text();
      pyodide.FS.writeFile("/home/pyodide/pkg/helio/" + name, text);
    }
    log("helio本体のソースコード読み込み完了 (" + HELIO_MODULES.length + "ファイル)");

    log("天体暦データ(de440s、約31MB、初回のみ)を読み込んでいます...");
    const t1 = performance.now();
    const kernelResp = await fetchAsset("web/assets/de440s.bsp");
    const kernelBytes = new Uint8Array(await kernelResp.arrayBuffer());
    pyodide.FS.writeFile("/home/pyodide/de440s.bsp", kernelBytes);
    log("天体暦データ読み込み完了 (" + Math.round(performance.now() - t1) + "ms)");

    // 小惑星・準惑星の黄経テーブル(minor_bodies.bin、約3MB、初回のみ) --
    // 2026-09-11「小惑星、準惑星、やってみましょう」より。JPL Horizonsの
    // 小惑星用SPKはjplephemが読めない形式(Type 21)なので、de440s.bspと
    // 同じ「バンドルしてオフライン参照」はできず、代わりに1日おきの黄経
    // だけを焼き込んだ自前の軽量テーブル形式にした(bake_minor_bodies.py
    // で1回だけ生成、詳細はminor_bodies.pyのdocstring参照)。
    const t2 = performance.now();
    const minorResp = await fetchAsset("web/assets/minor_bodies.bin");
    const minorBytes = new Uint8Array(await minorResp.arrayBuffer());
    pyodide.FS.writeFile("/home/pyodide/minor_bodies.bin", minorBytes);
    log("小惑星・準惑星データ読み込み完了 (" + Math.round(performance.now() - t2) + "ms)");

    pyodide.FS.mkdirTree("/home/pyodide/data");
    pyodide.FS.mount(pyodide.FS.filesystems.IDBFS, {}, "/home/pyodide/data");
    await syncIDBFS(true);

    pyodide.runPython(`
import sys
sys.path.insert(0, "/home/pyodide/pkg")

from helio import config
config.EPHEMERIS_KERNEL = "/home/pyodide/de440s.bsp"  # local file, not the "de440s" auto-download name
config.MINOR_BODIES_TABLE_PATH = "/home/pyodide/minor_bodies.bin"
`);

    log("計算エンジンの準備完了 (合計 " + Math.round(performance.now() - t0) + "ms)");
  }

  // 呼び出し側が何度呼んでも、実際のブート処理は1回しか走らない(2回目
  // 以降は同じPromiseを返すだけ)。UIの複数箇所が「エンジンが要る」と
  // 思ったタイミングでそれぞれ呼んでも安全にするため。
  // 2026-09-08: 失敗した場合はbootPromiseをnullに戻し、次の呼び出しで
  // 再挑戦できるようにした -- 以前は一度失敗すると(GitHub Pagesの
  // デプロイ直後のCDN反映待ちなど、一過性のネットワークエラーでも)
  // 失敗したPromiseをそのまま覚え続けてしまい、ページを再読み込みする
  // までずっと同じエラーを返し続けていた(「トランジットの日食/月食は
  // 相変わらずエラー」という報告で発覚 -- 実際は起動時の一時的な失敗が
  // 尾を引いていただけで、日食/月食検索自体のコードの問題ではなかった)。
  function boot(onProgress) {
    if (!bootPromise) {
      bootPromise = bootOnce(onProgress).catch((err) => {
        bootPromise = null;
        throw err;
      });
    }
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
from helio.minor_bodies import minor_body_heliocentric_longitudes_fast
from helio.reference_points import resolve_reference_longitude

resolved = resolve_birth_time(_year, _month, _day, _hour, _minute, _second, tz_name=_tz_name)
lons = heliocentric_longitudes(resolved.time)
lons.update(minor_body_heliocentric_longitudes_fast(resolved.time))
if _star_key:
    ref_lon = resolve_reference_longitude(_star_key, resolved.time)
    lons = {k: (v - ref_lon) % 360 for k, v in lons.items()}
json.dumps(lons)
`);
    return JSON.parse(json);
  }

  // トランジットの日食/月食ジャンプ用(HANDOFF「②」、2026-09-05)。
  // utcMsを起点に、直近の(previous)/次の(next)日食・月食の瞬間を実際に
  // 検索し、その瞬間の主要9天体の黄経も同じ呼び出しで返す -- 固定の
  // T_SPECIAL_TIMES(2026年8月の1組の日付)しか使えなかったのを、実際に
  // 計算して前後どちらへも動的にジャンプできるようにする。
  async function findTransitEclipse(utcMs, kind, direction) {
    if (!pyodide) throw new Error("HelioEngine.boot() がまだ完了していません");
    pyodide.globals.set("_unix_s", utcMs / 1000);
    pyodide.globals.set("_kind", kind === "eclipseSolar" ? "solar" : "lunar");
    pyodide.globals.set("_direction", direction); // "previous" | "next"
    const json = await pyodide.runPythonAsync(`
import json
from astropy.time import Time
from helio.eclipses import find_previous_eclipse, find_next_eclipse
from helio.ephemeris import heliocentric_longitudes
from helio.minor_bodies import minor_body_heliocentric_longitudes_fast

t0 = Time(_unix_s, format="unix", scale="utc")
finder = find_previous_eclipse if _direction == "previous" else find_next_eclipse
event = finder(t0, _kind)
lons = heliocentric_longitudes(event.time)
lons.update(minor_body_heliocentric_longitudes_fast(event.time))
json.dumps({"lons": lons, "utcMs": event.time.unix * 1000, "moonLatitudeDeg": event.moon_latitude_deg})
`);
    return JSON.parse(json);
  }

  // 四季図(春分/夏至/秋分/冬至)の動的な前後検索(2026-09-10、「四季図も
  // 次の春分、夏至、秋分、冬至...と選択できると」より) -- findTransitEclipse
  // と全く同じ形。seasonは"springEquinox"/"summerSolstice"/"autumnEquinox"/
  // "winterSolstice"のいずれか(helio.seasons.SEASON_TARGET_DEGのキーと一致)。
  async function findTransitSeason(utcMs, season, direction) {
    if (!pyodide) throw new Error("HelioEngine.boot() がまだ完了していません");
    pyodide.globals.set("_unix_s", utcMs / 1000);
    pyodide.globals.set("_season", season);
    pyodide.globals.set("_direction", direction); // "previous" | "next"
    const json = await pyodide.runPythonAsync(`
import json
from astropy.time import Time
from helio.seasons import find_previous_season, find_next_season
from helio.ephemeris import heliocentric_longitudes
from helio.minor_bodies import minor_body_heliocentric_longitudes_fast

t0 = Time(_unix_s, format="unix", scale="utc")
finder = find_previous_season if _direction == "previous" else find_next_season
event = finder(t0, _season)
lons = heliocentric_longitudes(event.time)
lons.update(minor_body_heliocentric_longitudes_fast(event.time))
json.dumps({"lons": lons, "utcMs": event.time.unix * 1000})
`);
    return JSON.parse(json);
  }

  // 「主要な恒星・銀河」キー一覧をPython側(reference_points.py)から
  // そのまま取得する(2026-09-10) -- GCS(8起点)は元々JS側で管理して
  // いるものをそのまま使うため、ここでは「主要」だけを返す。
  async function listMajorReferenceKeys() {
    if (!pyodide) throw new Error("HelioEngine.boot() がまだ完了していません");
    const json = await pyodide.runPythonAsync(`
import json
from helio.reference_points import MAJOR_REFERENCE_KEYS

json.dumps(sorted(MAJOR_REFERENCE_KEYS))
`);
    return JSON.parse(json);
  }

  // 恒星・銀河との合(コンジャンクション)をその都度実際に検索する
  // (2026-09-10、「恒星・銀河との合を任意の人物へ一般化」より) -- 以前は
  // サンプル花子の1990年のデータを固定で埋め込んでいたモックアップを
  // 置き換える。bodyLonsは{惑星キー: トロピカル黄経}(起点回転をかける前
  // の、いわゆる素の値 -- conjunctions.pyのfind_conjunctions自身が
  // 「回転しても合の判定は変わらない」設計のため)。keysは検索対象の
  // 参照点キー一覧(GCS/主要な恒星・銀河などのタブに対応)。
  async function findConjunctions(bodyLons, utcMs, orbDeg, keys) {
    if (!pyodide) throw new Error("HelioEngine.boot() がまだ完了していません");
    pyodide.globals.set("_body_lons_json", JSON.stringify(bodyLons));
    pyodide.globals.set("_unix_s", utcMs / 1000);
    pyodide.globals.set("_orb_deg", orbDeg);
    pyodide.globals.set("_keys_json", JSON.stringify(keys));
    const json = await pyodide.runPythonAsync(`
import json
from astropy.time import Time
from helio.conjunctions import find_conjunctions

body_lons = json.loads(_body_lons_json)
keys = json.loads(_keys_json)
t = Time(_unix_s, format="unix", scale="utc")
hits = find_conjunctions(body_lons, t, orb_deg=_orb_deg, keys=keys)
json.dumps({
    body_key: [
        {"refKey": h.ref_key, "kind": h.ref_kind, "labelJa": h.label_ja, "constellationJa": h.constellation_ja, "lon": h.lon, "sep": h.separation_deg}
        for h in hit_list
    ]
    for body_key, hit_list in hits.items()
})
`);
    return JSON.parse(json);
  }

  // 出生図の日食図/月食図用(HANDOFF「①」、2026-09-05)。resolve_birth_time
  // (タイムゾーン込みの現地日時->UTC)からfind_previous_eclipseまでを
  // 1回のPython呼び出しで完結させる -- CLIの`--mode eclipse-solar`と同じ
  // 処理(出生時刻より前の直近の日食/月食を探し、その瞬間のヘリオ図を出す)。
  async function computeNatalEclipseChart({ year, month, day, hour, minute, second = 0, tzName, kind }) {
    if (!pyodide) throw new Error("HelioEngine.boot() がまだ完了していません");
    pyodide.globals.set("_year", year);
    pyodide.globals.set("_month", month);
    pyodide.globals.set("_day", day);
    pyodide.globals.set("_hour", hour);
    pyodide.globals.set("_minute", minute);
    pyodide.globals.set("_second", second);
    pyodide.globals.set("_tz_name", tzName);
    pyodide.globals.set("_kind", kind === "eclipseSolar" ? "solar" : "lunar");
    const json = await pyodide.runPythonAsync(`
import json
from helio.time_resolve import resolve_birth_time
from helio.eclipses import find_previous_eclipse
from helio.ephemeris import heliocentric_longitudes
from helio.minor_bodies import minor_body_heliocentric_longitudes_fast

resolved = resolve_birth_time(_year, _month, _day, _hour, _minute, _second, tz_name=_tz_name)
event = find_previous_eclipse(resolved.time, _kind)
lons = heliocentric_longitudes(event.time)
lons.update(minor_body_heliocentric_longitudes_fast(event.time))
json.dumps({"lons": lons, "isoUtc": event.time.isot, "moonLatitudeDeg": event.moon_latitude_deg})
`);
    return JSON.parse(json);
  }

  // ---------- 人物データ(storage.py)のCRUD、HANDOFF「①」 ----------
  // IDBFSは起動時にsyncIDBFS(true)で一度読み込み済み(bootOnce参照)。
  // 書き込み系(save/delete)は最後に必ずsyncIDBFS(false)でIndexedDBへ
  // 書き戻す -- これをしないと、このタブのメモリ上のFSにしか変わらず、
  // リロードすると保存したはずのデータが消える。
  async function listPeople() {
    if (!pyodide) throw new Error("HelioEngine.boot() がまだ完了していません");
    const json = await pyodide.runPythonAsync(`
import json
from dataclasses import asdict
from helio.storage import Storage

with Storage() as store:
    people = [asdict(p) for p in store.list_people()]
json.dumps(people, ensure_ascii=False)
`);
    return JSON.parse(json);
  }

  async function savePerson(person) {
    if (!pyodide) throw new Error("HelioEngine.boot() がまだ完了していません");
    pyodide.globals.set("_id", person.id ?? null);
    pyodide.globals.set("_name", person.name);
    pyodide.globals.set("_birth_date", person.birthDate);
    pyodide.globals.set("_birth_time", person.birthTime ?? null);
    pyodide.globals.set("_time_unknown", !!person.timeUnknown);
    pyodide.globals.set("_timezone", person.timezone);
    pyodide.globals.set("_latitude", person.latitude);
    pyodide.globals.set("_longitude", person.longitude);
    pyodide.globals.set("_place_name", person.placeName || "");
    pyodide.globals.set("_category", person.category || "");
    pyodide.globals.set("_notes", person.notes || "");
    const savedId = await pyodide.runPythonAsync(`
from helio.storage import Storage, Person

with Storage() as store:
    if _id is None:
        new_person = Person(
            id=None, name=_name, birth_date=_birth_date, birth_time=_birth_time,
            time_unknown=bool(_time_unknown), timezone=_timezone,
            latitude=_latitude, longitude=_longitude, place_name=_place_name,
            category=_category, notes=_notes,
        )
        result_id = store.add_person(new_person)
    else:
        store.update_person(
            _id, name=_name, birth_date=_birth_date, birth_time=_birth_time,
            time_unknown=int(bool(_time_unknown)), timezone=_timezone,
            latitude=_latitude, longitude=_longitude, place_name=_place_name,
            category=_category, notes=_notes,
        )
        result_id = _id
result_id
`);
    await syncIDBFS(false);
    return savedId;
  }

  async function deletePerson(id) {
    if (!pyodide) throw new Error("HelioEngine.boot() がまだ完了していません");
    pyodide.globals.set("_id", id);
    await pyodide.runPythonAsync(`
from helio.storage import Storage

with Storage() as store:
    store.delete_person(_id)
`);
    await syncIDBFS(false);
  }

  return {
    boot, computeMainLongitudes, findTransitEclipse, findTransitSeason, computeNatalEclipseChart,
    findConjunctions, listMajorReferenceKeys, listPeople, savePerson, deletePerson,
  };
})();
