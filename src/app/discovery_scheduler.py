# src/app/discovery_scheduler.py
import os
import yaml
import logging
import urllib.parse
from datetime import datetime
from onvif_discovery import build_rtsp_url, probe_rtsp
from ip_resolver import IPResolver, UnresolvableError

logger = logging.getLogger(__name__)

_CONFIG_PATH = os.environ.get('ONENVR_CONFIG', '/config/config.yaml')


def _write_config(config: dict):
    tmp = _CONFIG_PATH + '.tmp'
    with open(tmp, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    os.replace(tmp, _CONFIG_PATH)
    logger.info("Config updated by discovery scheduler")


class DiscoveryScheduler:
    def __init__(self, config_ref: dict, lock, discovery_config: dict):
        self.config_ref = config_ref
        self.lock = lock
        self.discovery_config = discovery_config
        self.camera_status = {}

    def run_rediscovery(self) -> list:
        updates = []
        rtsp_timeout = self.discovery_config.get('rtsp_probe_timeout', 3)

        with self.lock:
            cameras = list(self.config_ref.get('cameras', []))

        for camera in cameras:
            name = camera['name']
            mac = camera.get('mac_address', '')
            rtsp_url = camera['rtsp_url']
            username = camera.get('username', '')
            password = camera.get('password', '')
            onvif_port = camera.get('onvif_port', 80)

            try:
                current_ip = urllib.parse.urlparse(rtsp_url).hostname
                resolved_ip = IPResolver().resolve(current_ip, mac=mac, onvif_port=onvif_port)
                new_url = build_rtsp_url(resolved_ip, rtsp_url, username, password)

                if new_url != rtsp_url:
                    if probe_rtsp(new_url, rtsp_timeout):
                        update = {'name': name, 'old_rtsp_url': rtsp_url,
                                  'new_rtsp_url': new_url, 'status': 'updated'}
                        updates.append(update)
                        self._apply_update(name, new_url)
                        logger.info(f"Updated {name}: {rtsp_url} -> {new_url}")
                    else:
                        updates.append({'name': name, 'status': 'rtsp_probe_failed',
                                        'new_rtsp_url': new_url})
                else:
                    self.camera_status[name] = {
                        'status': 'ok',
                        'last_resolved': datetime.now().isoformat()
                    }

            except UnresolvableError as e:
                logger.warning(f"Camera {name} unresolvable: {e}")
                self.camera_status[name] = {
                    'status': 'unresolvable',
                    'last_error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
                updates.append({'name': name, 'status': 'unresolvable', 'error': str(e)})

        return updates

    def _apply_update(self, camera_name: str, new_rtsp_url: str):
        with self.lock:
            for camera in self.config_ref['cameras']:
                if camera['name'] == camera_name:
                    camera['rtsp_url'] = new_rtsp_url
                    break
            _write_config(self.config_ref)

    def get_camera_status(self) -> dict:
        return dict(self.camera_status)
