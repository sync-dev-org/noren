# snapshot と test

## 公開用のリポジトリから文書を公開する

private の開発用リポジトリから public の公開用リポジトリへ noren で送る構成では、MkDocs の文書は、送った原本を使い、公開用リポジトリの GitHub Pages で build して公開します。開発用リポジトリから直接公開すると、noren の選択と禁止語の検査を通らない経路ができ、検査した原本と公開した site が一致しなくなりえます。

site の原本、設定、build に使う依存の lock、Pages の workflow を、送るファイルに含めます。公開の workflow は公開用のリポジトリでだけ動くよう制限してください。`exclude` は `include` より優先されるため、`.github/` 全体を除外すると、送る一覧に加えた workflow も除外されます。issue の template などの private のファイルに除外を絞り、dry-run の実際の選択を確かめます。

noren 自身の文書は、公開用リポジトリの workflow が `uv sync --locked --no-install-project` で依存を入れ、`uv run --locked --no-sync mkdocs build --strict` で両言語を build し、Pages の成果物を公開します。同じ build を公開側の checkout からも実行でき、private の設定は必要ありません。[GitHub の Pages の workflow](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) も参照してください。

公開用のリポジトリでだけ動く workflow は、noren で送った後に初めて動きます。そのため、存在しない action の参照は、手元の build と test では見つかりません。送る前に、各 `uses:` の参照が action のリポジトリに実在することを、たとえば `git ls-remote https://github.com/<owner>/<action> <ref>` で確かめます。major の version の tag があると決めてかからないでください。正確な version の tag だけを出す action があり、`astral-sh/setup-uv@v9.0.0` は解決できても `astral-sh/setup-uv@v9` は解決できません。action を commit の SHA で固定する場合は、workflow を書く時に tag から SHA を引き、version を注記に残します。存在しない tag は、公開の時ではなくその時点で失敗します。

## 公開の文書に開発の内情を載せない

公開する site と README は、公開側の利用者に向けて書きます。secret と認証の情報、開発環境の構成、host の名前、内部の path、開発用 tool の設定、private のリポジトリの名前、内部の手順を載せないでください。公開した物だけで再現できる使い方を説明します。

内部の名前は、除外する禁止語の一覧に入れ、公開前に noren で選んだ原本を検査します。公開する各ファイルも読んでください。禁止語の一覧だけでは、すべての機微情報を見つけたり、文書全体を公開してよいと証明したりはできません。private の報告、内部の link、log、実際の設定値を、公開する説明にコピーしないでください。

## 新しいファイルを見落とさずに path を分類する

`/src/`、`/tests/`、`/docs/` のように root に固定した directory の規則は、その下のファイルの変更に同じ分類を適用できます。新しい top-level path は、`include` か `exclude` を決めるまで未分類になります。開発用の指示、private の script、設定、禁止語の一覧は明示的に除外します。両方の一覧に当たる場合は除外が優先されます。

`noren init` が書いた元の URL とリポジトリの名前は、禁止語の一覧に残します。private の依存、application、package、host の識別子も加えます。一覧には comment の書式がありません。`#` で始まる行も、空白でなければ禁止する文です。

tag と commit ID を選ぶ前に修正を commit します。古い tag は新しい設定を読みません。必須の key `branch` は送り先の branch と、送る commit を含む元の local branch の両方を指定し、remote-tracking branch では代用できません。`noren init` は `branch: main` を入れますが、既存の設定にもこの key が必要です。設定した名前だけを信用せず、`destination` と `branch` が予定の公開先かを確かめてください。

送り先に branch が無い場合は、親無しの commit にする `--initial` か、送り先の既存の tag を基点にする `--base-tag <tag>` のどちらかを使い、dry-run と push に同じ option を付けます。二つを同時に指定した場合、既に branch がある時にどちらかを付けた場合、基点の tag が無い場合、その tag が commit 以外の object を指す場合は止まります。既存の公開済み release から分ける例は、[保守する系列の公開](publication-workflow.md#publish-a-maintenance-series) を参照してください。

## dry-run のファイルと送り先の snapshot を比較する

成功した dry-run の YAML を保存し、`files` を設定した送り先の branch の checkout と比べます。`../public-checkout` をその checkout に、`main` を出力の `branch` に置き換えた例:

```sh
noren publish --commit a1b2c3d --message "Review snapshot" > /tmp/noren-check.yaml
git -C ../public-checkout fetch origin main
git -C ../public-checkout ls-tree -rz --name-only origin/main > /tmp/noren-previous-files
```

元の commit ID も置き換えてください。PyYAML を入れた環境で実行します。

```sh
python - <<'PY'
from pathlib import Path
import yaml

result = yaml.safe_load(Path("/tmp/noren-check.yaml").read_text())
selected = set(result["files"])
previous = set(Path("/tmp/noren-previous-files").read_bytes().decode().split("\0")) - {""}
print("Added:", sorted(selected - previous))
print("Removed:", sorted(previous - selected))
PY
```

増減を一つずつ点検します。先に fetch することで、古い local branch との比較を避けられます。最初の snapshot は、`--initial` なら空のファイル集合、`--base-tag` なら送り先の tag の tree と比較してください。送った後は、出力された送り先の commit の tree が選んだ path だけを持つことを確かめます。branch が進んだ場合は送り先の履歴を調べてください。ファイル集合の一致は、中身の検査や過去の snapshot の消去ではありません。

## noren の内部 module を import せずに設定を test する

noren の安定した使い方はコマンドと YAML の出力です。Python の module は内部の物で、version の間で変わりえます。noren の内部 module を import せず、自分の設定と禁止語の data を test してください。dry-run は結合の検査です。commit 済みの tree と送り先への Git のアクセスが必要で、GitHub CLI の account の取得が必要になる場合もあります。未 commit の変更は読まず、offline の unit test にはなりません。

公開する test に private の名前を直書きしたり、文字列を分割して検査を回避したりしないでください。その名前は、除外した禁止語の一覧から読みます。`tests/` の直下の pytest の module での例:

```python
from pathlib import Path
import pytest

word_list = Path(__file__).resolve().parents[1] / "noren-words.txt"
if not word_list.is_file():
    pytest.skip("Source-only word list is absent", allow_module_level=True)
forbidden_words = [
    line.strip()
    for line in word_list.read_text(encoding="utf-8").splitlines()
    if line.strip()
]
```

必要な検査でこの値を使います。公開側の checkout に除外した入力が無い場合は、元のリポジトリに固有の test だけを skip し、通常の package の test は実行してください。元のリポジトリで設定が消えた場合まで黙って skip せず、元のリポジトリの検証でその test が実行されることを確かめます。[package の中身](package-checks.md) の約束は、実際に build した package で test してください。

## 既存の公開方法から移行する

同じ元の commit で、従来の方法が選ぶファイル集合と noren の dry-run の `files` を比べます。送る前に増減の理由を説明できる状態にしてください。package の収録ファイルも別に比較します。生成 metadata が差になる場合もありますが、その中身の検査は必要です。選んだファイルだけの directory で必要な test を実行すると、private の入力への依存を見つけられます。

更新後は `noren --version` を確認し、予定の commit で dry-run を繰り返します。報告された 0.2 から 0.3 への更新では設定を変えずに済みましたが、すべての構成の互換性の保証ではありません。現在の `--commit` は一意に決まる 16 進の省略形を受け付けます。未確認の旧 version の記憶を、完全な ID が必要という規則にしないでください。

元のリポジトリを改名し、旧名を公開用リポジトリに使う場合は、公開前に管理下の clone の remote URL を調べてください。旧名が改名後の元のリポジトリへ転送されず、新しい公開用リポジトリを指した実務報告があります。checkout を移した後に仮想環境の script が古い path を指す場合は、依存を管理するツールで仮想環境を作り直します。これらは環境に関する観測であり、noren が実行する操作ではありません。
