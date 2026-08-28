# Dataset real ESC-50

El entrenamiento usa 240 grabaciones reales de ESC-50:

```text
dataset/esc50/
├── claxon/       # categoría original: car_horn
├── ladrido/      # dog
├── aplausos/     # clapping
├── lluvia/       # rain
├── sirena/       # siren
├── helicoptero/  # helicopter
└── manifest.csv
```

Cada clase contiene 40 WAV de cinco segundos. El manifiesto conserva el fold
oficial y el identificador original. La división utilizada es:

- folds 1–3: entrenamiento, 144 audios (60 %);
- fold 4: validación, 48 audios (20 %);
- fold 5: prueba, 48 audios (20 %).

Para reconstruir esta carpeta desde el repositorio oficial:

```powershell
git clone --depth 1 https://github.com/karolpiczak/ESC-50.git C:\tmp\ESC-50
.venv\Scripts\python.exe -m src.prepare_esc50 --source-dir C:\tmp\ESC-50
```

Los WAV del dataset están ignorados por Git. ESC-50 tiene licencia CC BY-NC y
debe utilizarse aquí con fines académicos no comerciales.
