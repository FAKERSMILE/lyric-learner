const BASE = ''

async function req(method, url, body) {
  const opt = { method, headers: { 'Content-Type': 'application/json' } }
  if (body !== undefined) opt.body = JSON.stringify(body)
  const r = await fetch(BASE + url, opt)
  if (!r.ok) {
    let detail = r.statusText
    try { detail = (await r.json()).detail || detail } catch { /* ignore */ }
    throw new Error(detail)
  }
  return r.json()
}

export const api = {
  get: (url) => req('GET', url),
  post: (url, body) => req('POST', url, body),
  del: (url) => req('DELETE', url),
}
