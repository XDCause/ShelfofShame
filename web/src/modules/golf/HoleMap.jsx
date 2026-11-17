import { useMemo, useRef, useState } from 'react'
import { holeFrame, metresBetween, ring } from './golfMath.js'

// One hole drawn from its map (api/app/golf_map.py: line, green, tees, fairways, bunkers, water as [[lat, lon], ...]),
// turned so the tee is at the bottom and the green at the top, at an equal scale (golfMath.holeFrame). On it: your
// position (when you're on the hole), the shots you marked joined up with their distances, and - tap anywhere - a
// marker with how far it is from you (or the tee) and on to the middle of the green: the layup numbers.
//
//   <HoleMap map={hole.map} holeNo={3} par={4} me={[lat, lon] | null} shots={[{lat, lon, club, metres}]} measure />
// Without a map it draws nothing (null): the page shows the hole's metres instead. Used by the live round (GolfPlay)
// and free for the other golf pages (measure={false}: a picture only).

const pts = (frame, shape) => ring(shape).map((p) => frame.toXY(p).map((v) => v.toFixed(1)).join(',')).join(' ')

function Label({ x, y, size, children }) {
  const w = String(children).length * size * 0.6 + size * 0.8
  return (
    <g className="gplay-map-label" transform={`translate(${x} ${y})`}>
      <rect x={-w / 2} y={-size * 0.85} width={w} height={size * 1.25} rx={size * 0.3} />
      <text x={0} y={0} fontSize={size} textAnchor="middle">{children}</text>
    </g>
  )
}

export default function HoleMap({ map, holeNo, par, me = null, shots = [], measure = true, className = '' }) {
  const frame = useMemo(() => (map ? holeFrame(map) : null), [map])
  const svg = useRef(null)
  const [mark, setMark] = useState(null)        // [lat, lon] of the tapped spot
  if (!frame) return null
  const { box } = frame
  const unit = box.h / 100                       // drawing sizes scale with the hole
  const font = Math.max(9, unit * 3.2)
  const meXY = me ? frame.toXY(me) : null
  const onHole = meXY && meXY[0] >= box.x && meXY[0] <= box.x + box.w && meXY[1] >= box.y && meXY[1] <= box.y + box.h
  const from = onHole ? me : frame.tee
  const tap = (e) => {
    if (!measure || !svg.current?.getScreenCTM) return
    const m = svg.current.getScreenCTM()
    if (!m) return
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(m.inverse())
    const at = frame.fromXY([p.x, p.y])
    setMark((old) => (old && metresBetween(old, at) < box.h / 60 ? null : at))   // (tap the marker again: gone)
  }
  const markXY = mark ? frame.toXY(mark) : null
  const markFrom = mark ? Math.round(metresBetween(from, mark)) : null
  const markTo = mark ? Math.round(metresBetween(mark, frame.pin)) : null
  const shotXY = shots.map((s) => frame.toXY([s.lat, s.lon]))
  const summary = [`Hole ${holeNo}${par ? `, par ${par}` : ''}`, `drawn from the tee at the bottom to the green at the top`,
    `${Math.round(metresBetween(frame.tee, frame.pin))} m tee to green`,
    map.bunkers?.length ? `${map.bunkers.length} bunker${map.bunkers.length === 1 ? '' : 's'}` : null,
    map.water?.length ? 'water' : null, onHole ? 'your position is shown' : null,
    shots.length ? `${shots.length} marked shot${shots.length === 1 ? '' : 's'}` : null].filter(Boolean).join(', ')

  return (
    <div className={`gplay-map ${className}`}>
      <svg ref={svg} viewBox={`${box.x} ${box.y} ${box.w} ${box.h}`} preserveAspectRatio="xMidYMid meet" role="img"
        aria-label={summary} onClick={tap} className={measure ? 'gplay-map-svg gplay-map-tappable' : 'gplay-map-svg'}>
        <rect className="gplay-map-rough" x={box.x} y={box.y} width={box.w} height={box.h} />
        {(map.water ?? []).map((w, i) => <polygon key={`w${i}`} className="gplay-map-water" points={pts(frame, w)} />)}
        {(map.fairways ?? []).map((f, i) => <polygon key={`f${i}`} className="gplay-map-fairway" points={pts(frame, f)} />)}
        {(map.tees ?? []).map((t, i) => <polygon key={`t${i}`} className="gplay-map-tee" points={pts(frame, t)} />)}
        {map.green?.length >= 3 && <polygon className="gplay-map-green" points={pts(frame, map.green)} />}
        {(map.bunkers ?? []).map((b, i) => <polygon key={`b${i}`} className="gplay-map-bunker" points={pts(frame, b)} />)}
        {map.line?.length >= 2 && <polyline className="gplay-map-line" points={map.line.map((p) => frame.toXY(p).join(',')).join(' ')} />}
        <circle className="gplay-map-flag" cx={frame.toXY(frame.pin)[0]} cy={frame.toXY(frame.pin)[1]} r={unit * 1.1} />
        {shotXY.length > 1 && <polyline className="gplay-map-shotline" points={shotXY.map((p) => p.join(',')).join(' ')} />}
        {shotXY.map(([x, y], i) => (
          <g key={`s${i}`}>
            <circle className="gplay-map-shot" cx={x} cy={y} r={unit * 1.3} />
            {shots[i].metres != null && shotXY[i + 1] && (
              <Label x={(x + shotXY[i + 1][0]) / 2 + unit * 6} y={(y + shotXY[i + 1][1]) / 2} size={font * 0.85}>{`${shots[i].metres} m`}</Label>
            )}
          </g>
        ))}
        {onHole && <circle className="gplay-map-me" cx={meXY[0]} cy={meXY[1]} r={unit * 1.6} />}
        {markXY && (
          <g>
            <line className="gplay-map-measure" x1={frame.toXY(from)[0]} y1={frame.toXY(from)[1]} x2={markXY[0]} y2={markXY[1]} />
            <line className="gplay-map-measure" x1={markXY[0]} y1={markXY[1]} x2={frame.toXY(frame.pin)[0]} y2={frame.toXY(frame.pin)[1]} />
            <circle className="gplay-map-mark" cx={markXY[0]} cy={markXY[1]} r={unit * 1.5} />
            <Label x={markXY[0]} y={markXY[1] - unit * 3} size={font}>{`${markFrom} m · ${markTo} m`}</Label>
          </g>
        )}
      </svg>
      {measure && (
        <p className="gplay-map-readout" aria-live="polite">
          {mark ? <><strong>{markFrom} m</strong> from {onHole ? 'you' : 'the tee'} · <strong>{markTo} m</strong> to the middle of the green</>
            : 'Tap the map to measure a layup.'}
        </p>
      )}
    </div>
  )
}
