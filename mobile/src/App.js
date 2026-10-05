import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Alert, KeyboardAvoidingView, Platform, Pressable, SafeAreaView, ScrollView, StatusBar, StyleSheet, Text, TextInput, View } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { clearToken, request, saveToken } from './api';

const C = { ink: '#24372E', green: '#355640', leaf: '#78916C', cream: '#F7F3EA', paper: '#FFFEFA', border: '#E2DACA', muted: '#778179', pale: '#EBEFE5', error: '#A1463B', gold: '#BD8D48' };

function Brand() { return <View style={s.brand}><View style={s.brandIcon}><Feather name="feather" size={20} color={C.paper} /></View><View><Text style={s.brandName}>Cocoa Field Station</Text><Text style={s.brandCaption}>IDENTITY & FIELD ACCESS</Text></View></View>; }
function Field({ label, icon, value, onChangeText, ...props }) { return <View style={s.fieldBox}><Text style={s.label}>{label}</Text><View style={s.inputRow}><Feather name={icon} size={17} color={C.leaf} /><TextInput accessibilityLabel={label} style={s.input} value={value} onChangeText={onChangeText} placeholderTextColor="#A6ACA5" {...props} /></View></View>; }
function Button({ title, onPress, busy, secondary = false }) { return <Pressable accessibilityRole="button" disabled={busy} onPress={onPress} style={[s.button, secondary && s.secondary]}>{busy && !secondary ? <ActivityIndicator color={C.paper} /> : <Text style={[s.buttonText, secondary && s.secondaryText]}>{title}</Text>}</Pressable>; }

export default function App() {
  const [screen, setScreen] = useState('login');
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ name: '', email: '', password: '', code: '' });
  const [challenge, setChallenge] = useState(null);
  const [user, setUser] = useState(null);
  const [users, setUsers] = useState([]);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const result = await request('/me', { auth: true });
        setUser(result.user); setScreen('home'); await loadWorkspace(result.user);
      } catch { await clearToken(); }
    })();
  }, []);

  async function loadWorkspace(account) {
    try {
      if (account.role === 'admin') setUsers((await request('/admin/users', { auth: true })).users);
      else setSummary(await request('/field/summary', { auth: true }));
    } catch (e) { setError(e.message); }
  }

  function change(key, value) { setForm((old) => ({ ...old, [key]: value })); setError(''); }
  async function submit() {
    setBusy(true); setError('');
    try {
      if (screen === 'verify') {
        const result = await request('/verify', { method: 'POST', body: { challenge_id: challenge, code: form.code } });
        await saveToken(result.token); setUser(result.user); setScreen('home'); await loadWorkspace(result.user);
      } else if (mode === 'register') {
        await request('/register', { method: 'POST', body: { name: form.name, email: form.email, password: form.password } });
        setMode('login'); Alert.alert('Account created', 'Your account has the user role. Sign in and verify your email.');
      } else {
        const result = await request('/login', { method: 'POST', body: { email: form.email, password: form.password } });
        setChallenge(result.challenge_id); setScreen('verify');
      }
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function logout() {
    try { await request('/logout', { method: 'POST', auth: true }); } catch {}
    await clearToken(); setUser(null); setMode('login'); setScreen('login'); setForm({ name: '', email: '', password: '', code: '' });
  }

  if (user && screen === 'home') {
    const admin = user.role === 'admin';
    return <SafeAreaView style={s.safe}><StatusBar barStyle="dark-content" backgroundColor={C.cream} /><ScrollView contentContainerStyle={s.page}>
      <Brand />
      <View style={s.welcome}><View><Text style={s.kicker}>YOUR FIELD DESK</Text><Text style={s.title}>Good to see you,</Text><Text style={[s.title, { color: C.green }]}>{user.name.split(' ')[0]}.</Text></View><View style={s.avatar}><Text style={s.avatarText}>{user.name[0].toUpperCase()}</Text></View></View>
      <View style={s.identity}><View style={s.roleIcon}><Feather name={admin ? 'shield' : 'map'} size={20} color={C.green} /></View><View style={{ flex: 1 }}><Text style={s.kicker}>SIGNED IN AS</Text><Text style={s.role}>{user.role}</Text><Text style={s.muted}>{user.email}</Text></View><View style={s.verified}><Feather name="check-circle" size={13} color={C.green} /><Text style={s.verifiedText}>VERIFIED</Text></View></View>
      {admin ? <><Text style={s.section}>Account directory</Text><Text style={s.body}>Admin workspace · {users.length} registered accounts</Text>{users.map((item) => <View key={item.id} style={s.userRow}><View style={s.avatarMini}><Text style={s.avatarText}>{item.name[0].toUpperCase()}</Text></View><View style={{ flex: 1 }}><Text style={s.userName}>{item.name}</Text><Text style={s.muted}>{item.email}</Text></View><Text style={s.roleTag}>{item.role}</Text></View>)}</> : <><Text style={s.section}>User workspace</Text><View style={s.feature}><Feather name="sun" size={22} color={C.gold} /><Text style={s.featureTitle}>Your field access is ready</Text><Text style={s.body}>Your verified account can access field station tools. The server checks your role on every protected request.</Text>{summary && <Text style={s.muted}>{summary.account_count} station accounts</Text>}</View></>}
      <View style={s.notice}><Feather name="lock" size={16} color={C.green} /><Text style={s.noticeText}>Passwords are stored as salted hashes. Sign-in requires your password and a one-time email code.</Text></View>
      <Button title="Sign out" secondary busy={busy} onPress={logout} />
    </ScrollView></SafeAreaView>;
  }

  return <SafeAreaView style={s.safe}><StatusBar barStyle="dark-content" backgroundColor={C.cream} /><KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}><ScrollView contentContainerStyle={s.page} keyboardShouldPersistTaps="handled">
    <Brand />
    <View style={s.hero}><Text style={s.kicker}>A MORE THOUGHTFUL WAY TO SIGN IN</Text><Text style={s.title}>{screen === 'verify' ? 'One more step.' : mode === 'register' ? 'Join your field station.' : 'Welcome back.'}</Text><Text style={s.body}>{screen === 'verify' ? 'Enter the six-digit code sent to your email.' : mode === 'register' ? 'Create a secure account for your cocoa field workspace.' : 'Sign in securely to continue to your cocoa workspace.'}</Text></View>
    {screen !== 'verify' && <View style={s.tabs}><Pressable onPress={() => { setMode('login'); setError(''); }} style={[s.tab, mode === 'login' && s.activeTab]}><Text style={[s.tabText, mode === 'login' && s.activeTabText]}>Sign in</Text></Pressable><Pressable onPress={() => { setMode('register'); setError(''); }} style={[s.tab, mode === 'register' && s.activeTab]}><Text style={[s.tabText, mode === 'register' && s.activeTabText]}>Create account</Text></Pressable></View>}
    <View style={s.card}>
      {screen === 'verify' ? <><View style={s.cardIcon}><Feather name="key" size={19} color={C.green} /></View><Text style={s.cardTitle}>Verify it’s you</Text><Text style={s.muted}>Your code expires in 10 minutes.</Text><Field label="6-digit verification code" icon="hash" value={form.code} onChangeText={(v) => change('code', v.replace(/\D/g, '').slice(0, 6))} keyboardType="number-pad" placeholder="000000" /></> : <>
        {mode === 'register' && <Field label="Your name" icon="user" value={form.name} onChangeText={(v) => change('name', v)} placeholder="e.g. Ama Mensah" />}
        <Field label="Email address" icon="mail" value={form.email} onChangeText={(v) => change('email', v)} keyboardType="email-address" autoCapitalize="none" placeholder="you@example.com" />
        <Field label="Password" icon="lock" value={form.password} onChangeText={(v) => change('password', v)} secureTextEntry placeholder="At least 10 characters" />
        {mode === 'register' && <Text style={s.helper}>New accounts start with the user role.</Text>}
      </>}
      {!!error && <View style={s.error}><Feather name="alert-circle" size={16} color={C.error} /><Text style={s.errorText}>{error}</Text></View>}
      <Button title={screen === 'verify' ? 'Verify and continue' : mode === 'register' ? 'Create account' : 'Continue securely'} busy={busy} onPress={submit} />
      {screen === 'verify' && <Pressable onPress={() => { setScreen('login'); setError(''); }}><Text style={s.back}>Back to sign in</Text></Pressable>}
    </View>
    <View style={s.trust}><View style={s.trustItem}><Feather name="shield" size={15} color={C.leaf} /><Text style={s.trustText}>Protected access</Text></View><View style={s.trustItem}><Feather name="key" size={15} color={C.leaf} /><Text style={s.trustText}>Two-step verification</Text></View></View>
    <Text style={s.footer}>COCOA FIELD STATION  ·  PRIVATE BY DESIGN</Text>
  </ScrollView></KeyboardAvoidingView></SafeAreaView>;
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: C.cream }, page: { flexGrow: 1, paddingHorizontal: 24, paddingTop: 18, paddingBottom: 32, maxWidth: 560, width: '100%', alignSelf: 'center' },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 11, marginBottom: 42 }, brandIcon: { width: 40, height: 40, borderRadius: 14, backgroundColor: C.green, alignItems: 'center', justifyContent: 'center' }, brandName: { color: C.ink, fontWeight: '700', fontSize: 16 }, brandCaption: { color: C.muted, fontSize: 9, letterSpacing: 1.6, fontWeight: '700', marginTop: 3 },
  kicker: { color: C.leaf, fontSize: 10, letterSpacing: 1.6, fontWeight: '800', marginBottom: 10 }, hero: { marginBottom: 23 }, title: { color: C.ink, fontSize: 32, lineHeight: 39, fontWeight: '700', letterSpacing: -0.8 }, body: { color: '#66736A', fontSize: 13, lineHeight: 21, marginTop: 8 },
  tabs: { flexDirection: 'row', padding: 4, borderRadius: 14, backgroundColor: '#EBE6DC', marginBottom: 14 }, tab: { flex: 1, alignItems: 'center', paddingVertical: 12, borderRadius: 11 }, activeTab: { backgroundColor: C.paper }, tabText: { color: C.muted, fontSize: 13, fontWeight: '600' }, activeTabText: { color: C.green },
  card: { padding: 20, backgroundColor: C.paper, borderColor: C.border, borderWidth: 1, borderRadius: 19 }, cardIcon: { width: 39, height: 39, borderRadius: 13, backgroundColor: C.pale, alignItems: 'center', justifyContent: 'center', marginBottom: 12 }, cardTitle: { color: C.ink, fontSize: 18, fontWeight: '700', marginBottom: 4 }, fieldBox: { marginTop: 16 }, label: { color: C.ink, fontSize: 12, fontWeight: '700', marginBottom: 8 }, inputRow: { minHeight: 49, flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 13, borderRadius: 12, borderWidth: 1, borderColor: C.border, backgroundColor: '#FFFDF8' }, input: { flex: 1, paddingVertical: 12, color: C.ink, fontSize: 14 }, muted: { color: C.muted, fontSize: 11, marginTop: 4 }, helper: { color: C.muted, fontSize: 11, marginTop: 8 },
  button: { minHeight: 50, marginTop: 20, borderRadius: 13, alignItems: 'center', justifyContent: 'center', backgroundColor: C.green }, buttonText: { color: C.paper, fontSize: 14, fontWeight: '700' }, secondary: { backgroundColor: 'transparent', borderColor: C.border, borderWidth: 1 }, secondaryText: { color: C.green }, back: { color: C.green, textAlign: 'center', marginTop: 17, fontSize: 13, fontWeight: '600' }, error: { flexDirection: 'row', gap: 8, marginTop: 14, padding: 11, borderRadius: 11, backgroundColor: '#F8EAE6' }, errorText: { flex: 1, color: C.error, fontSize: 12, lineHeight: 17 },
  trust: { flexDirection: 'row', justifyContent: 'center', gap: 20, marginTop: 22 }, trustItem: { flexDirection: 'row', alignItems: 'center', gap: 6 }, trustText: { color: C.muted, fontSize: 10, fontWeight: '600' }, footer: { color: '#9BA097', fontSize: 9, letterSpacing: 1.3, textAlign: 'center', marginTop: 30 },
  welcome: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 23 }, avatar: { width: 48, height: 48, borderRadius: 17, backgroundColor: '#E8EDE2', alignItems: 'center', justifyContent: 'center' }, avatarText: { color: C.green, fontSize: 16, fontWeight: '700' }, identity: { flexDirection: 'row', alignItems: 'center', gap: 11, padding: 14, borderRadius: 17, backgroundColor: C.paper, borderWidth: 1, borderColor: C.border, marginBottom: 27 }, roleIcon: { width: 42, height: 42, borderRadius: 14, backgroundColor: C.pale, alignItems: 'center', justifyContent: 'center' }, role: { color: C.ink, fontSize: 14, fontWeight: '700' }, verified: { flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 20, padding: 7, backgroundColor: C.pale }, verifiedText: { color: C.green, fontWeight: '800', fontSize: 8 }, section: { color: C.ink, fontSize: 19, fontWeight: '700', marginBottom: 5 }, feature: { backgroundColor: C.paper, borderWidth: 1, borderColor: C.border, borderRadius: 18, padding: 20, marginTop: 14 }, featureTitle: { color: C.ink, fontSize: 16, fontWeight: '700', marginTop: 13 }, notice: { flexDirection: 'row', gap: 9, padding: 14, marginTop: 22, backgroundColor: '#EAF0E6', borderRadius: 14 }, noticeText: { flex: 1, color: '#4E6453', fontSize: 11, lineHeight: 17 }, userRow: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, marginTop: 9, backgroundColor: C.paper, borderColor: C.border, borderWidth: 1, borderRadius: 14 }, avatarMini: { width: 34, height: 34, borderRadius: 12, backgroundColor: C.pale, alignItems: 'center', justifyContent: 'center' }, userName: { color: C.ink, fontSize: 13, fontWeight: '700' }, roleTag: { color: C.green, backgroundColor: C.pale, overflow: 'hidden', borderRadius: 9, paddingHorizontal: 8, paddingVertical: 6, fontSize: 9, fontWeight: '700' },
});
