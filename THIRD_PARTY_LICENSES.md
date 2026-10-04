# 第三者のデータ・ソフトウェアについて(Third-Party Notices)

「日輪 Helio Wheel」は、次のデータ・ソフトウェア・フォントを利用しています。それぞれの作者・提供元に感謝します。条件の正確な内容は、各ライセンス文(リンク先)を見てください。

## データ

| 名前 | 何に使っているか | 提供元・条件 |
|---|---|---|
| JPL DE440s(惑星の天体暦) | 惑星の位置の計算(`de440s.bsp`を同梱) | NASA Jet Propulsion Laboratory(NASA/JPLの公開データ) |
| JPL Horizons | 小惑星・準惑星の表(`minor_bodies.bin`の元データ) | NASA/JPL |
| Hipparcos 新還元 | 恒星の位置 | ESA、F. van Leeuwen (2007)、VizieR I/311 |
| SIMBAD データベース | 深宇宙天体などの位置、一部の恒星の視線速度 | CDS、ストラスブール天文データセンター(利用時に謝辞を示すことが求められています) |

## ソフトウェア

| 名前 | 何に使っているか | ライセンス | ライセンス文 |
|---|---|---|---|
| Pyodide 0.26.4 | ブラウザの中でPythonを動かす | MPL-2.0 | https://github.com/pyodide/pyodide/blob/main/LICENSE |
| Astropy | 時刻・座標の計算 | BSD 3-Clause | https://github.com/astropy/astropy/blob/main/LICENSE.rst |
| NumPy | 数値計算 | BSD 3-Clause | https://github.com/numpy/numpy/blob/main/LICENSE.txt |
| jplephem 2.24 | 天体暦(`de440s.bsp`)の読み取り。`web/assets/jplephem.zip`に、そのままの形とライセンス文を同梱 | MIT | https://github.com/brandon-rhodes/python-jplephem/blob/master/LICENSE |
| tz-lookup 6.1.25 | 緯度・経度からタイムゾーンを求める | CC0-1.0 | https://www.npmjs.com/package/tz-lookup |
| tzdata(Pythonのパッケージ) | タイムゾーンのデータ | Apache-2.0 | https://github.com/python/tzdata/blob/master/LICENSE |
| certifi | 証明書(Pyodideの依存) | MPL-2.0 | https://github.com/certifi/python-certifi/blob/master/LICENSE |
| SQLite | 人物データの保存(端末のブラウザの中) | パブリックドメイン | https://www.sqlite.org/copyright.html |

Astropy などは、さらにほかのパッケージ(pyerfa、PyYAML、packaging など)に依存しています。これらはPyodideの配布物を通じて読み込まれ、それぞれのライセンスに従います。

## フォント

| 名前 | 何に使っているか | ライセンス |
|---|---|---|
| Astronomicon(Roberto Corona) | 惑星・サインの記号。`assets/Astronomicon.ttf`を同梱 | SIL Open Font License 1.1。ライセンス文は`assets/Astronomicon-OFL-License.txt`に同梱 |
| Shippori Mincho、Cormorant Garamond、Zen Kaku Gothic New、Space Mono、Noto Sans Symbols 2 | 画面の文字。Google Fontsから読み込む(同梱はしていない) | いずれも SIL Open Font License 1.1 |

## このリポジトリに入れていないもの

- 著者の文章(松村潔先生のサビアンシンボルの解釈文、石塚さんの訳など)は、**入っていません**。許諾なく入れることはしません。サビアンの画面は「準備中」の枠だけです。
- Microsoft のフォント(Meiryo、Segoe UI Symbol)は、再配布できないため、公開用には入れていません。

## 本アプリ自身について

本アプリ自身のコード・画面・文章・デザインは、作者(ふね)の著作物で、PolyForm Noncommercial License 1.0.0 の条件で公開しています(非営利の利用は自由、営利の利用は作者の許可が必要)。条件は、リポジトリ直下の`LICENSE`を見てください。上の第三者の部分は、それぞれのライセンスに従い、`LICENSE`の対象ではありません。

## 開発用のコマンドライン版について

コマンドライン版(`src/helio/cli.py`)は、上のほかに、matplotlib(PSF系ライセンス)、astroquery(BSD 3-Clause)、timezonefinder(MIT。地図データはODbL)を使います。これらはブラウザ版・公開用フォルダには含まれません。
