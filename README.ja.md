# noren

[English](README.md) · [文書の site](https://sync-dev-org.github.io/noren/ja/)

noren は、Git リポジトリで選んだファイルを別のリポジトリへ一つの commit として送るコマンドです。パッケージのレジストリへの公開は行いません。

例えば、private のリポジトリから公開するファイルを選び、GitHub に送るために使います。送り先には、選んだファイル、指定した commit message、設定した author と committer が置かれます。元の commit、その message、注釈付き tag の message はコピーされません。選んだファイルの path と中身はコピーされます。

## インストールと実行方法

Python 3.12 以上、Git、[uv](https://docs.astral.sh/uv/) が必要です。コマンドは元の Git リポジトリの中で実行します。

noren を tool として入れ、`noren` を直接実行します。

```sh
uv tool install noren
noren --help
```

代わりに、Python プロジェクトの開発時の依存として noren を追加することもできます。

```sh
uv add --dev noren
uv run noren --help
```

この方法を選んだ場合は、以下の各 `noren ...` の前に `uv run` を付けてください。

プロジェクトの依存に追加せずに使う場合は、[uvx](https://docs.astral.sh/uv/guides/tools/) で隔離された実行環境から起動することもできます。

```sh
uvx noren --help
```

uvx を選んだ場合は、以下の各 `noren ...` の前に `uvx` を付けてください。

以下の例は `noren` を直接実行します。`noren init` と `noren publish` は対話の入力を求めません。

入っている version は `noren --version` で確認できます。Git の tag から導いた version を一行で出し、終了コード 0 で終わります。Git リポジトリの外でも実行できます。

tool として入れた noren の version を上げるには、`uv tool upgrade noren` を実行します。特定の version を入れるには、`uv tool install noren==X.Y.Z` の `X.Y.Z` を必要な version に置き換えてください。更新時も、インストール時に指定した version の制約が保たれます。

## 初期セットアップ

元のリポジトリには remote の `origin` が必要です。GitHub に別の送り先リポジトリを作り、普段使っている Git の認証で読み取りと push ができるようにしてください。noren は、既存の Git の設定で `https://github.com/OWNER/REPO.git` にアクセスします。

```sh
noren init
```

`noren init` は引数を取らず、元のリポジトリの root に `noren.yaml` と `noren-words.txt` を作ります。サブディレクトリから実行した場合も同じです。成功時は設定の案内を標準出力に出し、終了コード 0 で終わります。失敗時は理由を標準エラー出力に出し、0 以外で終わります。どちらかのファイルがすでにあれば上書きせずに止まり、`origin` が無い場合はどちらのファイルも作りません。

### noren.yaml を設定する

生成された雛形を編集します。次の例は `README.md`、`LICENSE`、`src/` の下のファイルを送り、`src/internal/` は外します。`OWNER/public-project` は送り先に置き換えてください。

```yaml
destination: OWNER/public-project
include: |
  README.md
  LICENSE
  src/
exclude: |
  src/internal/
  private/
  tests/
  .github/
  .nf/
  .gitignore
  pyproject.toml
  uv.lock
  noren.yaml
  noren-words.txt
word-list: noren-words.txt
author:
  name: Release Bot
  email: release@example.invalid
```

| key | 書く内容 |
| --- | --- |
| `destination` | 送り先の GitHub の `OWNER/REPO`。URL ではありません。元のリポジトリ自身を指定すると止まります。 |
| `include` | 送るファイルの一覧。`.gitignore` の書式のまま、複数行の文字列で書きます。 |
| `exclude` | 送らないファイルの一覧。同じ書式で書きます。両方の一覧に当たるファイルは `exclude` が優先されます。 |
| `word-list` | 禁止語の一覧のファイルの path。リポジトリの root からの相対 path で、リポジトリの中のファイルを指定します。 |
| `author` | 任意の `name` と `email`。送り先の commit の author と committer の両方に使います。例の値は利用する名義に置き換えてください。 |

指定した元の commit の tree にあるファイルは、すべて `include` または `exclude` に当たる必要があります。どちらにも無いファイルがあると、コマンドは止まります。一覧の対象はその commit に記録されたファイルで、working directory の未追跡のファイルは対象にしません。各一覧は Git の `.gitignore` の規則に従い、`#` の comment、`!` の否定、`/` による root への固定、`**` を使えます。同じ一覧の中では後に書いた一致する規則が優先されます。親のディレクトリが除外されたままでは、子のファイルを否定の pattern だけで戻すことはできません。

設定ファイルと禁止語の一覧のファイルは `exclude` に残し、リポジトリの他の追跡するファイルも一覧に加えてください。`word-list` を変えた場合は、そのファイルの除外も更新します。必須の四つの key はすべて必要です。`include` または `exclude` を空の文字列として設定することはできますが、どのファイルも分類する必要があります。

`author` を省いた場合、noren は [GitHub CLI](https://cli.github.com/) の `gh` が使える時に、認証済み account の名前 (名前が空なら username) と `ID+USERNAME@users.noreply.github.com` を使います。account を取得できない場合は止まり、`author.name` と `author.email` の設定を求めます。`gh` は任意で、この既定の名義を作るためだけに使います。push の認証は Git の設定を使います。

SSH の認証を使う場合は、この元のリポジトリの中で GitHub の HTTPS URL を書き換えるよう Git に設定できます。

```sh
git config --local url."git@github.com:".insteadOf https://github.com/
```

### noren-words.txt を設定する

禁止する語や文を一行に一つずつ書きます。生成されたファイルには、元の `origin` の URL とリポジトリの名前が入っています。その二つを残し、送るファイルの中身に含まれてはいけない識別子や文を加えてください。例えば、`origin` が `git@github.com:OWNER/source-private.git` の場合:

```text
git@github.com:OWNER/source-private.git
source-private
internal-project
private@example.invalid
```

一覧には空白でない行が一つ以上必要です。`#` で始まる行も含め、空白でない行はすべて禁止語になります。禁止語の一覧には comment の書式はありません。noren は Unicode の NFKC 正規化と case folding の後に部分一致で探すため、大文字と小文字の違い、全角の表記でも当たります。UTF-8 として読めない byte は、検査の際に置き換え文字として扱います。送るファイルの byte は元のままです。

### 設定を commit してから tag または commit ID を指定する

noren は、`--tag` または `--commit` が指す commit から、送るファイル、`noren.yaml`、禁止語の一覧を読みます。working directory や後の commit で変更しても、その commit の検査や送信には反映されません。

送る予定の元のファイルを commit した後、設定を commit します。

```sh
git add noren.yaml noren-words.txt
git commit -m "Configure noren"
```

送り先にも同じ名前の tag を付けたい場合は、`--tag` を使います。

```sh
git tag v1.0.0
```

README の訂正のように version を上げない変更は、`--commit` を使うと送り先に tag を付けずに送れます。`git rev-parse HEAD` で元の commit ID を取得し、出力された ID を `--commit` に渡します。指定できるのは 16 進の commit ID と一意に決まる省略形です。`HEAD`、branch の名前、tag の名前、存在しない ID、曖昧な省略形を指定すると止まります。

検査で止まった後に設定やファイルの中身を直した場合は、修正を commit し、その修正を含む tag または commit ID を選んでから、もう一度検査してください。

## 送る前に確認する

`noren publish` の既定の動作は dry-run です。`--tag` と `--commit` はどちらか一方が必須で、両方を指定した時とどちらも指定しない時は止まります。検査の場合も `--message` は必須です。最初の一回で、送り先に `main` branch が無い場合:

```sh
noren publish --tag v1.0.0 --message "Release v1.0.0" --initial
```

送る一覧に当たるファイルが `README.md` と `src/app.py` の二つだけの tag なら、最初の検査の成功時に次の結果を出します。

```yaml
tag: v1.0.0
source_commit: 0123456789abcdef0123456789abcdef01234567
destination: OWNER/public-project
author:
  name: Release Bot
  email: release@example.invalid
files:
- README.md
- src/app.py
destination_main_before: null
commit: null
pushed: false
```

`source_commit`、`destination`、`author` の値と、`files` の各 path を確認してください。出力の `author.name` と `author.email` は、送り先の commit の author と committer の両方に使う値です。dry-run は送り先の commit を作らず、送り先の branch と tag を更新しません。ただし、送り先の参照を読むので、Git のアクセスが必要です。dry-run の成功は push の権限を保証しません。

検査が成功すると、コマンドは終了コード 0 で終わります。どちらの一覧にも無いファイルがある場合、送る中身に禁止語がある場合、必須の設定や語を含む禁止語の一覧が無い場合、送り先を読めない場合などは、0 以外で終わり、理由を標準エラー出力に出します。未分類のファイルのエラーは path を示し、禁止語のエラーはファイルと行を示します。送る一覧に当たる submodule は除外する必要があります。symlink はリンク先の文字列を検査し、symlink のまま送ります。

tag 指定でも commit ID 指定でも、dry-run と push のどちらも、送り先に `main` が無い時だけ `--initial` を使います。`--initial` があって `main` が存在する場合と、`--initial` が無く `main` が存在しない場合は止まります。`--tag` を使う時は、送り先に指定した名前の tag がすでにある場合も止まります。

## 確認したファイルを送る

確認したコマンドに `--push` を加えます。

```sh
noren publish --tag v1.0.0 --message "Release v1.0.0" --initial --push
```

最初の一回は、親の無い commit を作ります。次からは、送り先の直前の `main` の先端だけを親にした commit を一つ足します。その tree は選んだ元のファイルだけを持ち、選んだ一覧に無いファイルは新しい送り先の tree に残りません。`--tag` を使う時は、送り先の `main` と元の tag と同じ名前の tag を、force を使わず、一回の atomic push で一緒に更新します。送り先の tag は軽い tag (注釈付きではない tag) で、元の tag が注釈付きでも、新しい commit を直接指します。`--commit` を使う時は、送り先の `main` だけを更新し、tag を付けません。

次の元の tag を送る時は `--initial` を外します。

```sh
noren publish --tag v1.1.0 --message "Release v1.1.0"
noren publish --tag v1.1.0 --message "Release v1.1.0" --push
```

README の訂正を tag 無しで送る場合は、次の ID を元の commit ID に置き換え、同じ ID で検査と送信を行います。

```sh
noren publish --commit a1b2c3d --message "Correct the README"
noren publish --commit a1b2c3d --message "Correct the README" --push
```

送り先の `main` がまだ無い場合は、両方のコマンドに `--initial` を加えます。`--commit` を使う時は、結果の `tag` は `null` になり、省略形の ID を指定した場合も `source_commit` は完全な ID になります。

送るファイルに合った送り先の commit message を指定してください。noren は元の commit message の代わりに、その message を使います。

## 送った結果を確かめる

`noren publish` は成功時も失敗時も、一つの YAML 文書を標準出力に出します。その文書と標準エラー出力を保存し、終了コードを確認してください。上の次回の push の出力を保存する場合は、その push のコマンドの代わりに次の形を使います。

```sh
noren publish --tag v1.1.0 --message "Release v1.1.0" --push > /tmp/noren-result.yaml 2> /tmp/noren-error.txt
```

| key | 意味 |
| --- | --- |
| `tag` | 指定した元の tag の名前。`--commit` の時は `null`、どちらの指定も取得できない場合は空の文字列です。 |
| `source_commit` | 送る file を取り出した元の commit の完全な ID。commit を決める前に止めた時は `null` です。 |
| `destination` | 送り先の `OWNER/REPO`。取得できない場合は空の文字列です。 |
| `author` | 送り先の commit の author と committer の両方に使う、解決した `name` と `email`。名義を決める前に止めた時は `null` です。 |
| `files` | 選んだファイルの path の YAML の list。空の場合もあります。この一覧だけでは検査や push の成功は分かりません。 |
| `destination_main_before` | 送る前に読んだ送り先の `main` の commit の ID。`null` は送り先を読めて `main` が無かった場合、`''` は値を取得できなかった場合です。 |
| `commit` | 作った送り先の commit の ID。dry-run の時と、commit を作る前に止めた時は `null` です。 |
| `pushed` | Git が送り先の `main` と、`--tag` の時は指定した tag の更新を成功と報告した場合は `true`。dry-run の時と、コマンドが push の成功を確認できなかった場合は `false` です。 |

push の成功時は終了コードが 0 で、`pushed: true` となり、`commit` は `null` 以外の値になります。この ID は送り先の commit の ID で、元の commit の ID ではありません。

push が失敗した場合や結果が不明な場合に、`commit` が `null` 以外なら、その ID と `destination_main_before` を残してください。`pushed: false` だけでは、送り先が更新を受け取ったかは決まりません。結果にあるリポジトリと tag に例を置き換え、送り先の参照を読みます。

```sh
git ls-remote --refs https://github.com/OWNER/public-project.git refs/heads/main refs/tags/v1.1.0
```

両方の参照が出力された `commit` の ID を示す場合、更新は送り先にあります。その後に `main` が進んだ場合も、tag が同じ ID なら送った時のファイルを特定できます。送り先の履歴を見て、その commit が現在の `main` の祖先かを確かめてください。`main` が `destination_main_before` のままで tag が無い場合、確認した時点では更新がありません。他の値になっている場合は、送り先の履歴を調べてから次の操作を決めてください。`ls-remote` の失敗では、push の成否は分かりません。終了コードだけで結果を決めたり、初回のコマンドをそのまま繰り返したりしないでください。すでに `main` や tag があれば、コマンドは止まります。

`tag` が `null` の場合は、`main` だけを読みます。

```sh
git ls-remote --refs https://github.com/OWNER/public-project.git refs/heads/main
```

`main` が出力された送り先の `commit` の ID と同じなら、更新は送り先にあります。その後に `main` が進んだ場合は、送り先の履歴を見て、その commit が現在の `main` の祖先かを確かめてください。`main` が `destination_main_before` のままなら、確認した時点では更新がありません。commit ID で送る時は送り先の tag による重複の防止が無いので、結果が不明な場合は成否を確かめてからコマンドを繰り返してください。

## コマンドの help

```sh
noren --help
noren init --help
noren publish --help
```

コマンドの help は英語です。この README は初期セットアップ、検査、送信、結果の確認を扱います。プロジェクトの version の変更、build、パッケージのレジストリへの公開は、そのプロジェクトの release の手順を参照してください。

一般的な公開の流れ、package の検査、落とし穴、TIPS は、[文書の site](https://sync-dev-org.github.io/noren/ja/) を参照してください。
