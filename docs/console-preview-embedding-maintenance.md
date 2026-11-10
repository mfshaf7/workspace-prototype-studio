# Console preview embedding maintenance

Source extension for the operator-approved editor maintenance release. Landing Unit: studio-console-preview-embedding-20261110, child_isolated_landing_unit. Reuse the existing Studio Preview Runtime and profile/schema/receipt model. Console consumer stays in its existing maintenance batch; Studio lands before that consumer is commissioned. Source author is Agent Gary, accountable reviewer mfshaf7 under standing delegation.

A project profile may opt into `embedding.allowed_origins`, with at most eight exact HTTP localhost/127.0.0.1 origins, unprivileged ports, no path, wildcard, credentials, query or fragment. Default remains frame-ancestors none and X-Frame-Options DENY. Opt-in uses CSP exact ancestors and omits conflicting X-Frame-Options; other content, network, form and source-custody restrictions remain. Allowed origins are safe projection metadata. The whole profile digest still binds state/proof; changing embedding requires reviewed profile custody and normal runtime reconciliation.

No active profile is changed by this source extension. No new server, proxy, external listener, app command, real data or source application is introduced. Console keeps source/draft editing separate from the running app and embeds only owner-confirmed loopback endpoints with explicit origin admission. Exact Security acceptance and normal Platform commissioning remain required before publication/live qualification.

The existing deterministic owner preparation request also accepts optional
`embedding_origins`; it emits the reviewed profile allowlist without applying
source or starting a process. Console provides a single explicit opt-in for
its current origin. OOS retains the exact choice in its request digest and
re-renders the native owner plan at execution. Empty/omitted choices remain
framing denied. This avoids a separate manual profile-edit procedure.
