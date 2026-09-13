// Inbound only. The clinic server sends outbound mail through its existing SMTP.
const MAX_RAW = 512 * 1024;
const ENDPOINT = '/api/mail-relay/inbound';
const encoder = new TextEncoder();
const hex = bytes => Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, '0')).join('');

export function authenticatedDomain(headers) {
  // Cloudflare prepends its ARC result. Never search earlier, sender-supplied
  // ARC sets for a pass. Fail closed if provider headers change or are absent.
  const value = headers.get('ARC-Authentication-Results') || '';
  const latest = value.split(/,\s*i=\d+;/i)[0];
  if (!/^i=\d+;\s*mx\.cloudflare\.net\s*;/i.test(latest.trim())) return null;
  const match = latest.match(/(?:^|;)\s*dmarc=pass\s+header\.from=([a-z0-9.-]+)(?=\s|;|$)/i);
  return match ? match[1].toLowerCase() : null;
}

export async function sign(body, secret, stamp, nonce) {
  const digest = hex(await crypto.subtle.digest('SHA-256', encoder.encode(body)));
  const key = await crypto.subtle.importKey('raw', encoder.encode(secret), {name:'HMAC', hash:'SHA-256'}, false, ['sign']);
  return hex(await crypto.subtle.sign('HMAC', key, encoder.encode(`POST\n${ENDPOINT}\n${stamp}\n${nonce}\n${digest}`)));
}

async function readBounded(stream) {
  const reader = stream.getReader();
  let size = 0;
  const chunks = [];
  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX_RAW) { await reader.cancel(); throw new Error('too_large'); }
    chunks.push(value);
  }
  const all = new Uint8Array(size);
  let offset = 0;
  for (const part of chunks) { all.set(part, offset); offset += part.byteLength; }
  let binary = '';
  for (let i=0; i<all.length; i+=8192) binary += String.fromCharCode(...all.subarray(i, i+8192));
  return btoa(binary);
}

export default {
  async email(message, env) {
    if (!env.RELAY_WEBHOOK_SECRET || env.RELAY_WEBHOOK_SECRET.length < 64
        || env.RELAY_URL !== 'https://zahnarzt-jaghsi.de' + ENDPOINT
        || env.REPLY_DOMAIN !== 'reply.zahnarzt-jaghsi.de') {
      message.setReject('Clinic relay is not configured. Please contact the clinic.'); return;
    }
    if (message.rawSize > MAX_RAW) {
      message.setReject('Message too large. Please send text only (maximum 512 KB).'); return;
    }
    const suffix = '@' + env.REPLY_DOMAIN;
    if (!message.to.endsWith(suffix) || !/^[dp]\.[a-f0-9]{24}\.[a-f0-9]{32}$/.test(message.to.slice(0, -suffix.length))) {
      message.setReject('Unknown clinic reply address. Please use Reply on the clinic message.'); return;
    }
    const domain = authenticatedDomain(message.headers);
    if (!domain || !message.from) {
      message.setReject('Sender authentication required. Please send directly from your original mailbox.'); return;
    }
    let raw;
    try { raw = await readBounded(message.raw); }
    catch { message.setReject('Unable to read message. Please send a smaller text-only message.'); return; }
    const body = JSON.stringify({recipient:message.to, envelope_from:message.from, authenticated_domain:domain, raw});
    const stamp = String(Math.floor(Date.now()/1000));
    const nonce = crypto.randomUUID().replaceAll('-', '');
    const signature = await sign(body, env.RELAY_WEBHOOK_SECRET, stamp, nonce);
    let response;
    // workerd rejects redirect:error before sending. Manual never follows redirects;
    // only the original endpoint's 202 below acknowledges the message.
    try {
      response = await fetch(env.RELAY_URL, {method:'POST', redirect:'manual', signal:AbortSignal.timeout(15000),
        headers:{'Content-Type':'application/json','X-Relay-Timestamp':stamp,'X-Relay-Nonce':nonce,'X-Relay-Signature':signature}, body});
    } catch {
      // HTTP failures can be ambiguous; retries are deduplicated by Message-ID.
      message.setReject('Clinic relay unavailable. Please retry later or call the clinic.'); return;
    }
    if (response.status === 202) return; // The server has durably committed the mail.
    let error = '';
    try { error = (await response.json()).error; } catch { /* Do not log content */ }
    const reasons = {
      attachments_not_supported:'Please resend as text only. Attachments are not supported by this clinic relay.',
      conversation_closed:'This conversation has expired. Please submit a new inquiry on the clinic website.',
      wrong_sender:'Please reply from the mailbox originally used for this conversation.',
      empty_reply:'Please write your reply above the quoted original message.',
      automated_message:'Automatic responses are not accepted by this clinic relay.'
    };
    message.setReject(reasons[error] || 'Clinic relay could not accept this message. Please retry later or call the clinic.');
  },
  async fetch() { return new Response('Not found', {status:404}); }
};
