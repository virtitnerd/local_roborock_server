# Cloudflare setup

Use this optional guide if you want Cloudflare DNS-01 certificate issuance and automatic renewal during [Installation](installation.md). Before choosing this path, check [Tested Vacuums](tested_vacuums.md) to confirm which ACME CA your model should start with. In most cases, prefer `zerossl`; use `actalis`, `letsencrypt`, or `sslcom` when the tested-vacuum notes point you there. If you would rather provide your own certificate files, see [Custom certificate management](custom_cert_management.md).

Cloudflare is used for DNS-01 validation against your zone so that the stack can request and renew certificates automatically. The ACME CA is configurable (`tls.acme_server`): `zerossl` (default and recommended for most users), `actalis`, `letsencrypt`, or `sslcom`. Switch away from ZeroSSL if an older vacuum trusts a different chain more reliably - see [Tested Vacuums](tested_vacuums.md) for reported results per CA.

DNS-01 validation only needs permission to create temporary TXT records in Cloudflare. It does not make the service reachable from the internet by itself, and local-only setups do not need public inbound access, public port forwarding, or Cloudflare proxying for the stack hostname.

If you choose `acme_server = actalis` or `acme_server = sslcom`, you must also provide `acme_eab_kid` and `acme_eab_hmac_key` (EAB credentials) from that CA's ACME account - both require External Account Binding to register. `zerossl` and `letsencrypt` need no EAB credentials at all. Generated configs store EAB values in separate secret files instead of embedding them directly in `config.toml`.

Actalis and SSL.com both provide the EAB KID and HMAC key from their own ACME account setup pages. Create or sign in to an account with that CA first, then copy both EAB values into the setup wizard or Home Assistant add-on options.

The automated issuance shape differs by ACME CA:

- `zerossl`, `letsencrypt`, and `sslcom` request `base_domain` plus `*.base_domain` (a wildcard cert)
- `actalis` requests only `stack_fqdn` (no wildcard) - this is a reported limitation specific to Actalis's EAB account tier, not a general restriction. We don't have field reports confirming SSL.com's wildcard behavior either way yet; if it turns out to need the same single-domain treatment, please open an issue.

## Create the Cloudflare Token

Create a user API token in Cloudflare for the zone you will use in `tls.base_domain`.

1. Sign in to the Cloudflare dashboard.
2. Open `My Profile` -> `API Tokens`.
3. Select `Create Token`.
4. Start from the `Edit Zone DNS` template.
5. Give the token a clear name such as `roborock-local-server-example-com`.
6. Scope the token to only the zone you will use for this project.
7. Review the summary and create the token.
8. Copy the token secret immediately. Cloudflare only shows it once.

For this project, keep the token limited to the single zone you are using. Do not use a global API key.

If you also create a public DNS record for the stack hostname because you want remote access, remember that you are making a self-hosted service publicly accessible. The server handles auth and can disable new devices from connecting, but there is still always risk. Keep it local-only if that works for you.

## Related Docs

- [Installation](installation.md)
- [Custom certificate management](custom_cert_management.md)
- [Onboarding](onboarding.md)
