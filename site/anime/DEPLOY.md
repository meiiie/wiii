# Deploy `wiii-anime-site`

The site is a Cloudflare Worker named `wiii-anime-site` with static assets.
The custom domain route is already in `wrangler.toml`:

```toml
routes = [
  { pattern = "anime.holilihu.online", custom_domain = true }
]
```

`dist/` is build output and is gitignored by the repository root. Build on the
machine that deploys. Do not commit `dist/`.

## Commands

From this folder (`site/anime`):

```bash
npm ci
npm run build
npx wrangler deploy --dry-run
npx wrangler deploy
```

`npm run build` typechecks, then writes `dist/`. Wrangler serves that folder
through the asset binding and adds the headers in `worker/index.js`.

The dry run bundles the worker without publishing. Deploy needs a Cloudflare
API token that can upload this worker and attach the custom domain
`anime.holilihu.online`. This repository does not store that token.
`wiii.holilihu.online` is the Wiii web app and must not be attached here.

## Local preview

```bash
npm ci
npm run build
npm run preview
```

The preview listens on `http://127.0.0.1:4173/`.

## Rollback

`npx wrangler rollback` returns the worker to the previous uploaded version.
The custom domain stays attached. There is no database and no migration.

## Notes

- No environment variables are required for the site to render.
- The content-security policy allows only same-origin scripts, styles, images,
  and fonts. Audio is synthesized in the browser.
- If the custom domain is not yet on the account, attach `anime.holilihu.online`
  in the Cloudflare dashboard for this worker, then deploy again. The route in
  `wrangler.toml` is the source of truth.
