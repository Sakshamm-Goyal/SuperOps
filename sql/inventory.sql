-- id: inventory
-- version: 1
-- sources: cloud
-- params: service_id:service_id, as_of:timestamp
SELECT provider, project_id, resource_id, service_id, display_name, environment, machine_type, vcpu, memory_gib,
       region, architecture, stateful, local_ssd, gpu, config_version
FROM {cloud}.inventory
WHERE service_id = :service_id AND effective_from <= :as_of
ORDER BY provider, project_id, resource_id
