-- id: pagination_probe
-- version: 1
-- key: probe_id
-- sources: cloud
-- params:
SELECT probe_id, label FROM {cloud}.pagination_probe ORDER BY probe_id
