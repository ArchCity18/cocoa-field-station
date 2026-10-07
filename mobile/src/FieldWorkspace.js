import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Alert, Pressable, SafeAreaView, ScrollView, StatusBar, StyleSheet, Text, TextInput, View } from 'react-native';
import { Feather } from '@expo/vector-icons';
import Svg, { Circle, Line, Polyline } from 'react-native-svg';
import { request } from './api';

const C = { ink: '#24372E', green: '#355640', leaf: '#78916C', cream: '#F7F3EA', paper: '#FFFEFA', border: '#E2DACA', muted: '#778179', pale: '#EBEFE5', gold: '#BD8D48', red: '#A1463B' };
const METRICS = { Rainfall: ['rainfall_mm', 'Rainfall', 'mm', 'cloud-rain'], Humidity: ['humidity_pct', 'Humidity', '%', 'droplet'], Temperature: ['temp_c', 'Temperature', '°C', 'thermometer'] };

function SmallButton({ label, active, onPress }) {
  return <Pressable onPress={onPress} style={[s.chip, active && s.chipActive]}><Text style={[s.chipText, active && s.chipTextActive]}>{label}</Text></Pressable>;
}

function TrendChart({ data, measure }) {
  const config = METRICS[measure];
  const values = data.map((row) => Number(row[config[0]]) || 0);
  if (!values.length) return <View style={s.empty}><Text style={s.muted}>No observations for this time window.</Text></View>;
  const min = Math.min(...values); const max = Math.max(...values); const range = max - min || 1;
  const points = values.map((value, index) => `${24 + index * (272 / Math.max(values.length - 1, 1))},${104 - ((value - min) / range) * 78}`).join(' ');
  return <View style={s.chartWrap}><Svg width="100%" height={132} viewBox="0 0 320 132" preserveAspectRatio="none"><Line x1="20" y1="26" x2="300" y2="26" stroke={C.border} strokeDasharray="4 5" /><Line x1="20" y1="65" x2="300" y2="65" stroke={C.border} strokeDasharray="4 5" /><Line x1="20" y1="104" x2="300" y2="104" stroke={C.border} strokeDasharray="4 5" /><Polyline points={points} fill="none" stroke={C.green} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />{values.map((value, index) => <Circle key={index} cx={24 + index * (272 / Math.max(values.length - 1, 1))} cy={104 - ((value - min) / range) * 78} r="3.5" fill={C.green} />)}</Svg><View style={s.chartLabels}><Text style={s.chartLabel}>{data[0]?.date || ''}</Text><Text style={s.chartLabel}>{data[data.length - 1]?.date || ''}</Text></View><Text style={s.chartUnit}>{config[1]} ({config[2]})</Text></View>;
}

function metric(value, places = 1) { return Number(value || 0).toFixed(places); }

export default function FieldWorkspace({ user, onLogout }) {
  const [view, setView] = useState('Plot monitor');
  const [plots, setPlots] = useState([]);
  const [plotId, setPlotId] = useState('Plot A');
  const [field, setField] = useState(null);
  const [days, setDays] = useState(14);
  const [measure, setMeasure] = useState('Rainfall');
  const [recommendation, setRecommendation] = useState(null);
  const [journal, setJournal] = useState([]);
  const [journalPlot, setJournalPlot] = useState('All plots');
  const [journalStatus, setJournalStatus] = useState('All decisions');
  const [users, setUsers] = useState([]);
  const [invites, setInvites] = useState([]);
  const [inputerForm, setInputerForm] = useState({ name: '', email: '' });
  const [observationForm, setObservationForm] = useState({ date: new Date().toISOString().slice(0,10), rainfall_mm: '', humidity_pct: '', temp_c: '', days_since_last_spray: '', inspection_note: '' });
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const loadPlot = useCallback(async (id = plotId, windowDays = days) => {
    try {
      const result = await request('/field/plot', { auth: true, query: { plot_id: id, days: String(windowDays) } });
      setPlotId(id); setField(result); setRecommendation(null); setError('');
    } catch (e) { setError(e.message); }
  }, [plotId, days]);

  const loadJournal = useCallback(async () => {
    try {
      const status = journalStatus === 'Awaiting review' ? 'pending' : journalStatus === 'Recorded' ? 'recorded' : 'all';
      const result = await request('/field/journal', { auth: true, query: { plot_id: journalPlot, status } });
      setJournal(result.decisions || []); setError('');
    } catch (e) { setError(e.message); }
  }, [journalPlot, journalStatus]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const result = await request('/field/plots', { auth: true });
        const available = result.plots || [];
        setPlots(available);
        if (available.length) await loadPlot(available[0].plot_id, 14);
        if (['manager','admin','administrator'].includes(user.role)) {
          const directory = await request('/admin/users', { auth: true });
          setUsers(directory.users || []); setInvites(directory.invites || []);
        }
      } catch (e) { setError(e.message); }
      finally { setLoading(false); }
    })();
  // Initial workspace hydration should run once per authenticated account.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user.id]);

  useEffect(() => { if (view === 'Decision journal') loadJournal(); }, [view, loadJournal]);

  const recent = field?.observations?.slice(-7) || [];
  const pendingCount = useMemo(() => journal.filter((item) => !item.human_decision).length, [journal]);
  const recordedCount = journal.length - pendingCount;

  async function generateRecommendation() {
    setBusy(true); setError(''); setReason('');
    try {
      const result = await request('/field/recommendation', { method: 'POST', auth: true, body: { plot_id: plotId } });
      setRecommendation(result.recommendation);
      if (view === 'Decision journal') await loadJournal();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function saveDecision(action) {
    setBusy(true); setError('');
    try {
      await request('/field/decision', { method: 'POST', auth: true, body: { decision_id: recommendation.id, action, reason } });
      setRecommendation((old) => ({ ...old, pending: false, human_decision: action, human_reason: reason }));
      setReason('');
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function addInputer() {
    setBusy(true); setError('');
    try {
      await request('/admin/inputers', { method: 'POST', auth: true, body: inputerForm });
      setInputerForm({ name: '', email: '' });
      const directory = await request('/admin/users', { auth: true }); setUsers(directory.users || []); setInvites(directory.invites || []);
      Alert.alert('Inputer added', 'Ask this person to register with the invited Google/email address.');
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function deleteInputer(email) {
    const confirmRemoval = () => Alert.alert('Delete inputer?', `Remove the inputer access for ${email}?`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        setBusy(true); setError('');
        try {
          await request('/admin/inputers', { method: 'DELETE', auth: true, body: { email } });
          const directory = await request('/admin/users', { auth: true }); setUsers(directory.users || []); setInvites(directory.invites || []);
        } catch (e) { setError(e.message); }
        finally { setBusy(false); }
      } },
    ]);
    if (Platform.OS === 'web') {
      if (globalThis.confirm(`Remove inputer access for ${email}?`)) {
        setBusy(true); setError('');
        try {
          await request('/admin/inputers', { method: 'DELETE', auth: true, body: { email } });
          const directory = await request('/admin/users', { auth: true }); setUsers(directory.users || []); setInvites(directory.invites || []);
        } catch (e) { setError(e.message); }
        finally { setBusy(false); }
      }
      return;
    }
    confirmRemoval();
  }

  async function saveObservation() {
    setBusy(true); setError('');
    try {
      await request('/field/observation', { method: 'POST', auth: true, body: { ...observationForm, plot_id: plotId, rainfall_mm: Number(observationForm.rainfall_mm), humidity_pct: Number(observationForm.humidity_pct), temp_c: Number(observationForm.temp_c), days_since_last_spray: Number(observationForm.days_since_last_spray) } });
      setObservationForm((old) => ({ ...old, rainfall_mm: '', humidity_pct: '', temp_c: '', days_since_last_spray: '', inspection_note: '' }));
      await loadPlot(plotId, days); Alert.alert('Observation saved', 'The new reading is in the plot history.');
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  const canManageInputers = ['manager','administrator'].includes(user.role);
  const canDeleteInputers = ['admin','administrator'].includes(user.role);
  const canInputObservations = ['inputer','manager','administrator'].includes(user.role);
  const canViewDirectory = ['manager','admin','administrator'].includes(user.role);
  const navItems = ['Plot monitor', 'Decision journal', ...(canViewDirectory ? ['Account directory'] : [])];

  if (loading) return <SafeAreaView style={s.safe}><StatusBar barStyle="dark-content" backgroundColor={C.cream} /><View style={s.loading}><ActivityIndicator color={C.green} /><Text style={s.muted}>Opening your field station…</Text></View></SafeAreaView>;

  return <SafeAreaView style={s.safe}><StatusBar barStyle="dark-content" backgroundColor={C.cream} /><ScrollView contentContainerStyle={s.page}>
    <View style={s.header}><View style={s.brandIcon}><Feather name="feather" size={19} color={C.paper} /></View><View style={{ flex: 1 }}><Text style={s.brandName}>Cocoa Field Station</Text><Text style={s.brandCaption}>YOUR FIELD DESK · {user.role.toUpperCase()}</Text></View><Pressable accessibilityRole="button" onPress={onLogout} style={s.logout}><Feather name="log-out" size={16} color={C.green} /><Text style={s.logoutText}>Sign out</Text></Pressable></View>
    <View style={s.nav}>{navItems.map((item) => <Pressable key={item} onPress={() => setView(item)} style={[s.navItem, view === item && s.navItemActive]}><Text style={[s.navText, view === item && s.navTextActive]}>{item}</Text></Pressable>)}</View>
    {!!error && <View style={s.error}><Feather name="alert-circle" size={16} color={C.red} /><Text style={s.errorText}>{error}</Text></View>}

    {view === 'Plot monitor' && <>
      <Text style={s.kicker}>FIELD NOTES / SELECT A PLOT</Text><Text style={s.pageTitle}>Your plots</Text><Text style={s.intro}>Recent conditions and decisions, ready for your review.</Text>
      <View style={s.plotChips}>{plots.map((plot) => <SmallButton key={plot.plot_id} label={plot.plot_id} active={plotId === plot.plot_id} onPress={() => { setRecommendation(null); loadPlot(plot.plot_id, days); }} />)}</View>
      <View style={s.plotHeading}><View style={{ flex: 1 }}><Text style={s.plotTitle}>{field?.plot?.plot_id || plotId} at a glance</Text><Text style={s.muted}>{field?.plot?.description}</Text></View><View style={s.simBadge}><Feather name="activity" size={12} color="#946A2D" /><Text style={s.simBadgeText}>SIMULATED DATA</Text></View></View>
      <View style={s.metricRow}><View style={s.metricCard}><Text style={s.metricLabel}>RAINFALL · 7 DAYS</Text><Text style={s.metricBig}>{metric(field?.summary?.rainfall_7d_mm)}<Text style={s.metricSmall}> mm</Text></Text></View><View style={s.metricCard}><Text style={s.metricLabel}>AVERAGE HUMIDITY</Text><Text style={s.metricBig}>{metric(field?.summary?.humidity_7d_pct,0)}<Text style={s.metricSmall}>%</Text></Text></View></View>
      <View style={s.metricRow}><View style={s.metricCard}><Text style={s.metricLabel}>AVERAGE TEMPERATURE</Text><Text style={s.metricBig}>{metric(field?.summary?.temperature_7d_c)}<Text style={s.metricSmall}> °C</Text></Text></View><View style={s.metricCard}><Text style={s.metricLabel}>LATEST READING</Text><Text style={s.metricDate}>{field?.summary?.latest_date || '—'}</Text></View></View>

      <View style={s.card}><View style={s.cardHeader}><View><Text style={s.cardTitle}>Field conditions</Text><Text style={s.muted}>Explore recent observations</Text></View><Feather name="bar-chart-2" size={20} color={C.green} /></View>
        <Text style={s.label}>Measure</Text><View style={s.chipRow}>{Object.keys(METRICS).map((name) => <SmallButton key={name} label={name} active={measure === name} onPress={() => setMeasure(name)} />)}</View>
        <Text style={s.label}>Time window</Text><View style={s.chipRow}>{[7,14,30].map((n) => <SmallButton key={n} label={`${n} days`} active={days === n} onPress={() => { setDays(n); loadPlot(plotId,n); }} />)}</View>
        <TrendChart data={(field?.observations || []).slice(-days)} measure={measure} />
      </View>

      <View style={s.card}><View style={s.cardHeader}><View><Text style={s.cardTitle}>Observation journal</Text><Text style={s.muted}>Latest daily field conditions</Text></View><Feather name="book-open" size={19} color={C.green} /></View>
        {(field?.observations || []).slice(-Math.min(days, 10)).reverse().map((row) => <View key={row.date} style={s.observationRow}><View style={s.dateBox}><Text style={s.dateDay}>{row.date.slice(8,10)}</Text><Text style={s.dateMonth}>{row.date.slice(5,7)}</Text></View><View style={s.observationMain}><Text style={s.observationDate}>{row.date}</Text><Text style={s.observationText}>{metric(row.rainfall_mm)} mm rain · {metric(row.humidity_pct,0)}% humidity · {metric(row.temp_c)} °C</Text></View><Feather name="chevron-right" size={16} color={C.leaf} /></View>)}
      </View>

      {canInputObservations && <View style={s.card}><View style={s.cardHeader}><View><Text style={s.cardTitle}>Enter a field observation</Text><Text style={s.muted}>Inputers can add a dated plot reading.</Text></View><Feather name="edit-3" size={19} color={C.green} /></View>
        <TextInput accessibilityLabel="Observation date" value={observationForm.date} onChangeText={(v) => setObservationForm((old) => ({ ...old, date: v }))} placeholder="Date (YYYY-MM-DD)" style={s.reasonInput} />
        <View style={s.metricRow}><TextInput accessibilityLabel="Rainfall in millimetres" value={observationForm.rainfall_mm} onChangeText={(v) => setObservationForm((old) => ({ ...old, rainfall_mm: v }))} placeholder="Rain mm" keyboardType="decimal-pad" style={s.numericInput} /><TextInput accessibilityLabel="Humidity percentage" value={observationForm.humidity_pct} onChangeText={(v) => setObservationForm((old) => ({ ...old, humidity_pct: v }))} placeholder="Humidity %" keyboardType="decimal-pad" style={s.numericInput} /></View>
        <View style={s.metricRow}><TextInput accessibilityLabel="Temperature Celsius" value={observationForm.temp_c} onChangeText={(v) => setObservationForm((old) => ({ ...old, temp_c: v }))} placeholder="Temperature °C" keyboardType="decimal-pad" style={s.numericInput} /><TextInput accessibilityLabel="Days since spray" value={observationForm.days_since_last_spray} onChangeText={(v) => setObservationForm((old) => ({ ...old, days_since_last_spray: v }))} placeholder="Days since spray" keyboardType="number-pad" style={s.numericInput} /></View>
        <TextInput accessibilityLabel="Inspection note" value={observationForm.inspection_note} onChangeText={(v) => setObservationForm((old) => ({ ...old, inspection_note: v }))} placeholder="Inspection note (optional)" placeholderTextColor="#969E96" style={s.reasonInput} multiline />
        <Pressable disabled={busy} onPress={saveObservation} style={s.primaryButton}>{busy ? <ActivityIndicator color={C.paper} /> : <><Feather name="save" size={15} color={C.paper} /><Text style={s.primaryButtonText}>Save observation</Text></>}</Pressable>
      </View>}

      <View style={s.recommendCard}><View style={s.cardHeader}><View><Text style={s.kicker}>HUMAN REVIEW REQUIRED</Text><Text style={s.cardTitle}>A clearer next step</Text></View><Feather name="sun" size={21} color={C.gold} /></View>
        <Text style={s.body}>Create a fresh rule-based suggestion from the latest observations. Check its evidence before recording a decision.</Text>
        <Pressable disabled={busy} onPress={generateRecommendation} style={s.primaryButton}>{busy ? <ActivityIndicator color={C.paper} /> : <><Feather name="search" size={15} color={C.paper} /><Text style={s.primaryButtonText}>{recommendation ? 'Refresh recommendation' : 'Review this plot'}</Text></>}</Pressable>
        {recommendation && <View style={s.recommendation}><View style={s.suggestedRow}><Feather name="alert-circle" size={18} color={C.green} /><Text style={s.suggestedTitle}>Suggested: {recommendation.action}</Text></View><Text style={s.body}>{recommendation.rationale}</Text><View style={s.scoreRow}><View><Text style={s.metricLabel}>CONFIDENCE</Text><Text style={s.score}>{Math.round(recommendation.confidence * 100)}%</Text></View><View><Text style={s.metricLabel}>RISK</Text><Text style={s.score}>{recommendation.risk_bucket}</Text></View></View><Text style={s.muted}>{recommendation.gated ? 'Inspection required' : 'Confidence gate passed'}</Text>
          <View style={s.evidenceBox}><Text style={s.evidenceTitle}><Feather name="lightbulb" size={14} color={C.green} />  Recommendation evidence</Text>{recommendation.evidence.map((item,index) => <Text key={index} style={s.evidenceText}>•  {item}</Text>)}</View>
          {recommendation.pending ? <><Text style={s.label}>Record your decision</Text><View style={s.chipRow}>{['spray','wait','inspect'].map((action) => <SmallButton key={action} label={action === recommendation.action ? `Keep ${action}` : action} active={action === (recommendation.human_decision || recommendation.action)} onPress={() => setRecommendation((old) => ({ ...old, selected_action: action }))} />)}</View><TextInput value={reason} onChangeText={setReason} placeholder="Reason (required when changing the suggestion)" placeholderTextColor="#969E96" style={s.reasonInput} multiline /><Pressable disabled={busy} onPress={() => saveDecision(recommendation.selected_action || recommendation.action)} style={s.primaryButton}>{busy ? <ActivityIndicator color={C.paper} /> : <><Feather name="check" size={15} color={C.paper} /><Text style={s.primaryButtonText}>Save decision</Text></>}</Pressable></> : <Text style={s.recorded}>Recorded decision: {recommendation.human_decision}{recommendation.human_reason ? ` · ${recommendation.human_reason}` : ''}</Text>}
        </View>}
      </View>
      <Text style={s.disclaimer}>Prototype only · Weather is simulated · Agronomy thresholds are unverified placeholders.</Text>
    </>}

    {view === 'Decision journal' && <>
      <Text style={s.kicker}>FIELD OVERVIEW / DECISION JOURNAL</Text><Text style={s.pageTitle}>Decision journal</Text><Text style={s.intro}>A transparent record of plot suggestions, grower decisions, and override reasons.</Text>
      <View style={s.metricRow}><View style={s.metricCard}><Text style={s.metricLabel}>FIELD READINGS</Text><Text style={s.metricBig}>{journal.length}</Text></View><View style={s.metricCard}><Text style={s.metricLabel}>AWAITING REVIEW</Text><Text style={s.metricBig}>{pendingCount}</Text></View><View style={s.metricCard}><Text style={s.metricLabel}>GROWER DECISIONS</Text><Text style={s.metricBig}>{recordedCount}</Text></View></View>
      <Text style={s.label}>Plot</Text><View style={s.chipRow}><SmallButton label="All plots" active={journalPlot === 'All plots'} onPress={() => setJournalPlot('All plots')} />{plots.map((plot) => <SmallButton key={plot.plot_id} label={plot.plot_id} active={journalPlot === plot.plot_id} onPress={() => setJournalPlot(plot.plot_id)} />)}</View>
      <Text style={s.label}>Status</Text><View style={s.chipRow}>{['All decisions','Awaiting review','Recorded'].map((status) => <SmallButton key={status} label={status} active={journalStatus === status} onPress={() => setJournalStatus(status)} />)}</View>
      {journal.length === 0 ? <View style={s.empty}><Feather name="book-open" size={23} color={C.leaf} /><Text style={s.emptyTitle}>The journal is empty</Text><Text style={s.muted}>Open a plot and create its first reading.</Text></View> : journal.map((item) => <View key={item.id} style={s.journalCard}><View style={s.journalTop}><Text style={s.journalPlot}>{item.plot_id}</Text><Text style={[s.statusTag, !item.human_decision && s.pendingTag]}>{item.human_decision ? 'RECORDED' : 'AWAITING REVIEW'}</Text></View><Text style={s.journalSuggestion}>Suggested: {item.recommendation} · {Math.round(item.confidence * 100)}% confidence · {item.risk_bucket} risk</Text><Text style={s.body}>{item.rationale}</Text><Text style={s.label}>Evidence</Text>{(item.evidence || []).map((line,index) => <Text key={index} style={s.evidenceText}>•  {line}</Text>)}{item.human_decision && <Text style={s.recorded}>Grower decision: {item.human_decision}{item.human_reason ? ` · ${item.human_reason}` : ''}</Text>}<Text style={s.muted}>By {item.grower_name} · {item.created_at}</Text></View>)}
      <Pressable onPress={loadJournal} style={s.refreshButton}><Feather name="refresh-cw" size={14} color={C.green} /><Text style={s.refreshText}>Refresh journal</Text></Pressable>
    </>}

    {view === 'Account directory' && <><Text style={s.kicker}>ROLE MANAGEMENT / ACCOUNTS</Text><Text style={s.pageTitle}>Account directory</Text><Text style={s.intro}>Access is assigned by role. Managers can add inputers; admins can remove inputers.</Text>
      {canManageInputers && <View style={s.card}><Text style={s.cardTitle}>Add an inputer</Text><Text style={s.muted}>They activate this invitation by registering with the same email.</Text><TextInput accessibilityLabel="Inputer name" value={inputerForm.name} onChangeText={(v) => setInputerForm((old) => ({ ...old, name: v }))} placeholder="Inputer name" style={s.reasonInput} /><TextInput accessibilityLabel="Inputer email" value={inputerForm.email} onChangeText={(v) => setInputerForm((old) => ({ ...old, email: v }))} placeholder="Inputer email" autoCapitalize="none" keyboardType="email-address" style={s.reasonInput} /><Pressable disabled={busy} onPress={addInputer} style={s.primaryButton}>{busy ? <ActivityIndicator color={C.paper} /> : <><Feather name="user-plus" size={15} color={C.paper} /><Text style={s.primaryButtonText}>Add inputer</Text></>}</Pressable></View>}
      <Text style={[s.cardTitle,{marginTop:20}]}>Registered accounts</Text>{users.map((item) => <View key={item.id} style={s.accountRow}><View style={s.accountIcon}><Text style={s.accountInitial}>{item.name[0]?.toUpperCase()}</Text></View><View style={{ flex: 1 }}><Text style={s.journalPlot}>{item.name}</Text><Text style={s.muted}>{item.email}</Text></View><Text style={s.roleTag}>{item.is_active ? item.role : 'inactive'}</Text>{canDeleteInputers && item.role === 'inputer' && item.is_active && <Pressable accessibilityRole="button" accessibilityLabel={`Delete inputer ${item.email}`} onPress={() => deleteInputer(item.email)} style={s.deleteButton}><Feather name="trash-2" size={15} color={C.red} /></Pressable>}</View>)}
      {invites.length > 0 && <><Text style={[s.cardTitle,{marginTop:20}]}>Pending inputer invitations</Text>{invites.map((item) => <View key={item.email} style={s.accountRow}><View style={s.accountIcon}><Feather name="mail" size={15} color={C.green} /></View><View style={{ flex: 1 }}><Text style={s.journalPlot}>{item.name}</Text><Text style={s.muted}>{item.email}</Text></View><Text style={s.roleTag}>pending</Text>{canDeleteInputers && <Pressable accessibilityRole="button" onPress={() => deleteInputer(item.email)} style={s.deleteButton}><Feather name="trash-2" size={15} color={C.red} /></Pressable>}</View>)}</>}
    </>}
    <View style={s.footer}><Text style={s.footerText}>COCOA FIELD STATION · PRIVATE BY DESIGN</Text></View>
  </ScrollView></SafeAreaView>;
}

const s = StyleSheet.create({
  safe:{flex:1,backgroundColor:C.cream},page:{flexGrow:1,paddingHorizontal:21,paddingTop:14,paddingBottom:32,maxWidth:760,width:'100%',alignSelf:'center'},loading:{flex:1,alignItems:'center',justifyContent:'center',gap:12},header:{flexDirection:'row',alignItems:'center',gap:10,marginBottom:20},brandIcon:{width:39,height:39,borderRadius:14,backgroundColor:C.green,alignItems:'center',justifyContent:'center'},brandName:{color:C.ink,fontSize:15,fontWeight:'700'},brandCaption:{color:C.muted,fontSize:8,letterSpacing:1.1,fontWeight:'700',marginTop:3},logout:{flexDirection:'row',alignItems:'center',gap:6,padding:9,borderRadius:11,borderColor:C.border,borderWidth:1},logoutText:{color:C.green,fontSize:11,fontWeight:'700'},nav:{flexDirection:'row',gap:5,padding:4,borderRadius:13,backgroundColor:'#EBE6DC',marginBottom:24},navItem:{flex:1,alignItems:'center',paddingVertical:11,paddingHorizontal:4,borderRadius:10},navItemActive:{backgroundColor:C.paper},navText:{color:C.muted,fontSize:10,fontWeight:'600'},navTextActive:{color:C.green},kicker:{color:C.leaf,fontSize:9,letterSpacing:1.3,fontWeight:'800',marginBottom:8},pageTitle:{color:C.ink,fontSize:30,lineHeight:37,fontWeight:'800',letterSpacing:-.7},intro:{color:C.muted,fontSize:12,lineHeight:19,marginTop:6,marginBottom:17},plotChips:{flexDirection:'row',gap:7,marginBottom:18},chipRow:{flexDirection:'row',flexWrap:'wrap',gap:7,marginBottom:13},chip:{paddingHorizontal:12,paddingVertical:9,borderRadius:12,borderWidth:1,borderColor:C.border,backgroundColor:'#FFFDF8'},chipActive:{backgroundColor:'#E9EEE4',borderColor:C.green},chipText:{color:C.muted,fontSize:10,fontWeight:'600'},chipTextActive:{color:C.green},plotHeading:{flexDirection:'row',alignItems:'center',gap:9,marginBottom:13},plotTitle:{color:C.ink,fontSize:20,fontWeight:'700'},muted:{color:C.muted,fontSize:10,lineHeight:16,marginTop:3},simBadge:{flexDirection:'row',alignItems:'center',gap:5,padding:7,borderRadius:20,backgroundColor:'#F2EAD9'},simBadgeText:{fontSize:7,color:'#946A2D',fontWeight:'800',letterSpacing:.5},metricRow:{flexDirection:'row',gap:9,marginBottom:9},metricCard:{flex:1,padding:13,borderRadius:15,backgroundColor:C.paper,borderWidth:1,borderColor:C.border},metricLabel:{color:C.muted,fontSize:8,fontWeight:'800',letterSpacing:.65},metricBig:{color:C.ink,fontSize:25,fontWeight:'700',marginTop:8},metricSmall:{color:C.muted,fontSize:11,fontWeight:'500'},metricDate:{color:C.ink,fontSize:15,fontWeight:'700',marginTop:11},card:{padding:15,borderRadius:18,backgroundColor:C.paper,borderWidth:1,borderColor:C.border,marginTop:12},cardHeader:{flexDirection:'row',alignItems:'center',justifyContent:'space-between',marginBottom:12},cardTitle:{color:C.ink,fontSize:16,fontWeight:'700'},label:{color:C.ink,fontSize:10,fontWeight:'700',marginTop:7,marginBottom:7},chartWrap:{paddingTop:10},chartLabels:{flexDirection:'row',justifyContent:'space-between',paddingHorizontal:4},chartLabel:{color:C.muted,fontSize:8},chartUnit:{color:C.muted,fontSize:8,marginTop:4},empty:{alignItems:'center',justifyContent:'center',padding:24,gap:7},observationRow:{flexDirection:'row',alignItems:'center',gap:10,paddingVertical:10,borderTopWidth:1,borderTopColor:C.border},dateBox:{width:35,height:39,borderRadius:11,backgroundColor:C.pale,alignItems:'center',justifyContent:'center'},dateDay:{color:C.green,fontSize:14,fontWeight:'800'},dateMonth:{color:C.muted,fontSize:7},observationMain:{flex:1},observationDate:{color:C.ink,fontSize:10,fontWeight:'700'},observationText:{color:C.muted,fontSize:9,marginTop:3},recommendCard:{padding:16,borderRadius:18,backgroundColor:'#F3F0E6',borderWidth:1,borderColor:C.border,marginTop:14},body:{color:'#66736A',fontSize:11,lineHeight:18,marginTop:7},primaryButton:{minHeight:43,paddingHorizontal:13,borderRadius:12,backgroundColor:C.green,flexDirection:'row',alignItems:'center',justifyContent:'center',gap:8,marginTop:13},primaryButtonText:{color:C.paper,fontSize:11,fontWeight:'700'},recommendation:{marginTop:17,paddingTop:15,borderTopWidth:1,borderTopColor:C.border},suggestedRow:{flexDirection:'row',alignItems:'center',gap:8},suggestedTitle:{color:C.ink,fontSize:16,fontWeight:'700',textTransform:'capitalize'},scoreRow:{flexDirection:'row',gap:35,marginVertical:13},score:{color:C.ink,fontSize:23,fontWeight:'700',textTransform:'capitalize'},evidenceBox:{borderRadius:13,borderWidth:1,borderColor:C.border,marginTop:12,padding:11,backgroundColor:C.paper},evidenceTitle:{color:C.ink,fontSize:10,fontWeight:'700',marginBottom:8},evidenceText:{color:'#4C5B50',fontSize:10,lineHeight:17,marginVertical:3},reasonInput:{minHeight:58,textAlignVertical:'top',padding:10,borderWidth:1,borderColor:C.border,borderRadius:11,color:C.ink,fontSize:11,backgroundColor:C.paper,marginTop:10},numericInput:{flex:1,minHeight:44,paddingHorizontal:10,borderWidth:1,borderColor:C.border,borderRadius:11,color:C.ink,fontSize:11,backgroundColor:C.paper,marginTop:8},deleteButton:{padding:8,borderRadius:9,backgroundColor:'#F8EAE6'},recorded:{color:C.green,fontSize:11,fontWeight:'700',marginTop:13},disclaimer:{color:C.muted,fontSize:9,lineHeight:14,textAlign:'center',marginTop:18},error:{flexDirection:'row',gap:8,padding:11,borderRadius:11,backgroundColor:'#F8EAE6',marginBottom:15},errorText:{flex:1,color:C.red,fontSize:11,lineHeight:16},emptyTitle:{color:C.ink,fontWeight:'700',fontSize:13},journalCard:{padding:14,backgroundColor:C.paper,borderWidth:1,borderColor:C.border,borderRadius:15,marginTop:10},journalTop:{flexDirection:'row',alignItems:'center',justifyContent:'space-between'},journalPlot:{color:C.ink,fontSize:13,fontWeight:'700'},statusTag:{color:C.green,backgroundColor:C.pale,fontSize:7,fontWeight:'800',letterSpacing:.4,padding:7,borderRadius:10,overflow:'hidden'},pendingTag:{color:'#946A2D',backgroundColor:'#F2EAD9'},journalSuggestion:{color:C.green,fontSize:10,fontWeight:'700',textTransform:'capitalize',marginTop:11},refreshButton:{alignSelf:'center',flexDirection:'row',gap:7,alignItems:'center',padding:12},refreshText:{color:C.green,fontSize:10,fontWeight:'700'},accountRow:{flexDirection:'row',alignItems:'center',gap:10,padding:12,marginTop:9,backgroundColor:C.paper,borderColor:C.border,borderWidth:1,borderRadius:14},accountIcon:{width:34,height:34,borderRadius:12,backgroundColor:C.pale,alignItems:'center',justifyContent:'center'},accountInitial:{color:C.green,fontSize:14,fontWeight:'700'},roleTag:{color:C.green,backgroundColor:C.pale,overflow:'hidden',borderRadius:9,paddingHorizontal:8,paddingVertical:6,fontSize:9,fontWeight:'700'},footer:{alignItems:'center',marginTop:20},footerText:{color:'#9BA097',fontSize:8,letterSpacing:1.1}
});
