import { useEffect, useLayoutEffect, useRef } from 'react'

// A textarea exactly as tall as its text (measured, not guessed from the length - a guess left a
// blank line under short notes on a wide screen and cut long ones off on a phone), re-measured
// when the text or the width changes.
export default function FitTextarea(props) {
  const box = useRef(null)
  const fit = () => {
    const el = box.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight + el.offsetHeight - el.clientHeight}px`
  }
  useLayoutEffect(fit, [props.value])
  useEffect(() => {
    let width = box.current.clientWidth
    const watch = new ResizeObserver(() => {     // only a new width re-measures (not its own height)
      if (box.current && box.current.clientWidth !== width) {
        width = box.current.clientWidth
        fit()
      }
    })
    watch.observe(box.current)
    return () => watch.disconnect()
  }, [])
  return <textarea ref={box} rows={1} {...props} />
}
