from voluptuous import Schema, Required, Optional, All, Range, Any

_discovery_schema = Schema({
    Required('enabled', default=False): bool,
    Optional('interval_minutes', default=30): All(int, Range(min=1)),
    Optional('rtsp_probe_timeout', default=3): All(int, Range(min=1)),
    Optional('onvif_timeout', default=5): All(int, Range(min=1)),
})

config_schema = Schema({
    Required('cameras'): [{
        Required('name'): str,
        Required('rtsp_url'): str,
        Optional('codec', default='copy'): str,
        Optional('interval', default=300): All(int, Range(min=60)),
        Optional('mac_address', default=''): str,
        Optional('onvif_port', default=80): int,
        Optional('username', default=''): str,
        Optional('password', default=''): str,
    }],
    Optional('retention_days', default=7): All(int, Range(min=1)),
    Optional('concatenation', default=True): bool,
    Optional('concatenation_time', default='02:00'): str,
    Optional('deletion_time', default='01:00'): str,
    Optional('discovery', default=None): Any(None, _discovery_schema),
})
