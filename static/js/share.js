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
  // 서버 설정이 비었거나 로컬 주소면 지금 접속한 주소를 쓴다 (카카오가 접근할 수 있는 공개 주소여야 함)
  const b = BOOT.baseUrl || '';
  if (!b || /\/\/(localhost|127\.0\.0\.1)(:|\/|$)/.test(b)) return location.origin;
  return b.replace(/\/$/, '');
}

export function shareUrl(runId) {
  const lang = getLang();
  return runId ? `${baseUrl()}/share/${runId}?lang=${lang}` : `${baseUrl()}/?lang=${lang}`;
}

export function shareTexts(r) {
  const rankText = r.showPercent
    ? t('top_percent', { percent: r.topPercent })
    : t('result.rank_of', { rank: r.rank, total: r.total });
  return {
    title: t('share.title', { time: formatTime(r.timeMs) }),
    desc: r.rank ? t('share.desc', { rank_text: rankText, torches: r.torches }) : t('share.page_desc'),
  };
}

function cardPath(r, lang) {
  return r && r.runId ? `/og/${r.runId}.png?lang=${lang}` : `/og/default.png?lang=${lang}`;
}

/**
 * 결과 카드 이미지를 카카오 서버에 미리 올려 둔다 (Kakao.Share.uploadImage).
 * 카카오가 우리 서버에서 이미지를 긁어 가지 않아도 되므로, 서버 주소/인증서/응답 시간/카카오 캐시와
 * 상관없이 공유 메시지에 이미지가 표시된다. 결과가 나오면 미리 호출해 두고, 공유 클릭 때는 바로 보낸다.
 */
export async function prepareKakaoImage(r) {
  if (!kakaoAvailable() || !r) return null;
  const lang = getLang();
  const key = cardPath(r, lang);
  r.kakaoImages = r.kakaoImages || {};
  r.kakaoPending = r.kakaoPending || {};
  if (r.kakaoImages[key]) return r.kakaoImages[key];
  if (!r.kakaoPending[key]) r.kakaoPending[key] = uploadCard(r, key);
  return r.kakaoPending[key];
}

async function uploadCard(r, key) {
  try {
    initKakao();
    const res = await fetch(key);
    if (!res.ok) throw new Error(`og_${res.status}`);
    const blob = await res.blob();
    const file = new File([blob], 'maze-in-dungeon.png', { type: blob.type || 'image/png' });
    const up = await window.Kakao.Share.uploadImage({ file: [file] });
    const url = up && up.infos && up.infos.original && up.infos.original.url;
    if (url) r.kakaoImages[key] = url;
    return url || null;
  } catch (e) {
    console.warn('[share] kakao image upload failed, falling back to server URL', e);
    delete r.kakaoPending[key];
    return null;
  }
}

export function shareKakao(r) {
  if (!kakaoAvailable()) return false;
  initKakao();
  const { title, desc } = shareTexts(r);
  const url = shareUrl(r.runId);
  const lang = getLang();
  const key = cardPath(r, lang);
  // 미리 올린 카카오 이미지가 있으면 사용, 없으면 우리 서버의 절대 주소
  const imageUrl = (r.kakaoImages && r.kakaoImages[key]) || `${baseUrl()}${key}`;
  if (!r.kakaoImages || !r.kakaoImages[key]) prepareKakaoImage(r);   // 다음 공유를 위해
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
