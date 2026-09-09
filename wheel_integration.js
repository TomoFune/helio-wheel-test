// wheel_integration.js -- boots the Pyodide-backed HelioEngine, then hands
// off to the main script's window.onHelioEngineReady() (defined inline in
// wheel.html) once ready.
//
// 2026-09-05(HANDOFF「①②」)までは、このファイル自身がサンプル花子固定の
// 実データをREF_LONGITUDESへ上書きしていた(起動時に1回だけ)。それを、
// 「保存済みの好きな人物を選ぶたびに、その人物の本物のデータを計算する」
// (①)、「トランジットの日食/月食ジャンプもその場で実際に検索する」(②)
// へ一般化するにあたり、その手のPyodide呼び出し・状態更新はどれも
// REF_LONGITUDES/ANCHOR_DATA/buildChart()や人物管理UIのDOM要素へ直接
// アクセスする必要があるため、メイン側のインラインスクリプト
// (applyPersonNatalData()/selectPerson()/jumpTTo()等)へ移した。この
// ファイルの役目は「エンジンを起動し、準備できたら知らせる」だけに縮小。
(function () {
  // オフライン(PWA)対応(2026-09-10、HANDOFF 7.89) -- Pyodide本体・科学
  // 計算パッケージ・天体暦カーネル(約31MB)を一度キャッシュしておけば、
  // 2回目以降の起動はネットワークを介さず一瞬で終わる(「おそろしく
  // おそい」への対応)。sw.js/manifest.jsonはこのファイルと同じ場所に
  // 置かれる前提(ローカルはweb/配下、gh_uploadはリポジトリ直下)なので、
  // 相対パスで登録すればどちらでも正しいscopeになる。Artifact単体公開
  // ではこのファイル自体が読み込まれない(wheel_integration.jsはローカル
  // /GitHub Pages版にしか組み込まれていない)ため、登録を分岐する必要は
  // ない。
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('sw.js').catch((err) => {
        console.warn('[pwa] service worker registration failed', err);
      });
    });
  }

  function showBootStatus(msg) {
    console.log('[engine]', msg);
    // 人物一覧(#person-select-list)は起動完了までここに進捗を出す --
    // person-selectビューが既定の初期表示なので、起動中もユーザーに
    // 「今何が起きているか」が見える。
    const el = document.getElementById('person-select-list');
    if (el && !window.__helioEngineReady) {
      el.innerHTML = '<div class="person-detail" style="padding:14px 4px;">' + msg + '</div>';
    }
  }

  async function start() {
    try {
      await HelioEngine.boot(showBootStatus);
      window.__helioEngineReady = true;
      if (typeof window.onHelioEngineReady === 'function') {
        await window.onHelioEngineReady();
      }
    } catch (err) {
      console.error('[engine] boot failed:', err);
      const el = document.getElementById('person-select-list');
      if (el) {
        el.innerHTML = '<div class="person-detail" style="padding:14px 4px; color:#c0392b;">計算エンジンの起動に失敗しました: ' + err + '</div>';
      }
    }
  }

  start();
})();
