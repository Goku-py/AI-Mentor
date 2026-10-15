# Deploying the execution runner

The API host (Render, Railway, Vercel — anything that is just a container)
**cannot run a Docker daemon**. So untrusted student code is executed on a
separate, cheap VM that owns Docker, and the API host calls it over private
HTTP with a shared secret.

```
  Browser ──HTTPS──> Vercel (static) ──/api/*──> Render (Flask API)
                                                    │
                                    private HTTP + bearer secret
                                                    ▼
                                          Hetzner VM (runner)
                                          owns Docker, executes code
```

Everything below happens **on the runner VM only**, except the two environment
variables on the API host.

---

## 1. Provision the VM

Any x86_64 VM with Docker works. Recommended: **Hetzner CX22** (~€4/mo,
2 vCPU / 4 GB) — enough RAM for the JVM when a Java snippet runs.

x86_64 matters: the sandbox images in `app_pkg/config.py` are pinned by
`sha256` digest, and `gcc:12` publishes amd64-only. ARM would break C and Java
and invalidate every pin.

```bash
ssh root@<runner-ip>
```

## 2. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
```

## 3. Pull the pinned images — do this first

The digests are parsed directly out of `app_pkg/config.py` by the script, so
they can never drift from what production validates.

```bash
git clone <your-repo-url> /opt/ai-mentor
cd /opt/ai-mentor
./scripts/prepull-images.sh
```

Pull these **before** the first request. Otherwise the first user to run code
pays a multi-hundred-MB image download inside a 30-second sandbox timeout and
sees a spurious failure.

## 4. Set the secret, then build

The secret must be identical on both hosts. Generate one:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Store it in an environment file (mode 600):

```bash
sudo install -o root -g root -m 600 /dev/null /etc/ai-mentor-runner.env
sudo tee /etc/ai-mentor-runner.env >/dev/null <<'EOF'
EXECUTION_RUNNER_SECRET=paste-the-generated-value-here
RUN_BIND=127.0.0.1
RUN_PORT=5001
EOF
```

> **Do NOT put `EXECUTION_RUNNER_URL` in this file.** That variable is for the
> API host. If the runner sets it, the runner tries to call itself over the
> network instead of executing locally.

Build and run:

```bash
docker build -f runner/Dockerfile -t ai-mentor-runner .
docker run -d --name ai-mentor-runner \
  --restart unless-stopped \
  --env-file /etc/ai-mentor-runner.env \
  -p 127.0.0.1:5001:5001 \
  ai-mentor-runner
```

Binding to `127.0.0.1` only means the port is unreachable from the internet
even if the firewall rule below is missing. Do not change it to `0.0.0.0`.

## 5. Restrict access at the firewall

Port 5001 accepts arbitrary code for execution. Treat it as privileged: only
the API host's IP may reach it.

With **ufw**:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from <render-api-ip> to any port 5001 proto tcp   # API host only
sudo ufw allow OpenSSH
sudo ufw enable
sudo ufw status numbered
```

Replace `<render-api-ip>` with the actual outbound IP of your Flask host
(`render.yaml` sets `TRUSTED_PROXY_COUNT=1`, so check Render's egress IP, not
the proxy's).

If you want belt-and-braces beyond the firewall, put the two hosts on a
provider private network (Hetzner Cloud Networks, AWS VPC, GCP VPC) and keep
5001 off the public internet entirely.

## 6. Verify before pointing production at it

```bash
# Health: does the runner see a Docker daemon?
curl -s http://127.0.0.1:5001/healthz

# Authenticated execution. Expect stdout "hi" and returncode 0.
curl -s -X POST http://127.0.0.1:5001/execute \
  -H "Authorization: Bearer $EXECUTION_RUNNER_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"code":"print(\"hi\")","language":"python",
       "image":"python:3.11-slim@sha256:b5d546c4...","cmd":["python","{source}"],"timeout":10}'
```

`/healthz` must report `docker_daemon_available: true`. If it does not, the
runner boots but every execution will fail — this is the single most likely
first-run failure.

Confirm the unauthenticated path is actually closed:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:5001/execute \
  -d '{"code":"print(1)","language":"python","image":"python:3.11-slim","cmd":["python","{source}"]}'
# expect 401
```

## 7. Point the API host at the runner

On **Render** (the API host), not the runner:

```
EXECUTION_RUNNER_URL=http://<runner-private-ip>:5001
EXECUTION_RUNNER_SECRET=<the same generated value>
```

Use the private IP if the hosts share a private network; otherwise use the
public IP and rely on the firewall rule from step 5.

Leave `HOST_EXECUTION_ENABLED` **unset**. It is refused at boot in production,
and it is no longer needed now that real containers are available.

## 8. Verify from the app

Run a Python snippet in the UI. In the response, `meta.execution.stdout` should
contain your output and `meta.execution.error` should be null.

If you instead see *"The sandbox service is currently unavailable"*, the API
host cannot reach the runner. Check in order: the URL is correct and has no
trailing slash, the firewall allows the API host's IP, and the secret matches
byte-for-byte.

---

## Running the runner under systemd instead of Docker

Only if you would rather not run the runner itself inside a container (the
nested-Docker setup is simpler to reason about, so this is the less common
choice). Install Docker as in step 2, then create the service user and venv:

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin runner
sudo -u runner python3 -m venv /opt/ai-mentor/.venv
sudo -u runner /opt/ai-mentor/.venv/bin/pip install -r runner/requirements.txt
```

Then install and start the unit:

```bash
sudo install -o root -g root -m 644 runner/ai-mentor-runner.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ai-mentor-runner
sudo systemctl status ai-mentor-runner
sudo journalctl -u ai-mentor-runner -f
```

The unit file runs gunicorn against the factory `runner.server:create_runner_app()`
as an unprivileged `runner` user, reads its secret from the 600-mode env file,
and binds 127.0.0.1 so step 5's firewall rule is the only thing exposing it.

Note that `ProtectSystem=strict` makes `/opt` read-only. That is why the unit
sets `PYTHONDONTWRITEBYTECODE=1` and why user code must be written to `/tmp`
(which `PrivateTmp=true` provides as a private writable mount).

## Rotating the secret

The secret is a shared bearer token with no expiry. To rotate: generate a new
one, update `/etc/ai-mentor-runner.env` **and** Render's environment, restart
both. There is no grace period where both values work — do it in one window,
and expect brief 401s while the two sides disagree.
