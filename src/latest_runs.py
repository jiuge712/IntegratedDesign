"""Safely publish only the latest personal result for each experiment."""
from __future__ import annotations

from pathlib import Path
import shutil
import uuid

from common import ROOT


def remove_owned(path: Path, parent: Path) -> None:
    """Never delete the parent itself, originals, or targets reached through links."""
    parent = parent.resolve()
    if not parent.is_relative_to(ROOT.resolve()):
        raise ValueError(f"清理根目录不在项目内: {parent}")
    if path.is_symlink() or path.is_junction():
        raise ValueError(f"拒绝清理链接目录: {path}")
    target = path.resolve()
    if target == parent or not target.is_relative_to(parent):
        raise ValueError(f"清理路径越界: {target}")
    if target.is_dir():
        shutil.rmtree(target)
    elif target.exists():
        target.unlink()


class LatestRun:
    """Stage a run and replace the previous result only after successful verification."""
    def __init__(self, name: str):
        if name not in ("lab1", "lab2", "lab3", "lab4", "lab5"):
            raise ValueError("Unknown experiment")
        self.name = name
        self.parents = (ROOT / "data/output", ROOT / "evidence")
        self.token = uuid.uuid4().hex
        self.output, self.evidence = [p / f".stage_{name}_{self.token}" for p in self.parents]
        self.final_output, self.final_evidence = [p / f"{name}_latest" for p in self.parents]
        self.lock = ROOT / "evidence" / f".{name}_running.lock"
        self.committed = False

    def __enter__(self):
        if any(not parent.resolve().is_relative_to(ROOT.resolve()) for parent in self.parents):
            raise ValueError("实验输出或证据目录通过链接指向项目之外")
        self.lock.parent.mkdir(parents=True, exist_ok=True)
        with self.lock.open("x", encoding="utf-8") as stream:
            stream.write(self.token)
        try:
            for path in (self.output, self.evidence):
                path.mkdir(parents=True, exist_ok=False)
        except Exception:
            self.lock.unlink()
            raise
        return self

    def commit(self) -> None:
        pairs = list(zip((self.output, self.evidence), (self.final_output, self.final_evidence), self.parents))
        backups, promoted = [], []
        try:
            for stage, final, parent in pairs:
                if final.is_symlink() or final.is_junction():
                    raise ValueError(f"最近结果不能是链接目录: {final}")
                if final.exists():
                    backup = parent / f".backup_{self.name}_{self.token}"
                    final.rename(backup)
                    backups.append((backup, final, parent))
                stage.rename(final)
                promoted.append((final, stage))
        except Exception:
            for final, stage in reversed(promoted):
                final.rename(stage)
            for backup, final, _ in reversed(backups):
                backup.rename(final)
            raise
        self.committed = True
        for backup, _, parent in backups:
            remove_owned(backup, parent)
        if self.name == "lab1":
            # Migrate only the known historical personal-run folders; preserve
            # all originals, preparation records, self-tests and other experiments.
            for parent in self.parents:
                for old in parent.glob("personal_*"):
                    if old.is_dir():
                        remove_owned(old, parent)

    def __exit__(self, exc_type, exc, traceback):
        try:
            for path, parent in zip((self.output, self.evidence), self.parents):
                if path.exists():
                    remove_owned(path, parent)
        finally:
            self.lock.unlink(missing_ok=True)

