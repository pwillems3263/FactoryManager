import { useRef, useState, useCallback } from 'react'

/**
 * Rend un élément (typiquement une fenêtre modale) déplaçable à la souris.
 *
 * Utilisation :
 *   const { pos, onMouseDown, reset } = useDraggable()
 *
 *   <div className="modal" style={{ transform: `translate(${pos.x}px, ${pos.y}px)` }}>
 *     <div className="modal-header" onMouseDown={onMouseDown} style={{ cursor: 'grab', userSelect: 'none' }}>
 *       ...
 *     </div>
 *   </div>
 *
 * Pense à appeler reset() à chaque fermeture du modal (bouton Cancel, croix,
 * clic sur l'overlay, sauvegarde réussie) pour que la fenêtre se rouvre centrée.
 */
export function useDraggable() {
  const [pos, setPos] = useState({ x: 0, y: 0 })
  const dragging = useRef(false)
  const start = useRef({ x: 0, y: 0 })
  const origin = useRef({ x: 0, y: 0 })

  const onMouseMove = useCallback((e) => {
    if (!dragging.current) return
    setPos({
      x: origin.current.x + (e.clientX - start.current.x),
      y: origin.current.y + (e.clientY - start.current.y),
    })
  }, [])

  const onMouseUp = useCallback(() => {
    dragging.current = false
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }, [onMouseMove])

  const onMouseDown = useCallback((e) => {
    // Ignore les clics sur le bouton fermer ("✕") ou tout élément interactif de l'en-tête
    if (e.target.closest('button, input, select, textarea, a')) return
    e.preventDefault()
    dragging.current = true
    start.current = { x: e.clientX, y: e.clientY }
    origin.current = pos
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }, [pos, onMouseMove, onMouseUp])

  const reset = useCallback(() => setPos({ x: 0, y: 0 }), [])

  return { pos, onMouseDown, reset }
}
