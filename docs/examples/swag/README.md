# SWAG example configs

Two files for running this stack behind [SWAG](https://github.com/linuxserver/docker-swag) in `external_tls` mode (SWAG terminates TLS, the local server speaks plain HTTP/TCP behind it). See [Reverse Proxy](../../reverse_proxy.md) for the full explanation.

- `api-roborock.subdomain.conf` -> copy into `/config/nginx/proxy-confs/` in your SWAG container. Handles the HTTPS/API traffic.
- `api-roborock-mqtt.stream.conf` -> copy into `/config/nginx/stream-confs/` in your SWAG container (requires a SWAG image recent enough to support `stream-confs`; check its changelog if the directory doesn't exist yet). Handles MQTT/TLS passthrough.

Before using them:

1. Replace `api-roborock.*` and `roborock-local-server` with your actual hostname and container/service name (or IP).
2. Double-check the `ssl_certificate`/`ssl_certificate_key` paths in the stream conf against your SWAG version - `stream {}` blocks can't use the `ssl.conf` include the HTTP proxy-conf uses, and that path has moved between SWAG releases in the past.
3. Set `network.listener_mode = "external_tls"` and `tls.mode = "provided"` in this stack's own `config.toml` (or the equivalent `ROBOROCK_SERVER_LISTENER_MODE`/`ROBOROCK_SERVER_TLS_MODE` env vars) - the local server issues no certificates of its own in this mode.
4. Set `network.advertised_https_port` / `network.advertised_mqtt_tls_port` to whatever public ports SWAG actually exposes, if they differ from the backend's `https_port` (555) / `mqtt_tls_port` (8881).
