import test from 'node:test';
import assert from 'node:assert/strict';
import {createHmac, createHash} from 'node:crypto';
import worker, {sign, authenticatedDomain} from './worker.mjs';

const env={RELAY_WEBHOOK_SECRET:'w'.repeat(64),RELAY_URL:'https://zahnarzt-jaghsi.de/api/mail-relay/inbound',REPLY_DOMAIN:'reply.zahnarzt-jaghsi.de'};
function message(auth='i=1; mx.cloudflare.net; dmarc=pass header.from=gmail.com; spf=pass') {
  const data = new TextEncoder().encode('From: patient@gmail.com\r\n\r\nHello');
  return {from:'patient@gmail.com',to:`p.${'a'.repeat(24)}.${'b'.repeat(32)}@reply.zahnarzt-jaghsi.de`,rawSize:data.length,
    headers:new Headers({'ARC-Authentication-Results':auth}),raw:new Blob([data]).stream(),
    rejection:null,setReject(reason){this.rejection=reason;}};
}
test('HMAC protocol matches backend canonical bytes',async()=>{
  const body='{"test":"مرحبا"}',stamp='1789300000',nonce='a'.repeat(32);
  const digest=createHash('sha256').update(body).digest('hex');
  const expected=createHmac('sha256',env.RELAY_WEBHOOK_SECRET).update(`POST\n/api/mail-relay/inbound\n${stamp}\n${nonce}\n${digest}`).digest('hex');
  assert.equal(await sign(body,env.RELAY_WEBHOOK_SECRET,stamp,nonce),expected);
});
test('trust newest Cloudflare authentication result only',()=>{
  assert.equal(authenticatedDomain(message().headers),'gmail.com');
  for(const auth of ['', 'i=1; attacker.example; dmarc=pass header.from=gmail.com',
    'i=2; mx.cloudflare.net; dmarc=fail header.from=gmail.com, i=1; mx.cloudflare.net; dmarc=pass header.from=gmail.com'])
    assert.equal(authenticatedDomain(message(auth).headers),null);
});
test('only durable server acceptance acknowledges mail',async()=>{
  const original=globalThis.fetch;
  try {
    let captured;
    globalThis.fetch=async(url,args)=>{captured=args;return new Response('{"status":"queued"}',{status:202});};
    const incoming=message(); await worker.email(incoming,env);
    assert.equal(incoming.rejection,null);
    assert.equal(JSON.parse(captured.body).authenticated_domain,'gmail.com');
    assert.ok(captured.headers['X-Relay-Signature']);
    assert.equal(captured.redirect,'manual');
    globalThis.fetch=async()=>new Response('{"error":"attachments_not_supported"}',{status:422});
    const attachment=message();await worker.email(attachment,env);
    assert.match(attachment.rejection,/text only/);
    globalThis.fetch=async()=>{throw new Error('network');};
    const failed=message();await worker.email(failed,env);
    assert.match(failed.rejection,/unavailable/);
  } finally {globalThis.fetch=original;}
});
test('reject malformed recipient and unauthenticated messages before webhook',async()=>{
  const original=globalThis.fetch;
  try {
    globalThis.fetch=async()=>{throw new Error('must not call');};
    const bad=message();bad.to='info@zahnarzt-jaghsi.de';await worker.email(bad,env);assert.match(bad.rejection,/Unknown/);
    const unauth=message('');await worker.email(unauth,env);assert.match(unauth.rejection,/authentication/);
    const large=message();large.rawSize=600000;await worker.email(large,env);assert.match(large.rejection,/large/);
  } finally {globalThis.fetch=original;}
});
