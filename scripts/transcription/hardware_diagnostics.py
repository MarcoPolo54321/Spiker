"""Lightweight hardware and inference-backend diagnostics for Spiker."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class HardwareReport:
    cpu: str
    cpu_threads: int
    ram_gb: float | None
    available_ram_gb: float | None
    gpu: str | None
    gpu_vram_gb: float | None
    gpu_vram_free_gb: float | None
    gpu_utilization_percent: float | None
    cuda_runtime_ready: bool
    recommendation: str
    recommended_device: str
    recommended_compute_type: str
    recommended_model: str
    recommended_batch_size: int
    notes: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _memory_gb() -> float | None:
    try:
        if os.name == "nt":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return round(status.ullTotalPhys / (1024 ** 3), 1)
        else:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return round(pages * page_size / (1024 ** 3), 1)
    except Exception:
        return None
    return None



def _memory_available_gb() -> float | None:
    """Return currently available physical RAM, not total installed RAM."""
    try:
        if os.name == "nt":
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return round(status.ullAvailPhys / (1024 ** 3), 1)
        else:
            available_pages = os.sysconf("SC_AVPHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return round(available_pages * page_size / (1024 ** 3), 1)
    except Exception:
        return None
    return None


def _nvidia_usage_info() -> tuple[float | None, float | None]:
    """Return free VRAM in GiB and current GPU utilization in percent."""
    executable = shutil.which("nvidia-smi")
    if not executable:
        return None, None
    try:
        result = subprocess.run(
            [executable, "--query-gpu=memory.free,utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None, None
        fields = [part.strip() for part in result.stdout.strip().splitlines()[0].split(",")]
        free = round(float(fields[0]) / 1024, 1) if fields and fields[0].isdigit() else None
        utilization = float(fields[1]) if len(fields) > 1 and fields[1].isdigit() else None
        return free, utilization
    except (OSError, subprocess.SubprocessError, ValueError):
        return None, None

def _nvidia_info() -> tuple[str | None, float | None]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return None, None
    try:
        result = subprocess.run(
            [executable, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None, None
        first = result.stdout.strip().splitlines()[0]
        name, _, memory = first.partition(",")
        try:
            vram = round(float(memory.strip()) / 1024, 1)
        except ValueError:
            vram = None
        return name.strip(), vram
    except (OSError, subprocess.SubprocessError):
        return None, None


def cuda_backend_ready() -> bool:
    """Check the installed CTranslate2 runtime, not merely the presence of an NVIDIA card."""
    try:
        import ctranslate2
        return int(ctranslate2.get_cuda_device_count()) > 0
    except Exception:
        return False


def diagnose_hardware() -> HardwareReport:
    cpu_name = platform.processor().strip() or platform.machine() or "Процессор не определён"
    cpu_threads = max(1, int(os.cpu_count() or 1))
    ram = _memory_gb()
    available_ram = _memory_available_gb()
    gpu, vram = _nvidia_info()
    vram_free, gpu_util = _nvidia_usage_info()
    cuda_ready = cuda_backend_ready()
    notes: list[str] = []
    # Use available, not total VRAM, when nvidia-smi can report it. If unavailable,
    # fall back to total capacity but make the recommendation explicitly provisional.
    usable_vram = vram_free if vram_free is not None else vram
    if vram_free is None and vram is not None:
        notes.append("Свободную видеопамять определить не удалось; рекомендация рассчитана по общему объёму VRAM.")

    if cuda_ready and usable_vram is None:
        mode, device, compute, model, batch = "CUDA (объём VRAM не определён)", "cuda", "float16", "small", 1
        notes.append("CTranslate2 видит CUDA, но объём VRAM определить не удалось; начните с Small и batch 1.")
    elif cuda_ready and usable_vram is not None and usable_vram >= 8:
        mode, device, compute, model, batch = "Высокая скорость (GPU)", "cuda", "float16", "large-v3-turbo", 4
        notes.append("Обнаружена доступная CUDA и видеопамять от 8 ГБ; начните с Large-v3 Turbo и batch 4.")
    elif cuda_ready and usable_vram is not None and usable_vram >= 6:
        mode, device, compute, model, batch = "Сбалансированный (GPU)", "cuda", "float16", "medium", 2
        notes.append("Для запаса видеопамяти рекомендована модель Medium и batch 2.")
    elif cuda_ready and usable_vram is not None and usable_vram >= 4:
        mode, device, compute, model, batch = "Быстрый (GPU)", "cuda", "float16", "small", 1
        notes.append("Ограниченная видеопамять: используйте Small и batch 1.")
    else:
        mode, device, compute, model, batch = "CPU INT8", "cpu", "int8", "small", 1
        notes.append("Режим CPU INT8 выбран как наиболее совместимый резервный вариант.")
        if cuda_ready and usable_vram is not None and usable_vram < 4:
            notes.append("Свободной VRAM меньше 4 ГБ; для пакетной транскрибации безопаснее начать с CPU.")
        if gpu and not cuda_ready:
            notes.append("NVIDIA GPU найдена, но CUDA не доступна из текущей сборки CTranslate2.")
        elif not gpu:
            notes.append("NVIDIA GPU не обнаружена; используется CPU.")

    if ram is not None and ram < 8 or (available_ram is not None and available_ram < 3):
        model, batch = "small", 1
        notes.append("ОЗУ или свободной оперативной памяти недостаточно для крупных моделей и большого batch.")
    elif ram is not None and ram < 16 and model in {"large-v3", "large-v3-turbo"}:
        model, batch = "medium", min(batch, 2)
        notes.append("Для доступной оперативной памяти рекомендована модель Medium.")
    if cpu_threads <= 4 and device == "cpu":
        notes.append("На CPU с небольшим числом потоков увеличенный batch может замедлить обработку.")

    if not notes:
        notes.append("Рекомендация ориентировочная; итоговую скорость нужно измерить на ваших записях.")
    return HardwareReport(
        cpu=cpu_name, cpu_threads=cpu_threads, ram_gb=ram, available_ram_gb=available_ram,
        gpu=gpu, gpu_vram_gb=vram, gpu_vram_free_gb=vram_free,
        gpu_utilization_percent=gpu_util, cuda_runtime_ready=cuda_ready,
        recommendation=mode, recommended_device=device,
        recommended_compute_type=compute, recommended_model=model,
        recommended_batch_size=batch, notes=tuple(notes),
    )


def resolve_compute_options(device: str = "auto", compute_type: str = "auto") -> tuple[str, str]:
    """Resolve explicit or automatic compute choices and validate forced CUDA."""
    requested_device = (device or "auto").lower()
    requested_type = (compute_type or "auto").lower()
    available = cuda_backend_ready()
    if requested_device not in {"auto", "cpu", "cuda"}:
        raise ValueError(f"Неизвестный тип устройства: {requested_device}")
    if requested_type not in {"auto", "int8", "float16", "int8_float16", "float32", "bfloat16"}:
        raise ValueError(f"Неизвестный тип вычислений: {requested_type}")
    if requested_device == "cuda" and not available:
        raise RuntimeError(
            "Выбран принудительный режим CUDA, но CTranslate2 не видит доступное CUDA-устройство. "
            "Установите совместимое окружение NVIDIA/CUDA или выберите «Авто»/CPU."
        )
    selected_device = "cuda" if (requested_device == "cuda" or (requested_device == "auto" and available)) else "cpu"
    if requested_type == "auto":
        selected_type = "float16" if selected_device == "cuda" else "int8"
    else:
        selected_type = requested_type
    if selected_device == "cpu" and selected_type in {"float16", "int8_float16", "bfloat16"}:
        raise RuntimeError(
            f"Тип вычислений {selected_type} предназначен для совместимой GPU-конфигурации. "
            "Для CPU выберите INT8 или FP32, либо переключите устройство на CUDA."
        )
    return selected_device, selected_type
