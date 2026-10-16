-- id: policy
-- version: 1
-- key: service_id,version
-- sources: ref
-- params: service_id:service_id, version:identifier
SELECT service_id, policy_id, version, effective_from, document
FROM {ref}.policies
WHERE service_id = :service_id AND version = :version
