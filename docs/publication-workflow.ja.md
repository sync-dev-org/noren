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

`noren.yaml` の必須の key `branch` に送り先の branch 名を書いて commit します。送る commit は、元の同名の local branch に含まれる必要があり、remote-tracking branch では代用できません。key が無い時、local branch が無い時、その branch に commit が含まれない時は止まります。以下は `branch: main` を設定し、送り先に `main` が存在する例です。

```sh
noren publish --tag v1.2.3 --message "Release v1.2.3" > /tmp/noren-check.yaml
```

送り先に branch が無い場合は、dry-run と後の push の両方に `--initial` (親無し) か `--base-tag <tag>` (送り先の既存の tag が指す commit を親にする) のどちらか一方を加えます。branch が既にある時はどちらも使えず、二つを同時に指定することもできません。基点の tag は送り先に存在し、直接または注釈付き tag を介して commit を指す必要があり、noren は送り先から取得します。dry-run も送り先の参照を読むために Git のアクセスを必要とします。author を設定していない場合は、GitHub CLI の認証済み account の取得も必要です。

終了コード、標準エラー出力、`source_commit`、`destination`、`branch`、`author`、`files` の各項目、`destination_branch_before` を確かめます。YAML は失敗時も九つの key を持ち、`branch` は設定から名前を得るまで null、`destination_branch_before` は送り先に branch が無い時は null、未読なら空の文字列です。前の snapshot とファイルの増減を比べる例は、[snapshot と test](snapshots-and-tests.md) にあります。検分の出力は公開するファイルの範囲から外してください。

## 4. 検分した snapshot を送る

元のファイルの指定、message、初回の指定を揃え、`--push` だけを足します。

```sh
noren publish --tag v1.2.3 --message "Release v1.2.3" --push
git ls-remote --refs https://github.com/OWNER/public-project.git refs/heads/main refs/tags/v1.2.3
```

成功時は `pushed: true` と送り先の `commit` が出ます。例の `main` を出力の `branch` に置き換え、指定した参照がその送り先の commit を示すことを確かめてください。`--tag` は branch と tag を force を使わずに一回の atomic push で一緒に更新し、`--commit` は branch だけを更新します。push の成否が不明な場合は、再実行する前に [README の結果の確認手順](https://github.com/sync-dev-org/noren/blob/main/README.ja.md#送った結果を確かめる) に従ってください。`pre-push` など元の Git の hook は動かないため、追加の検査は送る前に行います。

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

公開側の workflow は noren が発火対象の branch を更新すると始まりうるため、完了を待って結果を確かめます。保守用の snapshot を送る前に、workflow がどの branch から公開するかを確認してください。`mkdocs build --strict` は手元の build を検査し、公開は行いません。[GitHub Pages の workflow の文書](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) と [MkDocs の公開方法](https://www.mkdocs.org/user-guide/deploying-your-docs/) も参照してください。

公開した site を開き、README からの link、対応する言語への切り替え、代表的な語での検索を確かめます。registry の version、license、project URL、配布ファイルの SHA-256 を、検査した成果物と照合します。registry が公開する package の紹介画面で、README の表示も確認してください。

## version を変えない文書の訂正

新しい version が不要な訂正は commit し、その 16 進の ID を使います。例:

```sh
noren publish --commit a1b2c3d --message "Correct the documentation"
noren publish --commit a1b2c3d --message "Correct the documentation" --push
```

ID は自分のものに置き換えてください。`--commit` は送り先に tag を作らず、package と GitHub Release の公開も行いません。文書は各プロジェクトの手順で公開し、結果を確認します。push の成否が不明な時は再実行前に設定した送り先の branch を調べてください。送り先の tag による snapshot の重複の防止はありません。

<a id="publish-a-maintenance-series"></a>

## 保守する系列を公開する

2.x が `main` で進んだ後も 1.x を保守するには、元の最後の 1.x release から `v1` などの local branch を作ります。

```sh
git switch -c v1 v1.2.3
```

`noren.yaml` の他の設定を残して `branch` だけを `v1` に直し、保守する修正とともに commit してから、新しい元の tag を選びます。

```yaml
branch: v1
```

```sh
git add noren.yaml
git commit -m "Configure maintenance publication branch"
git tag v1.2.4
```

受け継いだ `branch: main` は必ず直します。保守用の branch にしか無い commit は元の local の `main` に含まれず、照合で止まります。古い共通の祖先は両方の branch に含まれることがあるため、設定した名前と dry-run の `branch` も確認してください。

送り先に `v1` が無く、送り先の tag `v1.2.3` が最後の公開済み 1.x release を指す場合は、その tag を親にして最初の保守用の snapshot を検査し、送ります。

```sh
noren publish --tag v1.2.4 --message "Release v1.2.4" --base-tag v1.2.3
noren publish --tag v1.2.4 --message "Release v1.2.4" --base-tag v1.2.3 --push
git ls-remote --refs https://github.com/OWNER/public-project.git refs/heads/v1 refs/tags/v1.2.4
```

`branch: v1` と `destination_branch_before: null` を確認します。新しい送り先の commit は送り先の tag の commit だけを親に持ち、送り先の `main` は変わりません。意図して親無しにしたい場合だけ、代わりに `--initial` を使います。基点の tag が無い場合や commit 以外の object を指す場合は、dry-run も push も止まります。

次の保守用の tag を送る時は `branch: v1` を保ち、初回の二つの option はどちらも付けません。送り先の既存の `v1` の先端に commit を足します。送り先に tag が不要な訂正には `--commit` を使います。公開した tag から package を build して検査し、既存の tag を使って公開用リポジトリに GitHub Release を作ります。例:

```sh
gh release create v1.2.4 --repo OWNER/public-project --verify-tag \
  --title "v1.2.4" --notes-file release-notes.md
```

noren が送るのは branch と tag です。package の upload、GitHub Release、文書の公開は、引き続き各プロジェクトの release の手順で行います。
