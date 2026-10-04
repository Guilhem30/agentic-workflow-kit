# Unfreeze log

Append-only: earlier entries are never rewritten. `{{python}} .agentkit/bin/agentkit lock unfreeze`
adds one entry per unfreeze, with its reason and the paths. Only the owner unfreezes.
