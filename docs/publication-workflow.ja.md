# 公開の流れ

この順序を、自分たちの release の手順を作る出発点にしてください。例は Python package、GitHub の送り先、version の tag を使います。他の構成では手順も変わります。noren は、test、package の build、registry への upload、GitHub Release の作成、文書の公開を実行しません。

## 1. 最初の snapshot から公開する物として準備する

送り先の URL、選ぶ path、ファイルの中身、依存の取得元、license、再配布する data を点検します。`noren.yaml` と禁止語の一覧は除外してください。元の commit を選ぶ前に、private の project、package、host の識別子を禁止語に加えます。

noren は送り先の履歴を書き換えずに commit を足します。次の snapshot でファイルを外しても、古い commit と tag には残ります。最初は private の送り先でも、public にすると最初の `--initial` を含む過去の snapshot が公開されます。可視性を変える前に履歴全体を点検してください。package の version を registry に出していなくても、Git の snapshot が非公開になるわけではありません。

## 2. 元のファイルを検証して commit する

必要に応じて、プロジェクトの test、format、lint、package の検査、文書の build を行います。pytest と MkDocs を使う構成での例:

```sh
uv run pytest -q
uv run mkdocs build --strict
```

送るファイルと設定、禁止語の一覧を commit します。noren はすべてを指定した commit から読みます。working directory の修正は古い tag に反映されません。`noren.yaml` を足す前の tag からは設定を読めないため、後の commit を選ぶか、設定を含む新しい tag を作ってください。

検分と必要な承認の後に、目的の version の tag を作ります。例:

```sh
git tag v1.2.3
```

VCS から version を導く場合は、tag、package の予定の version、送る commit を揃えます。送り先の commit ID は元の commit ID と異なります。公開済みの tag は動かさず、修正には新しい version を使います。

## 3. dry-run を検分する

送り先の `main` が存在する場合の例:

```sh
noren publish --tag v1.2.3 --message "Release v1.2.3" > /tmp/noren-check.yaml
```

送り先に `main` が無い場合は、dry-run と後の push の両方に `--initial` を加えます。`main` が無い時は必須で、存在する時に付けると止まります。dry-run も送り先の参照を読むために Git のアクセスを必要とします。author を設定していない場合は、GitHub CLI の認証済み account の取得も必要です。

終了コード、標準エラー出力、`source_commit`、`destination`、`author`、`files` の各項目、`destination_main_before` を確かめます。前の snapshot とファイルの増減を比べる例は、[snapshot と test](snapshots-and-tests.md) にあります。検分の出力は公開するファイルの範囲から外してください。

## 4. 検分した snapshot を送る

元のファイルの指定、message、初回の指定を揃え、`--push` だけを足します。

```sh
noren publish --tag v1.2.3 --message "Release v1.2.3" --push
git ls-remote --refs https://github.com/OWNER/public-project.git refs/heads/main refs/tags/v1.2.3
```

成功時は `pushed: true` と送り先の `commit` が出ます。指定した参照がその送り先の commit を示すことを確かめてください。push の成否が不明な場合は、再実行する前に [README の結果の確認手順](https://github.com/sync-dev-org/noren/blob/main/README.ja.md#送った結果を確かめる) に従ってください。`pre-push` など元の Git の hook は動かないため、追加の検査は送る前に行います。

## 5. release する package を build して検査する

公開した送り先の tag を checkout して build する方法を推奨します。選んだファイルと、VCS から version を導くための同じ名前の tag が揃います。それでも build hook はファイルや metadata を追加しうるため、実物を調べます。元のリポジトリで build する場合は、package を作るツールの設定で private の設定や開発用のファイルを別途除外してください。

空の出力先を使い、upload するファイルを特定して検査します。適切な checkout での例:

```sh
uv build
uvx twine check dist/*.tar.gz dist/*.whl
```

archive の path、中身、生成された version、license、metadata、README の link、依存の URL を同じ禁止語の一覧で検査します。[package の検査](package-checks.md) に、noren の検査との違いを説明しています。noren の dry-run が成功しても、sdist と wheel は未検査です。

## 6. 検査した成果物だけを upload する

registry への upload より前に、noren での送信と package の検査を終えます。検査したファイルの名前に置き換えた例:

```sh
uv publish dist/project-1.2.3.tar.gz dist/project-1.2.3-py3-none-any.whl
```

認証は registry が提供する方法を使い、credential をソース、コマンドの引数、log に入れないでください。削除で公開を取り消せるとは限りません。実務報告には、registry で削除したファイルを約 45 時間後も CDN から取得できた一例があります。これは一回の観測であり、registry 全般の保持期間を保証するものではありません。

## 7. tag を確かめて GitHub Release を作る

GitHub Release は、noren が送る tag とは別です。公開用のリポジトリを指定する例:

```sh
gh release create v1.2.3 --repo OWNER/public-project --verify-tag \
  --title "v1.2.3" --notes-file release-notes.md
```

release notes と添付する package は、公開する前に検分します。noren は選んだ snapshot の外のファイルを検査していません。送り先の tag は軽い tag で、snapshot の commit を直接指します。元の注釈付き tag の message はコピーされません。

## 8. 文書と registry の配布ファイルを確かめる

private の開発用リポジトリと public の公開用リポジトリを使う構成では、noren で送った原本から、公開用リポジトリの GitHub Pages で文書を build します。公開する site と検査したファイルを揃えられます。開発用リポジトリからの直接の公開が検査を通らない理由は、[文書の TIPS](snapshots-and-tests.md) に説明しています。

公開側の workflow は noren が `main` を更新すると始まりうるため、完了を待って結果を確かめます。`mkdocs build --strict` は手元の build を検査し、公開は行いません。[GitHub Pages の workflow の文書](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) と [MkDocs の公開方法](https://www.mkdocs.org/user-guide/deploying-your-docs/) も参照してください。

公開した site を開き、README からの link、対応する言語への切り替え、代表的な語での検索を確かめます。registry の version、license、project URL、配布ファイルの SHA-256 を、検査した成果物と照合します。package の頁に表示された README も確認してください。

## version を変えない文書の訂正

新しい version が不要な訂正は commit し、その 16 進の ID を使います。例:

```sh
noren publish --commit a1b2c3d --message "Correct the documentation"
noren publish --commit a1b2c3d --message "Correct the documentation" --push
```

ID は自分のものに置き換えてください。`--commit` は送り先に tag を作らず、package と GitHub Release の公開も行いません。文書は各プロジェクトの手順で公開し、結果を確認します。push の成否が不明な時は再実行前に送り先の `main` を調べてください。送り先の tag による snapshot の重複の防止はありません。
