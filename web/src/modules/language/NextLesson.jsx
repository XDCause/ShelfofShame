import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../api.js'
import { useApp } from '../../core/app-context.js'

// Today's "Next lesson" card (when the language follows a course: language_course.py): the lesson, its unit, Continue.
// Kept apart from LanguageLearn.jsx so Today doesn't load the lesson player.
export function NextLesson({ lang }) {
  const { refreshKey } = useApp()
  const [data, setData] = useState(null)
  useEffect(() => {
    if (lang.course) api.languageCourse(lang.language_id).then(setData).catch(() => setData(null))
  }, [lang.language_id, lang.course, refreshKey])
  if (!lang.course || !data?.course) return null
  const next = data.next
  return (
    <section className="card lngc-today" aria-labelledby="lngc-today-title">
      <div className="lngc-today-text">
        <h2 id="lngc-today-title" className="home-card-title">{next ? 'Next lesson' : `${data.course.name} course`}</h2>
        {next ? (
          <p><strong>{next.title}</strong> <span className="muted small">Unit {next.unit} · {next.unit_title} · {data.done} of {data.total} done</span></p>
        ) : <p className="muted small">Every lesson done - {data.total} of {data.total}.</p>}
      </div>
      {next
        ? <Link className="button primary lngc-main" to={`/language/learn?lesson=${encodeURIComponent(next.id)}&language=${lang.language_id}`}>Continue</Link>
        : <Link className="button secondary" to="/language/learn">The course</Link>}
    </section>
  )
}
