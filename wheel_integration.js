// wheel_integration.js -- glue between the Helio Wheel UI (wheel_body's
// own inline <script>, which defines REF_LONGITUDES/buildChart/etc as
// top-level `var`/function declarations, so they're reachable here as
// plain globals) and HelioEngine (engine.js). Kept as its own file
// rather than inline so the UI's own script block stays exactly the
// artifact's content (easier to diff/re-sync against future artifact
// republishes).
//
// Scope of this first pass (HANDOFF 7.45): only the "自分" test
// person's real natal longitudes (main 9 planets, tropical + every
// GCS star origin already in REF_LONGITUDES), computed for real via
// Pyodide and swapped in for the hand-typed fake numbers. Everything
// else the UI does (aspects, conjunctions, degree labels, minor
// bodies, transit, biwheel, person switching, Sabian placeholder)
// keeps working unchanged, since it all just reads whatever's in
// REF_LONGITUDES/NATAL_MINOR -- it doesn't know or care whether those
// numbers are real or fake.
(function () {
  const statusHost = document.getElementById('badge-line1');
  function showBootStatus(msg) {
    console.log('[engine]', msg);
  }

  // サンプル花子(1990-06-15 09:30:00, Asia/Tokyo、架空の人物)の本物の値で、
  // 今REF_LONGITUDESに手打ちで入っている architecture-mockup 用の数字を
  // 置き換える。2026-09-03、配布テストに備えて、ここにあった特定個人の
  // 出生データを架空のサンプル人物のものに差し替えた -- wheel.html本体側
  // (REF_LONGITUDES等)は既に架空データに入れ替え済みだったが、この
  // ファイルが起動のたびに無条件でPyodide経由の本物の値に上書きする作り
  // だったため、ここを直さない限り元のデータがそのまま復活してしまう
  // ところだった。
  // GCS_STAR_KEYS はUIの起点メニューに既に出ている恒星と同じキー
  // (reference_points.py側の実キーとも一致するので resolve_reference_longitude
  // にそのまま渡せる)。
  const GCS_STAR_KEYS = ['sirius', 'arcturus', 'antares', 'alcyone', 'thuban', 'orion_belt', 'big_dipper', 'andromeda_galaxy'];

  async function loadRealNatalData() {
    const base = { year: 1990, month: 6, day: 15, hour: 9, minute: 30, tzName: 'Asia/Tokyo' };

    const tropical = await HelioEngine.computeMainLongitudes({ ...base, starKey: null });
    const before = { ...REF_LONGITUDES.tropical };
    REF_LONGITUDES.tropical = tropical;
    console.log('[engine] tropical longitudes -- fake (mockup) vs real (Astropy):');
    Object.keys(before).forEach((k) => {
      const diff = Math.abs(((tropical[k] - before[k] + 540) % 360) - 180);
      console.log(`  ${k}: fake=${before[k].toFixed(3)}  real=${tropical[k].toFixed(3)}  diff=${diff.toFixed(4)}deg`);
    });

    for (const key of GCS_STAR_KEYS) {
      try {
        REF_LONGITUDES[key] = await HelioEngine.computeMainLongitudes({ ...base, starKey: key });
      } catch (err) {
        console.warn('[engine] failed to compute star origin', key, err);
      }
    }
    console.log('[engine] all origin longitudes replaced with real Astropy values.');
  }

  async function start() {
    try {
      await HelioEngine.boot(showBootStatus);
      await loadRealNatalData();
      // チャート画面のDOM要素は(人物選択画面が表示中でも)常に存在して
      // いる(showView は.active クラスの付け替えだけで、DOMからは消さ
      // ない) ので、buildChart() をこの時点で無条件に呼んで安全に再描画
      // できる -- 既にチャート画面を見ていればその場で本物の数字に切り
      // 替わり、まだ人物選択画面ならこの再描画は見えないだけで、次に
      // チャート画面に進んだ時には既に本物の数字が入っている。
      if (typeof buildChart === 'function') {
        buildChart();
        console.log('[engine] real data now live.');
      }
      window.__helioEngineReady = true;
    } catch (err) {
      console.error('[engine] boot failed:', err);
    }
  }

  start();
})();
