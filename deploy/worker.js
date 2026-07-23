/**
 * Cloudflare Worker: Notion link -> GitHub Actions trigger
 *
 * Notion's "Send webhook" button action requires a paid plan. A plain
 * hyperlink/bookmark is free on every plan, but clicking a link does a
 * GET request (opened in a new tab), not a POST — so this Worker accepts
 * GET (as well as POST, in case you switch back to a button later) and
 * responds with a small HTML page so the new tab isn't just blank text.
 *
 * Required secrets/vars (see wrangler.toml + setup notes):
 *   GITHUB_TOKEN    - a GitHub PAT with permission to trigger workflows
 *   TRIGGER_SECRET  - a random string only you and the Notion link know
 *   GITHUB_OWNER    - your GitHub username or org
 *   GITHUB_REPO     - the repo name
 */

export default {
  async fetch(request, env) {
    // Link-preview crawlers (Notion fetches a URL in the background to
    // generate the link's preview/favicon) commonly use HEAD. Answer them
    // harmlessly without triggering a real dispatch.
    if (request.method === "HEAD") {
      return new Response(null, { status: 200 });
    }

    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST",
        },
      });
    }

    if (request.method !== "GET" && request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    // Basic protection: only proceed if the URL has the right ?key=...
    const url = new URL(request.url);
    if (url.searchParams.get("key") !== env.TRIGGER_SECRET) {
      return new Response("Unauthorized", { status: 401 });
    }

    const dispatchUrl = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/dispatches`;

    const githubResponse = await fetch(dispatchUrl, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "grid-flex-sankey",
      },
      body: JSON.stringify({
        event_type: "notion-trigger", // must match the workflow's `types:` list
      }),
    });

    if (!githubResponse.ok) {
      const errText = await githubResponse.text();
      return new Response(
        `GitHub dispatch failed (status ${githubResponse.status}) calling ${dispatchUrl}: ${errText || "(empty response body)"}`,
        { status: 502 }
      );
    }

    const html = `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Report queued</title>
<style>
  body { font-family: system-ui, sans-serif; display: flex; align-items: center;
         justify-content: center; height: 100vh; margin: 0; background: #fafafa; }
  .card { text-align: center; padding: 2rem; }
  h1 { font-size: 1.25rem; }
  p { color: #666; }
</style></head>
<body>
  <div class="card">
    <h1>✅ Report queued</h1>
    <p>The workflow is running now. You can close this tab —<br>
       the updated report will appear in Notion in about a minute.</p>
  </div>
</body>
</html>`;

    return new Response(html, {
      status: 200,
      headers: { "Content-Type": "text/html; charset=utf-8" },
    });
  },
};