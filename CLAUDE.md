# Indy's Year — project notes for Claude Code

Personal fitness + weight + blood-sugar tracker for one user (NZ mum, postpartum, type 2 diabetes / prediabetes).
Goals: −5 kg in 3 months, −15 kg by Indy's first birthday, HbA1c into the NZ non-diabetic range (≤40 mmol/mol).

## Stack (keep it this way)
- Single-file app: `index.html` (all CSS + JS inline, no build step, no frameworks). The ONLY external script is the pinned supabase-js UMD (cdn.jsdelivr.net, with an SRI hash), loaded lazily and also cached by `sw.js`. If you bump it, update the version + SRI in `index.html` (`SB_SRC`/`SB_SRI`) and `SB_JS` in `sw.js`.
- `sw.js` offline cache, `manifest.webmanifest`, icons. Static hosting over HTTPS on Vercel (`vercel.json` sets headers; `robots.txt` blocks indexing).
- Storage: IndexedDB (`indy-tracker` db, `kv` store, key `state`) with localStorage mirror (`indy-tracker-v1`).
- Data schema is backward-compatible with the v1 backup JSON. Never break `migrate()`.

## Rules
- Bump `VERSION` in `sw.js` on every change to `index.html`, then commit and push (Vercel auto-deploys from `main`).
- Deterministic analytics only (no AI calls). NZ units: kg, cm, mmol/L, mmol/mol.
- Safety thresholds live in `insights()` and `preStart()` in index.html. Do not loosen: breastfeeding pace cap 0.5 kg/wk, hypo < 3.9 mmol/L, NZ HbA1c bands 40/41–49/50+.
- No remote images or tracking. Exercise figures are inline SVG poses in `POSES`.
- Not medical advice; never add medication-dose advice.

## Deploy
Hosted on Vercel (project `indys-year`, framework Other, no build, output dir `.`), auto-deploys from the private GitHub repo `indys-year` on every push to `main`. First install: open the production URL in Safari on iPhone → Share → Add to Home Screen.

## Cloud sync (Supabase) — project "fitness", ref `rexnqtgodowbwjdvmudm`, region Seoul
Use ONLY this Supabase project. Never touch the user's other Supabase projects (Buildup, WorkUp, ...).
IndexedDB stays the primary store; Supabase is backup + merge-sync + read-only sharing. The app works fully offline and signed out.
- `SUPABASE_URL` / `SUPABASE_KEY` (publishable key, safe to commit) are at the top of the script in `index.html`. Never commit a secret/service_role key or an account token.
- Auth: email OTP (`signInWithOtp` + `verifyOtp`, type `email`). Code length is set in the Supabase dashboard (currently 8); the input accepts 6–8 digits. Default Supabase SMTP (rate-limited, org members only) — add custom SMTP if emails to other people don't arrive. Session persists in localStorage key `indy-sb-auth`; `indy-sync-meta` remembers who is signed in.
- Schema: `supabase/migrations/20261005000000_app_state_and_viewers.sql`
  - `public.app_state(user_id uuid pk -> auth.users, state jsonb, updated_at timestamptz)` — one row per user holding the whole `S` object.
  - `public.viewers(owner_id uuid -> auth.users, viewer_email text, pk(owner_id, viewer_email))` — the share list (emails stored lowercase).
- RLS (both tables enabled; policies use `(select auth.uid())`):
  - app_state: owner select/insert/update/delete where `user_id = auth.uid()`; viewers select where a `viewers` row has `owner_id = app_state.user_id` and `viewer_email = auth.jwt()->>'email'`.
  - viewers: owner all where `owner_id = auth.uid()`; plus "viewer sees own invite" select where `viewer_email = auth.jwt()->>'email'` (needed, otherwise RLS hides the viewers table inside the app_state viewer policy).
- Merge design (`mergeStates`, `syncNow` in `index.html`) — merge, never overwrite:
  - Every record has an `id`. Deleting uses `dropWhere(arrayName, predicate)`, which writes `S.deleted[id]=timestampMs` tombstones (pruned after 400 days). Any new code that removes a record MUST use `dropWhere`.
  - Arrays (weights, measures, glucose, hba1c, activity, sessions): union by id, minus ids in either side's tombstones. `pf`: union. `protein`: per-date max (so un-ticking pf/protein on a synced account does not stick). Profile: the side with the newer `profile.updatedAt` wins (set it whenever the profile is saved); wiping sets `profileCleared`.
  - Sync = pull own row, merge, then push only if the cloud copy differs, using compare-and-swap on `updated_at` (retries up to 4x). Triggers: launch, sign-in, `visibilitychange`→visible, `online`, and 2 s after any `commit()`. Offline or failed syncs are silent and never block the UI or lose local data.
  - Viewer mode (`RO`): a signed-in user with no own row and no local data who can read another user's row sees that person's Home + Insights read-only (banner, no log/edit tabs, nothing persisted locally; `commit()`/`persistNow()` are no-ops).
