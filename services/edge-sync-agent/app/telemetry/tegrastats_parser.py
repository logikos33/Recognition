"""Parser da saída do `tegrastats` (NVIDIA Jetson / L4T).

`tegrastats` é a ferramenta oficial de telemetria do Jetson. A saída é uma linha
por amostra, com tokens rotulados que variam por JetPack/módulo. Este parser é
DEFENSIVO: extrai cada campo por regex independente e tolera tokens ausentes —
um sensor offline (ex.: `CV0@-256C`) ou uma versão sem `SWAP` não quebra o parse.

Referência de formato (Orin NX, JetPack 6.2 / L4T r36.4.3):
    RAM 1234/15368MB (lfb 8x4MB) SWAP 0/7684MB (cached 0MB)
    CPU [0%@729,0%@729,off,off,...] EMC_FREQ 0%@2133 GR3D_FREQ 0%@[305]
    CPU@45.5C GPU@44.5C tj@45.5C SOC0@43.9C CV0@-256C
    VDD_IN 4319mW/4319mW VDD_CPU_GPU_CV 500mW/500mW VDD_SOC 1200mW/1200mW

Campos-chave para observabilidade (task-100 / migration 089):
    gpu_pct        ← GR3D_FREQ
    gpu_temp_c     ← GPU@  (fallback tj@)
    cpu_temp_c     ← CPU@
    ram_pct        ← RAM used/total
    power_mw       ← VDD_IN (instantâneo)

O parser é stdlib-only (re, dataclasses) de propósito: máxima portabilidade no
box e testabilidade offline (sem hardware).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Sensores térmicos desligados reportam -256C — sentinela a descartar.
_TEMP_SENTINEL_C = -100.0

_RE_RAM = re.compile(r"\bRAM\s+(\d+)/(\d+)\s*MB")
_RE_SWAP = re.compile(r"\bSWAP\s+(\d+)/(\d+)\s*MB")
_RE_CPU_BLOCK = re.compile(r"\bCPU\s+\[([^\]]*)\]")
_RE_CPU_CORE = re.compile(r"(\d+)%@(\d+)")
_RE_EMC = re.compile(r"\bEMC_FREQ\s+(\d+)%")
_RE_GR3D = re.compile(r"\bGR3D_FREQ\s+(\d+)%")
# Temperaturas: `NOME@12.3C` ou `NOME@-256C`. Nome alfanumérico (CPU, GPU, tj, SOC0…).
_RE_TEMP = re.compile(r"\b([A-Za-z][A-Za-z0-9_]*)@(-?\d+(?:\.\d+)?)C\b")
# Rails de potência: `VDD_IN 4319mW/4319mW` → (instantâneo, média).
_RE_POWER = re.compile(r"\b([A-Z][A-Z0-9_]*)\s+(\d+)mW/(\d+)mW")


@dataclass
class TegrastatsSample:
    """Uma amostra estruturada de `tegrastats`. Campos ausentes ficam None."""

    ram_used_mb: int | None = None
    ram_total_mb: int | None = None
    swap_used_mb: int | None = None
    swap_total_mb: int | None = None
    cpu_pct: float | None = None            # média entre cores online
    cpu_cores_pct: list[int] = field(default_factory=list)
    emc_pct: int | None = None              # controlador de memória
    gpu_pct: int | None = None              # GR3D_FREQ — utilização da GPU
    temps_c: dict[str, float] = field(default_factory=dict)  # {'GPU': 44.5, ...}
    power_mw: dict[str, int] = field(default_factory=dict)    # {'VDD_IN': 4319, ...}
    raw: str = ""

    # --- derivados de conveniência (mapeiam pro modelo Heartbeat) ---

    @property
    def ram_pct(self) -> float | None:
        if not self.ram_total_mb:
            return None
        return round(100.0 * (self.ram_used_mb or 0) / self.ram_total_mb, 2)

    @property
    def gpu_temp_c(self) -> float | None:
        """Temperatura da GPU: prefere `GPU@`, cai pra junction `tj@`."""
        for key in ("GPU", "tj", "TJ"):
            if key in self.temps_c:
                return self.temps_c[key]
        return None

    @property
    def cpu_temp_c(self) -> float | None:
        return self.temps_c.get("CPU")

    @property
    def power_in_mw(self) -> int | None:
        """Potência total de entrada instantânea (VDD_IN)."""
        return self.power_mw.get("VDD_IN")


def parse_tegrastats_line(line: str) -> TegrastatsSample:
    """Parseia uma linha de `tegrastats` → `TegrastatsSample`.

    Nunca levanta em entrada malformada: campos não reconhecidos ficam None/vazio.
    Uma linha em branco vira uma amostra totalmente vazia (raw preservado).
    """
    sample = TegrastatsSample(raw=line)
    if not line or not line.strip():
        return sample

    if m := _RE_RAM.search(line):
        sample.ram_used_mb, sample.ram_total_mb = int(m.group(1)), int(m.group(2))

    if m := _RE_SWAP.search(line):
        sample.swap_used_mb, sample.swap_total_mb = int(m.group(1)), int(m.group(2))

    if m := _RE_CPU_BLOCK.search(line):
        cores = [int(c) for c, _freq in _RE_CPU_CORE.findall(m.group(1))]
        sample.cpu_cores_pct = cores
        if cores:
            sample.cpu_pct = round(sum(cores) / len(cores), 2)

    if m := _RE_EMC.search(line):
        sample.emc_pct = int(m.group(1))

    if m := _RE_GR3D.search(line):
        sample.gpu_pct = int(m.group(1))

    for name, value in _RE_TEMP.findall(line):
        temp = float(value)
        if temp > _TEMP_SENTINEL_C:  # descarta sensores offline (-256C)
            sample.temps_c[name] = temp

    for rail, instant, _avg in _RE_POWER.findall(line):
        sample.power_mw[rail] = int(instant)

    return sample
