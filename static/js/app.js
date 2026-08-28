"use strict";

const MAX_RECORDING_MS = 8000;
const state = {
  file: null,
  objectUrl: null,
  recording: false,
  audioContext: null,
  stream: null,
  processor: null,
  source: null,
  chunks: [],
  timer: null,
  startedAt: 0,
};

const $ = (selector) => document.querySelector(selector);
const tabs = [...document.querySelectorAll(".mode-tab")];
const fileInput = $("#audio-file");
const dropZone = $("#drop-zone");
const audioPreview = $("#audio-preview");
const player = $("#audio-player");
const analyzeButton = $("#analyze-button");
const feedback = $("#feedback");
const recordButton = $("#record-button");

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((candidate) => {
      const selected = candidate === tab;
      candidate.classList.toggle("active", selected);
      candidate.setAttribute("aria-selected", String(selected));
      const panel = document.getElementById(candidate.dataset.panel);
      panel.hidden = !selected;
      panel.classList.toggle("active", selected);
    });
  });
});

fileInput.addEventListener("change", () => setFile(fileInput.files[0]));
["dragenter", "dragover"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("dragging");
  });
});
["dragleave", "drop"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragging");
  });
});
dropZone.addEventListener("drop", (event) => setFile(event.dataTransfer.files[0]));
$("#remove-file").addEventListener("click", clearFile);
recordButton.addEventListener("click", () => state.recording ? stopRecording() : startRecording());
analyzeButton.addEventListener("click", analyzeAudio);

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

function setFeedback(message = "", type = "error") {
  feedback.textContent = message;
  feedback.classList.remove("info", "success");
  if (message && type !== "error") feedback.classList.add(type);
}

async function setFile(file) {
  if (!file) return;
  if (file.size > 10 * 1024 * 1024) {
    setFeedback("El archivo supera el límite de 10 MB.");
    return;
  }
  setFeedback();
  if (state.objectUrl) URL.revokeObjectURL(state.objectUrl);
  state.file = file;
  state.objectUrl = URL.createObjectURL(file);
  player.src = state.objectUrl;
  $("#file-name").textContent = file.name;
  $("#file-size").textContent = formatBytes(file.size);
  $(".file-type").textContent = (file.name.split(".").pop() || "audio").toUpperCase();
  audioPreview.hidden = false;
  analyzeButton.disabled = false;
  setFeedback("Audio listo. Pulsa “Analizar audio” para obtener la predicción.", "info");
  await drawWaveform(file);
}

function clearFile() {
  if (state.objectUrl) URL.revokeObjectURL(state.objectUrl);
  state.file = null;
  state.objectUrl = null;
  fileInput.value = "";
  player.removeAttribute("src");
  player.load();
  audioPreview.hidden = true;
  analyzeButton.disabled = true;
  setFeedback();
}

async function drawWaveform(file) {
  const canvas = $("#waveform");
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, canvas.width, canvas.height);
  try {
    const bytes = await file.arrayBuffer();
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const buffer = await audioContext.decodeAudioData(bytes.slice(0));
    const data = buffer.getChannelData(0);
    const step = Math.max(1, Math.floor(data.length / canvas.width));
    const gradient = context.createLinearGradient(0, 0, canvas.width, 0);
    gradient.addColorStop(0, "#8a6bff");
    gradient.addColorStop(1, "#16d8e9");
    context.strokeStyle = gradient;
    context.lineWidth = 1.4;
    context.beginPath();
    for (let x = 0; x < canvas.width; x += 1) {
      let min = 1;
      let max = -1;
      for (let j = 0; j < step; j += 1) {
        const value = data[x * step + j] || 0;
        min = Math.min(min, value);
        max = Math.max(max, value);
      }
      context.moveTo(x, (1 + min) * canvas.height / 2);
      context.lineTo(x, (1 + max) * canvas.height / 2);
    }
    context.stroke();
    await audioContext.close();
  } catch {
    context.fillStyle = "#567184";
    context.font = "13px system-ui";
    context.textAlign = "center";
    context.fillText("Vista previa no disponible para este formato", canvas.width / 2, 65);
  }
}

async function startRecording() {
  setFeedback();
  if (!navigator.mediaDevices?.getUserMedia) {
    setFeedback("Este navegador no permite acceder al micrófono.");
    return;
  }
  try {
    state.stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    });
    state.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    state.source = state.audioContext.createMediaStreamSource(state.stream);
    state.processor = state.audioContext.createScriptProcessor(4096, 1, 1);
    const silentGain = state.audioContext.createGain();
    silentGain.gain.value = 0;
    state.chunks = [];
    state.processor.onaudioprocess = (event) => {
      if (state.recording) state.chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
    };
    state.source.connect(state.processor);
    state.processor.connect(silentGain);
    silentGain.connect(state.audioContext.destination);
    state.recording = true;
    state.startedAt = performance.now();
    recordButton.classList.add("recording");
    recordButton.setAttribute("aria-label", "Detener grabación");
    $("#record-label").textContent = "Grabando… pulsa para detener";
    updateTimer();
    state.timer = window.setInterval(updateTimer, 100);
    window.setTimeout(() => { if (state.recording) stopRecording(); }, MAX_RECORDING_MS);
  } catch (error) {
    setFeedback(error.name === "NotAllowedError" ? "Permiso de micrófono denegado." : "No se pudo iniciar la grabación.");
    cleanupRecorder();
  }
}

function updateTimer() {
  const elapsed = Math.min(performance.now() - state.startedAt, MAX_RECORDING_MS);
  const seconds = elapsed / 1000;
  $("#record-time").textContent = `00:${seconds.toFixed(1).padStart(4, "0")}`;
}

async function stopRecording() {
  if (!state.recording) return;
  state.recording = false;
  const duration = performance.now() - state.startedAt;
  const sampleRate = state.audioContext.sampleRate;
  const chunks = state.chunks.slice();
  cleanupRecorder();
  recordButton.classList.remove("recording");
  recordButton.setAttribute("aria-label", "Iniciar grabación");
  $("#record-label").textContent = "Listo para volver a grabar";
  if (duration < 250 || chunks.length === 0) {
    setFeedback("La grabación fue demasiado corta. Intenta al menos medio segundo.");
    return;
  }
  const wavBlob = encodeWav(mergeChunks(chunks), sampleRate);
  await setFile(new File([wavBlob], "grabacion.wav", { type: "audio/wav" }));
}

function cleanupRecorder() {
  if (state.timer) window.clearInterval(state.timer);
  state.timer = null;
  if (state.processor) state.processor.disconnect();
  if (state.source) state.source.disconnect();
  if (state.stream) state.stream.getTracks().forEach((track) => track.stop());
  if (state.audioContext && state.audioContext.state !== "closed") state.audioContext.close();
  state.processor = null;
  state.source = null;
  state.stream = null;
  state.audioContext = null;
}

function mergeChunks(chunks) {
  const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const result = new Float32Array(length);
  let offset = 0;
  chunks.forEach((chunk) => { result.set(chunk, offset); offset += chunk.length; });
  return result;
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const write = (offset, value) => [...value].forEach((char, index) => view.setUint8(offset + index, char.charCodeAt(0)));
  write(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, samples.length * 2, true);
  let offset = 44;
  samples.forEach((sample) => {
    const clipped = Math.max(-1, Math.min(1, sample));
    view.setInt16(offset, clipped < 0 ? clipped * 0x8000 : clipped * 0x7fff, true);
    offset += 2;
  });
  return new Blob([buffer], { type: "audio/wav" });
}

async function analyzeAudio() {
  if (!state.file) {
    setFeedback("Primero selecciona o graba un archivo de audio.");
    return;
  }
  setFeedback("Enviando el audio y ejecutando el modelo…", "info");
  analyzeButton.disabled = true;
  analyzeButton.classList.add("loading");
  $(".button-label").textContent = "Escuchando…";
  const form = new FormData();
  form.append("audio", state.file, state.file.name);
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 60000);
  try {
    const response = await fetch("/api/predict", {
      method: "POST",
      body: form,
      signal: controller.signal,
      headers: { "X-Requested-With": "fetch" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || "El servidor no pudo procesar el audio.");
    renderResult(payload);
    setFeedback(`Análisis completado: ${payload.label} (${Math.round(payload.confidence * 100)}%).`, "success");
  } catch (error) {
    console.error("Error al analizar audio", error);
    const message = error.name === "AbortError"
      ? "El análisis tardó más de 60 segundos. Intenta nuevamente con un WAV corto."
      : (error.message || "Error de conexión con el servidor.");
    setFeedback(message);
  } finally {
    window.clearTimeout(timeout);
    analyzeButton.disabled = false;
    analyzeButton.classList.remove("loading");
    $(".button-label").textContent = "Analizar audio";
  }
}

function renderResult(result) {
  if (!result || !Array.isArray(result.probabilities)) {
    throw new Error("El servidor devolvió una respuesta incompleta.");
  }
  const emptyResult = $("#empty-result");
  const resultContent = $("#result-content");
  emptyResult.hidden = true;
  emptyResult.style.display = "none";
  resultContent.hidden = false;
  resultContent.style.display = "block";
  const percent = Math.round(result.confidence * 100);
  $("#confidence").textContent = `${percent}%`;
  $("#confidence-ring").style.setProperty("--confidence", `${percent * 3.6}deg`);
  $("#prediction-label").textContent = result.label;
  $("#latency").textContent = `${result.latency_ms} ms`;
  const list = $("#probability-list");
  list.replaceChildren(...result.probabilities.map((item) => {
    const row = document.createElement("div");
    row.className = "probability-row";
    const label = document.createElement("span");
    label.textContent = item.label;
    const track = document.createElement("div");
    track.className = "probability-track";
    const bar = document.createElement("i");
    bar.style.setProperty("--value", `${item.probability * 100}%`);
    track.append(bar);
    const value = document.createElement("span");
    value.textContent = `${(item.probability * 100).toFixed(1)}%`;
    row.append(label, track, value);
    return row;
  }));
  try {
    drawSpectrogram(result.spectrogram);
  } catch (error) {
    console.warn("No se pudo dibujar el espectrograma", error);
  }
  const warning = $("#model-warning");
  warning.hidden = !result.model.warning;
  warning.textContent = result.model.warning || "";
  $("#result-panel").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function drawSpectrogram(matrix) {
  if (!Array.isArray(matrix) || matrix.length === 0 || !Array.isArray(matrix[0])) {
    throw new Error("Espectrograma vacío");
  }
  const canvas = $("#spectrogram");
  const context = canvas.getContext("2d");
  const height = matrix.length;
  const width = matrix[0]?.length || 0;
  const image = context.createImageData(width, height);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const value = Math.max(0, Math.min(1, matrix[height - 1 - y][x]));
      const color = heatColor(value);
      const index = (y * width + x) * 4;
      image.data[index] = color[0];
      image.data[index + 1] = color[1];
      image.data[index + 2] = color[2];
      image.data[index + 3] = 255;
    }
  }
  const offscreen = document.createElement("canvas");
  offscreen.width = width;
  offscreen.height = height;
  offscreen.getContext("2d").putImageData(image, 0, 0);
  context.imageSmoothingEnabled = true;
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.drawImage(offscreen, 0, 0, canvas.width, canvas.height);
}

function heatColor(value) {
  const stops = [
    [6, 16, 27],
    [33, 35, 87],
    [106, 71, 179],
    [22, 216, 233],
    [217, 255, 245],
  ];
  const scaled = value * (stops.length - 1);
  const left = Math.min(stops.length - 2, Math.floor(scaled));
  const mix = scaled - left;
  return stops[left].map((channel, index) => Math.round(channel + (stops[left + 1][index] - channel) * mix));
}

window.addEventListener("unhandledrejection", (event) => {
  console.error("Error no controlado", event.reason);
  setFeedback("Ocurrió un error de interfaz. Recarga con Ctrl+F5 e inténtalo otra vez.");
});
