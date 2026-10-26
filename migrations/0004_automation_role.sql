-- Automation actors (Autopilot) may start investigations only. Approval, trial, revoke, cancel and execute stay
-- operator-only in the API, and execution re-checks for operator/admin independently.
ALTER TABLE actors DROP CONSTRAINT actors_role_check;
ALTER TABLE actors ADD CONSTRAINT actors_role_check CHECK (role IN ('viewer', 'automation', 'operator', 'admin'));
