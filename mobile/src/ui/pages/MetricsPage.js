import React, { useState, useMemo } from "react";
import { View, Text, TextInput, TouchableOpacity, ScrollView, Image, Linking, ActivityIndicator, StyleSheet } from "react-native";
import { COLORS, sharedStyles } from "../theme";
import * as StatCellMod from "../molecules/StatCell";
import * as OceanBarMod from "../molecules/OceanBar";
import { extractHashtags, calculatePublicationFrequency } from "../../domain/metrics";
import { evaluateOceanPsychometrics, OCEAN_COLOR_MAP } from "../../domain/psychometrics";
import { fetchGeminiAuditReport } from "../../domain/advisoryClient";

const StatCell = StatCellMod.StatCell || StatCellMod.default;
const OceanBar = OceanBarMod.OceanBar || OceanBarMod.default;

export function MetricsPage({ data, backendIp }) {
  const [tab, setTab] = useState("videos");
  const [filter, setFilter] = useState("");
  const [geminiApiKey, setGeminiApiKey] = useState("");
  const [geminiReport, setGeminiReport] = useState(null);
  const [loadingAi, setLoadingAi] = useState(false);
  const [aiError, setAiError] = useState(null);

  const profile = data?.profile;
  const videos = data?.videos || [];
  const comments = data?.comments || [];

  const hashtags = useMemo(() => extractHashtags(data), [data]);
  const frequency = useMemo(() => calculatePublicationFrequency(videos), [videos]);
  const psychometrics = useMemo(() => evaluateOceanPsychometrics(data), [data]);

  const handleGeminiAudit = async () => {
    setLoadingAi(true);
    setAiError(null);
    try {
      const report = await fetchGeminiAuditReport({
        backendIp,
        apiKey: geminiApiKey,
        profile,
        psychometrics,
        frequency: frequency.label,
      });
      if (report.error) throw new Error(report.error);
      setGeminiReport(report);
    } catch (err) {
      setAiError(err.message || "Error al conectar con Gemini");
    } finally {
      setLoadingAi(false);
    }
  };

  if (!data) {
    return (
      <View style={[sharedStyles.panelCard, { margin: 14, alignItems: "center", paddingVertical: 32 }]}>
        <Text style={styles.title}>No hay métricas disponibles todavía</Text>
        <Text style={styles.muted}>Ejecuta primero un scraping desde la pestaña Extractor.</Text>
      </View>
    );
  }

  const filteredVideos = videos.filter((v) => !filter.trim() || (v?.desc || "").toLowerCase().includes(filter.toLowerCase()));
  const filteredComments = comments.filter(
    (c) => !filter.trim() || (c?.text || "").toLowerCase().includes(filter.toLowerCase()) || (c?.author || "").toLowerCase().includes(filter.toLowerCase())
  );
  const insights = data?.insights || data?.analytics?.insights || [];

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      {/* Banner del Perfil */}
      <View style={sharedStyles.panelCard}>
        <View style={sharedStyles.rowCenter}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{profile?.name ? profile.name[0].toUpperCase() : "?"}</Text>
          </View>
          <View style={{ marginLeft: 12, flex: 1 }}>
            <Text style={styles.title}>{profile?.name || "Perfil TikTok"}</Text>
            <Text style={styles.cyanText}>{profile?.username || "@usuario"}</Text>
          </View>
        </View>
        <Text style={[styles.bodyText, { marginTop: 8 }]}>{profile?.bio || "Sin biografía disponible."}</Text>

        <View style={[styles.rowGap, { marginTop: 10 }]}>
          <StatCell label="Seguidores" value={profile?.followers || "0"} accent={COLORS.sky} />
          <StatCell label="Likes Totales" value={profile?.likes || "0"} accent={COLORS.primary} />
        </View>
        <View style={[styles.rowGap, { marginTop: 8 }]}>
          <StatCell label="Prom. Vistas" value={profile?.avgViews || "N/A"} accent={COLORS.emerald} />
          <StatCell label="Engagement" value={profile?.engagement || "0%"} accent={COLORS.purple} />
        </View>
      </View>

      {/* Sub-Tabs (Sin Comunidad & Red) */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 10 }}>
        <View style={styles.tabsBar}>
          {[
            { id: "videos", label: `Videos (${videos.length})` },
            { id: "comments", label: `Comentarios (${comments.length})` },
            { id: "hashtags", label: `Hashtags (${hashtags.length})` },
            { id: "bigfive", label: "Big Five & Gemini" },
          ].map((t) => (
            <TouchableOpacity key={t.id} style={[styles.tab, tab === t.id && styles.tabActive]} onPress={() => setTab(t.id)}>
              <Text style={[styles.tabText, tab === t.id && styles.tabTextActive]}>{t.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>

      {(tab === "videos" || tab === "comments") && (
        <TextInput
          style={styles.search}
          value={filter}
          onChangeText={setFilter}
          placeholder="Filtrar por texto o usuario..."
          placeholderTextColor="#475569"
        />
      )}

      {/* TAB VIDEOS */}
      {tab === "videos" &&
        filteredVideos.map((vid) => (
          <View key={vid.id} style={[sharedStyles.panelCard, { flexDirection: "row", gap: 10 }]}>
            {!!vid.thumbnail && <Image source={{ uri: vid.thumbnail }} style={styles.thumb} />}
            <View style={{ flex: 1, justifyContent: "space-between" }}>
              <Text style={styles.boldWhite}>Video #{vid.id} • {vid.duration || "15s"}</Text>
              <Text style={styles.muted} numberOfLines={2}>{vid.desc || "Sin descripción"}</Text>
              <View style={styles.rowGap}>
                <Text style={{ color: COLORS.cyan, fontSize: 11 }}>👁 {vid.views || "0"}</Text>
                <Text style={{ color: COLORS.primary, fontSize: 11 }}>♥ {vid.likes || "0"}</Text>
                <Text style={{ color: COLORS.emerald, fontSize: 11 }}>↗ {vid.shares || "0"}</Text>
              </View>
              {!!vid.url && (
                <TouchableOpacity onPress={() => Linking.openURL(vid.url)}>
                  <Text style={styles.skyLink}>Abrir en TikTok ↗</Text>
                </TouchableOpacity>
              )}
            </View>
          </View>
        ))}

      {/* TAB COMENTARIOS */}
      {tab === "comments" &&
        filteredComments.map((com, idx) => (
          <View key={com.id || idx} style={sharedStyles.panelCard}>
            <View style={sharedStyles.rowBetween}>
              <Text style={styles.cyanText}>@{(com.author || "usuario").replace(/^@/, "")}</Text>
              <Text style={{ color: COLORS.primary, fontSize: 11 }}>♥ {com.likes || "0"}</Text>
            </View>
            <Text style={[styles.bodyText, { marginVertical: 4 }]}>{com.text}</Text>
            <View style={sharedStyles.rowBetween}>
              <Text style={styles.muted}>{com.date || ""}</Text>
              {!!com.video_url && (
                <TouchableOpacity onPress={() => Linking.openURL(com.video_url)}>
                  <Text style={styles.skyLink}>Ver Video ↗</Text>
                </TouchableOpacity>
              )}
            </View>
          </View>
        ))}

      {/* TAB HASHTAGS & ESTADÍSTICAS */}
      {tab === "hashtags" && (
        <>
          <View style={sharedStyles.panelCard}>
            <Text style={styles.subLabel}>HASHTAGS DETECTADOS ({hashtags.length})</Text>
            <View style={styles.wrapRow}>
              {hashtags.map(({ tag, count }) => (
                <View key={tag} style={styles.tagPill}>
                  <Text style={styles.cyanText}>{tag} {count > 1 ? `x${count}` : ""}</Text>
                </View>
              ))}
            </View>
          </View>
          <View style={sharedStyles.panelCard}>
            <Text style={styles.subLabel}>PROMEDIO DE INTERACCIONES</Text>
            <Text style={[styles.bigStat, { color: COLORS.primary }]}>{profile?.engagement || "0%"}</Text>
          </View>
          <View style={sharedStyles.panelCard}>
            <Text style={styles.subLabel}>FRECUENCIA DE PUBLICACIÓN</Text>
            <Text style={[styles.bigStat, { color: frequency.color }]}>{frequency.label}</Text>
            <Text style={styles.muted}>{frequency.desc}</Text>
          </View>
        </>
      )}

      {/* TAB BIG FIVE & GEMINI */}
      {tab === "bigfive" && psychometrics && (
        <>
          <View style={[sharedStyles.panelCard, { borderColor: COLORS.purple }]}>
            <Text style={styles.subLabel}>ARQUETIPO PSICOMÉTRICO OCEAN</Text>
            <Text style={[styles.title, { marginTop: 4 }]}>{psychometrics.arquetipo}</Text>
            <Text style={{ color: COLORS.emerald, fontSize: 12, fontWeight: "700", marginTop: 4 }}>
              Rasgo Dominante: {psychometrics.dominant_trait}
            </Text>
          </View>

          <View style={[sharedStyles.panelCard, { borderColor: COLORS.cyan }]}>
            <Text style={styles.title}>Auditoría Ejecutiva con Google Gemini</Text>
            <TextInput
              style={[styles.search, { marginTop: 8 }]}
              value={geminiApiKey}
              onChangeText={setGeminiApiKey}
              placeholder="API key de Gemini (AIza...)"
              placeholderTextColor="#475569"
              secureTextEntry
              autoCapitalize="none"
            />
            <TouchableOpacity style={styles.geminiBtn} onPress={handleGeminiAudit} disabled={loadingAi}>
              {loadingAi ? <ActivityIndicator color="#020617" /> : <Text style={styles.geminiBtnText}>Generar Auditoría con Gemini</Text>}
            </TouchableOpacity>

            {!!aiError && <Text style={{ color: "#fda4af", fontSize: 12, marginTop: 6 }}>{aiError}</Text>}

            {geminiReport && (
              <View style={{ gap: 8, marginTop: 10 }}>
                <View style={styles.reportBox}>
                  <Text style={styles.cyanText}>Diagnóstico del Perfil</Text>
                  <Text style={styles.bodyText}>{geminiReport.diagnostico_perfil}</Text>
                </View>
                <View style={styles.reportBox}>
                  <Text style={{ color: COLORS.emerald, fontSize: 12, fontWeight: "700" }}>Estrategia de Monetización</Text>
                  <Text style={styles.bodyText}>{geminiReport.estrategia_monetizacion}</Text>
                </View>
                <View style={styles.reportBox}>
                  <Text style={{ color: COLORS.amber, fontSize: 12, fontWeight: "700" }}>Recomendación de Crecimiento</Text>
                  <Text style={styles.bodyText}>{geminiReport.consejo_mejora}</Text>
                </View>
              </View>
            )}
          </View>

          {insights.length > 0 && (
            <View style={sharedStyles.panelCard}>
              <Text style={styles.subLabel}>HALLAZGOS DEL ALGORITMO</Text>
              {insights.map((ins, idx) => (
                <View key={idx} style={[styles.reportBox, { marginTop: 8 }]}>
                  <Text style={{ color: COLORS.amber, fontSize: 12, fontWeight: "700" }}>{ins.titulo}</Text>
                  <Text style={styles.muted}>{ins.texto}</Text>
                </View>
              ))}
            </View>
          )}

          <View style={sharedStyles.panelCard}>
            <Text style={styles.subLabel}>DIMENSIONES OCEAN</Text>
            <View style={{ gap: 12, marginTop: 4 }}>
              {Object.entries(psychometrics.ocean_scores || {}).map(([trait, score]) => (
                <OceanBar
                  key={trait}
                  trait={trait}
                  score={score}
                  cfg={OCEAN_COLOR_MAP[trait] || { bar: "#6366f1", text: "#818cf8", sub: "Métrica general" }}
                />
              ))}
            </View>
          </View>

          <View style={sharedStyles.panelCard}>
            <Text style={styles.subLabel}>FIT ESTRATÉGICO Y MARCAS</Text>
            <View style={styles.wrapRow}>
              {(psychometrics.marcas_recomendadas || []).map((m, idx) => (
                <View key={idx} style={styles.tagPill}>
                  <Text style={styles.cyanText}>
                    {m.niche} {m.similarity ? `(${m.similarity}%)` : ""}
                  </Text>
                </View>
              ))}
            </View>
            <Text style={[styles.muted, { marginTop: 8 }]}>
              Tono de comunidad: {psychometrics.resumen_audiencia?.tono_comunidad} ({comments.length} comentarios analizados)
            </Text>
          </View>
        </>
      )}
    </ScrollView>
  );
}

export default MetricsPage;

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: COLORS.bg },
  content: { padding: 14, paddingBottom: 36 },
  title: { color: "#fff", fontSize: 17, fontWeight: "800" },
  boldWhite: { color: "#fff", fontSize: 12, fontWeight: "700" },
  cyanText: { color: COLORS.cyan, fontSize: 12, fontWeight: "700" },
  skyLink: { color: COLORS.sky, fontSize: 11, fontWeight: "700", marginTop: 4 },
  bodyText: { color: "#cbd5e1", fontSize: 12, lineHeight: 18 },
  muted: { color: "#94a3b8", fontSize: 11 },
  subLabel: { color: "#94a3b8", fontSize: 10, fontWeight: "800", letterSpacing: 0.7, marginBottom: 6 },
  avatar: { width: 48, height: 48, borderRadius: 24, backgroundColor: "#1e1b4b", borderWidth: 2, borderColor: COLORS.primary, alignItems: "center", justifyContent: "center" },
  avatarText: { color: "#fff", fontSize: 18, fontWeight: "900" },
  rowGap: { flexDirection: "row", gap: 8 },
  wrapRow: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  tabsBar: { flexDirection: "row", backgroundColor: COLORS.input, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, padding: 4, gap: 4 },
  tab: { paddingHorizontal: 10, paddingVertical: 7, borderRadius: 8 },
  tabActive: { backgroundColor: COLORS.primary },
  tabText: { color: "#94a3b8", fontSize: 11, fontWeight: "700" },
  tabTextActive: { color: "#fff" },
  search: { backgroundColor: COLORS.input, borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, color: "#fff", paddingHorizontal: 12, paddingVertical: 9, fontSize: 12, marginBottom: 10 },
  thumb: { width: 60, height: 84, borderRadius: 8, backgroundColor: COLORS.input },
  tagPill: { backgroundColor: COLORS.input, borderWidth: 1, borderColor: COLORS.border, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4 },
  bigStat: { fontSize: 26, fontWeight: "900" },
  geminiBtn: { backgroundColor: COLORS.cyan, borderRadius: 10, paddingVertical: 11, alignItems: "center", marginTop: 8 },
  geminiBtnText: { color: "#020617", fontSize: 12, fontWeight: "800" },
  reportBox: { backgroundColor: COLORS.input, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, padding: 10, gap: 4 },
});