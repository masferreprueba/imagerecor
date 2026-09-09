"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Archive, ArrowRight, Check, Download, FileArchive, ImageIcon, LoaderCircle, RefreshCw, ShieldCheck, Sparkles, UploadCloud, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Toaster } from "@/components/ui/sonner";

type JobState = "idle" | "ready" | "waking" | "uploading" | "queued" | "processing" | "completed" | "failed";
type Job = {
  id: string; status: JobState; filename: string; total_images: number;
  processed_images: number; failed_images: number; progress: number; provider: string;
  error?: string | null; download_url?: string | null;
  download_png_url?: string | null; download_jpeg_url?: string | null;
  download_studio_url?: string | null;
  download_template_url?: string | null;
  previews?: Array<{ name: string; original_url: string; processed_url?: string | null; status: string }>;
};

const CONFIGURED_API_URL = process.env.NEXT_PUBLIC_API_URL?.trim() || "https://mas-ferre-image-processor.onrender.com";
const API_URL = CONFIGURED_API_URL.replace(/\/$/, "");
const API_CONFIGURED = Boolean(CONFIGURED_API_URL);
const MAX_BYTES = 250 * 1024 * 1024;

const sleep = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds));

async function waitForService() {
  let lastError: unknown;
  for (let attempt = 0; attempt < 5; attempt += 1) {
    try {
      const response = await fetch(`${API_URL}/health`, { cache: "no-store" });
      if (response.ok) return;
      lastError = new Error(`Respuesta ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    if (attempt < 4) await sleep(3000 * (attempt + 1));
  }
  throw new Error(
    lastError
      ? "El servicio gratuito está tardando en iniciar. Espera un minuto y vuelve a intentarlo."
      : "No fue posible iniciar el servicio de procesamiento."
  );
}

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function Home() {
  const inputRef = useRef<HTMLInputElement>(null);
  const templateInputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollFailuresRef = useRef(0);
  const [file, setFile] = useState<File | null>(null);
  const [templateFile, setTemplateFile] = useState<File | null>(null);
  const [templateName, setTemplateName] = useState("");
  const [state, setState] = useState<JobState>("idle");
  const [dragging, setDragging] = useState(false);
  const [job, setJob] = useState<Job | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const acceptFile = (candidate?: File) => {
    if (!candidate) return;
    if (!templateFile) { toast.error("Selecciona primero una plantilla PNG."); return; }
    if (!candidate.name.toLowerCase().endsWith(".zip")) {
      toast.error("Selecciona un archivo ZIP válido.");
      return;
    }
    if (candidate.size > MAX_BYTES) {
      toast.error("El ZIP supera el límite de 250 MB.");
      return;
    }
    setFile(candidate); setState("ready"); setJob(null);
  };

  const acceptTemplate = async (candidate?: File) => {
    if (!candidate) return;
    if (!candidate.name.toLowerCase().endsWith(".png")) { toast.error("Selecciona una plantilla PNG."); return; }
    const bitmap = await createImageBitmap(candidate);
    const validSize = bitmap.width === 500 && bitmap.height === 500;
    bitmap.close();
    if (!validSize) { toast.error("La plantilla debe medir exactamente 500 × 500 px."); return; }
    setTemplateFile(candidate);
    if (!templateName) setTemplateName(candidate.name.replace(/\.png$/i, "").replace(/[_-]+/g, " "));
    setFile(null); setState("idle"); setJob(null);
  };

  const refreshJob = useCallback(async (jobId: string) => {
    const response = await fetch(`${API_URL}/api/jobs/${jobId}`, { cache: "no-store" });
    if (!response.ok) throw new Error("No fue posible consultar el proceso.");
    const data: Job = await response.json();
    pollFailuresRef.current = 0;
    setJob(data); setState(data.status);
    if (data.status === "completed" || data.status === "failed") {
      stopPolling();
      data.status === "completed"
        ? toast.success(`${data.processed_images} imágenes listas para descargar.`)
        : toast.error(data.error || "El proceso no pudo completarse.");
    }
  }, [stopPolling]);

  const startProcessing = async () => {
    if (!file || !templateFile || !templateName.trim()) { toast.error("Selecciona y nombra la plantilla antes de procesar."); return; }
    if (!API_CONFIGURED) {
      const message = "El servidor de procesamiento todavía no está conectado a esta versión publicada.";
      setState("failed");
      setJob({
        id: "", status: "failed", filename: file.name, total_images: 0,
        processed_images: 0, failed_images: 0, progress: 0,
        provider: "pendiente", error: message,
      });
      toast.error(message);
      return;
    }
    pollFailuresRef.current = 0;
    setState("waking");
    const form = new FormData(); form.append("file", file); form.append("template", templateFile); form.append("template_name", templateName.trim());
    try {
      await waitForService();
      setState("uploading");
      const response = await fetch(`${API_URL}/api/jobs`, { method: "POST", body: form });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || "No se pudo cargar el ZIP.");
      setJob(payload); setState(payload.status);
      pollRef.current = setInterval(() => refreshJob(payload.id).catch((error) => {
        pollFailuresRef.current += 1;
        if (pollFailuresRef.current < 12) return;
        stopPolling();
        setState("failed");
        setJob((current) => current ? { ...current, status: "failed", error: "Se perdió temporalmente la conexión. Pulsa Volver e inténtalo nuevamente." } : current);
        toast.error(error.message);
      }), 1500);
      await refreshJob(payload.id);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Error de conexión con el servidor.";
      setState("failed");
      setJob({
        id: "", status: "failed", filename: file.name, total_images: 0,
        processed_images: 0, failed_images: 0, progress: 0,
        provider: "photoroom", error: message,
      });
      toast.error(message);
    }
  };

  const reset = () => {
    stopPolling(); pollFailuresRef.current = 0; setFile(null); setTemplateFile(null); setTemplateName(""); setJob(null); setState("idle");
    if (inputRef.current) inputRef.current.value = "";
    if (templateInputRef.current) templateInputRef.current.value = "";
  };
  const busy = ["waking", "uploading", "queued", "extracting", "processing", "packaging"].includes(state);
  const progress = state === "waking" ? 3 : state === "uploading" ? 8 : job?.progress || 0;

  return (
    <main className="min-h-screen bg-[#f5f7f8] text-[#102321]">
      <Toaster richColors position="top-right" />
      <header className="border-b border-black/8 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-18 max-w-7xl items-center justify-between px-5 sm:px-8">
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-xl bg-[#ef312d] text-white shadow-[0_8px_24px_rgba(239,49,45,.24)]"><Sparkles className="size-5" /></div>
            <div><p className="text-[12px] font-extrabold uppercase tracking-[.22em] text-[#ef312d]">Mas Ferre</p><p className="text-[15px] font-bold leading-5">Estudio de imágenes</p></div>
          </div>
          <div className="hidden items-center gap-2 rounded-full border border-[#c9d6d2] bg-[#f4faf7] px-3 py-1.5 text-sm font-semibold text-[#1f5c48] sm:flex"><ShieldCheck className="size-4" /> Archivos protegidos</div>
        </div>
      </header>

      <section className="mx-auto grid max-w-7xl gap-8 px-5 py-10 sm:px-8 lg:grid-cols-[minmax(0,1fr)_360px] lg:py-14">
        <div>
          <div className="mb-8 max-w-3xl">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-[#e4f0eb] px-3 py-1.5 text-xs font-extrabold uppercase tracking-[.14em] text-[#1f5c48]"><span className="size-1.5 rounded-full bg-[#ef312d]" /> Flujo automatizado</div>
            <h1 className="text-balance text-4xl font-black leading-[1.05] tracking-[-.045em] sm:text-5xl lg:text-[3.6rem]">Productos limpios, listos para catálogo.</h1>
            <p className="mt-5 max-w-2xl text-lg leading-7 text-[#536360]">Carga un ZIP y recibe imágenes sin fondo, con fondo blanco y una versión gratuita con acabado de estudio.</p>
            {!API_CONFIGURED && (
              <div className="mt-5 flex max-w-2xl items-start gap-3 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950">
                <ShieldCheck className="mt-0.5 size-4 shrink-0" />
                <p><b>Procesamiento pendiente de activación.</b> La interfaz está disponible, pero falta conectar el backend y la llave del proveedor de IA.</p>
              </div>
            )}
          </div>

          <div className="overflow-hidden rounded-[28px] border border-black/8 bg-white shadow-[0_24px_70px_rgba(16,35,33,.09)]">
            <div className="flex items-center justify-between border-b border-black/7 px-6 py-4"><div className="flex items-center gap-2 text-sm font-bold"><Archive className="size-4 text-[#ef312d]" /> Nuevo procesamiento</div><span className="text-xs font-semibold text-[#71807d]">ZIP · Máx. 250 MB</span></div>
            <div className="p-5 sm:p-7">
              <div className="mb-5 rounded-2xl border border-[#d7e0dd] bg-[#f8fbfa] p-5">
                <p className="font-extrabold">1. Selecciona la plantilla</p>
                <p className="mt-1 text-sm text-[#657572]">PNG de 500 × 500 px con un área transparente para el producto.</p>
                <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
                  <input value={templateName} onChange={(event) => setTemplateName(event.target.value)} maxLength={120} placeholder="Nombre de la plantilla" className="rounded-lg border border-[#cbd6d2] bg-white px-4 py-3" />
                  <Button variant="outline" onClick={() => templateInputRef.current?.click()}>{templateFile ? "Cambiar plantilla" : "Seleccionar PNG"}</Button>
                </div>
                {templateFile && <p className="mt-3 truncate text-sm font-bold text-[#1f5c48]">✓ {templateFile.name} · 500 × 500 px</p>}
                <input ref={templateInputRef} type="file" accept="image/png,.png" className="hidden" onChange={(event) => acceptTemplate(event.target.files?.[0]).catch(() => toast.error("No fue posible leer la plantilla."))} />
              </div>
              {templateFile && (!file ? (
                <button
                  className={`group relative grid min-h-[290px] w-full place-items-center overflow-hidden rounded-2xl border-2 border-dashed p-8 text-center transition ${dragging ? "border-[#ef312d] bg-[#fff7f6]" : "border-[#b9c7c3] bg-[#f8fbfa] hover:border-[#ef312d] hover:bg-[#fffafa]"}`}
                  onClick={() => inputRef.current?.click()}
                  onDragEnter={(e) => { e.preventDefault(); setDragging(true); }}
                  onDragOver={(e) => e.preventDefault()}
                  onDragLeave={() => setDragging(false)}
                  onDrop={(e) => { e.preventDefault(); setDragging(false); acceptFile(e.dataTransfer.files[0]); }}
                  type="button"
                >
                  <div className="absolute inset-0 opacity-[.035] [background-image:linear-gradient(#102321_1px,transparent_1px),linear-gradient(90deg,#102321_1px,transparent_1px)] [background-size:28px_28px]" />
                  <div className="relative">
                    <div className="mx-auto mb-5 grid size-16 place-items-center rounded-2xl bg-[#102321] text-white shadow-xl transition group-hover:-translate-y-1"><UploadCloud className="size-7" /></div>
                    <p className="text-xl font-black">2. Carga las fotografías</p>
                    <p className="mt-2 text-[15px] text-[#6c7977]">Arrastra o selecciona el archivo ZIP</p>
                    <span className="mt-6 inline-flex rounded-lg border border-black/10 bg-white px-4 py-2 text-sm font-bold shadow-sm">Seleccionar archivo</span>
                  </div>
                </button>
              ) : (
                <div>
                  <div className="flex flex-col gap-4 rounded-2xl border border-[#d7e0dd] bg-[#f8fbfa] p-5 sm:flex-row sm:items-center">
                    <div className="grid size-14 shrink-0 place-items-center rounded-xl bg-[#e3eee9] text-[#1f5c48]"><FileArchive className="size-7" /></div>
                    <div className="min-w-0 flex-1"><p className="truncate font-extrabold">{file.name}</p><p className="mt-1 text-sm text-[#71807d]">{formatBytes(file.size)} · Listo para procesar</p></div>
                    {!busy && state !== "completed" && <Button variant="ghost" size="icon" onClick={reset} aria-label="Quitar archivo"><X /></Button>}
                  </div>
                  {state === "ready" && <><div className="mt-5 flex items-start gap-3 rounded-xl border border-[#bdd7cc] bg-[#f1f8f5] p-4"><div className="grid size-9 shrink-0 place-items-center rounded-lg bg-[#1f5c48] text-white"><Sparkles className="size-4" /></div><div><p className="text-sm font-extrabold">Plantilla y mejora en un solo proceso</p><p className="mt-1 text-sm leading-5 text-[#60716d]">Después de colocar y ampliar cada producto 15%, mejoraremos nitidez, iluminación y detalle sin alterar el diseño de la plantilla.</p></div></div><div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end"><Button variant="outline" size="lg" onClick={reset}>Cancelar</Button><Button size="lg" onClick={startProcessing} className="bg-[#ef312d] font-bold text-white hover:bg-[#d92522]">▦ Crear con plantilla + mejorar calidad <ArrowRight /></Button></div></>}
                  {(busy || state === "completed" || state === "failed") && (
                    <div className="mt-7">
                      <div className="mb-3 flex items-end justify-between gap-4"><div><p className="font-extrabold">{state === "completed" ? "Procesamiento terminado" : state === "failed" ? "Revisa el proceso" : "Procesando imágenes"}</p><p className="mt-1 text-sm text-[#71807d]">{state === "waking" ? "Conectando con el servicio gratuito…" : state === "uploading" ? "Subiendo ZIP…" : state === "queued" ? "Trabajo en cola…" : job ? `${job.processed_images} de ${job.total_images} imágenes` : "Preparando archivos…"}</p></div><span className="text-2xl font-black tabular-nums">{Math.round(progress)}%</span></div>
                      <Progress value={progress} className="h-3 bg-[#e4ebe8] [&_[data-slot=progress-indicator]]:bg-[#ef312d]" />
                      {state === "completed" && job && <div className="mt-6 flex flex-col gap-4 rounded-2xl bg-[#102321] p-5 text-white"><div className="flex items-center gap-4"><div className="grid size-11 shrink-0 place-items-center rounded-full bg-[#47b881] text-[#102321]"><Check className="size-5 stroke-[3]" /></div><div className="flex-1"><p className="font-extrabold">{job.processed_images} archivos listos</p><p className="mt-1 text-sm text-white/65">JPEG de alta calidad · 500 × 500 px · plantilla protegida.</p></div></div><Button asChild size="lg" className="bg-[#ef312d] font-bold text-white hover:bg-[#d92522]"><a href={`${API_URL}${job.download_template_url}`}><Download /> Descargar imágenes en ZIP</a></Button></div>}
                      {state === "failed" && <div className="mt-6 flex items-center justify-between gap-4 rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-950"><p className="text-sm font-semibold">{job?.error || "No fue posible conectar con el servicio."}</p><Button variant="outline" size="sm" onClick={reset}><RefreshCw /> Volver</Button></div>}
                    </div>
                  )}
                </div>
              ))}
              <input ref={inputRef} type="file" accept=".zip,application/zip" className="hidden" onChange={(e) => acceptFile(e.target.files?.[0])} />
            </div>
          </div>
          {job?.previews && job.previews.length > 0 && <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{job.previews.slice(0, 6).map((preview) => <article key={preview.name} className="overflow-hidden rounded-2xl border border-black/8 bg-white"><div className="checkerboard aspect-square p-4"><img src={`${API_URL}${preview.processed_url || preview.original_url}`} alt={preview.name} className="h-full w-full object-contain" /></div><p className="truncate border-t border-black/7 px-4 py-3 text-sm font-bold">{preview.name}</p></article>)}</div>}
        </div>

        <aside className="space-y-5 lg:pt-[172px]">
          <div className="rounded-[24px] bg-[#102321] p-6 text-white shadow-[0_20px_55px_rgba(16,35,33,.18)]"><div className="mb-6 flex items-center justify-between"><p className="font-black">Resultado final</p><Sparkles className="size-5 text-[#ef312d]" /></div><div className="grid grid-cols-2 gap-3"><Stat value="500" label="JPEG final" suffix="× 500" /><Stat value="+15%" label="tamaño visual" /><Stat value="Auto" label="luz y nitidez" /><Stat value="1 ZIP" label="nombre de plantilla" /></div></div>
          <div className="rounded-[24px] border border-black/8 bg-white p-6"><p className="mb-5 font-black">Así funciona</p><ol className="space-y-5"><Step number="01" icon={<FileArchive />} title="Preparamos" text="Validamos las fotografías y eliminamos sus fondos." /><Step number="02" icon={<ImageIcon />} title="Componemos" text="Las colocamos en la plantilla y aumentamos su tamaño visual 15% desde el centro." /><Step number="03" icon={<Sparkles />} title="Mejoramos" text="Optimizamos el producto y generamos un único ZIP en JPEG." /></ol></div>
          <div className="flex items-center gap-3 px-2 text-sm text-[#657572]"><LoaderCircle className="size-4" /><span>Servicio: <b className="capitalize">{API_CONFIGURED ? (job?.provider || "conectado") : "pendiente de conexión"}</b></span></div>
        </aside>
      </section>
    </main>
  );
}

function Stat({ value, label, suffix }: { value: string; label: string; suffix?: string }) {
  return <div className="rounded-xl bg-white/7 p-4"><p className="text-xl font-black">{value}<span className="ml-1 text-xs font-semibold text-white/50">{suffix}</span></p><p className="mt-1 text-xs text-white/55">{label}</p></div>;
}

function Step({ number, icon, title, text }: { number: string; icon: React.ReactNode; title: string; text: string }) {
  return <li className="flex gap-3"><div className="relative grid size-10 shrink-0 place-items-center rounded-xl bg-[#edf4f1] text-[#1f5c48] [&_svg]:size-4">{icon}<span className="absolute -right-1 -top-1 grid size-4 place-items-center rounded-full bg-[#ef312d] text-[8px] font-black text-white">{number}</span></div><div><p className="text-sm font-extrabold">{title}</p><p className="mt-1 text-sm leading-5 text-[#71807d]">{text}</p></div></li>;
}
