"""Basic checks on a selected image file.

WHAT THIS CAN ESTABLISH
  * the file exists, is a regular non-empty file and can be read;
  * the first bytes (header) look like a known Android image format;
  * that format is consistent with the destination partition the user chose.

WHAT THIS CANNOT ESTABLISH
  * that the image was built for this device or matches its firmware;
  * that it is correctly signed or will boot;
  * which of two partitions sharing one format (boot / recovery) it was built for.

A filename is never used to decide what an image is.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

LEVEL_OK = "OK"
LEVEL_WARNING = "WARNING"
LEVEL_ERROR = "ERROR"

KIND_ANDROID_BOOT = "android_boot"
KIND_VENDOR_BOOT = "vendor_boot"
KIND_VBMETA = "vbmeta"
KIND_DTBO = "dtbo"
KIND_SPARSE = "sparse"

KIND_LABELS = {
    KIND_ANDROID_BOOT: "Android boot image",
    KIND_VENDOR_BOOT: "vendor_boot image",
    KIND_VBMETA: "vbmeta (AVB) image",
    KIND_DTBO: "dtbo image",
    KIND_SPARSE: "sparse image",
}

# Header format each destination partition normally uses.
EXPECTED_KIND = {
    "boot": KIND_ANDROID_BOOT,
    "init_boot": KIND_ANDROID_BOOT,
    "recovery": KIND_ANDROID_BOOT,
    "vendor_boot": KIND_VENDOR_BOOT,
    "vbmeta": KIND_VBMETA,
    "dtbo": KIND_DTBO,
}

_DTBO_MAGIC = bytes.fromhex("d7b7ab1e")
_SPARSE_MAGIC = bytes.fromhex("3aff26ed")


@dataclass(frozen=True)
class ImageInfo:
    path: Path
    size: int | None = None
    kind: str | None = None  # one of the KIND_* values, or None if not recognised
    header_version: int | None = None
    kernel_size: int | None = None  # Android boot images only
    error: str | None = None  # file-level problem (missing, empty, unreadable)


@dataclass(frozen=True)
class ValidationResult:
    level: str  # LEVEL_OK / LEVEL_WARNING / LEVEL_ERROR
    message: str
    info: ImageInfo


def format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def _u32(data: bytes, offset: int) -> int | None:
    if len(data) < offset + 4:
        return None
    return struct.unpack_from("<I", data, offset)[0]


def read_image_info(path: Path) -> ImageInfo:
    """Read file size and header magic. Never raises."""
    try:
        stat = path.stat()
    except OSError as exc:
        return ImageInfo(path, error=f"File not found or unreadable ({exc.strerror or exc}).")
    if not path.is_file():
        return ImageInfo(path, error="Not a regular file.")
    if stat.st_size == 0:
        return ImageInfo(path, size=0, error="The file is empty.")
    try:
        with path.open("rb") as handle:
            head = handle.read(64)
    except OSError as exc:
        return ImageInfo(path, size=stat.st_size, error=f"Cannot read the file ({exc.strerror or exc}).")

    kind = None
    header_version = None
    kernel_size = None
    if head.startswith(b"ANDROID!"):
        kind = KIND_ANDROID_BOOT
        header_version = _u32(head, 40)
        kernel_size = _u32(head, 8)
    elif head.startswith(b"VNDRBOOT"):
        kind = KIND_VENDOR_BOOT
        header_version = _u32(head, 8)
    elif head.startswith(b"AVB0"):
        kind = KIND_VBMETA
    elif head.startswith(_DTBO_MAGIC):
        kind = KIND_DTBO
    elif head.startswith(_SPARSE_MAGIC):
        kind = KIND_SPARSE
    return ImageInfo(path, stat.st_size, kind, header_version, kernel_size)


def validate_image(path: Path, partition: str | None) -> ValidationResult:
    """Check `path` against the destination `partition` (None = file-level checks only)."""
    info = read_image_info(Path(path))
    if info.error:
        return ValidationResult(LEVEL_ERROR, info.error, info)

    label = KIND_LABELS.get(info.kind or "", None)
    if partition is None:
        text = f"Detected: {label}." if label else "Header not recognised."
        return ValidationResult(LEVEL_OK if label else LEVEL_WARNING, text + " Choose a destination partition.", info)

    expected = EXPECTED_KIND.get(partition)
    if expected is None:
        return ValidationResult(LEVEL_ERROR, f"'{partition}' is not a supported destination partition.", info)

    if info.kind is None:
        return ValidationResult(
            LEVEL_WARNING,
            f"The header is not recognised, so this file cannot be validated for '{partition}'. "
            "Only continue if you are certain about it.",
            info,
        )
    if info.kind == KIND_SPARSE:
        return ValidationResult(
            LEVEL_WARNING,
            f"This is a sparse image, which is unusual for '{partition}' and cannot be checked further.",
            info,
        )
    if info.kind != expected:
        return ValidationResult(
            LEVEL_ERROR,
            f"The header looks like a {label}, which does not match '{partition}'.",
            info,
        )

    warnings: list[str] = []
    if info.kind == KIND_ANDROID_BOOT:
        has_kernel = bool(info.kernel_size)
        if partition == "init_boot":
            if info.header_version is not None and info.header_version != 4:
                warnings.append(f"init_boot images normally use boot header version 4 (this one reports {info.header_version}).")
            if has_kernel:
                warnings.append("It contains a kernel, which is typical of boot images, not init_boot.")
        elif partition in ("boot", "recovery") and info.kernel_size == 0:
            warnings.append("It contains no kernel, which is typical of init_boot images, not boot/recovery.")

    if not Path(path).name.lower().endswith(".img"):
        warnings.append("The file does not have the .img extension.")

    if warnings:
        return ValidationResult(LEVEL_WARNING, " ".join(warnings), info)

    note = f"The header is consistent with '{partition}'. This does not prove the image is correct or compatible with your device."
    if partition in ("boot", "recovery"):
        note += " Boot and recovery images share one header format, so this check cannot tell them apart."
    return ValidationResult(LEVEL_OK, note, info)
