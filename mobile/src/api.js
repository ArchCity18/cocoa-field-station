import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

// For a physical phone, replace with your computer's LAN IP address.
const HOST = Platform.OS === 'android' ? '10.0.2.2' : 'localhost';
export const API_URL = `http://${HOST}/cocoa-security/api.php`;
const TOKEN_KEY = 'cocoa_session_token';

export const saveToken = (token) => SecureStore.setItemAsync(TOKEN_KEY, token);
export const readToken = () => SecureStore.getItemAsync(TOKEN_KEY);
export const clearToken = () => SecureStore.deleteItemAsync(TOKEN_KEY);

export async function request(path, { method = 'GET', body, auth = false } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (auth) {
    const token = await readToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  let response;
  try {
    response = await fetch(`${API_URL}?route=${encodeURIComponent(path.replace(/^\//, ''))}`, {
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
