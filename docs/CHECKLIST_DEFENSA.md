# Checklist de defensa

## 48 horas antes

- [ ] Confirmar `dataset.kind = real_recordings` y `source = ESC-50`.
- [ ] Confirmar seis clases y 40 muestras por clase en `metadata.json`.
- [ ] Revisar matriz de confusión y memorizar 89,58 % de test y 89,29 % F1.
- [ ] Recordar que SGD fue seleccionado por validación, no por test.
- [ ] Ejecutar `.venv\Scripts\python.exe -m pytest -q`.
- [ ] Subir modelo, metadata, resultados y los seis audios demo.
- [ ] Desplegar la misma revisión en Railway.

## 24 horas antes

- [ ] Escuchar los seis reproductores de la web.
- [ ] Analizar al menos un WAV de respaldo por clase.
- [ ] Probar la URL desde laptop y teléfono.
- [ ] Confirmar `/health` con HTTP 200.
- [ ] Guardar capturas de matriz, curvas y una predicción.
- [ ] Ensayar con cronómetro y respetar el reparto de tres personas.

## Antes de entrar

- [ ] URL y repositorio accesibles.
- [ ] Carpeta local con seis WAV del fold 5.
- [ ] Aplicación local preparada con `scripts/run_local.ps1`.
- [ ] Permiso de micrófono concedido.
- [ ] Capturas disponibles como plan B.
- [ ] Notificaciones desactivadas, cargador y adaptadores listos.
