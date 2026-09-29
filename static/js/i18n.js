// 다국어: static/i18n/{lang}.json 에서 모든 문구를 읽는다.
import { load, save } from './storage.js';

export const LANGS = ['ko', 'en', 'zh', 'ja'];
const HTML_LANG = { ko: 'ko', en: 'en', zh: 'zh-CN', ja: 'ja' };

let dict = {};
let fallback = {};
let current = 'en';
const listeners = [];

export function detectLang() {
  const q = new URLSearchParams(location.search).get('lang');
  if (q && LANGS.includes(q)) return q;
  const saved = load('lang');
  if (saved && LANGS.includes(saved)) return saved;
  for (const l of navigator.languages || [navigator.language || '']) {
    const base = (l || '').toLowerCase().slice(0, 2);
    if (LANGS.includes(base)) return base;
  }
  return 'en';
}

async function fetchDict(lang) {
  const v = (window.__BOOT__ && window.__BOOT__.version) || '';
  const res = await fetch(`/static/i18n/${lang}.json?v=${v}`);
  if (!res.ok) throw new Error('i18n_load_failed');
  return res.json();
}

export async function setLang(lang, persist = true) {
  if (!LANGS.includes(lang)) lang = 'en';
  if (!Object.keys(fallback).length) fallback = await fetchDict('en');
  dict = lang === 'en' ? fallback : await fetchDict(lang);
  current = lang;
  if (persist) save('lang', lang);
  document.documentElement.lang = HTML_LANG[lang];
  document.title = t('title');
  applyDom(document);
  listeners.forEach((fn) => fn(lang));
}

export function getLang() {
  return current;
}

export function onLangChange(fn) {
  listeners.push(fn);
}

export function t(key, params) {
  let s = dict[key];
  if (s == null) {
    s = fallback[key];
    if (s == null) {
      console.warn('[i18n] missing key', key);
      return key;
    }
  }
  if (params) s = s.replace(/\{(\w+)\}/g, (m, k) => (params[k] != null ? params[k] : m));
  return s;
}

export function applyDom(root) {
  root.querySelectorAll('[data-i18n]').forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  root.querySelectorAll('[data-i18n-aria]').forEach((el) => {
    el.setAttribute('aria-label', t(el.dataset.i18nAria));
    el.setAttribute('title', t(el.dataset.i18nAria));
  });
}

export function formatTime(ms) {
  ms = Math.max(0, Math.floor(ms));
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  const cs = Math.floor((ms % 1000) / 10);
  return `${m}:${String(s).padStart(2, '0')}.${String(cs).padStart(2, '0')}`;
}
