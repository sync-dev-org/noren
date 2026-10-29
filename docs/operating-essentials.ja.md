# 運用の要点

この推奨は、noren で公開する複数のリポジトリから集めた運用を材料にしています。自分たちの release の手順を作る出発点であり、すべての構成に当てはまる規則ではありません。[他の説明の使い方](index.md) と同じく、利用する build backend、registry、承認の手順に合わせてください。

採用する方針は、各プロジェクトが自分たちの公開や開発の文書に書き、決めた根拠も記録します。共通する方針は、別のプロジェクトの文書の項目の ID に頼らず、その文書だけで読めるように書きます。

## 開発と公開を別のリポジトリで行う

開発は private の元のリポジトリで行います。別に public の公開用リポジトリを用意し、noren が送る snapshot だけを受け、そこで直接開発しないようにします。これにより、公開する中身を、元のリポジトリでのファイルの選択と検分に従わせられます。

公開用リポジトリの可視性の変更は、その所有者が判断する操作として扱います。public にすると、以前の snapshot も公開されます。変更前の点検は、[公開の流れ](publication-workflow.md) に説明しています。

## noren を tool として入れる

noren をプロジェクトの依存に含めず、tool として入れ、`noren` を直接実行します。

```sh
uv tool install noren
```

## 公開する物をすべて検査する

公開用のリポジトリ、文書、配布物には、利用側の application や案件の名前、private のリポジトリの名前と URL、host 名、開発の経緯、開発用の記録を載せないようにします。それらの識別子を、公開対象から除外した禁止語の一覧に加え、公開するファイルも検分してください。開発の内情を公開しないための説明は、[snapshot と test](snapshots-and-tests.md) にあります。

noren が検査しない物にも、同じ禁止語の一覧を使います。sdist と wheel の中身、archive 内のファイル名、生成された metadata、GitHub Release の本文も対象です。NFKC 正規化と case folding の後に、部分一致で検査します。[package の検査](package-checks.md) に、実際の archive を検査する方法があります。noren の dry-run の成功が示すのは、選んだ Git のファイルの検査だけです。

## version と公開済みの配布物を変えない

release の tag は、`v1.2.3` のように、distribution の名前を付けない `vX.Y.Z` にします。新しい release の version は、直前に公開した version より進めます。

公開済みの tag、GitHub Release、package registry のファイルは、動かさず、書き換えず、消さないようにします。失敗した公開の修正を含め、release の修正は新しい version で出します。失敗を調べる間も、すでに公開した配布物は変更しません。

## 公開の各段階を検分して結果を確かめる

release の tag が指す決まった commit から build します。build の起点は、公開用リポジトリに何を送るかで分かれます。

- 公開用リポジトリが source と build の設定を受け取る構成では、公開した送り先の tag を checkout して build できます。[公開の流れの節 5](publication-workflow.md#5-release-package-build) を参照してください。
- 公開用リポジトリが `README.md` や `LICENSE` などの文書だけを受け取り、package を GitHub Release と registry で配る構成では、送り先で package を build できません。元のリポジトリに tag を置き、その tag から build して package を検査した後に、noren で snapshot を送ります。

どちらの構成でも、noren の dry-run を検分してから送り、snapshot の公開と package の検査を終えてから package を配布します。公開用リポジトリの GitHub Release の添付ファイルと package registry には、検査した同じ bytes のファイルを置きます。両方の取得先からファイルを取り直し、SHA-256 を検査済みの元のファイルと照合します。個々の検査は、[公開の流れ](publication-workflow.md) と [package の検査](package-checks.md) に説明しています。

どこかで失敗した時や結果を確かめられない時は、次の段階へ進まずに止まります。公開先の状態を調べ、同じ操作を自動で繰り返さないようにします。

## credential は upload の process だけに渡す

registry の credential は、upload を行う process にだけ渡します。値をソース、コマンドの引数、log に入れないでください。credential が環境変数にある shell では、`uv publish --help` のように、その値を表示しうるコマンドを実行しません。credential の値を表示せずに認証する方法を用意します。

## 検分した原本から文書を公開する

公開用リポジトリの GitHub Actions が、noren で送った原本から文書を build し、そのリポジトリの GitHub Pages に公開する構成にします。private の開発用リポジトリには Pages を置きません。ファイルの選択と workflow の確認は、[snapshot と test](snapshots-and-tests.md) に説明しています。

GitHub Actions の用途は、その文書の site の build と公開に限ります。test、build の検証、package registry への upload は、Actions の外で行います。workflow は secret を使わず、権限を `contents: read`、`pages: write`、`id-token: write` に限ります。これらの制限により、公開する site を検査した原本に対応させ、自動化する操作と権限を文書の公開に必要な範囲に絞れます。

## 配布物に依存するプロジェクトの担当者へ知らせる

公開を検証した後、その配布物に依存するプロジェクトの担当者に、公開した version と取得先を知らせます。確認済みの公開の取得先を伝えると、担当者は検証済みの release を使って依存を更新できます。
