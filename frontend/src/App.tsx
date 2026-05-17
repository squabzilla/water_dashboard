import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'

export default function App() {
  const mapContainer = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!mapContainer.current) return

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: 'https://demotiles.maplibre.org/style.json',
      center: [-114.0719, 51.0447],
      zoom: 10,
    })

    map.on('load', async () => {
      const bounds = map.getBounds()

      const response = await fetch(
        `http://127.0.0.1:8000/features?minx=${bounds.getWest()}&miny=${bounds.getSouth()}&maxx=${bounds.getEast()}&maxy=${bounds.getNorth()}`
      )

      const data = await response.json()

      map.addSource('locations', {
        type: 'geojson',
        data,
      })

      map.addLayer({
        id: 'locations-layer',
        type: 'circle',
        source: 'locations',
        paint: {
          'circle-radius': 6,
          'circle-color': '#ff0000',
        },
      })
    })

    return () => map.remove()
  }, [])

  return (
    <div
      ref={mapContainer}
      style={{
        width: '100vw',
        height: '100vh',
      }}
    />
  )
}