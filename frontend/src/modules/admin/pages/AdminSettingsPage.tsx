import * as s from '../components/admin.css'
import { usePermissions } from '../hooks/usePermissions'
import { PermissionMatrixTable } from '../components/PermissionMatrixTable'

export function AdminSettingsPage() {
  const { matrix, loading } = usePermissions()

  return (
    <div className={s.pageRoot}>
      <div className={s.pageHeader}>
        <div>
          <div className={s.pageTitle}>Configurações da Plataforma</div>
          <div className={s.pageSubtitle}>Permissões e configurações globais</div>
        </div>
      </div>

      <div className={s.card} style={{ marginBottom: 24 }}>
        <div className={s.cardTitle}>Matriz de Permissões</div>
        {loading ? (
          <div className={s.muted}>Carregando...</div>
        ) : matrix ? (
          <PermissionMatrixTable matrix={matrix} />
        ) : (
          <div className={s.alertBanner.warning}>Não foi possível carregar a matriz de permissões.</div>
        )}
      </div>

      <div className={s.card}>
        <div className={s.cardTitle}>Sobre</div>
        <div className={s.flex}>
          <span className={s.muted}>Versão da plataforma</span>
          <span className={s.mono}>Recognition 2.0</span>
        </div>
        <div className={s.flex} style={{ marginTop: 8 }}>
          <span className={s.muted}>Desenvolvido por</span>
          <span>Logikos</span>
        </div>
      </div>
    </div>
  )
}
