# package の検査

noren は、指定した Git の commit から選んだファイルの中身を検査します。package の archive、archive 内のファイル名、build backend が生成したファイルは検査しません。sdist の `PKG-INFO`、wheel の `METADATA`、生成された version のファイルは、別途検査する必要があります。

## package に private の設定を入れない

commit した禁止語の一覧には、外に出したくない識別子が並びます。`noren.yaml` で除外しても、その設定は Git の snapshot にだけ効きます。元のリポジトリから build する sdist と wheel の収録範囲は変わりません。

送り先の tag を checkout し、それを build の入力にする方法を推奨します。元のリポジトリから build する必要がある場合は、build backend のファイルの選択も設定します。Hatchling での例:

```toml
[tool.hatch.build.targets.sdist]
exclude = ["/noren.yaml", "/noren-words.txt"]
```

この例は二つのファイルを除外し、他のすべてのファイルを公開してよいことは保証しません。実務報告には、Hatchling の収録範囲を絞る前の sdist に、開発用の指示や directory が入った事例があります。すべての backend の既定の挙動を示す観測ではありません。

明示的な選択を使う構成もあります。例:

```toml
[tool.hatch.build.targets.sdist]
only-include = ["src", "tests", "README.md", "LICENSE", "pyproject.toml"]
```

必要な data を含め、自分の package に合う path を選んでください。`only-include` ですでに設定を外している場合、その設定の除外を足しても、archive の他の中身の正しさは証明できません。build hook、artifacts、強制的な追加も収録範囲に影響しえます。それらの設定と生成されたファイルを調べてください。[Hatchling のファイル選択の文書](https://hatch.pypa.io/latest/config/build/#file-selection) も参照してください。

## build した実物を検査する

古い成果物を誤って upload しないよう、空の出力先で build します。名前と version が正しく見えても、sdist と wheel の両方を検査してください。

1. archive 内のファイル名をすべて列挙し、開発用のファイル、設定、予期しない data、path に含まれる private の名前を確認します。
2. 除外した禁止語の一覧を使い、各ファイルの名前と中身を NFKC 正規化と case folding の後に照合します。生成された metadata と version のファイルも含めます。
3. package の metadata、予定の version、license と同梱 data の license、依存、公開用の project URL と文書の URL を確認します。
4. 公開する `pyproject.toml` と lock に、private の Git URL、local path、private の package の取得元が無いことを調べます。code に private の名前が無くても、これらが残ることがあります。
5. 配布 metadata と表示された README を確認します。registry がリポジトリへの相対 link と画像を解決できない場合は、公開先の絶対 link か同じ頁の anchor を使います。

次は、空の `dist/` に作った Python の sdist と wheel の検査の例です。除外した禁止語の一覧がある元のリポジトリで実行し、`dist/` には検査する成果物だけを置いてください。archive は展開せずに読み、ファイルの path を報告します。path に private の名前が含まれうるため、その出力は公開しないでください。部分一致の検査であり、一般的な secret の検出や license の監査ではありません。

```sh
python - <<'PY'
from pathlib import Path
import tarfile
import unicodedata
import zipfile

def normalized(text):
    return unicodedata.normalize("NFKC", text).casefold()

words = [
    normalized(line.strip())
    for line in Path("noren-words.txt").read_text(encoding="utf-8").splitlines()
    if line.strip()
]
artifacts = sorted(Path("dist").glob("*.tar.gz")) + sorted(Path("dist").glob("*.whl"))
if not words or not artifacts:
    raise SystemExit("A nonempty word list and built artifacts are required")

failures = []

def inspect(artifact, name, data):
    text = normalized(name + "\n" + data.decode("utf-8", errors="replace"))
    if any(word in text for word in words):
        failures.append(f"{artifact.name}: {name}")

for artifact in artifacts:
    if artifact.suffix == ".whl":
        with zipfile.ZipFile(artifact) as archive:
            for member in archive.infolist():
                inspect(artifact, member.filename, archive.read(member))
    else:
        with tarfile.open(artifact) as archive:
            for member in archive:
                stream = archive.extractfile(member) if member.isfile() else None
                data = stream.read() if stream else member.linkname.encode()
                inspect(artifact, member.name, data)

if failures:
    raise SystemExit("Forbidden content in:\n" + "\n".join(failures))
print(f"Checked {len(artifacts)} artifacts")
PY
```

upload の前に、プロジェクトに必要な追加の検査を行います。例:

```sh
uvx twine check dist/*.tar.gz dist/*.whl
```

設定の値を比較するだけの test で、archive の検査を代替しないでください。実務報告では、既存の許可の一覧がすでにファイルを外しており、除外設定の test が保護を増やさない事例がありました。実際の sdist を調べることで、設定の test が証明できない中身を確認していました。

## registry への公開は残る物として扱う

upload より前に、noren の検査と package の検査を終えてください。実務報告には、registry から削除したファイルを約 45 時間後も CDN の URL から取得できた一例があります。その registry や他の registry の保持期間の上限や削除の保証は、この一例からは決まりません。公開後の削除に頼らず、最初の upload より前に問題を直します。

## 配布ファイルと metadata を確かめる

upload の後、registry の version、license、project URL、ファイルの hash を検査した成果物と照合します。自分が管理する PyPI の project と version での例:

```sh
curl --fail https://pypi.org/pypi/PROJECT/1.2.3/json
sha256sum dist/project-1.2.3.tar.gz dist/project-1.2.3-py3-none-any.whl
```

project、version、ファイル名は置き換えてください。metadata と配布ファイルの digest は、[PyPI の JSON API の文書](https://docs.pypi.org/api/json/) に説明があります。公開した頁と取得できるファイルの両方が、意図した物であることを確かめます。

実務報告には、upload 直後に version 別の JSON endpoint が 404 を返す一方、project の endpoint はその version を載せた観測があります。cache が疑われましたが、原因の切り分けと再現は完了していません。取得できる metadata と配布ファイルを照合してください。一つの endpoint の失敗だけでは公開の失敗は決まらず、upload の繰り返しは検証の代わりになりません。
