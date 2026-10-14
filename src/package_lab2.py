"""Build the requested source ZIP without environments, personal images or history."""
from __future__ import annotations
import io
from pathlib import Path
import zipfile
from common import ROOT, atomic_write


def build_package(experiment=2) -> int:
    files = [ROOT / "README.md", ROOT / "requirements.txt", ROOT / ".gitignore"]
    if (ROOT / "AGENTS.md").is_file():
        files.append(ROOT / "AGENTS.md")
    if (ROOT / "pytest.ini").is_file():
        files.append(ROOT / "pytest.ini")
    for folder, pattern in (("src","*.py"),("config","*.json"),("docs","*.md")):
        files.extend(sorted((ROOT / folder).glob(pattern)))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, arcname=path.relative_to(ROOT).as_posix())
    content = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        if archive.testzip() is not None:
            raise OSError("源码 ZIP 校验失败")
    destination = ROOT / f"deliverables/lab{experiment}_source.zip"
    atomic_write(destination,content)
    print(f"SUCCESS: {destination}; {len(files)} files; {len(content)} bytes")
    return 0


def main() -> int:
    return build_package(2)


if __name__ == "__main__":
    raise SystemExit(main())
