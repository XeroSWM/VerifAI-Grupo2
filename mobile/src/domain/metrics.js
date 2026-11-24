export const DEFAULT_LIMITS = {
  modo: "hibrido",
  max_videos: "19",
  max_comment_videos: "2",
  bloquear_multimedia: true,
};

export const POPULAR_PROFILES = [
  { name: "khaby.lame", cat: "Comedia / 162M" },
  { name: "mrbeast", cat: "Retos / 104M" },
  { name: "_iamnot_leo_", cat: "Creador / 341K" },
];

export const EXPORT_SCOPES = [
  { id: "all", label: "Completo", desc: "Perfil, videos y comentarios" },
  { id: "videos", label: "Videos & Feed", desc: "Sólo lista de videos y vistas" },
  { id: "comments", label: "Comentarios", desc: "Sólo respuestas y autores" },
];

export function extractHashtags(data) {
  if (!data) return [];
  const counts = {};
  const scan = (text) => {
    if (!text) return;
    const matches = text.match(/#[\w\u00f1\u00d1_]+/gi);
    if (matches) {
      matches.forEach((t) => {
        const clean = t.toLowerCase();
        counts[clean] = (counts[clean] || 0) + 1;
      });
    }
  };
  scan(data.profile?.bio);
  (data.videos || []).forEach((v) => scan(v.desc));
  (data.comments || []).forEach((c) => scan(c.text));
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .map(([tag, count]) => ({ tag, count }));
}

export function calculatePublicationFrequency(videos = []) {
  const timestamps = videos
    .map((v) => Number(v?.create_time))
    .filter((t) => t > 0)
    .sort((a, b) => b - a);

  if (timestamps.length >= 2) {
    const diffsInDays = [];
    for (let i = 0; i < timestamps.length - 1; i++) {
      const diffDays = (timestamps[i] - timestamps[i + 1]) / (1000 * 60 * 60 * 24);
      if (diffDays >= 0) diffsInDays.push(diffDays);
    }
    if (diffsInDays.length > 0) {
      const avgDays = diffsInDays.reduce((a, b) => a + b, 0) / diffsInDays.length;
      if (avgDays <= 1.5) return { label: "Muy Alta", color: "#34d399", desc: "Publica casi a diario (≤ 1-2 días)" };
      if (avgDays <= 4) return { label: "Frecuente", color: "#22d3ee", desc: "Publica cada 2-4 días" };
      if (avgDays <= 8) return { label: "Semanal", color: "#818cf8", desc: "Aprox. 1 video por semana" };
      return { label: "Esporádica", color: "#fbbf24", desc: "Intervalos mayores a 10 días" };
    }
  }

  const count = videos.length;
  if (count >= 15) return { label: "Alta", color: "#34d399", desc: "Gran volumen reciente" };
  if (count >= 6) return { label: "Moderada", color: "#38bdf8", desc: "Ritmo constante" };
  if (count > 0) return { label: "Pausada", color: "#fbbf24", desc: "Poca actividad detectada" };
  return { label: "Sin Datos", color: "#64748b", desc: "Muestra insuficiente" };
}

export function buildExportCSV(data, scope = "all") {
  if (!data) return "";
  let csv = "";
  if (scope === "all") {
    csv += "Tipo,Identificador,Titulo/Texto,Vistas/Autor,Url\n";
    if (data.profile) {
      csv += `Perfil,${data.profile.username},"${(data.profile.bio || "").replace(/"/g, '""')}",${data.profile.followers},https://tiktok.com/${data.profile.username}\n`;
    }
    (data.videos || []).forEach((v) => {
      csv += `Video,${v.id},"${(v.desc || "Video Item").replace(/"/g, '""')}",${v.views},${v.url}\n`;
    });
    (data.comments || []).forEach((c) => {
      csv += `Comentario,${c.id},"${(c.text || "").replace(/"/g, '""')}",${c.author || c.user || "anonimo"},${c.video_url || "-"}\n`;
    });
  } else if (scope === "videos") {
    csv += "ID,URL,Vistas,Likes,Compartidos,Duracion\n";
    (data.videos || []).forEach((v) => {
      csv += `${v.id},${v.url},${v.views},${v.likes || "0"},${v.shares || "0"},${v.duration || "-"}\n`;
    });
  } else if (scope === "comments") {
    csv += "ID_Comentario,Video_ID,Autor,Nombre,Comentario,Likes,Fecha\n";
    (data.comments || []).forEach((c) => {
      csv += `${c.id || "-"},${c.video_id || "-"},${c.author || "-"},"${(c.author_name || "").replace(/"/g, '""')}","${(c.text || "").replace(/"/g, '""')}",${c.likes || "0"},${c.date || "-"}\n`;
    });
  }
  return csv;
}

export function buildExportJSON(data, scope = "all") {
  if (!data) return "{}";
  if (scope === "videos") return JSON.stringify({ profile: data.profile, videos: data.videos || [] }, null, 2);
  if (scope === "comments") return JSON.stringify({ profile: data.profile, comments: data.comments || [] }, null, 2);
  return JSON.stringify(data, null, 2);
}