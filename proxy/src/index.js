// Cloudflare Worker: serve diamometer.us by passing every request through to the Modal app.
// (Modal's free plan has no custom domains, so this keeps diamometer.us in the address bar.)

const ORIGIN = "https://adityathakur6176--diatometer-web.modal.run";
const CANONICAL_HOST = "diamometer.us";

export default {
  async fetch(request) {
    const url = new URL(request.url);

    // www.diamometer.us -> diamometer.us
    if (url.hostname === `www.${CANONICAL_HOST}`) {
      url.hostname = CANONICAL_HOST;
      return Response.redirect(url.toString(), 301);
    }

    const target = new URL(url.pathname + url.search, ORIGIN);
    const headers = new Headers(request.headers);
    // hop-by-hop headers belong to this connection only; forwarding "expect: 100-continue"
    // (curl sends it for big uploads) makes the origin answer 100, which a Worker can't return
    for (const h of ["host", "expect", "connection", "keep-alive", "te", "trailer", "upgrade", "proxy-connection"]) {
      headers.delete(h);
    }
    headers.set("x-forwarded-host", url.hostname);
    headers.set("x-forwarded-proto", url.protocol.replace(":", ""));

    const hasBody = !["GET", "HEAD"].includes(request.method);
    // stream the upload straight through; the response streams back the same way
    return fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      redirect: "manual",
    });
  },
};
