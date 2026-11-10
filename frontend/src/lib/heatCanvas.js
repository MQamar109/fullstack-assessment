/**
 * A small canvas heat layer for Leaflet.
 *
 * We render this ourselves rather than depending on `leaflet.heat`: that plugin
 * is a classic script that attaches to a global `L`, which Leaflet's ESM build
 * never creates, so it fails to register under Vite. Drawing the field directly
 * keeps the heatmap dependency-free and deterministic.
 *
 * Points are [lat, lng, weight] with weight in 0..1, coloured by the risk ramp.
 */
import L from 'leaflet'
import { RISK_LEVELS, RISK_COLORS } from './risk'

function rampColor(weight) {
  const idx = Math.max(0, Math.min(RISK_LEVELS.length - 1, Math.round(weight * 4)))
  return RISK_COLORS[RISK_LEVELS[idx]]
}

function rgba(hex, alpha) {
  const h = hex.replace('#', '')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

const HeatCanvas = L.Layer.extend({
  options: { radius: 38, opacity: 0.6 },

  initialize(points, options) {
    this._points = points || []
    L.setOptions(this, options)
  },

  setData(points) {
    this._points = points || []
    this._redraw()
  },

  onAdd(map) {
    this._map = map
    if (!this._canvas) this._initCanvas()
    map.getPanes().overlayPane.appendChild(this._canvas)
    map.on('moveend zoomend resize viewreset', this._reset, this)
    if (map.options.zoomAnimation && L.Browser.any3d) {
      map.on('zoomanim', this._animateZoom, this)
    }
    this._reset()
    return this
  },

  onRemove(map) {
    if (this._canvas?.parentNode) this._canvas.parentNode.removeChild(this._canvas)
    map.off('moveend zoomend resize viewreset', this._reset, this)
    map.off('zoomanim', this._animateZoom, this)
    return this
  },

  _initCanvas() {
    const canvas = L.DomUtil.create('canvas', 'leaflet-heat-canvas leaflet-layer')
    const size = this._map.getSize()
    canvas.width = size.x
    canvas.height = size.y
    canvas.style.pointerEvents = 'none'
    const originProp = L.DomUtil.testProp([
      'transformOrigin',
      'WebkitTransformOrigin',
      'msTransformOrigin',
    ])
    if (originProp) canvas.style[originProp] = '50% 50%'
    this._canvas = canvas
  },

  _animateZoom(e) {
    const scale = this._map.getZoomScale(e.zoom)
    const offset = this._map._getCenterOffset(e.center)
      ._multiplyBy(-scale)
      .subtract(this._map._getMapPanePos())
    L.DomUtil.setTransform(this._canvas, offset, scale)
  },

  _reset() {
    const topLeft = this._map.containerPointToLayerPoint([0, 0])
    L.DomUtil.setTransform(this._canvas, topLeft, 1)
    const size = this._map.getSize()
    if (this._canvas.width !== size.x) this._canvas.width = size.x
    if (this._canvas.height !== size.y) this._canvas.height = size.y
    this._redraw()
  },

  _redraw() {
    if (!this._map || !this._canvas) return
    const ctx = this._canvas.getContext('2d')
    const size = this._map.getSize()
    ctx.clearRect(0, 0, size.x, size.y)

    const radius = this.options.radius
    const peak = this.options.opacity

    for (const [lat, lng, weight] of this._points) {
      const p = this._map.latLngToContainerPoint([lat, lng])
      if (
        p.x < -radius || p.y < -radius ||
        p.x > size.x + radius || p.y > size.y + radius
      ) {
        continue
      }
      const color = rampColor(weight)
      const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, radius)
      grad.addColorStop(0, rgba(color, peak))
      grad.addColorStop(0.55, rgba(color, peak * 0.45))
      grad.addColorStop(1, rgba(color, 0))
      ctx.fillStyle = grad
      ctx.beginPath()
      ctx.arc(p.x, p.y, radius, 0, Math.PI * 2)
      ctx.fill()
    }
  },
})

export function heatCanvas(points, options) {
  return new HeatCanvas(points, options)
}

export default HeatCanvas
