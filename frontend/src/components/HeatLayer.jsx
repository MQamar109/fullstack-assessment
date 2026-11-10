/**
 * React binding for the canvas heat layer. Creates and destroys the layer
 * with its visibility, and pushes new weights without rebuilding it.
 */
import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import { heatCanvas } from '../lib/heatCanvas'

const MIN_WEIGHT = 0.06

export default function HeatLayer({ points, intensity, visible }) {
  const map = useMap()
  const layerRef = useRef(null)

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
