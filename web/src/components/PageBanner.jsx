import { useRef, useState } from 'react'
import { api } from '../api.js'
import { bannersChanged, useBanners } from '../core/banners.js'
import { useApp } from '../core/app-context.js'
import { CameraIcon } from './icons.jsx'
import Landscape from './Landscape.jsx'
import { shrink } from './PhotoUpload.jsx'

// The picture behind a banner: yours (placed where you put it), or a drawn landscape in the area's colour.
export function BannerArt({ area, photo }) {
  if (photo) {
    return <img className="banner-photo" src={photo.photo_url} alt="" style={{ objectPosition: `50% ${photo.focus_y}%` }} />
  }
  return <Landscape scene={area.banner?.scene} seed={area.banner?.seed} hue={area.hue} />
}

// "Picture": choose a photo of your own for this banner, move it up or down, or go back to the drawing.
export function BannerPicture({ area, photo }) {
  const { showToast } = useApp()
  const input = useRef(null)
  const menu = useRef(null)
  const [busy, setBusy] = useState(false)
  const run = async (work, done) => {
    setBusy(true)
    try {
      await work()
      bannersChanged()
      if (done) showToast(done)
    } catch (e) {
      showToast(`Couldn't change the picture: ${e.message}`)
    } finally {
      setBusy(false)
      if (menu.current) menu.current.open = false
    }
  }
  const pick = (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (file) run(async () => api.setBanner(area.id, await shrink(file, 2200)), 'Picture saved.')
  }
  const move = (by) => run(() => api.moveBanner(area.id, Math.max(0, Math.min(100, photo.focus_y + by))))
  return (
    <details className="banner-picture" ref={menu}>
      <summary aria-label={`Change the ${area.name ?? 'page'} picture`} title="Change this picture">
        {busy ? <span className="spinner" aria-hidden="true" /> : <CameraIcon size={16} />}<span>Picture</span>
      </summary>
      <div className="banner-picture-menu">
        <input ref={input} type="file" accept="image/*" onChange={pick} hidden />
        <button type="button" onClick={() => input.current.click()} disabled={busy}>
          {photo ? 'Choose another picture' : 'Use a picture of mine'}
        </button>
        {photo && <>
          <button type="button" onClick={() => move(-10)} disabled={busy || photo.focus_y <= 0}>Show more of the top</button>
          <button type="button" onClick={() => move(10)} disabled={busy || photo.focus_y >= 100}>Show more of the bottom</button>
          <button type="button" onClick={() => run(() => api.removeBanner(area.id), 'Back to the drawing.')} disabled={busy}>
            Use the drawing again
          </button>
        </>}
      </div>
    </details>
  )
}

// A page's banner: its picture with the page's name and line over it. The navigation bar's <h1> is the
// page's real heading (it shows once the banner scrolls away), so this name is decoration for screen readers.
export default function PageBanner({ area, title, eyebrow }) {
  const banners = useBanners()
  const photo = banners[area.id]
  return (
    <header className="page-banner" style={{ '--hue': area.hue }}>
      <div className="banner-art"><BannerArt area={area} photo={photo} /></div>
      <div className="banner-text" aria-hidden="true">
        {eyebrow && <p className="banner-eyebrow">{eyebrow}</p>}
        <p className="banner-title">{title}</p>
        {area.banner?.tagline && <p className="banner-tagline">{area.banner.tagline}</p>}
      </div>
      <BannerPicture area={{ ...area, name: title }} photo={photo} />
    </header>
  )
}
