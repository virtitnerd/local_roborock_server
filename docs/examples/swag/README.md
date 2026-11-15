# SWAG example config

[SWAG](https://github.com/linuxserver/docker-swag) ships `nginx-mod-stream`
but its build deliberately removes the default `stream.conf` that would
enable it (`rm -f /etc/nginx/conf.d/stream.conf` in its Dockerfile), and it
doesn't provide a `stream-confs` auto-include convention the way it does
`proxy-confs`/`site-confs`. So MQTT (raw TCP/TLS, not HTTP) can't be proxied
through SWAG's supported config layout without you hand-editing
`nginx.conf` yourself to re-enable the module. Not recommended.

Use `local_tls` instead - the local server terminates TLS itself, using a
copy of SWAG's own certificate, and you publish its MQTT port directly
(bypassing nginx for that port entirely). See [Reverse Proxy](../../reverse_proxy.md#local_tls-default--the-server-terminates-tls).

In this stack's `config.toml` (or the equivalent `ROBOROCK_SERVER_*` env vars):

```toml
[network]
stack_fqdn = "api-roborock.example.com"
listener_mode = "local_tls"

[tls]
mode = "provided"
cert_file = "/config/keys/letsencrypt/fullchain.pem"
key_file = "/config/keys/letsencrypt/privkey.pem"
```

(Verify that cert path against your SWAG version - mount SWAG's `/config/keys/letsencrypt`
directory, or a copy of it, into this stack's container so those paths resolve.)

Publish both `https_port` (555) and `mqtt_tls_port` (8881) directly from the
container - via your router/firewall, or a plain TCP passthrough if you
have one - rather than through SWAG.

`api-roborock.subdomain.conf` in this folder is an **optional** SWAG
proxy-conf for the HTTPS/API side only, if you'd still like SWAG-fronted
access to `/admin` etc. alongside the direct MQTT port. Copy it into
`/config/nginx/proxy-confs/`, and update `api-roborock.*` and
`roborock-local-server` to your actual hostname and container/service name.
Since the backend already presents a real, valid cert in `local_tls` mode,
nginx proxies to it as a normal HTTPS upstream - no stream module involved.
