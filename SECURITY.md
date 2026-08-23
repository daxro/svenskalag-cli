# Security

Report vulnerabilities privately to the project owner instead of opening a public GitHub issue.

After explicit local setup, the CLI uses undocumented web flows and stores login credentials and session cookies in the platform-standard user configuration directory. Files are written atomically with `0600` permissions.

Never share configuration or session files.
