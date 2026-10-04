# impl-reviewer: spec 002 (test-freeze lock) for done

Scope: R002-33/34 in depth, plus one read of the rest of lock.py (freeze, unfreeze, verify,
restore, audit) and the lock CLI. The earlier 001/002 passes were by another reviewer instance
and are not repeated here.

The 100 tests in tests/test_002_*.py pass, and R002-01..34 are all traced. No test gaming.
freeze writes nothing when it reports errors (R002-11). Exit codes: 1 for LockError, 2 for
OwnerCheckError (R002-20/31). Forced freezes and unfreezes ask for the exact console answer and
append the logged entries (R002-21/24/32). CRLF and LF hash the same (R002-03). The R002-34
refusal comes before freeze(); R002-33 audits the chaos log with the lenient path. The public
names match the contract.

Open, not drift: a chaos log that existed at REF and was deleted is not audited by
`lock audit`. That follows R002-33 as written; changing it needs an owner amendment.

Nit (fixed since): _git.prefix()/toplevel() decode strictly as UTF-8; use surrogateescape.

verdict: approve
