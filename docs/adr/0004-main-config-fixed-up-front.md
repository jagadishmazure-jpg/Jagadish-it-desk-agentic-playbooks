# ADR 0004: The main configuration was fixed before measuring

## Status

Accepted.

## Context

With ten configurations it is tempting to call the best one on the test set "main". That reports a
number that was chosen by looking at the test set.

## Decision

Main is the playbook agent with the TF-IDF + logistic regression classifier, a fixed confidence floor
of 0.5 and approvals on. It was chosen before any model output existed. The hybrid triage threshold is
picked on the dev split only.

## Consequences

- The hybrid configuration scored higher on test. It is reported as a measured option, not swapped in
  as main. Adopting it should be confirmed on a fresh ticket set first.
