#!/usr/bin/env bash
# perf-jetson.sh — perfil de energia/clock/fan para o soak (task-113). EXIGE SUDO.
#
# ⚠️ PENDÊNCIA: nvpmodel/jetson_clocks/fan exigem sudo NO BOX. A sessão de nuvem
# não alcança o Jetson — este script fica pronto para aplicação hands-on.
#
# Decisões (ver REGRAS §3.2): perfil de fan default 'quiet' (tach NÃO ligado neste
# hardware — health de fan = PWM + curva térmica, nunca RPM). Modo 40W (MAXN Super).
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "ERRO: rode com sudo."; exit 1; fi

echo "==> nvpmodel: modo 0 (MAXN Super / 40W) — máximo de núcleos+clock disponível"
nvpmodel -m 0 || echo "  (nvpmodel indisponível — registrar pendência)"
nvpmodel -q || true

echo "==> jetson_clocks: travar clocks no máximo (remove latência de DVFS no soak)"
# TRADEOFF: mais estável em latência, porém +potência/+calor. Para o soak medimos
# AMBOS os cenários — comece SEM jetson_clocks (térmica realista), aplique se a
# variância de latência (p95) incomodar. Descomente para travar:
# jetson_clocks
echo "  (jetson_clocks NÃO aplicado por padrão — soak mede térmica realista primeiro)"

echo "==> Fan: perfil 'cool' opcional. Default do box é 'quiet'. Aplicar só se térmica"
echo "   encostar em throttle (~95°+). Tach não ligado → validar por PWM/curva, não RPM."
# Exemplo (ajustar ao driver do box):
#   echo cool > /sys/devices/platform/pwm-fan/hwmon/hwmon*/pwm1_profile 2>/dev/null || true

echo "OK — registrar no REGRAS o que foi efetivamente aplicado + medição térmica."
