# noren を使う公開

noren は、選んだファイルを別の Git リポジトリへ一つの commit として送ります。package の upload、GitHub Release、文書の site の公開は、それぞれ別の操作です。この文書は、それらの操作を組み合わせる流れと、公開する物を確かめる箇所を説明します。

入れ方、初期セットアップ、コマンドの使い方、結果の各項目は、[README](https://github.com/sync-dev-org/noren/blob/main/README.ja.md) を参照してください。コマンドの help は次の形で読めます。

```sh
noren --help
noren init --help
noren publish --help
```

## 目的に合わせて読む

- [運用の要点](operating-essentials.md): 開発と公開の分担、公開する物の検査、release の扱いについての推奨。
- [公開の流れ](publication-workflow.md): 準備から registry と文書の公開後の確認まで、推奨する順序。
- [package の検査](package-checks.md): sdist と wheel の中身、生成された metadata、private の識別子、公開後の配布ファイルの検査。
- [snapshot と test](snapshots-and-tests.md): 送るファイルの比較、network を使わない設定の test、既存の公開方法からの移行。

## 推奨の使い方と根拠の範囲

推奨は、2026 年 10 月に集めた公開実務の報告を材料にしています。主な構成は noren 0.2〜0.3、uv、Hatchling、hatch-vcs です。すべての構成に共通する手順として独立に再現したものではありません。観測した一例や原因の推測にとどまる箇所には、その範囲を記します。build backend や registry の設定が違えば、挙動も変わりえます。

各コマンドは例です。利用するプロジェクト、version、送り先、build backend、registry、承認の手順に合わせてください。各プロジェクトに固有の release の手順を定めるものではありません。利用するツールの現在の文書も確認してください。

英語版と日本語版には、それぞれ同じ内容の五つのページがあります。言語を選ぶと、読んでいるページの対応する翻訳を開けます。

## この文書を手元で読む

uv を入れた環境で noren の checkout から実行します。

```sh
uv sync --locked
uv run --locked mkdocs build --strict
uv run --locked mkdocs serve
```

一つの MkDocs の設定から、英語を site の root に、日本語を `ja/` の下に作ります。Material for MkDocs と mkdocs-static-i18n を使い、依存の version は `uv.lock` に記録しています。
