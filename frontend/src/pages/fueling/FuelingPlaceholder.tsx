/**
 * FuelingPlaceholder — Tela "em breve" para o módulo Fueling Control.
 */
import * as styles from './FuelingPlaceholder.css'

export function FuelingPlaceholder() {
  return (
    <div className={styles.wrapper}>
      <div className={styles.iconCircle}>⛽</div>
      <h1 className={styles.title}>Fueling Control</h1>
      <p className={styles.description}>
        Módulo de acompanhamento de abastecimento com OCR de placas e contagem automática de produtos carregados.
      </p>
      <div className={styles.badge}>
        <span>⏳</span>
        <span>Em breve</span>
      </div>
    </div>
  )
}

export default FuelingPlaceholder
