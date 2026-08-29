# Authority Safety Boundary

Without exact authorization, do not:

- delete unknown source or governance/history;
- discard unfamiliar uncommitted work;
- rewrite Git history or force-push;
- deploy or promote releases;
- migrate/alter production data;
- alter infrastructure or destroy external resources;
- rotate/revoke credentials;
- expose secrets or personal/sensitive data;
- make irreversible changes without a known target and recovery path.

Diagnosis does not authorize remediation beyond the user's/directive's stated scope.

When destructive action is authorized, resolve the exact target, preserve recovery/rollback where applicable, and verify the result.
