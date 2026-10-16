-- id: machine_types
-- version: 1
-- key: machine_type
-- sources: ref
-- params:
SELECT machine_type, family, vcpu, memory_gib, architecture FROM {ref}.machine_types ORDER BY machine_type
