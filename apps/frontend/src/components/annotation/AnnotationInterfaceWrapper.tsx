/**
 * AnnotationInterfaceWrapper — TypeScript wrapper para AnnotationInterface.jsx congelado.
 * Tipos das props inferidos do uso em AnnotationPage.tsx.
 * AnnotationInterface.jsx NUNCA deve ser modificado diretamente.
 */

// @ts-ignore — componente JSX congelado sem tipos declarados
import AnnotationInterface from '../AnnotationInterface'

interface AnnotationInterfaceWrapperProps {
  videoId: string
  onBack: () => void
}

export function AnnotationInterfaceWrapper({ videoId, onBack }: AnnotationInterfaceWrapperProps) {
  return (
    <AnnotationInterface videoId={videoId} onBack={onBack} />
  )
}
