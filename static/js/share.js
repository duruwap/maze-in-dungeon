// 공유: 카카오톡(Kakao.Share.sendDefault), Web Share API, 링크 복사.
import { t, getLang, formatTime } from './i18n.js';

const BOOT = window.__BOOT__ || {};

export function kakaoAvailable() {
  return !!(BOOT.kakaoKey && window.Kakao);
}

export function initKakao() {
  try {
    if (BOOT.kakaoKey && window.Kakao && !window.Kakao.isInitialized()) window.Kakao.init(BOOT.kakaoKey);
  } catch (e) {
    console.warn('[share] kakao init failed', e);
  }
}

export function baseUrl() {
  return (BOOT.baseUrl || location.origin).replace(/\/$/, '');
}

export function shareUrl(runId) {
  const lang = getLang();
  return runId ? `${baseUrl()}/share/${runId}?lang=${lang}` : `${baseUrl()}/?lang=${lang}`;
}

export function shareTexts(r) {
  const rankText = r.showPercent
    ? t('top_percent', { percent: r.topPercent })
    : t('result.rank_of', { rank: r.rank, total: r.total });
  const diff = r.mode === 'daily' ? t('share.daily_label') : t(`difficulty.${r.difficulty}`);
  return {
    title: t('share.title', { time: formatTime(r.timeMs) }),
    desc: r.rank ? t('share.desc', { rank_text: rankText, torches: r.torches, difficulty: diff }) : t('share.page_desc'),
  };
}

export function shareKakao(r) {
  if (!kakaoAvailable()) return false;
  initKakao();
  const { title, desc } = shareTexts(r);
  const url = shareUrl(r.runId);
  const lang = getLang();
  const imageUrl = r.runId ? `${baseUrl()}/og/${r.runId}.png?lang=${lang}` : `${baseUrl()}/og/default.png?lang=${lang}`;
  window.Kakao.Share.sendDefault({
    objectType: 'feed',
    content: {
      title,
      description: desc,
      imageUrl,
      imageWidth: 1200,
      imageHeight: 630,
      link: { mobileWebUrl: url, webUrl: url },
    },
    buttons: [{ title: t('share.cta'), link: { mobileWebUrl: url, webUrl: url } }],
  });
  return true;
}

export async function webShare(r) {
  if (!navigator.share) return false;
  const { title, desc } = shareTexts(r);
  try {
    await navigator.share({ title, text: `${title} · ${desc}`, url: shareUrl(r.runId) });
    return true;
  } catch {
    return false;
  }
}

export async function copyLink(r) {
  const url = shareUrl(r.runId);
  try {
    await navigator.clipboard.writeText(url);
    return true;
  } catch {
    const ta = document.createElement('textarea');
    ta.value = url;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch { ok = false; }
    ta.remove();
    return ok;
  }
}
