import React, { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, ScrollView, Switch, Share, Linking, StyleSheet } from "react-native";
import { COLORS, sharedStyles } from "../theme";
import { PlaywrightTerminal } from "../organisms/PlaywrightTerminal";
import { POPULAR_PROFILES, EXPORT_SCOPES, buildExportCSV, buildExportJSON } from "../../domain/metrics";

export function ExtractorPage({
  backendIp, setBackendIp, username, setUsername,
  loading, startScrape, showLimits, setShowLimits,
  limitsConfig, setLimitsConfig, logs, onClearLogs, data, onGoMetrics
}) {
  const [exportScope, setExportScope] = useState("all");

  const shareExport = async (fmt) => {
    if (!data) return;
    const content = fmt === "csv" ? buildExportCSV(data, exportScope) : buildExportJSON(data, exportScope);
    await Share.share({ title: `tiktok_${username}_${exportScope}.${fmt}`, message: content });
  };

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <View style={sharedStyles.panelCard}>
        <View style={sharedStyles.rowBetween}>
          <Text style={s.title}>Objetivo de Scraping</Text>
          <View style={s.badge}><Text style={s.badgeTxt}>● Bypass Anti-Bot</Text></View>
        </View>

        <View style={s.ipRow}>
          <Text style={s.muted}>IP Backend:</Text>
          <TextInput style={s.ipInput} value={backendIp} onChangeText={setBackendIp} placeholder="192.168.1.90" placeholderTextColor="#475569" />
        </View>

        <View style={s.inputBox}>
          <Text style={s.prefix}>@</Text>
          <TextInput style={s.input} value={username} onChangeText={setUsername} placeholder="_iamnot_leo_, khaby.lame" placeholderTextColor="#475569" autoCapitalize="none" />
        </View>

        <TouchableOpacity style={[s.btnPrimary, (loading || !username.trim()) && s.disabled]} onPress={startScrape} disabled={loading || !username.trim()}>
          <Text style={s.btnPrimaryTxt}>{loading ? "Extrayendo Todo..." : "▶  Scrapear Perfil"}</Text>
        </TouchableOpacity>

        <View style={s.rowWrap}>
          {POPULAR_PROFILES.map((p) => (
            <TouchableOpacity key={p.name} style={s.chip} onPress={() => setUsername(p.name)}>
              <Text style={s.chipUser}>@{p.name}</Text>
              <Text style={s.muted}> ({p.cat})</Text>
            </TouchableOpacity>
          ))}
        </View>

        <View style={s.divider} />
        <View style={sharedStyles.rowBetween}>
          <Text style={s.subLbl}>DATOS A EXPORTAR (CSV / JSON)</Text>
          <Text style={s.scopeTag}>{exportScope.toUpperCase()}</Text>
        </View>

        <View style={s.rowGap}>
          {EXPORT_SCOPES.map((tab) => {
            const act = exportScope === tab.id;
            return (
              <TouchableOpacity key={tab.id} style={[s.scopeCard, act && s.scopeAct]} onPress={() => setExportScope(tab.id)}>
                <Text style={[s.scopeTitle, act && { color: "#fda4af" }]}>{tab.label}</Text>
                <Text style={s.scopeDesc}>{tab.desc}</Text>
              </TouchableOpacity>
            );
          })}
        </View>

        <View style={s.divider} />
        <TouchableOpacity onPress={() => setShowLimits(!showLimits)}>
          <Text style={s.linkSky}>⚙  {showLimits ? "Ocultar Límites de Extracción" : "Configurar Límites de Extracción"}</Text>
        </TouchableOpacity>

        {showLimits && (
          <View style={s.advBox}>
            <View style={s.rowGap}>
              <View style={{ flex: 1 }}>
                <Text style={s.muted}>Videos a Capturar</Text>
                <TextInput style={s.numInput} keyboardType="numeric" value={String(limitsConfig.max_videos)} onChangeText={(v) => setLimitsConfig({ ...limitsConfig, max_videos: v })} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={s.muted}>Videos p/ Comentarios</Text>
                <TextInput style={s.numInput} keyboardType="numeric" value={String(limitsConfig.max_comment_videos)} onChangeText={(v) => setLimitsConfig({ ...limitsConfig, max_comment_videos: v })} />
              </View>
            </View>

            <View style={s.rowWrap}>
              {["hibrido", "red", "dom", "rapido"].map((m) => (
                <TouchableOpacity key={m} style={[s.pill, limitsConfig.modo === m && s.pillAct]} onPress={() => setLimitsConfig({ ...limitsConfig, modo: m })}>
                  <Text style={[s.pillTxt, limitsConfig.modo === m && { color: COLORS.primary }]}>{m.toUpperCase()}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <View style={sharedStyles.rowBetween}>
              <Text style={s.muted}>Bloquear multimedia (Ahorro RAM)</Text>
              <Switch value={!!limitsConfig.bloquear_multimedia} onValueChange={(v) => setLimitsConfig({ ...limitsConfig, bloquear_multimedia: v })} trackColor={{ false: COLORS.border, true: COLORS.primary }} />
            </View>
          </View>
        )}

        <View style={s.divider} />
        <View style={s.rowWrap}>
          {data?.scrape_id && (
            <TouchableOpacity style={s.xlsxBtn} onPress={() => Linking.openURL(`http://${backendIp}:8000/api/export/${data.scrape_id}.xlsx`)}>
              <Text style={s.xlsxTxt}>Excel (.xlsx)</Text>
            </TouchableOpacity>
          )}
          <TouchableOpacity style={[s.expBtn, !data && s.disabled]} disabled={!data} onPress={() => shareExport("csv")}>
            <Text style={s.expTxt}>CSV ({exportScope})</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[s.expBtn, !data && s.disabled]} disabled={!data} onPress={() => shareExport("json")}>
            <Text style={s.expTxt}>JSON ({exportScope})</Text>
          </TouchableOpacity>
        </View>
      </View>

      <PlaywrightTerminal logs={logs} onClear={onClearLogs} />

      {data?.profile && (
        <View style={sharedStyles.panelCard}>
          <Text style={s.subLbl}>VISTA PREVIA DEL PERFIL</Text>
          <Text style={s.prevName}>{data.profile.name}</Text>
          <Text style={s.prevUser}>{data.profile.username}</Text>
          <View style={s.rowWrap}>
            <Text style={s.statChip}>Seguidores: {data.profile.followers || "0"}</Text>
            <Text style={s.statChip}>Videos: {data.videos?.length || 0}</Text>
            <Text style={s.statChip}>Comentarios: {data.comments?.length || 0}</Text>
          </View>
          <TouchableOpacity style={s.metricsBtn} onPress={onGoMetrics}>
            <Text style={s.metricsBtnTxt}>Ver Resultados e IA →</Text>
          </TouchableOpacity>
        </View>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: COLORS.bg },
  content: { padding: 14, paddingBottom: 32 },
  title: { color: "#fff", fontSize: 15, fontWeight: "700" },
  muted: { color: "#94a3b8", fontSize: 11 },
  badge: { backgroundColor: "rgba(52,211,153,0.12)", borderColor: COLORS.emerald, borderWidth: 1, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 99 },
  badgeTxt: { color: COLORS.emerald, fontSize: 10, fontWeight: "700" },
  ipRow: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 10 },
  ipInput: { flex: 1, backgroundColor: COLORS.input, borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, color: COLORS.cyan, paddingHorizontal: 10, paddingVertical: 6, fontSize: 12 },
  inputBox: { flexDirection: "row", alignItems: "center", backgroundColor: COLORS.input, borderWidth: 1, borderColor: COLORS.border, borderRadius: 12, paddingHorizontal: 12, marginTop: 8 },
  prefix: { color: "#64748b", fontSize: 15, fontWeight: "700", marginRight: 6 },
  input: { flex: 1, color: "#fff", fontSize: 13, paddingVertical: 11 },
  btnPrimary: { backgroundColor: COLORS.primary, borderRadius: 12, paddingVertical: 13, alignItems: "center", marginTop: 10 },
  btnPrimaryTxt: { color: "#fff", fontWeight: "800", fontSize: 14 },
  disabled: { opacity: 0.4 },
  rowWrap: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 8 },
  rowGap: { flexDirection: "row", gap: 6, marginTop: 8 },
  chip: { flexDirection: "row", backgroundColor: COLORS.input, borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 5 },
  chipUser: { color: COLORS.primary, fontSize: 11, fontWeight: "700" },
  divider: { height: 1, backgroundColor: COLORS.border, marginVertical: 12 },
  subLbl: { color: "#94a3b8", fontSize: 10, fontWeight: "800", letterSpacing: 0.7 },
  scopeTag: { color: COLORS.primary, fontSize: 10, fontWeight: "800" },
  scopeCard: { flex: 1, backgroundColor: COLORS.input, borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, padding: 8 },
  scopeAct: { borderColor: COLORS.primary, backgroundColor: "rgba(244,63,94,0.12)" },
  scopeTitle: { color: "#cbd5e1", fontSize: 11, fontWeight: "700" },
  scopeDesc: { color: "#64748b", fontSize: 9, marginTop: 2 },
  linkSky: { color: COLORS.sky, fontSize: 12, fontWeight: "700" },
  advBox: { backgroundColor: COLORS.input, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, padding: 10, marginTop: 8, gap: 6 },
  numInput: { backgroundColor: COLORS.card, borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, color: "#fff", paddingHorizontal: 10, paddingVertical: 6, fontSize: 13, marginTop: 4 },
  pill: { paddingHorizontal: 8, paddingVertical: 5, borderRadius: 6, backgroundColor: COLORS.card, borderWidth: 1, borderColor: COLORS.border },
  pillAct: { borderColor: COLORS.primary },
  pillTxt: { color: "#94a3b8", fontSize: 10, fontWeight: "700" },
  xlsxBtn: { backgroundColor: "#064e3b", borderColor: COLORS.emerald, borderWidth: 1, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 7 },
  xlsxTxt: { color: COLORS.emerald, fontSize: 11, fontWeight: "700" },
  expBtn: { backgroundColor: COLORS.input, borderColor: COLORS.border, borderWidth: 1, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 7 },
  expTxt: { color: "#e2e8f0", fontSize: 11, fontWeight: "600" },
  prevName: { color: "#fff", fontSize: 17, fontWeight: "800", marginTop: 4 },
  prevUser: { color: COLORS.cyan, fontSize: 12, fontWeight: "600" },
  statChip: { color: "#cbd5e1", backgroundColor: COLORS.input, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6, fontSize: 11 },
  metricsBtn: { backgroundColor: "#1e1b4b", borderColor: COLORS.purple, borderWidth: 1, borderRadius: 10, paddingVertical: 11, alignItems: "center", marginTop: 10 },
  metricsBtnTxt: { color: "#e9d5ff", fontSize: 12, fontWeight: "700" }
});