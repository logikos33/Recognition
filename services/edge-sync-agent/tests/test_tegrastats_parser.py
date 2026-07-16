"""Testes do parser de tegrastats (task-100). Offline — sem Jetson."""
from app.telemetry.tegrastats_parser import parse_tegrastats_line

# Linha idle real-istic do Orin NX 16GB (JetPack 6.2 / L4T r36.4.3):
# baseline registrado pela sessão de bancada — GPU 0%, ~1.2GB/16GB, ~42°C, ~4.3W.
IDLE_LINE = (
    "RAM 1224/15368MB (lfb 8x4MB) SWAP 0/7684MB (cached 0MB) "
    "CPU [1%@729,0%@729,0%@729,0%@729,off,off,off,off] "
    "EMC_FREQ 0% GR3D_FREQ 0%@[305] "
    "CPU@43.5C GPU@42.5C tj@43.5C SOC0@42.906C SOC1@42.156C CV0@-256C "
    "VDD_IN 4319mW/4319mW VDD_CPU_GPU_CV 499mW/499mW VDD_SOC 1200mW/1200mW"
)

# Linha sob inferência: GPU ocupada, mais quente, mais potência.
INFERENCE_LINE = (
    "RAM 4096/15368MB (lfb 2x4MB) SWAP 0/7684MB (cached 0MB) "
    "CPU [45%@1497,38%@1497,52%@1497,40%@1497,off,off,off,off] "
    "EMC_FREQ 25% GR3D_FREQ 88% "
    "CPU@58.5C GPU@61.0C tj@61.0C "
    "VDD_IN 12800mW/11500mW VDD_CPU_GPU_CV 6500mW/6000mW VDD_SOC 2200mW/2100mW"
)

# Linha REAL capturada do box (pandora, JetPack 6.2, 2026-07-16) — rótulos de
# temperatura em MINÚSCULAS, ao contrário do exemplo da doc oficial. Regressão
# para o bug em que gpu_temp_c/cpu_temp_c não casavam por causa do casing.
REAL_BOX_IDLE_LINE = (
    "07-16-2026 13:03:45 RAM 1224/15656MB (lfb 8x4MB) SWAP 0/7828MB (cached 0MB) "
    "CPU [1%@729,0%@729,0%@729,0%@729,0%@729,0%@729,0%@729,0%@729] GR3D_FREQ 0% "
    "cv0@41.156C cpu@45.843C soc2@39.593C soc0@42.562C cv1@42.156C gpu@43.406C "
    "tj@45.843C soc1@40.25C cv2@38.593C "
    "VDD_IN 4304mW/4304mW VDD_CPU_GPU_CV 573mW/573mW VDD_SOC 1218mW/1218mW"
)


def test_parses_ram_and_swap():
    s = parse_tegrastats_line(IDLE_LINE)
    assert s.ram_used_mb == 1224
    assert s.ram_total_mb == 15368
    assert s.swap_used_mb == 0
    assert s.swap_total_mb == 7684
    assert s.ram_pct == round(100 * 1224 / 15368, 2)


def test_parses_cpu_cores_ignoring_offline():
    s = parse_tegrastats_line(IDLE_LINE)
    assert s.cpu_cores_pct == [1, 0, 0, 0]  # 4 cores online, 4 'off' ignorados
    assert s.cpu_pct == round((1 + 0 + 0 + 0) / 4, 2)


def test_parses_gpu_and_emc():
    s = parse_tegrastats_line(IDLE_LINE)
    assert s.gpu_pct == 0        # GR3D_FREQ 0%@[305] — robusto ao sufixo @[freq]
    assert s.emc_pct == 0
    assert parse_tegrastats_line(INFERENCE_LINE).gpu_pct == 88


def test_temps_with_offline_sensor_filtered():
    s = parse_tegrastats_line(IDLE_LINE)
    assert s.temps_c["CPU"] == 43.5
    assert s.temps_c["GPU"] == 42.5
    assert "CV0" not in s.temps_c          # -256C (sensor offline) descartado
    assert s.gpu_temp_c == 42.5            # prefere GPU@
    assert s.cpu_temp_c == 43.5


def test_gpu_temp_falls_back_to_tj_when_no_gpu_sensor():
    line = "RAM 1000/15368MB CPU [0%@729] GR3D_FREQ 0% tj@50.0C VDD_IN 4000mW/4000mW"
    s = parse_tegrastats_line(line)
    assert "GPU" not in s.temps_c
    assert s.gpu_temp_c == 50.0            # cai pro junction tj@


def test_parses_power_rails():
    s = parse_tegrastats_line(INFERENCE_LINE)
    assert s.power_mw["VDD_IN"] == 12800   # instantâneo (não a média 11500)
    assert s.power_in_mw == 12800
    assert s.power_mw["VDD_SOC"] == 2200


def test_missing_swap_still_parses_ram():
    line = "RAM 900/15368MB CPU [2%@729] GR3D_FREQ 5% GPU@40.0C VDD_IN 4000mW/4000mW"
    s = parse_tegrastats_line(line)
    assert s.ram_used_mb == 900
    assert s.swap_used_mb is None
    assert s.gpu_pct == 5


def test_real_box_line_lowercase_temp_labels():
    """Regressão: JetPack 6.2 real emite `cpu@`/`gpu@`/`tj@` minúsculos — o
    parser deve normalizar para casar com gpu_temp_c/cpu_temp_c mesmo assim."""
    s = parse_tegrastats_line(REAL_BOX_IDLE_LINE)
    assert s.cpu_temp_c == 45.843          # antes do fix: None (só casava "CPU")
    assert s.gpu_temp_c == 43.406          # antes do fix: 45.843 (caía no "tj")
    assert s.temps_c["TJ"] == 45.843       # tj preservado, só não é o gpu_temp_c
    assert s.gpu_pct == 0
    assert s.ram_pct == round(100 * 1224 / 15656, 2)
    assert s.power_in_mw == 4304


def test_empty_and_garbage_lines_do_not_raise():
    assert parse_tegrastats_line("").ram_total_mb is None
    assert parse_tegrastats_line("   ").gpu_pct is None
    garbage = parse_tegrastats_line("tegrastats: some banner text\n")
    assert garbage.ram_total_mb is None
    assert garbage.temps_c == {}
    assert garbage.raw == "tegrastats: some banner text\n"
