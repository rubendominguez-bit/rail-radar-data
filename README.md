# Actualizador de Ouigo para Rail Radar

Publicación gratuita preparada para un repositorio público de GitHub, GitHub Actions y GitHub Pages. Este directorio es el repositorio de publicación; no se publica el código de la app ni se incluye la clave del NAP en ningún fichero.

1. Crear el repositorio con el contenido de este directorio.
2. Guardar la clave del NAP como secreto de Actions llamado `NAP_API_KEY`.
3. Activar GitHub Pages con Source: GitHub Actions. El trabajo publica únicamente el directorio `docs` con las acciones oficiales de Pages.
4. Ejecutar «Renovar horario Ouigo» una primera vez y verificar la publicación.
5. Configurar `RailRadarOuigoManifestURL` en la app con `https://rubendominguez-bit.github.io/rail-radar-data/ouigo.json`.

El trabajo comprueba diariamente a las 06:17 UTC el último fichero GTFS validado del conjunto 1515. Descarga el enlace temporal emitido por el NAP sin enviar la clave al almacén del fichero. Valida estructura, límites, calendarios y caducidad antes de publicar. La app solo recibe el GTFS público y metadatos con hash SHA-256; nunca recibe la clave ni el enlace firmado temporal.

Si falla la renovación, el trabajo falla y conserva la última publicación válida. GitHub puede retrasar los trabajos programados; la app debe comprobar la vigencia del calendario y no asumir una renovación exitosa. El manifiesto cambia con cada comprobación correcta y su commit mantiene actividad en el repositorio. No se declara una fecha de consulta nueva cuando el NAP falla.

La publicación contiene datos programados, sin retrasos ni confirmaciones de circulación. Los avisos de ADIF y los comunicados oficiales del operador se consultan por separado.

Estado inicial: preparado localmente. No está desplegado ni renovándose hasta conectar GitHub, configurar el secreto y verificar la primera ejecución.
