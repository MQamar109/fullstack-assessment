import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import { heatCanvas } from '../lib/heatCanvas'

const MIN_WEIGHT = 0.06 // keeps the corridor faintly visible in calm weather

/**
 * Weather-intensity heat layer along the trip corridor.
 * `points` is [[lat, lng], ...] and `intensity` is a parallel array of 0..1.
 */
export default function HeatLayer({ points, intensity, visible }) {
  const map = useMap()
  const layerRef = useRef(null)

  // Create / destroy the layer with visibility.
  useEffect(() => {
    if (!visible) {
      if (layerRef.current) {
        map.removeLayer(layerRef.current)
        layerRef.current = null
      }
      return
    }
    if (!layerRef.current) {
      layerRef.current = heatCanvas([], { radius: 38, opacity: 0.6 })
      layerRef.current.addTo(map)
    }
    return () => {
      if (layerRef.current) {
        map.removeLayer(layerRef.current)
        layerRef.current = null
      }
    }
  }, [map, visible])

  // Push data on every change (slider moves land here, no layer churn).
  useEffect(() => {
    if (!layerRef.current || !visible) return
    const data = (points ?? []).map((p, i) => [
      p[0],
      p[1],
      Math.max(intensity?.[i] ?? 0, MIN_WEIGHT),
    ])
    layerRef.current.setData(data)
  }, [points, intensity, visible])

  return null
}
