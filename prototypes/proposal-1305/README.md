# Console To-do

Explore a simple responsive to-do web app with add, complete and delete actions and browser-local reload persistence. Use synthetic local tasks only; no identity, remote backend, external network, or public deployment. Preserve Proposal 1305 and the reserved durable repository for the later Prototype-to-Delivery handoff.

This incubation source was prepared by Prototype Landing.

## App

Little List is a standalone browser app: add tasks, check/uncheck completion,
delete a task and reload without losing accepted changes. It starts empty and
uses only synthetic tasks entered by the operator. HTML, CSS and ES modules;
no package installation, account, server API, external asset or model required.

Persistence is browser-local, not cloud or client-grade storage. The read-only
Preview server does not receive task text. Failed storage writes leave the
visible list unchanged; malformed saved data is retained and editing pauses.
No data reset/migration is silently performed.

The operator explicitly requested Codex-authored code instead of local-model
generation. Source delivery is reviewed external input to the Console exercise,
not evidence that Console or its local model authored this app. Use the Console
for the actual Preview, Candidate/Baseline, Delivery and owner-transfer steps.
This source change does not approve those lifecycle transitions or public hosting.

## Checks

`node --test prototypes/proposal-1305/tests/tasks.test.mjs` from the Studio root
checks actual task transitions and persistence encoding. Real-browser checks
must separately exercise add/complete/delete/reload, keyboard, mobile layout,
literal HTML-looking text and storage failures. Studio `make validate` covers
owner records, not the browser behavior. Both are needed before source landing.
