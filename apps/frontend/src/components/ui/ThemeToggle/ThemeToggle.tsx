import * as Switch from '@radix-ui/react-switch'
import { Sparkles, Monitor } from 'lucide-react'
import { useThemeStore } from '../../../stores/themeStore'
import { container, label, switchRoot, switchThumb } from './ThemeToggle.css'

export function ThemeToggle() {
  const { mode, toggleMode } = useThemeStore()
  const isDemo = mode === 'cyberpunk'

  return (
    <div className={container}>
      <span className={label}>
        {isDemo ? (
          <><Sparkles size={12} /> Demo</>
        ) : (
          <><Monitor size={12} /> Pro</>
        )}
      </span>
      <Switch.Root
        className={switchRoot}
        checked={isDemo}
        onCheckedChange={() => toggleMode()}
        aria-label="Alternar tema"
      >
        <Switch.Thumb className={switchThumb} />
      </Switch.Root>
    </div>
  )
}
