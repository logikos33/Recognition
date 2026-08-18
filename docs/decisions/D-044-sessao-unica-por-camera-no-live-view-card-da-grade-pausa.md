# D-044 · Sessão única por câmera no live view — card da grade pausa quando o drawer da mesma câmera abre

**Seção:** Rodada de 04/08 — Live view fluido + canal 6 · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude → aceito · ✅ vigente · PR #298**

Causa das sessões de playback duplicadas (dois tokens vivos baixando o mesmo `.ts`, ~457s de gap): grade
e drawer montavam, cada um, seu próprio `useLiveView` + `CameraPlayer` para a mesma câmera, sem
coordenação entre si. Corrigido por composição em `MonitoringPage` (prop `suppressed`), sem tocar em
`useLiveView`/`CameraPlayer`.

**Não era consequência do cross-tenant (D-40)** — confirmado como causa independente.
