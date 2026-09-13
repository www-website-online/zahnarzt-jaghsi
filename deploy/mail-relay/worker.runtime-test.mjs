import worker, {sign} from './worker.mjs';

const env = {
  RELAY_WEBHOOK_SECRET: 'test-only-'.repeat(8),
  RELAY_URL: 'https://zahnarzt-jaghsi.de/api/mail-relay/inbound',
  REPLY_DOMAIN: 'reply.zahnarzt-jaghsi.de'
};

function check(value, reason) { if (!value) throw new Error(reason); }
function incoming(from = 'patient@gmail.com') {
  const data = `From: ${from}\r\nMessage-ID: <runtime-test@example.test>\r\n\r\nTest only`;
  return {
    from, to: `d.${'a'.repeat(24)}.${'b'.repeat(32)}@${env.REPLY_DOMAIN}`,
    rawSize: data.length, raw: new Blob([data]).stream(),
    headers: new Headers({'ARC-Authentication-Results': 'i=1; mx.cloudflare.net; dmarc=pass header.from=gmail.com'}),
    rejection: null, setReject(reason) { this.rejection = reason; }
  };
}

export default {
  async fetch(request) {
    check(request.url === env.RELAY_URL, 'Must not follow a redirect to another endpoint');
    const body = await request.text();
    const signature = await sign(body, env.RELAY_WEBHOOK_SECRET,
      request.headers.get('X-Relay-Timestamp'), request.headers.get('X-Relay-Nonce'));
    check(request.headers.get('X-Relay-Signature') === signature, 'Invalid webhook signature');
    const payload = JSON.parse(body);
    check(payload.authenticated_domain === 'gmail.com', 'Lost sender authentication');
    if (payload.envelope_from === 'redirect@gmail.com')
      return new Response(null, {status:302, headers:{Location:'https://other.example.test/'}});
    return new Response('{"status":"queued"}', {status:202});
  },
  async test() {
    // Exercise the actual Workers runtime, including fetch option validation,
    // AbortSignal.timeout, stream reading, crypto, and an HTTP subrequest.
    const accepted = incoming();
    await worker.email(accepted, env);
    check(accepted.rejection === null, `Expected delivery: ${accepted.rejection}`);
    const redirected = incoming('redirect@gmail.com');
    await worker.email(redirected, env);
    check(redirected.rejection === 'Clinic relay could not accept this message. Please retry later or call the clinic.',
      `Expected rejection without following redirect: ${redirected.rejection}`);
  }
};
