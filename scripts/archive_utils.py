"""Safe helpers for extracting downloaded or user-supplied ZIP archives."""
from __future__ import annotations

import stat
import tarfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath


def safe_extract_zip(
    archive: zipfile.ZipFile,
    destination: str | Path,
    *,
    allowed_top_level: set[str] | None = None,
    max_total_bytes: int = 16 * 1024**3,
) -> None:
    """Extract only normal files and directories, with cross-platform path checks."""
    root = Path(destination).resolve()
    root.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    total_size = 0
    entries: list[tuple[zipfile.ZipInfo, Path, bool]] = []

    for info in archive.infolist():
        name = info.filename
        if not name or "\x00" in name or "\\" in name or ":" in name:
            raise ValueError(f"Недопустимое имя в ZIP-архиве: {name!r}")
        posix = PurePosixPath(name)
        windows = PureWindowsPath(name)
        if (
            posix.is_absolute() or windows.is_absolute() or windows.drive
            or not posix.parts or any(part in {"", ".", ".."} for part in posix.parts)
        ):
            raise ValueError(f"Недопустимый путь в ZIP-архиве: {name}")
        if allowed_top_level and posix.parts[0] not in allowed_top_level:
            raise ValueError(f"Запрещённая папка в ZIP-архиве: {name}")

        target = (root.joinpath(*posix.parts)).resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"Путь выходит за папку назначения: {name}")
        is_directory = info.is_dir() or name.endswith("/")
        mode = (info.external_attr >> 16) & 0xFFFF
        kind = stat.S_IFMT(mode)
        if kind not in {0, stat.S_IFREG, stat.S_IFDIR}:
            raise ValueError(f"Символические ссылки и специальные файлы запрещены: {name}")
        if (kind == stat.S_IFDIR and not is_directory) or (kind == stat.S_IFREG and is_directory):
            raise ValueError(f"Несогласованный тип файла в ZIP-архиве: {name}")

        key = str(target).casefold()
        if key in seen:
            raise ValueError(f"Повторяющийся путь в ZIP-архиве: {name}")
        seen.add(key)
        if not is_directory:
            total_size += info.file_size
            if info.file_size < 0 or total_size > max_total_bytes:
                raise ValueError("Размер ZIP-архива превышает безопасный предел распаковки.")
        entries.append((info, target, is_directory))

    for info, target, is_directory in entries:
        if is_directory:
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        copied = 0
        with archive.open(info, "r") as source, target.open("wb") as output:
            while chunk := source.read(1024 * 1024):
                copied += len(chunk)
                if copied > info.file_size or copied > max_total_bytes:
                    raise ValueError(f"Некорректный размер файла в ZIP-архиве: {info.filename}")
                output.write(chunk)
        if copied != info.file_size:
            raise ValueError(f"Файл в ZIP-архиве обрезан: {info.filename}")


def safe_extract_tar(
    archive: tarfile.TarFile,
    destination: str | Path,
    *,
    max_total_bytes: int = 512 * 1024**2,
) -> None:
    """Extract only regular files/directories after validating every tar path."""
    root = Path(destination).resolve()
    root.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    total_size = 0
    entries: list[tuple[tarfile.TarInfo, Path, bool]] = []
    for member in archive.getmembers():
        name = member.name
        if not name or "\x00" in name or "\\" in name or ":" in name:
            raise ValueError(f"Недопустимое имя в TAR-архиве: {name!r}")
        posix = PurePosixPath(name)
        if posix.is_absolute() or not posix.parts or any(part in {"", ".", ".."} for part in posix.parts):
            raise ValueError(f"Недопустимый путь в TAR-архиве: {name}")
        is_directory = member.isdir()
        if not (is_directory or member.isfile()):
            raise ValueError(f"Ссылки и специальные файлы запрещены в TAR-архиве: {name}")
        target = (root.joinpath(*posix.parts)).resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"Путь выходит за папку назначения: {name}")
        key = str(target).casefold()
        if key in seen:
            raise ValueError(f"Повторяющийся путь в TAR-архиве: {name}")
        seen.add(key)
        if not is_directory:
            if member.size < 0:
                raise ValueError(f"Некорректный размер в TAR-архиве: {name}")
            total_size += member.size
            if total_size > max_total_bytes:
                raise ValueError("Размер TAR-архива превышает безопасный предел распаковки.")
        entries.append((member, target, is_directory))

    for member, target, is_directory in entries:
        if is_directory:
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        source = archive.extractfile(member)
        if source is None:
            raise ValueError(f"Не удалось прочитать TAR-файл: {member.name}")
        copied = 0
        with source, target.open("wb") as output:
            while chunk := source.read(1024 * 1024):
                copied += len(chunk)
                if copied > member.size:
                    raise ValueError(f"Некорректный размер файла в TAR-архиве: {member.name}")
                output.write(chunk)
        if copied != member.size:
            raise ValueError(f"Файл в TAR-архиве обрезан: {member.name}")
