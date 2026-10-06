import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Alert, KeyboardAvoidingView, Platform, Pressable, SafeAreaView, ScrollView, StatusBar, StyleSheet, Text, TextInput, View } from 'react-native';
import { Feather } from '@expo/vector-icons';
import * as Google from 'expo-auth-session/providers/google';
import * as WebBrowser from 'expo-web-browser';
import QRCode from 'react-native-qrcode-svg';
import { SvgXml } from 'react-native-svg';
import FieldWorkspace from './FieldWorkspace';
import { clearToken, request, saveToken } from './api';
import groveHero from './groveArtwork';

WebBrowser.maybeCompleteAuthSession();
const C = { ink: '#24372E', green: '#355640', leaf: '#78916C', cream: '#F7F3EA', paper: '#FFFEFA', border: '#E2DACA', muted: '#778179', pale: '#EBEFE5', error: '#A1463B', gold: '#BD8D48' };
function Brand() { return <View style={s.brand}><View style={s.brandIcon}><Feather name="feather" size={20} color={C.paper} /></View><View><Text style={s.brandName}>Cocoa Field Station</Text><Text style={s.brandCaption}>IDENTITY & FIELD ACCESS</Text></View></View>; }
function Field({ label, icon, value, onChangeText, ...props }) { return <View style={s.fieldBox}><Text style={s.label}>{label}</Text><View style={s.inputRow}><Feather name={icon} size={17} color={C.leaf} /><TextInput accessibilityLabel={label} style={s.input} value={value} onChangeText={onChangeText} placeholderTextColor="#A6ACA5" {...props} /></View></View>; }
function Button({ title, onPress, busy, secondary = false }) { return <Pressable accessibilityRole="button" disabled={busy} onPress={onPress} style={[s.button, secondary && s.secondary]}>{busy && !secondary ? <ActivityIndicator color={C.paper} /> : <Text style={[s.buttonText, secondary && s.secondaryText]}>{title}</Text>}</Pressable>; }
const plotDetails = { 'Plot A': 'Rising rain and humidity', 'Plot B': 'Recent gaps in observations', 'Plot C': 'Middle-range conditions' };
const plotMetrics = { 'Plot A': ['66.7', '89'], 'Plot B': ['8.5', '76'], 'Plot C': ['24.3', '83'] };

export default function App() {
  const [screen, setScreen] = useState('welcome');
  const [previewPlot, setPreviewPlot] = useState('Plot A');
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ name: '', email: '', password: '', code: '' });
  const [challenge, setChallenge] = useState(null);
  const [oauth, setOauth] = useState({});
  const [user, setUser] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const [googleRequest, googleResponse, promptGoogle] = Google.useIdTokenAuthRequest({
    webClientId: oauth.google_web_client_id || 'google-web-client-not-configured',
    androidClientId: oauth.google_android_client_id || 'google-android-client-not-configured',
    iosClientId: oauth.google_ios_client_id || 'google-ios-client-not-configured',
    scopes: ['openid', 'profile', 'email'],
  }, { scheme: 'cocoa-field-station-mobile' });

  useEffect(() => { request('/public-config').then(setOauth).catch(() => {}); }, []);
  useEffect(() => { (async () => { try { const result = await request('/me', { auth: true }); setUser(result.user); setScreen('home'); } catch { await clearToken(); } })(); }, []);
  useEffect(() => {
    if (googleResponse?.type !== 'success') return;
    const idToken = googleResponse.params?.id_token || googleResponse.authentication?.idToken;
    if (!idToken) { setError('Google did not return an ID token. Check the OAuth client settings.'); return; }
    (async () => { setBusy(true); setError(''); try { const result = await request('/google-login', { method: 'POST', body: { id_token: idToken } }); setChallenge(result); setScreen('totp'); setForm((f) => ({ ...f, code: '' })); } catch (e) { setError(e.message); } finally { setBusy(false); } })();
  }, [googleResponse]);

  function change(key, value) { setForm((old) => ({ ...old, [key]: value })); setError(''); }
  async function submit() {
    setBusy(true); setError('');
    try {
      if (screen === 'totp') {
        const result = await request('/verify-totp', { method: 'POST', body: { challenge_id: challenge.challenge_id, code: form.code } });
        await saveToken(result.token); setUser(result.user); setScreen('home');
      } else if (mode === 'register') {
        await request('/register', { method: 'POST', body: { name: form.name, email: form.email, password: form.password } });
        setMode('login'); Alert.alert('Account created', 'Your account has the user role. Sign in and connect Google Authenticator.');
      } else {
        const result = await request('/login', { method: 'POST', body: { email: form.email, password: form.password } });
        setChallenge(result); setScreen('totp'); setForm((f) => ({ ...f, code: '' }));
      }
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function finishGoogleSignIn() {
    const nativeClientId = Platform.OS === 'android' ? oauth.google_android_client_id : oauth.google_ios_client_id;
    if (Platform.OS !== 'web' && !nativeClientId) { setError('Add this platform’s Google OAuth client ID and use an Expo development build for native Google sign-in.'); return; }
    if (Platform.OS === 'web' && !oauth.google_web_client_id) { setError('Google sign-in is not configured yet. Add the Expo web OAuth client ID to the XAMPP config.'); return; }
    try { await promptGoogle(); } catch { setError('Could not open Google sign-in.'); }
  }
  async function logout() {
    try { await request('/logout', { method: 'POST', auth: true }); } catch {}
    await clearToken(); setUser(null); setMode('login'); setScreen('welcome'); setChallenge(null); setForm({ name: '', email: '', password: '', code: '' });
  }

  function openAuth(nextMode = 'login') { setMode(nextMode); setError(''); setScreen('login'); }

  if (screen === 'welcome' && !user) {
    return <SafeAreaView style={s.safe}><StatusBar barStyle="dark-content" backgroundColor={C.cream} /><ScrollView contentContainerStyle={s.page}>
      <Brand />
      <View style={s.landingHero}>
        <View style={s.landingBadge}><Feather name="sun" size={13} color={C.green} /><Text style={s.landingBadgeText}>A COCOA GROWER'S FIELD DESK</Text></View>
        <Text style={s.landingTitle}>Know your cocoa fields. Tend them with confidence.</Text>
        <Text style={s.landingBody}>A thoughtful view of changing conditions across your cocoa plots, with practical next steps you can review before you act.</Text>
        <Pressable accessibilityRole="button" onPress={() => openAuth('login')} style={s.landingButton}><Text style={s.buttonText}>Explore the field station</Text><Feather name="arrow-right" size={17} color={C.paper} /></Pressable>
        <Pressable onPress={() => openAuth('register')}><Text style={s.landingSecondary}>New here? Create an account <Text style={s.landingArrow}>→</Text></Text></Pressable>
      </View>
      <View style={s.landingImageFrame}><SvgXml xml={groveHero} width="100%" height="100%" /><View style={s.imageLabel}><Feather name="map-pin" size={12} color={C.green} /><Text style={s.imageLabelText}>An illustrated cocoa-growing landscape</Text></View></View>
      <View style={s.plotPreview}>
        <View style={s.previewTop}><View><Text style={s.kicker}>FIELD JOURNAL / PLOT PREVIEW</Text><Text style={s.previewTitle}>A clearer view of your plots</Text></View><View style={s.previewIcon}><Feather name="bar-chart-2" size={19} color={C.green} /></View></View>
        <Text style={s.previewPrompt}>Start with a plot</Text>
        <View style={s.plotChoices}>{['Plot A', 'Plot B', 'Plot C'].map((plot) => <Pressable key={plot} accessibilityRole="button" onPress={() => setPreviewPlot(plot)} style={[s.plotChoice, previewPlot === plot && s.plotChoiceActive]}><Text style={[s.plotChoiceText, previewPlot === plot && s.plotChoiceTextActive]}>{plot}</Text></Pressable>)}</View>
        <Text style={s.plotDescription}>{plotDetails[previewPlot]}</Text>
        <View style={s.previewMetrics}><View style={s.metricTile}><Feather name="cloud-rain" size={15} color={C.leaf} /><Text style={s.previewMetricTitle}>Rain this week</Text><Text style={s.metricValue}>{plotMetrics[previewPlot][0]}<Text style={s.metricUnit}> mm</Text></Text></View><View style={s.metricTile}><Feather name="droplet" size={15} color={C.leaf} /><Text style={s.previewMetricTitle}>Average humidity</Text><Text style={s.metricValue}>{plotMetrics[previewPlot][1]}<Text style={s.metricUnit}>%</Text></Text></View><View style={s.metricTile}><Feather name="calendar" size={15} color={C.leaf} /><Text style={s.previewMetricTitle}>Field notes</Text><Text style={s.metricValue}>7<Text style={s.metricUnit}> days</Text></Text></View></View>
        <Text style={s.previewFootnote}>SIMULATED DEMO DATA · Conditions and agronomy thresholds are illustrative.</Text>
      </View>
      <Text style={s.section}>A field routine built around your judgement</Text>
      <View style={s.landingStep}><View style={s.stepIcon}><Feather name="eye" size={17} color={C.green} /></View><View style={s.landingStepCopy}><Text style={s.landingStepTitle}>Read the conditions</Text><Text style={s.landingStepBody}>Bring recent plot observations into view.</Text></View></View>
      <View style={s.landingStep}><View style={s.stepIcon}><Feather name="search" size={17} color={C.green} /></View><View style={s.landingStepCopy}><Text style={s.landingStepTitle}>See why it matters</Text><Text style={s.landingStepBody}>Review the evidence behind each suggestion.</Text></View></View>
      <View style={s.landingStep}><View style={s.stepIcon}><Feather name="check-square" size={17} color={C.green} /></View><View style={s.landingStepCopy}><Text style={s.landingStepTitle}>Make the call</Text><Text style={s.landingStepBody}>Record your decision and keep control.</Text></View></View>
      <View style={s.landingFooter}><Pressable onPress={() => openAuth('login')}><Text style={s.landingFooterLink}>Already have an account? Sign in</Text></Pressable><Text style={s.footer}>COCOA FIELD STATION · PRIVATE BY DESIGN</Text></View>
    </ScrollView></SafeAreaView>;
  }

  if (user && screen === 'home') {
    return <FieldWorkspace user={user} onLogout={logout} />;
  }

  const setup = screen === 'totp' && challenge?.setup_required;
  return <SafeAreaView style={s.safe}><StatusBar barStyle="dark-content" backgroundColor={C.cream} /><KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}><ScrollView contentContainerStyle={s.page} keyboardShouldPersistTaps="handled">
    <Brand />
    {screen !== 'totp' && <Pressable onPress={() => setScreen('welcome')} style={s.backHome}><Feather name="arrow-left" size={15} color={C.green} /><Text style={s.backHomeText}>Back to welcome</Text></Pressable>}
    <View style={s.hero}><Text style={s.kicker}>A MORE THOUGHTFUL WAY TO SIGN IN</Text><Text style={s.title}>{screen === 'totp' ? setup ? 'Set up your authenticator.' : 'One more step.' : mode === 'register' ? 'Join your field station.' : 'Welcome back.'}</Text><Text style={s.body}>{screen === 'totp' ? setup ? 'Scan this QR code in Google Authenticator, then enter the six-digit code it creates.' : 'Enter the current six-digit code from your authenticator app.' : mode === 'register' ? 'Create a secure account for your cocoa field workspace.' : 'Sign in securely to continue to your cocoa workspace.'}</Text></View>
    {screen !== 'totp' && <View style={s.tabs}><Pressable onPress={() => { setMode('login'); setError(''); }} style={[s.tab, mode === 'login' && s.activeTab]}><Text style={[s.tabText, mode === 'login' && s.activeTabText]}>Sign in</Text></Pressable><Pressable onPress={() => { setMode('register'); setError(''); }} style={[s.tab, mode === 'register' && s.activeTab]}><Text style={[s.tabText, mode === 'register' && s.activeTabText]}>Create account</Text></Pressable></View>}
    <View style={s.card}>
      {screen === 'totp' ? <><View style={s.cardIcon}><Feather name="key" size={19} color={C.green} /></View><Text style={s.cardTitle}>{setup ? 'Connect Google Authenticator' : 'Verify it’s you'}</Text>{setup && challenge?.otpauth_uri && <View style={s.qrBox}><QRCode value={challenge.otpauth_uri} size={180} /></View>}{setup && <><Text style={s.label}>Can’t scan? Enter this setup key manually</Text><Text selectable style={s.secret}>{challenge.secret}</Text><Text style={s.muted}>Setup expires in 10 minutes. Enter the code shown in your authenticator app to finish.</Text></>}<Field label="6-digit authenticator code" icon="hash" value={form.code} onChangeText={(v) => change('code', v.replace(/\D/g, '').slice(0, 6))} keyboardType="number-pad" placeholder="000000" /></> : <>
        {mode === 'register' && <Field label="Your name" icon="user" value={form.name} onChangeText={(v) => change('name', v)} placeholder="e.g. Ama Mensah" />}
        <Field label="Email address" icon="mail" value={form.email} onChangeText={(v) => change('email', v)} keyboardType="email-address" autoCapitalize="none" placeholder="you@example.com" />
        <Field label="Password" icon="lock" value={form.password} onChangeText={(v) => change('password', v)} secureTextEntry placeholder="At least 10 characters" />
        {mode === 'register' && <Text style={s.helper}>New accounts start with the user role.</Text>}
      </>}
      {!!error && <View style={s.error}><Feather name="alert-circle" size={16} color={C.error} /><Text style={s.errorText}>{error}</Text></View>}
      <Button title={screen === 'totp' ? setup ? 'Connect and continue' : 'Verify and continue' : mode === 'register' ? 'Create account' : 'Continue securely'} busy={busy} onPress={submit} />
      {screen === 'totp' && <Pressable onPress={() => { setScreen('login'); setChallenge(null); setError(''); }}><Text style={s.back}>Back to sign in</Text></Pressable>}
      {screen !== 'totp' && mode === 'login' && <><View style={s.divider}><Text style={s.dividerText}>OR</Text></View><Pressable accessibilityRole="button" disabled={!googleRequest || busy} onPress={finishGoogleSignIn} style={s.googleButton}><Text style={s.googleMark}>G</Text><Text style={s.googleText}>Continue with Google</Text></Pressable><Text style={s.googleNote}>Google sign-in also requires your authenticator code.</Text>{!oauth.google_web_client_id && googleRequest?.redirectUri && <Text selectable style={s.googleSetup}>For OAuth setup, register this local redirect URI in Google Cloud: {googleRequest.redirectUri}</Text>}</>}
    </View>
    <View style={s.trust}><View style={s.trustItem}><Feather name="shield" size={15} color={C.leaf} /><Text style={s.trustText}>Protected access</Text></View><View style={s.trustItem}><Feather name="key" size={15} color={C.leaf} /><Text style={s.trustText}>Authenticator verification</Text></View></View>
    <Text style={s.footer}>COCOA FIELD STATION · PRIVATE BY DESIGN</Text>
  </ScrollView></KeyboardAvoidingView></SafeAreaView>;
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: C.cream }, page: { flexGrow: 1, paddingHorizontal: 24, paddingTop: 18, paddingBottom: 32, maxWidth: 560, width: '100%', alignSelf: 'center' },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 11, marginBottom: 42 }, brandIcon: { width: 40, height: 40, borderRadius: 14, backgroundColor: C.green, alignItems: 'center', justifyContent: 'center' }, brandName: { color: C.ink, fontWeight: '700', fontSize: 16 }, brandCaption: { color: C.muted, fontSize: 9, letterSpacing: 1.6, fontWeight: '700', marginTop: 3 },
  kicker: { color: C.leaf, fontSize: 10, letterSpacing: 1.6, fontWeight: '800', marginBottom: 10 }, hero: { marginBottom: 23 }, title: { color: C.ink, fontSize: 32, lineHeight: 39, fontWeight: '700', letterSpacing: -0.8 }, body: { color: '#66736A', fontSize: 13, lineHeight: 21, marginTop: 8 },
  tabs: { flexDirection: 'row', padding: 4, borderRadius: 14, backgroundColor: '#EBE6DC', marginBottom: 14 }, tab: { flex: 1, alignItems: 'center', paddingVertical: 12, borderRadius: 11 }, activeTab: { backgroundColor: C.paper }, tabText: { color: C.muted, fontSize: 13, fontWeight: '600' }, activeTabText: { color: C.green },
  card: { padding: 20, backgroundColor: C.paper, borderColor: C.border, borderWidth: 1, borderRadius: 19 }, cardIcon: { width: 39, height: 39, borderRadius: 13, backgroundColor: C.pale, alignItems: 'center', justifyContent: 'center', marginBottom: 12 }, cardTitle: { color: C.ink, fontSize: 18, fontWeight: '700', marginBottom: 4 }, fieldBox: { marginTop: 16 }, label: { color: C.ink, fontSize: 12, fontWeight: '700', marginBottom: 8 }, inputRow: { minHeight: 49, flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 13, borderRadius: 12, borderWidth: 1, borderColor: C.border, backgroundColor: '#FFFDF8' }, input: { flex: 1, paddingVertical: 12, color: C.ink, fontSize: 14 }, muted: { color: C.muted, fontSize: 11, marginTop: 4 }, helper: { color: C.muted, fontSize: 11, marginTop: 8 },
  button: { minHeight: 50, marginTop: 20, borderRadius: 13, alignItems: 'center', justifyContent: 'center', backgroundColor: C.green }, buttonText: { color: C.paper, fontSize: 14, fontWeight: '700' }, secondary: { backgroundColor: 'transparent', borderColor: C.border, borderWidth: 1 }, secondaryText: { color: C.green }, back: { color: C.green, textAlign: 'center', marginTop: 17, fontSize: 13, fontWeight: '600' }, error: { flexDirection: 'row', gap: 8, marginTop: 14, padding: 11, borderRadius: 11, backgroundColor: '#F8EAE6' }, errorText: { flex: 1, color: C.error, fontSize: 12, lineHeight: 17 },
  qrBox: { alignItems: 'center', padding: 16, marginVertical: 14, backgroundColor: '#FFFFFF', borderRadius: 14 }, secret: { alignSelf: 'flex-start', marginTop: 9, padding: 10, color: C.ink, backgroundColor: C.cream, borderRadius: 8, fontWeight: '700', letterSpacing: 1 }, divider: { alignItems: 'center', marginTop: 17 }, dividerText: { color: C.muted, fontSize: 10, fontWeight: '700' }, googleButton: { minHeight: 50, marginTop: 14, borderRadius: 13, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 10, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: C.border }, googleMark: { fontSize: 17, fontWeight: '800', color: '#4285F4' }, googleText: { color: C.ink, fontSize: 14, fontWeight: '700' }, googleNote: { color: C.muted, fontSize: 10, textAlign: 'center', marginTop: 9 }, googleSetup: { color: C.muted, fontSize: 10, lineHeight: 15, textAlign: 'center', marginTop: 8 },
  trust: { flexDirection: 'row', justifyContent: 'center', gap: 20, marginTop: 22 }, trustItem: { flexDirection: 'row', alignItems: 'center', gap: 6 }, trustText: { color: C.muted, fontSize: 10, fontWeight: '600' }, footer: { color: '#9BA097', fontSize: 9, letterSpacing: 1.3, textAlign: 'center', marginTop: 30 },
  landingHero: { paddingTop: 9, paddingBottom: 25 }, landingBadge: { alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 7, backgroundColor: '#E9EEE4', borderRadius: 18, paddingVertical: 8, paddingHorizontal: 11, marginBottom: 18 }, landingBadgeText: { color: C.green, fontSize: 9, fontWeight: '800', letterSpacing: 1.1 }, landingTitle: { color: C.ink, fontSize: 39, lineHeight: 45, fontWeight: '800', letterSpacing: -1.3 }, landingBody: { color: '#66736A', fontSize: 15, lineHeight: 23, marginTop: 14 }, landingButton: { minHeight: 50, marginTop: 20, borderRadius: 13, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: C.green }, landingSecondary: { color: C.green, textAlign: 'center', fontSize: 13, fontWeight: '700', marginTop: 15 }, landingArrow: { fontSize: 15 }, landingImageFrame: { height: 235, borderRadius: 20, overflow: 'hidden', marginBottom: 22, backgroundColor: '#D5DDC6', position: 'relative' }, landingImage: { width: '100%', height: '100%' }, imageLabel: { position: 'absolute', bottom: 12, left: 12, flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: 'rgba(255,254,250,0.92)', paddingHorizontal: 11, paddingVertical: 8, borderRadius: 20 }, imageLabelText: { color: C.ink, fontSize: 10, fontWeight: '700' }, plotPreview: { padding: 17, backgroundColor: C.paper, borderColor: C.border, borderWidth: 1, borderRadius: 20, marginBottom: 28 }, previewTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }, previewTitle: { color: C.ink, fontSize: 17, fontWeight: '700' }, previewIcon: { width: 40, height: 40, borderRadius: 14, backgroundColor: C.pale, alignItems: 'center', justifyContent: 'center' }, previewPrompt: { color: C.ink, fontSize: 11, fontWeight: '700', marginTop: 17, marginBottom: 9 }, plotChoices: { flexDirection: 'row', gap: 7 }, plotChoice: { flex: 1, alignItems: 'center', paddingVertical: 10, backgroundColor: C.cream, borderColor: C.border, borderWidth: 1, borderRadius: 11 }, plotChoiceActive: { backgroundColor: '#E9EEE4', borderColor: C.green }, plotChoiceText: { color: C.muted, fontSize: 11, fontWeight: '600' }, plotChoiceTextActive: { color: C.green }, plotDescription: { color: C.muted, fontSize: 10, marginTop: 9 }, previewMetrics: { flexDirection: 'row', gap: 7, marginTop: 14 }, metricTile: { flex: 1, minHeight: 92, padding: 9, borderRadius: 12, borderWidth: 1, borderColor: C.border, backgroundColor: '#FFFDF8' }, previewMetricTitle: { color: C.muted, fontSize: 9, lineHeight: 12, fontWeight: '600', marginTop: 7 }, metricValue: { color: C.ink, fontSize: 20, fontWeight: '700', marginTop: 4 }, metricUnit: { color: C.muted, fontSize: 10, fontWeight: '500' }, previewFootnote: { color: '#9BA097', fontSize: 8, lineHeight: 12, letterSpacing: 0.3, marginTop: 13 }, landingStep: { flexDirection: 'row', alignItems: 'center', gap: 13, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: C.border }, stepIcon: { width: 38, height: 38, borderRadius: 13, backgroundColor: C.pale, alignItems: 'center', justifyContent: 'center' }, landingStepCopy: { flex: 1 }, landingStepTitle: { color: C.ink, fontSize: 13, fontWeight: '700' }, landingStepBody: { color: C.muted, fontSize: 11, marginTop: 4 }, landingFooter: { alignItems: 'center', gap: 15, marginTop: 25 }, landingFooterLink: { color: C.green, fontSize: 13, fontWeight: '700' }, backHome: { flexDirection: 'row', alignItems: 'center', gap: 7, alignSelf: 'flex-start', marginTop: -23, marginBottom: 25 }, backHomeText: { color: C.green, fontSize: 12, fontWeight: '600' },
  welcome: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 23 }, avatar: { width: 48, height: 48, borderRadius: 17, backgroundColor: '#E8EDE2', alignItems: 'center', justifyContent: 'center' }, avatarText: { color: C.green, fontSize: 16, fontWeight: '700' }, identity: { flexDirection: 'row', alignItems: 'center', gap: 11, padding: 14, borderRadius: 17, backgroundColor: C.paper, borderWidth: 1, borderColor: C.border, marginBottom: 27 }, roleIcon: { width: 42, height: 42, borderRadius: 14, backgroundColor: C.pale, alignItems: 'center', justifyContent: 'center' }, role: { color: C.ink, fontSize: 14, fontWeight: '700' }, verified: { flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 20, padding: 7, backgroundColor: C.pale }, verifiedText: { color: C.green, fontWeight: '800', fontSize: 8 }, section: { color: C.ink, fontSize: 19, fontWeight: '700', marginBottom: 5 }, feature: { backgroundColor: C.paper, borderWidth: 1, borderColor: C.border, borderRadius: 18, padding: 20, marginTop: 14 }, featureTitle: { color: C.ink, fontSize: 16, fontWeight: '700', marginTop: 13 }, notice: { flexDirection: 'row', gap: 9, padding: 14, marginTop: 22, backgroundColor: '#EAF0E6', borderRadius: 14 }, noticeText: { flex: 1, color: '#4E6453', fontSize: 11, lineHeight: 17 }, userRow: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, marginTop: 9, backgroundColor: C.paper, borderColor: C.border, borderWidth: 1, borderRadius: 14 }, avatarMini: { width: 34, height: 34, borderRadius: 12, backgroundColor: C.pale, alignItems: 'center', justifyContent: 'center' }, userName: { color: C.ink, fontSize: 13, fontWeight: '700' }, roleTag: { color: C.green, backgroundColor: C.pale, overflow: 'hidden', borderRadius: 9, paddingHorizontal: 8, paddingVertical: 6, fontSize: 9, fontWeight: '700' },
});
