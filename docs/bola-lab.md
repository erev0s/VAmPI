# Controlled BOLA evaluation lab

## Purpose and upstream separation

This repository now includes an **opt-in, independently deployable Flask service** for controlled BOLA evaluation. It does not import, modify, or share persistence with VAmPI's original `app.py`, `config.py`, models, routes, database, or OpenAPI document. The recorded upstream baseline is the Git commit written into each private answer sheet by the controller.

The original VAmPI service remains the comparison target. The lab is started only through [`bola_lab_app.py`](../bola_lab_app.py) after private state has been prepared locally.

## Public data-plane contract

The lab intentionally exposes only these routes:

| Route | Auth | Stable response pointers |
| --- | --- | --- |
| `GET /health` | no | neutral `{"status":"ready"}` only |
| `GET /me` | bearer | principal: `/principal/username` |
| `GET /books/{book_id}` | bearer | resource ID: `/data/id`; restricted field: `/data/secret` |

The public specification is [`openapi_specs/bola-lab.openapi.json`](../openapi_specs/bola-lab.openapi.json). It is invariant across scenarios and deliberately omits scenario names, markers, ground truth, token values, controller routes, and reset functions.

The normal book form is:

```json
{
  "data": {
    "id": "book-B1",
    "owner": "userB",
    "title": "User B book one",
    "secret": "private marker"
  }
}
```

Some experiments intentionally use a null/masked/public-only/wrong-resource or alternate-form response. The returned `data.id`, when present, always identifies the resource actually returned; it is never relabeled to look like the requested resource.

## Private controller and reproducibility

The controller is local-only Python code, not an HTTP API. Choose a fresh directory accessible only to the lab operator:

```bash
mkdir -m 700 bola-lab-state
```

```bash
python3 -m bola_lab.controller --state-dir "$PWD/bola-lab-state" --scenario S01 --token-ttl 3600 init
```

It creates owner-only (`0700` directory; `0600` files), atomically written files:

- `active-run.json`: immutable-at-startup run configuration and signing secret;
- `lab.sqlite3`: principals, resources, actual owners, and shares;
- `issued-tokens.json`: operator-supplied bearer tokens;
- `operator-config.json`: pointers and policy input with no marker values or answer;
- `answer-sheet.json`: evaluator-only ground truth and accepted outcomes.

Never copy the state directory or these files to the tool machine. They are ignored by Git if created at the repository root. The controller rejects resets or scenario changes while the server lock names a live process. The service reads and validates the manifest once at boot, locks the run atomically, and does not observe later configuration-file modifications. Stop the process before reset:

```bash
python3 -m bola_lab.controller --state-dir "$PWD/bola-lab-state" --scenario S04 --token-ttl 3600 reset
```

```bash
python3 -m bola_lab.controller --state-dir "$PWD/bola-lab-state" validate
```

Each initialization regenerates bearer tokens and secret markers. Resource IDs and authorization semantics remain deterministic. S10 alone intentionally duplicates the `book-B1`/`book-B2` secret marker pair.

## Start the isolated service

```bash
BOLA_LAB_STATE_DIR="$PWD/bola-lab-state" BOLA_LAB_HOST=0.0.0.0 BOLA_LAB_PORT=5003 python3 bola_lab_app.py
```

The application logs, errors, `/health`, and other public responses contain no scenario identifier, controller secret, issued token, private answer, or marker values unless a scenario intentionally discloses a resource secret through the tested resource endpoint.

Docker is optional and does not change upstream images or services. Prepare the named volume using a one-off local controller container **before** starting the public service:

```bash
docker compose -f docker-compose.lab.yaml run --rm --no-deps bola-lab python -m bola_lab.controller --state-dir /var/lib/bola-lab --scenario S01 --token-ttl 3600 init
```

```bash
docker compose -f docker-compose.lab.yaml up --build
```

The controller corrects the volume directory to mode `0700` before writing state. Set `BOLA_LAB_PUBLISH_ADDRESS` and, when needed, `BOLA_LAB_PUBLISH_PORT` to the intended lab-network interface/port instead of exposing the service broadly. `BOLA_LAB_VOLUME_NAME` selects a separate named volume for an isolated trial. Only the container's port 5003 is a data-plane port. Do not publish the operator state directory, a controller shell, or a reset service.

For a non-destructive acceptance run, use a separate Compose project, loopback port, and distinct volume name:

```bash
BOLA_LAB_PUBLISH_ADDRESS=127.0.0.1 BOLA_LAB_PUBLISH_PORT=5503 BOLA_LAB_VOLUME_NAME=vampi-bola-acceptance-state docker compose -p vampi-bola-acceptance -f docker-compose.lab.yaml config
```

This leaves the normal `vampi_bola-lab-state` volume untouched.

Before reset, stop the service and prepare the next run with the same one-off controller command, replacing `init` with `reset`.

```bash
docker compose -f docker-compose.lab.yaml down
```

```bash
docker compose -f docker-compose.lab.yaml run --rm --no-deps bola-lab python -m bola_lab.controller --state-dir /var/lib/bola-lab --scenario S04 --token-ttl 3600 reset
```

Use the one-off controller container only from Machine B's operator context; it prints no bearer token values. Read the owner-only token artifact locally through an approved protected channel when supplying a token to Machine A.

## Data and policy

Each run seeds `admin`, `userA`, and `userB`, with `book-A1`, `book-A2`, `book-B1`, and `book-B2`. `books.owner` is the actual ownership record. The standard policy is owner access to private data, declared shared-reader access where configured, and public access to ID/owner/title only. Admin policy is `UNKNOWN` in the operator configuration except for the S11 measurement control.

The answer sheet is the authority for policy; it explicitly does **not** infer intended policy from server behavior. Every cross-user answer row records independent dimensions:

- `authorization_allowed`
- `private_data_disclosed`
- `returned_resource_identity`
- `expected_classification`
- `acceptable_conclusions`
- `evidence_requirements`

HTTP status is transport evidence only. A 200 never proves authorization, and a 403 never proves that no private data was sent.

### Scenario table

| Case | Unauthorized read behavior | Evaluation point |
| --- | --- | --- |
| S01 | 200 with requested target and real secret | Confirm BOLA. |
| S02 | 200 denial envelope, no secret | No confirmed disclosure; policy-consistent only if the supplied denial convention is known, otherwise insufficient evidence is acceptable. |
| S03 | 403 with requested target and real secret | Confirm BOLA from the body despite 403. |
| S04 | 403 denial envelope, no secret | Policy-consistent with denial convention and owner control. |
| S05 | 200 with `data: null` | No disclosure; insufficient evidence is accepted. |
| S06 | 200 public data with `secret: "***"` | A field key/mask is not a real marker disclosure. |
| S07 | 200 with the requester’s own book | The returned ID truthfully differs from the requested target. Do not count it as disclosure of the target. |
| S08 | 200 with B1 secret after B1 is shared to A | Cross-owner access is policy-consistent, not BOLA. |
| S09 | 200 public ID/owner/title only | Different ownership alone is not a violation. |
| S10 | Duplicate marker pair; B2 variant omits resource ID | Use all evidence. If source attribution is unavailable, `INSUFFICIENT_EVIDENCE` is acceptable. |
| S11 | Leaking response and admin denial control have equal serialized UTF-8 byte lengths | Body length must not be the sole decision rule; compression is not enabled. |
| S12 | 202 alternate body form with the same target data | Formatting/status differences do not negate demonstrated disclosure. |

Owners receive the full resource in every scenario. Invalid or expired tokens receive neutral 401 responses.

## Manual tool input

Provide the external tool with only:

```json
{
  "principal_pointer": "/principal/username",
  "resource_id_pointer": "/data/id",
  "restricted_field_pointers": ["/data/secret"],
  "ownership": "The stored owner may read private data; declared shares may grant equivalent access.",
  "denial_convention_when_supplied": {"pointer": "/result", "value": "access_denied"}
}
```

Use the account/resource list and policy from the private `operator-config.json`; supply the denial convention only for the evaluation profile that declares it known. Do not give the tool the private answer sheet, marker values, scenario name, or controller artifacts.

## Two-machine procedure

1. **Machine B (lab)**: create a protected state directory; run `init` for one chosen scenario; validate it; start the lab on the approved lab-network interface and port.
2. **Machine A (tool)**: set base URL to `http://MACHINE_B:5003`, import the public OpenAPI JSON, and enter a bearer token manually from the operator through a protected channel. Add only the documented pointers, identity/resource/policy configuration, and any declared denial convention.
3. **Run**: keep the lab process and network path stable. Do not reset or change scenarios during the run.
4. **After completion**: stop the lab on Machine B, inspect the private answer sheet locally, and compare allowed conclusions. The evaluator must not invoke the tool again to generate answers.
5. **Between runs**: reset after the process exits, distribute new tokens, and start a new service process.

## Verification layers

Run source and integration checks:

```bash
python3 -m compileall -q bola_lab bola_lab_app.py tests
```

```bash
python3 -m unittest discover -s tests -v
```

The integration suite starts a real local WSGI HTTP server and covers all S01-S12, owner controls, `/me`, invalid/expired tokens, S03 body leakage, masking, wrong-object truthfulness, sharing, S10 ambiguity, S11 UTF-8 byte equality, file modes, live-reset refusal, startup lock behavior, reset isolation, and attempts to fetch private/control paths over HTTP.

Docker validation is intentionally separate: it is only reported as passed if Docker is available and the isolated compose service was built and run. The controller cannot initialize an unmounted named volume from the public container; deployers must provision the private volume state on the lab host first.

## Limits

This increment intentionally does not implement mutation/post-state cases, async flows, mixed-resource lists, redirects/login HTML, share revocation during a run, ownership transfers, cross-account caches, BFLA, or ZAP integration. No claim about a tool’s detection quality follows merely from the lab behaving as designed.
