// Fishing's live-trip waiting list (modules/fishing/fishQueue.js): queue, swap a temporary id, resend safely.
import { describe, expect, it, vi } from 'vitest'
import { addLocalCatch, applySwaps, bumpRecent, catchCount, dataUrlToBlob, elapsedText, enqueue, failure, isTemp, lengthFrom, nearestSpot, newKey,
  recentFirst, runQueue, sendItem, startLocalTrip, swapRef } from '../modules/fishing/fishQueue.js'

const store = (initial, onSwap) => {
  const s = { q: initial, get: () => s.q, set: (q) => { s.q = q }, swapped: onSwap }
  return s
}
const err = (status) => Object.assign(new Error('x'), { status })

describe('temporary ids', () => {
  it('are told apart from the server ids and never repeat', () => {
    const a = newKey('c')
    expect(isTemp(a)).toBe(true)
    expect(isTemp(12)).toBe(false)
    expect(newKey('c')).not.toBe(a)
  })
  it('are swapped for the real id in everything waiting', () => {
    const q = swapRef([{ kind: 'catch', trip: 'tmp-t-1' }, { kind: 'photo', catch: 'tmp-c-1' }, { kind: 'end', trip: 'tmp-t-1' }], 'tmp-t-1', 40)
    expect(q.map((x) => x.trip)).toEqual([40, undefined, 40])
    expect(q[1].catch).toBe('tmp-c-1')
  })
})

describe('failure', () => {
  it('retries what no signal or a server hiccup lost, and drops what the server refused', () => {
    expect(failure(err(undefined))).toBe('retry')
    expect(failure(err(503))).toBe('retry')
    expect(failure(err(401))).toBe('retry')
    expect(failure(err(422))).toBe('drop')
    expect(failure(err(404))).toBe('drop')
  })
})

describe('runQueue', () => {
  const list = () => {
    let q = []
    q = enqueue(q, { kind: 'trip', temp: 'tmp-t-1', spot: 5, data: { started_at: '2026-11-18T05:00:00Z' } })
    q = enqueue(q, { kind: 'catch', temp: 'tmp-c-1', trip: 'tmp-t-1', data: { species_id: 1 } })
    q = enqueue(q, { kind: 'photo', catch: 'tmp-c-1', dataUrl: 'data:image/jpeg;base64,AAAA' })
    q = enqueue(q, { kind: 'end', trip: 'tmp-t-1', data: { ended_at: 'x' } })
    return q
  }
  it('sends in order and swaps each temporary id before the next item goes', async () => {
    const sent = []
    const swaps = []
    const s = store(list(), (x) => swaps.push(x))
    const out = await runQueue(s, async (item) => {
      sent.push([item.kind, item.trip ?? item.catch ?? null])
      return item.kind === 'trip' ? { trip_id: 40 } : item.kind === 'catch' ? { catch: { catch_id: 900 } } : {}
    })
    expect(sent).toEqual([['trip', null], ['catch', 40], ['photo', 900], ['end', 40]])
    expect(out.stalled).toBe(false)
    expect(s.q).toEqual([])
    expect(swaps.map((x) => [x.temp, x.real])).toEqual([['tmp-t-1', 40], ['tmp-c-1', 900]])
  })
  it('stops with no signal and keeps everything for the next try (the trip start marked as tried)', async () => {
    const s = store(list())
    const out = await runQueue(s, async () => { throw err(undefined) })
    expect(out.stalled).toBe(true)
    expect(s.q).toHaveLength(4)
    expect(s.q[0].tried).toBe(true)
    const again = []
    await runQueue(s, async (item, wasTried) => { again.push([item.kind, wasTried]); return { trip_id: 41 } })
    expect(again[0]).toEqual(['trip', true])
  })
  it('drops an item the server refused and what hangs on it, and goes on with the rest', async () => {
    const s = store(list())
    const dropped = []
    const out = await runQueue(s, async (item) => {
      if (item.kind === 'catch') throw err(422)
      return item.kind === 'trip' ? { trip_id: 40 } : {}
    })
    dropped.push(...out.dropped.map((d) => d.item.kind))
    expect(dropped).toEqual(['catch', 'photo'])            // the photo's catch never got an id
    expect(out.results.map((r) => r.item.kind)).toEqual(['trip', 'end'])
    expect(s.q).toEqual([])
  })
  it('does not lose what is added while a send is under way', async () => {
    const s = store(enqueue([], { kind: 'end', trip: 7, data: {} }))
    let added = false
    const sent = []
    await runQueue(s, async (item) => {
      sent.push(item.trip)
      if (!added) { added = true; s.q = enqueue(s.q, { kind: 'end', trip: 8, data: {} }) }
      return {}
    })
    expect(sent).toEqual([7, 8])
    expect(s.q).toHaveLength(0)                            // both sent: the second was seen by the loop
  })
})

describe('sendItem', () => {
  const api = () => ({
    fishingLiveAddSpot: vi.fn().mockResolvedValue({ spot_id: 3 }), fishingLiveStart: vi.fn().mockResolvedValue({ trip_id: 9 }),
    fishingLiveCatch: vi.fn().mockResolvedValue({ catch_id: 5 }), fishingLiveEnd: vi.fn().mockResolvedValue({}),
    addFishingPhoto: vi.fn().mockResolvedValue({ photo_id: 1 }), fishingLiveSummary: vi.fn().mockResolvedValue({ open_trip: null }),
  })
  it('sends a catch with its temporary id as the client_key, so a resend is the same catch', async () => {
    const a = api()
    await sendItem(a, { kind: 'catch', temp: 'tmp-c-9', trip: 9, data: { species_id: 1, fate: 'kept' } })
    expect(a.fishingLiveCatch).toHaveBeenCalledWith(9, { species_id: 1, fate: 'kept', client_key: 'tmp-c-9' })
  })
  it('starts a trip at its spot; a start that may have gone out is looked for among the open trips first', async () => {
    const a = api()
    const item = { kind: 'trip', temp: 'tmp-t-1', spot: 3, data: { started_at: '2026-11-18T05:00:00.000Z', platform: 'boat' } }
    await sendItem(a, item)
    expect(a.fishingLiveStart).toHaveBeenCalledWith({ started_at: '2026-11-18T05:00:00.000Z', platform: 'boat', spot_id: 3, client_key: 'tmp-t-1' })
    a.fishingLiveStart.mockClear()
    a.fishingLiveSummary.mockResolvedValue({ open_trip: { trip_id: 77, started_at: '2026-11-18T15:00:00+10:00' } })
    expect((await sendItem(a, item, true)).trip_id).toBe(77)
    expect(a.fishingLiveStart).not.toHaveBeenCalled()
  })
  it('ends a trip, makes a spot and sends a photo as an image', async () => {
    const a = api()
    await sendItem(a, { kind: 'end', trip: 9, data: { ended_at: 'T' } })
    expect(a.fishingLiveEnd).toHaveBeenCalledWith(9, { ended_at: 'T' })
    await sendItem(a, { kind: 'spot', temp: 'tmp-s-1', data: { name: 'Jetty', lat: -27.4, lon: 153.1 } })
    expect(a.fishingLiveAddSpot).toHaveBeenCalledWith({ name: 'Jetty', lat: -27.4, lon: 153.1 })
    await sendItem(a, { kind: 'photo', catch: 5, dataUrl: 'data:image/jpeg;base64,AAAA' })
    const blob = a.addFishingPhoto.mock.calls[0][1]
    expect(a.addFishingPhoto.mock.calls[0][0]).toBe(5)
    expect(blob.type).toBe('image/jpeg')
  })
  it('turns a data: address back into an image', () => {
    const b = dataUrlToBlob('data:image/png;base64,AAAA')
    expect(b.type).toBe('image/png')
    expect(b.size).toBe(3)
  })
})

describe('the trip kept on the phone', () => {
  it('counts the catches (the server\'s count before this phone joined plus its own) and takes the server ids', () => {
    let t = startLocalTrip({ id: 'tmp-t-1', started_at: 'T', spot_id: 'tmp-s-1', base: 2 })
    t = addLocalCatch(t, { key: 'tmp-c-1', id: 'tmp-c-1', species: 'Bream' })
    expect(catchCount(t)).toBe(3)
    t = applySwaps(t, [{ temp: 'tmp-t-1', real: 40, kind: 'trip' }, { temp: 'tmp-s-1', real: 6, kind: 'spot' }, { temp: 'tmp-c-1', real: 900, kind: 'catch' }])
    expect([t.id, t.spot_id, t.catches[0].id, t.catches[0].key]).toEqual([40, 6, 900, 'tmp-c-1'])
  })
})

describe('small helpers', () => {
  it('puts what you used last first', () => {
    expect(bumpRecent([1, 2, 3], 3)).toEqual([3, 1, 2])
    expect(bumpRecent([], 'Bream')).toEqual(['Bream'])
    expect(recentFirst([{ id: 1 }, { id: 2 }, { id: 3 }], [3, 1], 'id').map((x) => x.id)).toEqual([3, 1, 2])
  })
  it('finds the nearest spot within 2 km, and none when they are all far', () => {
    const spots = [{ spot_id: 1, lat: -27.4, lon: 153.1 }, { spot_id: 2, lat: -27.405, lon: 153.1 }, { spot_id: 3, lat: null, lon: null }]
    expect(nearestSpot(spots, { lat: -27.4003, lon: 153.1 }).spot.spot_id).toBe(1)
    expect(nearestSpot(spots, { lat: -27.9, lon: 153.1 })).toBeNull()
    expect(nearestSpot(spots, { lat: -27.4011, lon: 153.1 }, 50)).toBeNull()
  })
  it('reads the time fishing and a typed length', () => {
    const t = Date.parse('2026-11-18T06:00:00Z')
    expect(elapsedText('2026-11-18T05:59:40Z', t)).toBe('just started')
    expect(elapsedText('2026-11-18T05:15:00Z', t)).toBe('45 min')
    expect(elapsedText('2026-11-18T04:35:00Z', t)).toBe('1 h 25 min')
    expect(lengthFrom('42,5')).toBe(42.5)
    expect(lengthFrom('')).toBeNull()
    expect(lengthFrom('0')).toBeNull()
    expect(lengthFrom('abc')).toBeNull()
  })
})
