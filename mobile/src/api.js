import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

// Set EXPO_PUBLIC_API_HOST in mobile/.env to your computer's LAN IP for phones.
// Without an override, Android emulators use their special host alias.
const HOST = process.env.EXPO_PUBLIC_API_HOST || (Platform.OS === 'android' ? '10.0.2.2' : 'localhost');
export const API_URL = `http://${HOST}/cocoa-security/api.php`;
const TOKEN_KEY = 'cocoa_session_token';

// expo-secure-store's native methods are unavailable in the web build.
// Keep tokens in browser localStorage on web; use device secure storage on iOS/Android.
export async function saveToken(token) {
  if (Platform.OS === 'web') { globalThis.localStorage?.setItem(TOKEN_KEY, token); return; }
  await SecureStore.setItemAsync(TOKEN_KEY, token);
}

export async function readToken() {
  if (Platform.OS === 'web') return globalThis.localStorage?.getItem(TOKEN_KEY) ?? null;
  return SecureStore.getItemAsync(TOKEN_KEY);
}

export async function clearToken() {
  if (Platform.OS === 'web') { globalThis.localStorage?.removeItem(TOKEN_KEY); return; }
  await SecureStore.deleteItemAsync(TOKEN_KEY);
}

export async function request(path, { method = 'GET', body, auth = false, query } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (auth) {
    const token = await readToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  let response;
  try {
    const params = new URLSearchParams({ route: path.replace(/^\//, ''), ...(query || {}) });
    response = await fetch(`${API_URL}?${params.toString()}`, {
      method,
      headers,
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
  } catch {
    throw new Error('Cannot reach the local API. Check XAMPP and the API_URL in mobile/src/api.js.');
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
}
