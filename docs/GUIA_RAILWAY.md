# Guía para desplegar en Railway

Guía verificada para la interfaz de Railway vigente en agosto de 2026. El
proyecto usa Docker porque fija Python 3.11, FFmpeg, libsndfile y TensorFlow de
forma reproducible.

## Antes de subir

1. Entrenen con el dataset definitivo.
2. Comprueben que existen `model/audio_classifier.keras` y
   `model/metadata.json`.
3. Ejecuten `.venv\Scripts\python.exe -m pytest -q`.
4. Inicien localmente y prueben un audio de cada clase.
5. Verifiquen que Git no incluya `.venv/` ni los audios del dataset. El modelo y
   `metadata.json` sí deben subirse.

## Opción recomendada: GitHub + Dockerfile

### 1. Crear el repositorio

Desde la raíz del proyecto:

```powershell
git init
git add .
git commit -m "Proyecto final de reconocimiento de audio"
git branch -M main
git remote add origin https://github.com/USUARIO/REPOSITORIO.git
git push -u origin main
```

Antes de `git add .`, revisen `git status`. Nunca suban contraseñas, tokens ni
un archivo `.env`.

### 2. Crear el servicio

1. Entren en [Railway](https://railway.com/) y creen **New Project**.
2. Elijan **Deploy from GitHub repo** y autoricen el repositorio.
3. Seleccionen este proyecto. Railway detecta automáticamente el archivo
   `Dockerfile` de la raíz y construye la imagen.
4. Esperen la primera compilación y abran **View logs**.

La [guía oficial de Flask](https://docs.railway.com/guides/flask) confirma el
flujo desde GitHub y la detección del Dockerfile; la referencia de
[Dockerfiles](https://docs.railway.com/builds/dockerfiles) indica que debe
llamarse exactamente `Dockerfile` con D mayúscula.

### 3. Configurar variables

En **Service → Variables**, las siguientes son opcionales porque ya tienen
valores seguros:

```text
MODEL_PATH=model/audio_classifier.keras
METADATA_PATH=model/metadata.json
MAX_AUDIO_MB=10
LOG_LEVEL=INFO
```

No definan `PORT`: Railway lo inyecta. Gunicorn se enlaza a `0.0.0.0` y a esa
variable desde el `Dockerfile`, tal como exige la
[guía de solución de errores de red](https://docs.railway.com/networking/troubleshooting/application-failed-to-respond).

### 4. Configurar el healthcheck

En **Service → Settings → Deploy → Healthcheck Path**, escriban:

```text
/health
```

Usen un timeout de 300 segundos porque el primer arranque de TensorFlow puede
tardar. Railway solo activa el nuevo despliegue cuando este endpoint devuelve
HTTP 200, según su documentación de
[healthchecks](https://docs.railway.com/deployments/healthchecks).

No se incluye `railway.toml`: el mecanismo Config as Code está deprecado para
servicios nuevos y tiene corte anunciado para diciembre de 2026. Estos dos
ajustes se hacen desde el panel.

### 5. Generar URL pública

1. Vayan a **Settings → Networking → Public Networking**.
2. Pulsen **Generate Domain**.
3. Abran la URL `https://...up.railway.app`.

Los servicios no reciben dominio automáticamente; este paso está documentado
en [Working with Domains](https://docs.railway.com/networking/domains/working-with-domains).

### 6. Prueba de aceptación

- Abrir `/health` y confirmar `"model_available": true`.
- Probar carga de WAV desde computadora.
- Probar grabación desde un teléfono; el navegador pedirá permiso de micrófono.
- Ejecutar al menos un ejemplo de cada clase.
- Revisar logs durante una predicción.
- Guardar capturas de Build, Deploy, URL y una predicción para la exposición.

## Si falla

| Síntoma | Causa probable | Solución |
|---|---|---|
| Build muy pesado | TensorFlow y FFmpeg tardan | Esperar el primer build; los siguientes aprovechan caché |
| `/health` devuelve 503 | Falta modelo o metadata | Subir ambos archivos de `model/` y redesplegar |
| Error 502 | Puerto/host incorrecto | No sobrescribir el CMD; revisar que exista `PORT` en logs |
| Worker killed / out of memory | Memoria insuficiente | Mantener 1 worker, CNN pequeña o aumentar recursos del servicio |
| MP3 no se decodifica | Codec o archivo corrupto | Probar WAV; el contenedor incluye FFmpeg |
| Micrófono bloqueado | Permiso o contexto inseguro | Usar la URL HTTPS de Railway y habilitar permiso del sitio |

## Alternativa con Railway CLI

Con la CLI autenticada, desde la raíz:

```powershell
railway login
railway init
railway up
```

Después configuren healthcheck y dominio desde el panel. La referencia actual de
comandos está en la [documentación de Railway CLI](https://docs.railway.com/cli).

