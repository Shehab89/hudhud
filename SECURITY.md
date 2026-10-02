# Security

Please report vulnerabilities privately through GitHub's "Report a vulnerability"
(Security tab) rather than in a public issue.

In scope: the API, the frontend, the pipeline and the workflows. Of particular interest:
anything that exposes user e-mails or API keys, lets someone write data without a key,
bypasses the admin token, injects SQL or script, or makes the collector bypass a
publisher's access controls.

Operator notes: keep `ADMIN_TOKEN` long and random; never commit `.env`; restrict
database network access; keep backups private (they contain user e-mails and key hashes).
